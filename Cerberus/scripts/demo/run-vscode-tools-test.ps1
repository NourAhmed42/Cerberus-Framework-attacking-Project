# Windows (PowerShell) wrapper: runs the local tool demo from the project root.
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\demo\run-vscode-tools-test.ps1
#         ... -File scripts\demo\run-vscode-tools-test.ps1 --include-public
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
& .\backend\.venv\Scripts\python.exe scripts\demo\run_everything.py @args
exit $LASTEXITCODE
