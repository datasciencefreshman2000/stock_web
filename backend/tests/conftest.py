import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Tests must explicitly provide a repository double. Never use a developer's .env DB.
import database


def blocked_database():
    raise RuntimeError("Tests cannot access the real database; provide a repository double.")


database.get_supabase = blocked_database
