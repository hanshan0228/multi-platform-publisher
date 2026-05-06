#!/usr/bin/env python3
from pathlib import Path
import runpy
import sys


if __name__ == "__main__":
    script = Path(__file__).parent / "scripts" / "publish_xiaohongshu.py"
    sys.path.insert(0, str(script.parent))
    runpy.run_path(str(script), run_name="__main__")
