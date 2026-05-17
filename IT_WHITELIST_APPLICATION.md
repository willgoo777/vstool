# Uniaccess 应用白名单申请 — vstool.exe

## 申请人信息

- 姓名：[填写]
- 工号：[填写]
- 部门：[填写]
- 申请日期：2026-05-17

## 软件信息

- **软件名称**：vstool（文件夹对比工具）
- **版本**：v0.1.0
- **文件名**：vstool.exe
- **文件大小**：255 MB
- **SHA256**：`ee2ed1da2a78f9927e3cacc3f73dcb5e59a35083f6f60dc264706568c0b32b40`
- **SHA1**：`ce3f2818ef33855ea8ee6457f458853a509dc9e0`
- **MD5**：`cf963297247df26148eb633516dc940a`
- **来源**：GitHub 公开仓库 https://github.com/willgoo777/vstool
- **直接下载链接**：https://github.com/willgoo777/vstool/releases/download/v0.1.0/vstool.exe
- **源码可审阅**：https://github.com/willgoo777/vstool（MIT 开源）
- **构建方式**：GitHub Actions 在官方 windows-latest runner 上用 PyInstaller 自动构建，构建日志公开可查

## 用途说明

本工具用于**对比两个本地文件夹中同名 Word/Excel 文件的差异**，是日常审稿/对比修订工作的提效辅助。具体功能：

1. 对 Word 文件（.docx / .doc）：调用本机已安装的 Microsoft Word 自带的"比较"功能（Application.CompareDocuments），生成带修订标记的差异文档
2. 对 Excel 文件（.xlsx / .xls）：从值、公式、格式、结构四个维度对比，生成综合差异报告
3. 输出一个 HTML 汇总页和若干差异文档到用户指定的本地目录

## 安全性说明

- **不联网**：本工具不发起任何网络请求，全程仅在本地磁盘读写
- **只读源文件**：对用户指定的 A、B 两个文件夹**只读**，不修改源文件
- **输出受控**：所有产物只写入用户在 GUI 中明确选定的"输出目录"
- **不调用其他可执行文件**：仅通过 COM 调用本机已装的 Microsoft Word/Excel
- **不写注册表**：免安装、双击运行，不修改系统配置
- **不修改宏安全设置**：调用 Word 时显式设置 AutomationSecurity=3（强制禁用宏），不会执行被对比文档中的宏
- **源码开源可审计**：完整 Python 源码公开在 GitHub，含 13 个单元测试

## 技术细节

- 编程语言：Python 3.12
- 主要依赖：PySide6（GUI 框架，Qt 官方 Python 绑定）、openpyxl（Excel 解析库）、pywin32（Microsoft 官方 Office COM 桥）
- 打包工具：PyInstaller 6.x（单文件模式，启动时解压到 %TEMP%\_MEI*）
- 数字签名：暂无（个人开发者，未购买代码签名证书）

## 申请操作

请将该文件 hash 加入 Uniaccess 白名单，授权我本人 / [团队名称] 在公司电脑上运行。

---

**附：直接验证 hash 的方法**（Uniaccess / IT 同事可用）

PowerShell 中执行：
```powershell
Get-FileHash -Algorithm SHA256 vstool.exe
```
应当与上述 SHA256 一致。
