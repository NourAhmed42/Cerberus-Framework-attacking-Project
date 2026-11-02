#!/bin/sh
# Mac (zsh) wrapper: runs the local tool demo from the project root.
# Usage:  zsh scripts/demo/run-vscode-tools-test.sh
#         zsh scripts/demo/run-vscode-tools-test.sh --include-public
set -e
cd "$(dirname "$0")/../.."
if [ -z "$SQLMAP_PATH" ] && command -v sqlmap >/dev/null 2>&1; then
  SQLMAP_PATH="$(command -v sqlmap)"
  export SQLMAP_PATH
fi
exec ./backend/.venv/bin/python scripts/demo/run_everything.py "$@"
