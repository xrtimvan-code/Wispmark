$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python -m pip install "pyinstaller>=6.0,<7"
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller install failed' }
    python -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name XuanJian-Markdown `
        --add-data "editor/index.html;editor" `
        --add-data "editor/style.css;editor" `
        --add-data "editor/bundle.js;editor" `
        --add-data "licenses;licenses" `
        --add-data "ocr_scan.ps1;." `
        --add-data "LICENSE;." `
        --add-data "THIRD_PARTY_NOTICES.txt;." `
        floating_notepad.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows build failed' }
} finally {
    Pop-Location
}
