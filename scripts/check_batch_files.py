"""Validate Windows batch sources for encoding, line endings, and escape damage."""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".nox",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
BACKSLASH = bytes((92,))
BAD_SEQUENCES = {
    b"%" + BACKSLASH + b"~dp0": "escaped script-directory expansion",
    b"build" + BACKSLASH + b"_android": "escaped Android filename",
}
MARKDOWN_ESCAPE = re.compile(re.escape(BACKSLASH) + rb"(?:_|[\x2a]|#|[\x5b]|[\x5d]|<|>)")


def iter_source_files(*patterns: str):
    """Yield repository sources, excluding files owned by development tools."""
    for pattern in patterns:
        for path in ROOT.rglob(pattern):
            if not IGNORED_DIRECTORIES.intersection(path.relative_to(ROOT).parts):
                yield path


def iter_batch_files():
    """Yield batch sources maintained by this project."""
    yield from iter_source_files("*.bat", "*.cmd")


def validate_batch_file(path: Path) -> list[str]:
    data = path.read_bytes()
    errors: list[str] = []
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        errors.append("UTF-16 encoding is not supported")
        return errors
    if data.startswith(b"\xef\xbb\xbf"):
        errors.append("UTF-8 BOM is not allowed")
    try:
        data.decode("ascii")
    except UnicodeDecodeError:
        errors.append("batch content must be ASCII-only")
    if b"\n" in data and b"\r\n" not in data:
        errors.append("line endings must be CRLF")
    if data.replace(b"\r\n", b"").find(b"\n") >= 0:
        errors.append("mixed or LF-only line endings detected")
    for sequence, label in BAD_SEQUENCES.items():
        if sequence in data: errors.append(label)
    if MARKDOWN_ESCAPE.search(data): errors.append("Markdown escape")
    text = data.decode("ascii", errors="ignore")
    if "%~dp0" not in text:
        errors.append("missing canonical %~dp0 script directory expansion")
    return errors

def validate_source_escapes() -> list[str]:
    errors: list[str] = []
    markdown_escape = MARKDOWN_ESCAPE
    for suffix in ("*.py", "*.toml"):
        for path in iter_source_files(suffix):
            if path.resolve() == Path(__file__).resolve(): continue
            if markdown_escape.search(path.read_bytes()):
                errors.append(f"possible Markdown escape in {path.relative_to(ROOT)}")
    return errors

def main() -> int:
    files = sorted(iter_batch_files())
    if not files:
        print("BATCH CHECK: FAIL - no .bat or .cmd files found")
        return 1
    failed = False
    for path in files:
        errors = validate_batch_file(path)
        label = path.relative_to(ROOT)
        if errors:
            failed = True
            print(f"FAIL: {label}: {'; '.join(errors)}")
        else:
            print(f"PASS: {label} (ASCII, CRLF, no BOM, no Markdown escapes)")
    source_errors = validate_source_escapes()
    for error in source_errors:
        failed = True
        print(f"FAIL: {error}")
    print(f"BATCH CHECK: {'FAIL' if failed else 'PASS'}")
    return int(failed)

if __name__ == "__main__":
    raise SystemExit(main())
