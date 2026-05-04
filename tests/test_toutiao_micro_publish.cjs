const test = require("node:test");
const assert = require("node:assert/strict");

const {
  fillMicroPostContent,
  uploadMicroPostImages,
  clickMicroPostPublish,
} = require("../scripts/toutiao_micro_publish_helpers.cjs");

function createLocator(options = {}) {
  return {
    _count: options.count ?? 0,
    _name: options.name ?? "locator",
    async count() {
      return this._count;
    },
    first() {
      return this;
    },
    locator() {
      return this;
    },
    async fill(value) {
      options.record.push(["fill", this._name, value]);
    },
    async click() {
      options.record.push(["click", this._name]);
    },
    async setInputFiles(files) {
      options.record.push(["setInputFiles", this._name, files]);
    },
    async waitFor() {
      options.record.push(["waitFor", this._name]);
    },
  };
}

test("fillMicroPostContent prefers ProseMirror editor on new page", async () => {
  const record = [];
  const locators = {
    '.ProseMirror[contenteditable="true"]': createLocator({
      count: 1,
      name: "editor",
      record,
    }),
    textarea: createLocator({ count: 0, name: "textarea", record }),
  };

  const page = {
    locator(selector) {
      return locators[selector] || createLocator({ count: 0, name: selector, record });
    },
  };

  await fillMicroPostContent(page, "hello world");

  assert.deepEqual(record, [["fill", "editor", "hello world"]]);
});

test("uploadMicroPostImages opens image panel and uploads through file input", async () => {
  const record = [];
  const locators = {
    ".weitoutiao-image-plugin .syl-toolbar-button": createLocator({
      count: 1,
      name: "image-button",
      record,
    }),
    'input[type="file"][accept*="image"]': createLocator({
      count: 2,
      name: "file-input",
      record,
    }),
    '[data-e2e="imageUploadConfirm-btn"]': createLocator({
      count: 1,
      name: "confirm-upload",
      record,
    }),
    ".byte-drawer-close-icon": createLocator({
      count: 1,
      name: "close-drawer",
      record,
    }),
    ".byte-drawer-wrapper": createLocator({
      count: 1,
      name: "drawer-wrapper",
      record,
    }),
  };

  const page = {
    locator(selector) {
      return locators[selector] || createLocator({ count: 0, name: selector, record });
    },
  };

  await uploadMicroPostImages(page, ["a.png", "b.png"]);

  assert.deepEqual(record, [
    ["click", "image-button"],
    ["waitFor", "file-input"],
    ["setInputFiles", "file-input", ["a.png", "b.png"]],
    ["click", "confirm-upload"],
    ["click", "close-drawer"],
    ["waitFor", "drawer-wrapper"],
  ]);
});

test("clickMicroPostPublish uses the new publish button class first", async () => {
  const record = [];
  const locators = {
    ".publish-content": createLocator({
      count: 1,
      name: "publish-button",
      record,
    }),
  };

  const page = {
    locator(selector) {
      return locators[selector] || createLocator({ count: 0, name: selector, record });
    },
  };

  await clickMicroPostPublish(page);

  assert.deepEqual(record, [["click", "publish-button"]]);
});
