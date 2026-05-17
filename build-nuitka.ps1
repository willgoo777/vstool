#requires -Version 5.1
# Nuitka 打包：把 Python 真正编译成 C，输出原生 PE 二进制。
# 相比 PyInstaller，对 AV/EDR（包括 Uniaccess 这类企业管控）误报率低得多。
#
# 同时出两份产物：
#   dist\vstool\vstool.exe   — 文件夹分发，启动不解压，最难被识别（Uniaccess 推荐）
#   dist\vstool-onefile.exe  — 单文件分发，首次启动解压到 %TEMP%
#
# 编译时间：15-25 分钟（PyInstaller 大概 5 分钟，Nuitka 慢但值得）。

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ProjectRoot

if (-Not (Test-Path .\.venv)) {
    Write-Host "[nuitka] 创建虚拟环境 .venv" -ForegroundColor Cyan
    python -m venv .venv
}

$Py = ".\.venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -r requirements.txt
& $Py -m pip install -e .            # 让 Nuitka 能在 site-packages 里找到 vstool
# Nuitka + 它的 C 编译器（Windows 上默认尝试用 MinGW64，没有就让 Nuitka 自动下载）
& $Py -m pip install "nuitka>=2.4" "ordered-set" "zstandard"

# 清旧产物
Remove-Item -Recurse -Force .\build, .\dist -ErrorAction SilentlyContinue

# 共用参数
$Common = @(
    "--enable-plugin=pyside6"
    "--include-package=PySide6"
    "--include-package=shiboken6"
    "--include-package=vstool"
    "--include-package=openpyxl"
    "--include-package=win32com"
    "--include-package=win32com.client"
    "--include-package=pythoncom"
    "--include-package=pywintypes"
    "--windows-console-mode=disable"
    "--windows-icon-from-ico=icon.ico"
    "--assume-yes-for-downloads"
    "--remove-output"
    "--company-name=vstool"
    "--product-name=vstool"
    "--file-version=0.3.0.0"
    "--product-version=0.3.0.0"
    "--file-description=文件夹对比工具"
)
# 若没准备 icon.ico，去掉对应参数（避免编译失败）
if (-Not (Test-Path .\icon.ico)) {
    $Common = $Common | Where-Object { $_ -notlike "--windows-icon-from-ico=*" }
}

Write-Host "[nuitka] 1/2 编译 standalone（文件夹分发）" -ForegroundColor Cyan
& $Py -m nuitka `
    --standalone `
    @Common `
    --output-dir=dist `
    --output-filename=vstool.exe `
    main.py

# 重命名输出目录为更友好的名字 + 打 zip 方便分发
if (Test-Path .\dist\main.dist) {
    Remove-Item -Recurse -Force .\dist\vstool -ErrorAction SilentlyContinue
    Move-Item .\dist\main.dist .\dist\vstool
    Remove-Item -Force .\dist\vstool.zip -ErrorAction SilentlyContinue
    Compress-Archive -Path .\dist\vstool -DestinationPath .\dist\vstool.zip
}

Write-Host "[nuitka] 2/2 编译 onefile（单 exe）" -ForegroundColor Cyan
& $Py -m nuitka `
    --standalone `
    --onefile `
    @Common `
    --output-dir=dist `
    --output-filename=vstool-onefile.exe `
    main.py

Write-Host "[nuitka] 完成。产物：" -ForegroundColor Green
Get-ChildItem dist | Format-Table Name, Length, LastWriteTime
