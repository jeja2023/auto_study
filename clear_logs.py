import os
import sys

# 将项目根目录添加到 Python 路径
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from backend.database import SessionLocal, engine, Base
from backend.models import LogEntry

def clear_log_entries():
    """Clears all entries from the LogEntry table."""
    print("Attempting to clear LogEntry table...")
    db = SessionLocal()
    try:
        # 删除所有记录
        num_deleted = db.query(LogEntry).delete()
        db.commit()
        print(f"Successfully deleted {num_deleted} log entries from the database.")
    except Exception as e:
        db.rollback()
        print(f"Error clearing log entries: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_log_entries()