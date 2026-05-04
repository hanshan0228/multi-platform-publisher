# multi-platform-publisher

A cleaned-up standalone project for publishing Chinese content to:

- WeChat Official Accounts draft box
- Toutiao micro posts

This project was extracted from a larger workspace and keeps only the code needed for those two publishing flows.

## Features

- Publish Markdown content to WeChat drafts
- Convert Markdown to WeChat-compatible inline HTML
- Upload WeChat cover and inline images
- Publish Toutiao micro posts from `brief.md + images/`
- Reuse local Toutiao login cookies
- Keep WeChat and Toutiao publishing in one repository with one config file

## Project Layout

```text
multi-platform-publisher/
  assets/
    themes/
    image-styles/
  examples/
    brief-demo/
  scripts/
    publish.py
    publish_toutiao_micro.py
    wechat_api.py
    wechat_token.py
    api.py
    config.py
    html_converter.py
    image_handler.py
    ai_score.py
    newspic_build.py
    toutiao_micro.py
    toutiao_micro_publish.cjs
    toutiao_micro_publish_helpers.cjs
  tests/
  publish_wechat.py
  publish_toutiao.py
  multi-platform-publisher.yaml.example
  requirements.txt
```

## Setup

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Copy the config template:

```bash
copy multi-platform-publisher.yaml.example multi-platform-publisher.yaml
```

3. Fill in your WeChat app credentials and Toutiao cookie path.

## WeChat Usage

Publish Markdown to the WeChat draft box:

```bash
python publish_wechat.py --input article.md --cover cover.jpg --account main
```

Or directly:

```bash
python scripts/publish.py --input article.md --cover cover.jpg --account main
```

## Toutiao Usage

Publish a micro post from a `brief.md + images/` directory:

```bash
python publish_toutiao.py --brief examples/brief-demo/brief.md
```

Dry run:

```bash
python publish_toutiao.py --brief examples/brief-demo/brief.md --dry-run
```

## Config

The project reads:

- `multi-platform-publisher.yaml`
- falls back to `wechat-publisher.yaml` for compatibility if needed

The config is split into:

- `wechat`
- `toutiao`
- `image_generation`
- `integrations`

## Tests

Python tests:

```bash
pytest tests/test_config.py tests/test_html_converter.py tests/test_ai_score.py
python -m unittest tests.test_toutiao_micro -v
```

Node test:

```bash
node tests/test_toutiao_micro_publish.cjs
```

## Notes

- Toutiao publishing depends on a working global `toutiao-mcp` installation and Playwright browser runtime.
- The repository does not include live credentials or cookies.
- The old generated/demo content was reduced to a single example under `examples/brief-demo/`.
