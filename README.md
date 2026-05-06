# multi-platform-publisher

A standalone project for publishing Chinese content to:

- WeChat Official Accounts drafts
- Toutiao micro posts
- Xiaohongshu posts and drafts

## Features

- Publish Markdown or HTML into WeChat drafts
- Support WeChat `api`, `browser`, and `auto` publish modes
- Keep WeChat browser login state in a persistent profile directory
- Convert Markdown to WeChat-compatible inline HTML
- Publish Toutiao micro posts from `brief.md + images/`
- Wrap Xiaohongshu browser automation for fill, draft, and publish flows

## Project Layout

```text
multi-platform-publisher/
  assets/
  examples/
  scripts/
    publish.py
    publish_wechat_api.py
    publish_wechat_browser.py
    publish_wechat_router.py
    publish_toutiao_micro.py
    publish_xiaohongshu.py
    config.py
    wechat_api.py
  tests/
  publish.py
  publish_xiaohongshu.py
  multi-platform-publisher.yaml.example
  requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
copy multi-platform-publisher.yaml.example multi-platform-publisher.yaml
```

Then fill:

- `wechat.accounts.*` for API publishing
- `wechat.publish` for default mode and fallback order
- `wechat.browser` for browser draft publishing
- `toutiao` and `xiaohongshu` only if you use those platforms

## Unified Entry

```bash
python publish.py wechat --input article.md --cover cover.jpg --account main
python publish.py toutiao --brief examples/brief-demo/brief.md
python publish.py xiaohongshu publish --input ../xhs-posts/ai-tools-guide --dry-run
```

## WeChat

API mode:

```bash
python publish.py wechat --input article.md --cover cover.jpg --publish-mode api
```

Browser mode:

```bash
python publish.py wechat --input article.md --cover cover.jpg --publish-mode browser
```

Auto fallback:

```bash
python publish.py wechat --input article.md --cover cover.jpg --publish-mode auto
```

You can also call the lower-level script directly:

```bash
python scripts/publish.py --input article.md --cover cover.jpg --account main --publish-mode auto
```

Browser mode notes:

- first login requires scanning the QR code in the persistent browser profile
- the script reuses the `token` from the logged-in WeChat backend URL to open the real editor page
- `auto` tries the configured fallback order, so API failure can fall back to browser draft save

## Toutiao

```bash
python publish.py toutiao --brief examples/brief-demo/brief.md
python publish_toutiao.py --brief examples/brief-demo/brief.md --dry-run
```

## Xiaohongshu

```bash
python publish.py xiaohongshu check-login
python publish.py xiaohongshu publish --input ../xhs-posts/ai-tools-guide --mode fill
python publish.py xiaohongshu publish --input ../xhs-posts/ai-tools-guide --mode fill --save-draft
python publish.py xiaohongshu click-publish
```

You can also override images and tags:

```bash
python publish.py xiaohongshu publish --input post-dir --images-dir post-dir/images --tags 旅行攻略 黄山 呈坎
```

## Tests

```bash
pytest tests/test_config.py tests/test_wechat_publish_router.py tests/test_html_converter.py tests/test_ai_score.py tests/test_xiaohongshu_publish.py -q
python -m unittest tests.test_toutiao_micro -v
node tests/test_toutiao_micro_publish.cjs
```

## Notes

- keep your real `multi-platform-publisher.yaml` out of git
- browser publishing needs Playwright plus a local Chromium-compatible browser
- the browser path in config can stay empty if Playwright-managed Chromium is enough for your setup
