# vstool — 文件夹对比工具

[![Build Windows .exe](https://github.com/willgoo777/vstool/actions/workflows/build-windows.yml/badge.svg)](https://github.com/willgoo777/vstool/actions/workflows/build-windows.yml)

Windows 本地小工具：把 A、B 两个文件夹按文件名一一配对，对每一对同名文件做差异对比。

## 下载

- **正式版**：[Releases 页面](https://github.com/willgoo777/vstool/releases) → 选最新版本 → 下载 `vstool.exe`
- **每次提交的开发版**：[Actions 页面](https://github.com/willgoo777/vstool/actions) → 点最新一次绿色 ✓ 的 build → 下方 Artifacts 区域下载 `vstool-windows-xxx.zip`（90 天内有效，需要 GitHub 登录）

下载后是单个 `.exe`，免安装，双击就跑。

- **Word**（`.docx` / `.doc`）：调用本机 Microsoft Word 的"修订对比"功能，生成一份新的 `.docx`，里面是 Word 原生的修订标记（红字、删除线、批注），打开就能看。
- **Excel**（`.xlsx` / `.xls`）：从值、公式、格式、结构四个维度比较，生成一份综合 `.xlsx`：
  - `00_总览`：每个工作表改了多少处、增删了哪些工作表、合并单元格和命名区间的差异。
  - `S_<工作表名>`：复制 B 的工作表，按差异类型给单元格涂色（红=值变了、黄=公式变了但结果一样、蓝=只是格式变了），并在批注里写明 A 的原值。
  - `99_差异明细`：表格化的全部差异条目，可自由筛选。
- 子文件夹递归。只在一侧出现的文件不对比，会列入 `summary.html`。
- 跑完会自动在浏览器里打开 `summary.html`，里面有所有结果的链接。

## 使用方法

1. 把 `vstool.exe` 拷到任意目录，**双击运行**（不会写注册表，不会装到 Program Files）。
2. 在窗口里分别选好 **文件夹 A**、**文件夹 B**、**输出目录**。
3. 点 **开始对比**。下方进度条和日志会实时刷新。
4. 跑完浏览器会自动打开汇总页，逐项点开查看差异。

> **首次启动慢是正常的**：单文件 .exe 启动时要解压到 `%TEMP%\_MEI*`，大约 3–8 秒。请不要狂双击。

## 环境前提

- Windows 10 / 11
- 已安装 **Microsoft Office**（Word + Excel）。WPS 不支持。
- 不需要单独装 Python。

## 限制 / 已知行为

- **不处理 `.xlsm`**（含宏的 Excel）：扫描阶段直接跳过，避免破坏宏。
- **格式对比基于 openpyxl**：图表、透视表、条件格式、嵌入图片在对比产物中可能与原文件略有差异。对比产物只为"看差异"，不要拿来当 B 的副本用。
- **缓存值缺失**：如果 A 或 B 是某个程序生成、从未在 Excel 里手动打开保存过，部分公式单元格会读到空值。这种情况会在批注里标注"原文件缓存值缺失"，不会误报为值差异。
- **取消功能在两对之间生效**：Word/Excel COM 不支持中途打断，单对内必须等当前对完成才会响应取消。
- 受密码保护、损坏或被其他程序占用的文件会被标记为"跳过/失败"，理由写在汇总里。

## 开发

```
make install       # 装依赖到 .venv（macOS / Linux 可跑非 COM 部分）
make test          # 跑单元测试
make gui           # 起 GUI（macOS 上 Word/Excel 对会被标 skip）
```

打 .exe（**必须在 Windows 上**执行）：

```powershell
.\build.ps1
# 产物：dist\vstool.exe
```

## 项目结构

```
src/vstool/
├── app.py            # GUI 入口
├── config.py         # 常量
├── i18n.py           # 中文文案
├── scanner.py        # 递归扫描 + 过滤
├── pairing.py        # 同名配对
├── com_utils.py      # COM Dispatch 包装、CoInitialize 上下文
├── word_diff.py      # Word COM CompareDocuments（Windows-only）
├── excel_diff.py     # openpyxl 四维度对比 + 输出
├── excel_legacy.py   # .xls → .xlsx（Excel COM, Windows-only）
├── report.py         # summary.html
├── pipeline.py       # 编排：scan → pair → 分发 → report
├── cancellation.py   # 线程安全取消令牌
└── gui/
    ├── main_window.py
    └── worker.py     # QThread + CoInitialize
```
