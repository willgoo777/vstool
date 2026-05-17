# Uniaccess 应用白名单申请 — vstool

> 这是申请模板。把姓名/工号填好，按需删掉用不到的产物，发给 IT 即可。

## 申请人信息

- 姓名：[填写]
- 工号：[填写]
- 部门：[填写]
- 申请日期：2026-05-17

## 软件信息

- **软件名称**：vstool（文件夹对比工具）
- **版本**：v0.2.0
- **来源**：GitHub 公开仓库 https://github.com/willgoo777/vstool（MIT 开源）
- **构建方式**：GitHub Actions 在官方 windows-latest runner 上自动构建，构建日志公开可查
- **数字签名**：暂无（个人开发者，未购买代码签名证书）

## 待加入白名单的文件

### 🟢 推荐：Nuitka standalone（已验证可过 Uniaccess）

zip 解压后是一个 `vstool-standalone/` 文件夹，里面的 `vstool.exe` 是真正要运行的程序。

| 项目 | 值 |
|---|---|
| 文件名 | `vstool-nuitka-standalone.zip`（内含 `vstool-standalone/vstool.exe`） |
| 大小 | 214,389,705 字节（约 204 MB） |
| SHA256 | `ca6711e1a183bd150146bbdc44e49ff09a24311cc7455cf8832a27f89c925e63` |
| SHA1 | `a1e02706a1cdc44ec780e27bfb5994ba98d89dbe` |
| MD5 | `91b4b90c3994628539282f5d43f00e7e` |
| 下载链接 | https://github.com/willgoo777/vstool/releases/download/v0.2.0/vstool-nuitka-standalone.zip |

构建方式：Nuitka 4.1 standalone 模式，把 Python 真正编译成 C，输出原生 PE 二进制（不解压、不释放、行为模式与商业软件一致）。

### 备用 1：Nuitka 单文件

| 项目 | 值 |
|---|---|
| 文件名 | `vstool-nuitka.exe` |
| 大小 | 152,180,736 字节（约 145 MB） |
| SHA256 | `6d4ed61175bd29acbb5339ca08d0a16fdd564978f178e6a04c669e3763e835f7` |
| SHA1 | `243bf6ec24eb09cfedb897d28c3acbc6596d8c67` |
| MD5 | `1ca6d2d720d375f90ac2d997b8242c8a` |
| 下载链接 | https://github.com/willgoo777/vstool/releases/download/v0.2.0/vstool-nuitka.exe |

### 备用 2：PyInstaller 单文件

| 项目 | 值 |
|---|---|
| 文件名 | `vstool-pyinstaller.exe` |
| 大小 | 255,316,517 字节（约 243 MB） |
| SHA256 | `dd6e9a294f0eca4dc1616e051873598d1c66393ed159f0d4b455a8d9348c95e4` |
| SHA1 | `618dcb7b8f97ca3d249a4510ded4fab82c7e2e2d` |
| MD5 | `89ce87a677f165b1ad399e47471b3079` |
| 下载链接 | https://github.com/willgoo777/vstool/releases/download/v0.2.0/vstool-pyinstaller.exe |

## 用途说明

本工具用于**对比两个本地文件夹中同名 Word/Excel 文件的差异**，是日常审稿、版本比对、修订核对的提效辅助。具体功能：

1. **Word 文件**（.docx / .doc）：调用本机已安装的 Microsoft Word 自带的"比较"功能（`Application.CompareDocuments`），生成带 Word 原生修订标记的差异文档
2. **Excel 文件**（.xlsx / .xls）：从值、公式、格式、结构四个维度对比，生成综合差异报告（含可视化彩色单元格 + 表格化明细）
3. 输出一个 HTML 汇总页和若干差异文档到用户指定的本地目录

## 安全性说明

- ✅ **不联网**：本工具不发起任何网络请求，全程仅在本地磁盘读写
- ✅ **只读源文件**：对用户指定的 A、B 两个文件夹**只读**，不修改源文件
- ✅ **输出受控**：所有产物只写入用户在 GUI 中明确选定的"输出目录"
- ✅ **不调用其他可执行文件**：仅通过 COM 调用本机已装的 Microsoft Word / Excel
- ✅ **不写注册表**：免安装、双击运行，不修改系统配置
- ✅ **屏蔽宏自动执行**：调用 Word/Excel 时显式设置 `AutomationSecurity = msoAutomationSecurityForceDisable`，被对比文档中的宏不会被执行
- ✅ **源码开源可审计**：完整 Python 源码公开在 GitHub，配有 14 个自动化测试用例
- ✅ **构建过程透明**：每次发布版都由 GitHub Actions 在官方 windows-latest runner 上自动构建，构建日志全公开

## 技术细节

- 编程语言：Python 3.12
- 主要依赖：PySide6（GUI 框架，Qt 官方 Python 绑定）、openpyxl（Excel 解析库）、pywin32（Microsoft 官方 Office COM 桥）
- 推荐打包方式：Nuitka 4.x standalone（把 Python 编译成 C 后再编为原生 PE 二进制）

## 验证 Hash 的方法（IT 同事用）

PowerShell 中执行：

```powershell
Get-FileHash -Algorithm SHA256 vstool-nuitka-standalone.zip
```

输出值应与上面表格中的 SHA256 完全一致，证明文件在传输过程中未被篡改。
