from __future__ import annotations

SUPPORTED_WORD_EXTS = frozenset({".docx", ".doc"})
SUPPORTED_EXCEL_EXTS = frozenset({".xlsx", ".xls"})
SUPPORTED_EXTS = SUPPORTED_WORD_EXTS | SUPPORTED_EXCEL_EXTS

# 文件名前缀/后缀过滤
EXCLUDE_NAME_PREFIXES = ("~$", ".")
EXCLUDE_SUFFIXES = (".tmp",)

# Excel 输出配色（ARGB；openpyxl PatternFill 接受 8 位 RGB）
COLOR_VALUE_DIFF = "FFFFC7CE"      # 浅红：值差异
COLOR_FORMULA_DIFF = "FFFFEB9C"    # 浅黄：公式差异
COLOR_FORMAT_DIFF = "FFBDD7EE"     # 浅蓝：仅格式差异
COLOR_ADDED_HEADER = "FFC6EFCE"    # 浅绿：B 新增行/列表头
COLOR_SUMMARY_HEADER = "FFD9D9D9"  # 灰：总览表头

# Word COM 魔法常量（晚期绑定下无 wdConstants）
WD_ALERTS_NONE = 0
WD_AUTOMATION_SECURITY_FORCE_DISABLE = 3
WD_FORMAT_DOCUMENT_DEFAULT = 16     # .docx
WD_COMPARE_DESTINATION_NEW = 2
WD_SAVE_CHANGES_NO = 0
WD_NO_PROTECTION = -1               # doc.ProtectionType 未保护

# Excel COM 魔法常量
XL_OPENXML_WORKBOOK = 51            # .xlsx

# 输出目录子文件夹
OUTPUT_DIFF_SUBDIR = "对比有差异"
OUTPUT_NODIFF_SUBDIR = "对比无差异"
OUTPUT_PROTECTED_WORKSPACE = "受保护文件工作区"
SUMMARY_FILENAME = "summary.html"
