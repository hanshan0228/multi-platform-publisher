#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const {
  fillMicroPostContent,
  uploadMicroPostImages,
  clickMicroPostPublish,
} = require("./toutiao_micro_publish_helpers.cjs");

function jsonOut(obj) {
  process.stdout.write(`${JSON.stringify(obj)}\n`);
}

async function loadPlaywright() {
  const toutiaoMcpDir = process.env.TOUTIAO_MCP_DIR;
  if (!toutiaoMcpDir) {
    throw new Error("缺少 TOUTIAO_MCP_DIR 环境变量");
  }
  return require(path.join(toutiaoMcpDir, "node_modules", "playwright"));
}

async function readPayload(payloadPath) {
  return JSON.parse(fs.readFileSync(payloadPath, "utf8"));
}

async function ensureLogin(context, cookiePath) {
  const cookiesRaw = JSON.parse(fs.readFileSync(cookiePath, "utf8"));
  const cookies = Array.isArray(cookiesRaw.cookies) ? cookiesRaw.cookies : [];
  if (!cookies.length) {
    throw new Error("头条 cookie 文件为空，请重新登录");
  }
  await context.addCookies(cookies);
}

async function run() {
  const payloadPath = process.argv[2];
  if (!payloadPath) {
    throw new Error("缺少 payload.json 路径");
  }

  const payload = await readPayload(payloadPath);
  const { chromium } = await loadPlaywright();

  if (!fs.existsSync(payload.cookie_path)) {
    throw new Error(`未找到头条登录态文件: ${payload.cookie_path}`);
  }

  const browser = await chromium.launch({
    headless: payload.headless !== false,
  });

  try {
    const context = await browser.newContext({
      locale: "zh-CN",
      viewport: { width: 1440, height: 960 },
    });

    await ensureLogin(context, payload.cookie_path);

    const page = await context.newPage();
    const homeResponse = await page.goto("https://mp.toutiao.com/profile_v4", {
      waitUntil: "domcontentloaded",
      timeout: 15000,
    });
    const homeUrl = homeResponse ? homeResponse.url() : page.url();
    if (!String(homeUrl).includes("mp.toutiao.com")) {
      throw new Error(`头条登录态已失效，当前跳转到: ${homeUrl}`);
    }

    if (payload.dry_run) {
      jsonOut({
        success: true,
        dry_run: true,
        isLoggedIn: true,
        contentLength: String(payload.content || "").length,
        imageCount: Array.isArray(payload.images) ? payload.images.length : 0,
        finalUrl: homeUrl,
      });
      return;
    }

    await page.goto("https://mp.toutiao.com/profile_v4/weitoutiao/publish", {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });
    await page.waitForLoadState("networkidle").catch(() => {});

    await fillMicroPostContent(page, payload.content || "");

    const images = Array.isArray(payload.images) ? payload.images : [];
    if (images.length > 0) {
      await uploadMicroPostImages(page, images);
      await page.waitForTimeout(2500);
    }

    await clickMicroPostPublish(page);
    await page.waitForTimeout(4000);

    jsonOut({
      success: true,
      dry_run: false,
      type: "toutiao_micro_post",
      contentLength: String(payload.content || "").length,
      imageCount: images.length,
      finalUrl: page.url(),
      briefPath: payload.brief_path || "",
      title: payload.title || "",
    });
  } finally {
    await browser.close();
  }
}

if (require.main === module) {
  run().catch((error) => {
    process.stderr.write(`${error && error.stack ? error.stack : String(error)}\n`);
    process.exit(1);
  });
}
