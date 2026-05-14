#!/usr/bin/env python3
"""Language-agnostic syntax check dispatcher.

Detects the language of the given file from its extension, looks up
the appropriate parse-only checker command, and runs it. Falls back to
a UTF-8 validity probe when no checker is available for the language
or the checker is not installed on PATH.

Used by /securecoder-fix as the per-fix verification step after the
patch applier writes a file. A non-zero exit code means the patch
introduced a syntax error and the caller should restore from backup.

Stdlib only.

Usage:
    python3 syntax_check.py <file> [--json]

Exit codes:
    0   — file parses cleanly OR no checker available and UTF-8 fallback passed
    1   — checker reported a syntax error
    2   — file missing or unreadable

When --json is set, a result document is printed to stdout regardless
of exit code so the caller can introspect why the check passed or failed.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


# Extension → checker command tuple. The target file path is appended
# to the tuple at invocation time.
CHECKERS: dict = {
    ".py":         ("python3", "-m", "py_compile"),
    ".js":         ("node", "--check"),
    ".mjs":        ("node", "--check"),
    ".cjs":        ("node", "--check"),
    ".go":         ("gofmt", "-e"),
    ".rb":         ("ruby", "-c"),
    ".php":        ("php", "-l"),
    ".sh":         ("bash", "-n"),
    ".bash":       ("bash", "-n"),
    ".zsh":        ("zsh", "-n"),
}


def check_with_command(cmd_tuple: tuple, path: Path) -> tuple:
    """Run `cmd <path>` and return (exit_code, message, method)."""
    if not shutil.which(cmd_tuple[0]):
        return None, f"{cmd_tuple[0]} not on PATH", " ".join(cmd_tuple)
    cmd = list(cmd_tuple) + [str(path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return 1, f"checker timed out after 30s", " ".join(cmd_tuple)
    msg = (r.stderr or r.stdout or "").strip()
    return r.returncode, msg, " ".join(cmd_tuple)


def check_json_stdlib(path: Path) -> tuple:
    try:
        with open(path, encoding="utf-8") as f:
            json.load(f)
        return 0, "", "python3 json.load"
    except json.JSONDecodeError as e:
        return 1, f"JSON parse error: {e}", "python3 json.load"
    except OSError as e:
        return 2, str(e), "python3 json.load"


def check_utf8(path: Path) -> tuple:
    """Fallback: confirm the file is valid UTF-8 (does not check syntax)."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        data.decode("utf-8")
        return 0, "", "utf8_fallback"
    except UnicodeDecodeError as e:
        return 1, f"file is not valid UTF-8: {e}", "utf8_fallback"
    except OSError as e:
        return 2, str(e), "utf8_fallback"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", help="Path to the file to check")
    ap.add_argument("--json", action="store_true",
                    help="Emit machine-readable JSON to stdout")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_file():
        msg = f"file not found: {path}"
        if args.json:
            sys.stdout.write(json.dumps({"file": str(path), "exit_code": 2,
                                          "message": msg, "method": "n/a"}))
        else:
            sys.stderr.write(msg + "\n")
        sys.exit(2)

    ext = path.suffix.lower()

    if ext == ".json":
        code, message, method = check_json_stdlib(path)
    elif ext in CHECKERS:
        code, message, method = check_with_command(CHECKERS[ext], path)
        if code is None:
            # Checker not installed → fall back to UTF-8
            code, message_fb, method_fb = check_utf8(path)
            method = f"{method} (not on PATH; fell back to {method_fb})"
            message = message or message_fb
    else:
        code, message, method = check_utf8(path)

    if args.json:
        sys.stdout.write(json.dumps({
            "file": str(path),
            "ext": ext,
            "method": method,
            "exit_code": code,
            "message": message,
        }, indent=2))
    elif code != 0 and message:
        sys.stderr.write(f"{path}: {message}\n")

    sys.exit(code)


if __name__ == "__main__":
    main()
