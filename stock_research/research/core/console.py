"""Windows 主控台編碼修正。

PowerShell / cmd 預設是 cp950，遇到 ✅ ⚠ ❌ 或框線字元會直接
UnicodeEncodeError 讓整支程式崩掉。每支 script 開頭呼叫一次即可。
"""

import sys


def setup() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
