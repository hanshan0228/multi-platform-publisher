function firstLocator(page, selectors) {
  return {
    async get() {
      for (const selector of selectors) {
        const locator = page.locator(selector).first();
        if (await locator.count()) {
          return locator;
        }
      }
      return null;
    },
  };
}

async function fillMicroPostContent(page, content) {
  const target = await firstLocator(page, [
    '.ProseMirror[contenteditable="true"]',
    "textarea",
  ]).get();
  if (!target) {
    throw new Error("未找到微头条内容输入区域");
  }
  await target.fill(String(content || ""));
}

async function uploadMicroPostImages(page, images) {
  const files = Array.isArray(images) ? images.filter(Boolean).slice(0, 9) : [];
  if (!files.length) {
    return;
  }

  const imageButton = await firstLocator(page, [
    ".weitoutiao-image-plugin .syl-toolbar-button",
    'button:has-text("图片")',
  ]).get();
  if (!imageButton) {
    throw new Error("未找到微头条图片上传入口");
  }
  await imageButton.click();

  const fileInput = await firstLocator(page, [
    'input[type="file"][accept*="image"]',
    'input[type="file"]',
  ]).get();
  if (!fileInput) {
    throw new Error("未找到微头条图片文件输入框");
  }
  await fileInput.waitFor({ state: "attached", timeout: 10000 });
  await fileInput.setInputFiles(files);

  const confirmButton = await firstLocator(page, [
    '[data-e2e="imageUploadConfirm-btn"]',
    'button:has-text("确定")',
  ]).get();
  if (confirmButton) {
    await confirmButton.click();
  }

  const closeDrawerButton = await firstLocator(page, [
    ".byte-drawer-close-icon",
  ]).get();
  if (closeDrawerButton) {
    await closeDrawerButton.click();
  }

  const drawerWrapper = page.locator(".byte-drawer-wrapper").first();
  if (await drawerWrapper.count()) {
    await drawerWrapper.waitFor({ state: "hidden", timeout: 15000 });
  }
}

async function clickMicroPostPublish(page) {
  const publishButton = await firstLocator(page, [
    ".publish-content",
    'button:has-text("发布")',
  ]).get();
  if (!publishButton) {
    throw new Error("未找到微头条发布按钮");
  }
  await publishButton.click();
}

module.exports = {
  fillMicroPostContent,
  uploadMicroPostImages,
  clickMicroPostPublish,
};
