#requires -Version 5.1
# Windows 上执行：在干净 venv 里装依赖并用 PyInstaller 打 dist\vstool.exe
# 用法（PowerShell）：
#   .\build.ps1
# 前置：本机已装 Python 3.10+ 和 Microsoft Office（运行 .exe 时需要）。

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ProjectRoot

if (-Not (Test-Path .\.venv)) {
    Write-Host "[build] 创建虚拟环境 .venv" -ForegroundColor Cyan
    python -m venv .venv
}

$Py = ".\.venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r requirements.txt
& $Py -m pip install pyinstaller

# 清旧产物
Remove-Item -Recurse -Force .\build, .\dist -ErrorAction SilentlyContinue
Remove-Item -Force .\vstool.spec -ErrorAction SilentlyContinue

Write-Host "[build] PyInstaller 打包" -ForegroundColor Cyan
& $Py -m PyInstaller `
    --onefile `
    --noconsole `
    --name vstool `
    --paths src `
    --hidden-import win32com `
    --hidden-import win32com.client `
    --hidden-import pythoncom `
    --collect-submodules openpyxl `
    --collect-submodules PySide6 `
    --exclude-module tkinter `
    --exclude-module PyQt5 `
    main.py

Write-Host "[build] 完成。产物：dist\vstool.exe" -ForegroundColor Green
