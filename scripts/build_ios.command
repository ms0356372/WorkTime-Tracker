#!/bin/bash
set -e
cd "$(dirname "$0")/.."
if [[ "$(uname)" != "Darwin" ]]; then echo "iOS 只能在 macOS + Xcode 建置。"; exit 1; fi
command -v xcodebuild >/dev/null || { echo "找不到 Xcode。"; exit 1; }
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]' briefcase
python build_mobile.py ios
echo "Xcode 簽章需要自行選擇 Apple Developer Team。"
find build -name '*.xcodeproj' -print -quit | xargs open
