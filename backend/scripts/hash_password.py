"""產生 APP_PASSWORD_HASH 與 JWT_SECRET。

用法（在 backend/ 目錄下）：
    python scripts/hash_password.py
"""

import secrets
import sys
from getpass import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.auth import hash_password  # noqa: E402


def main() -> None:
    password = getpass("設定網站密碼：")
    confirm = getpass("再輸入一次：")
    if password != confirm:
        print("兩次輸入不一致。")
        raise SystemExit(1)
    if len(password) < 8:
        print("密碼至少 8 個字元。")
        raise SystemExit(1)

    print("\n把下面兩行貼進 .env 與 Vercel 環境變數：\n")
    print(f"APP_PASSWORD_HASH={hash_password(password)}")
    print(f"JWT_SECRET={secrets.token_urlsafe(48)}")
    print()


if __name__ == "__main__":
    main()
