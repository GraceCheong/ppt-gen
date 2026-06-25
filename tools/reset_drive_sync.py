"""
드라이브 동기화 초기화 스크립트.

drive_file_id가 있는 sheet_files 레코드와 해당 물리 파일을 모두 삭제합니다.
직접 업로드한 파일(drive_file_id IS NULL)은 보존됩니다.

사용법: python tools/reset_drive_sync.py
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GDRIVE_SYNC_ENABLED", "false")

from server.app.services.db import history_db_path

db = history_db_path()
print(f"DB: {db}\n")

with sqlite3.connect(db) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, display_title, storage_path FROM sheet_files WHERE drive_file_id IS NOT NULL"
    ).fetchall()

if not rows:
    print("삭제할 Drive 동기화 파일이 없습니다.")
    sys.exit(0)

print(f"Drive 동기화 파일 {len(rows)}개 발견:\n")
for r in rows:
    print(f"  {r['display_title']} — {r['storage_path']}")

print()
confirm = input(f"\n{len(rows)}개 파일을 모두 삭제하시겠습니까? (y/N): ").strip().lower()
if confirm != "y":
    print("취소됨.")
    sys.exit(0)

deleted_files = 0
missing_files = 0
with sqlite3.connect(db) as conn:
    for r in rows:
        path = r["storage_path"]
        if path and os.path.exists(path):
            os.remove(path)
            deleted_files += 1
        else:
            missing_files += 1
    conn.execute("DELETE FROM sheet_files WHERE drive_file_id IS NOT NULL")
    conn.commit()

print(f"\n완료:")
print(f"  물리 파일 삭제: {deleted_files}개")
print(f"  파일 없음 (이미 삭제됨): {missing_files}개")
print(f"  DB 레코드 삭제: {len(rows)}개")
print("\n서버를 재시작하면 새 Drive 폴더에서 자동으로 동기화됩니다.")
