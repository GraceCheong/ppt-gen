# -*- coding: utf-8 -*-
"""
악보 DB 파싱 수정 스크립트.

- display_title, key_root, key_mode, page_number, normalized_title, song_title_key 재파싱
- uploaded_by 'gdrive_sync' → '드라이브' 일괄 변경
- key 없는 파일은 key_root='', key_mode='' 로 설정 (사용자 요청: "지금까지 입력된 악보 키 값 초기화")

사용법: python tools/fix_sheet_parsing.py [--apply]
  --apply 없이 실행하면 미리보기만, --apply 붙이면 실제 반영
"""
import os, re, sqlite3, sys, unicodedata

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["GDRIVE_SYNC_ENABLED"] = "false"

from server.app.services.db import history_db_path
from server.app.services.gdrive_sync import _parse_sheet_filename, _normalize_fname

def normalize_title(s: str) -> str:
    s = unicodedata.normalize("NFC", s).strip()
    s = re.sub(r"\s+", " ", s)
    return s.lower()

def ensure_song_exists(conn: sqlite3.Connection, title: str) -> str:
    title_key = normalize_title(title)
    exists = conn.execute(
        "SELECT 1 FROM lyrics_catalog WHERE title_key=?", (title_key,)
    ).fetchone()
    if not exists:
        conn.execute(
            "INSERT OR IGNORE INTO lyrics_catalog (title_key, display_title) VALUES (?,?)",
            (title_key, title),
        )
    return title_key

DRY_RUN = "--apply" not in sys.argv

db = history_db_path()
print(f"DB: {db}")
print(f"모드: {'미리보기 (--apply 없음)' if DRY_RUN else '적용'}\n")

with sqlite3.connect(db) as conn:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, display_title, key_root, key_mode, page_number, "
        "       original_filename, uploaded_by, song_title_key "
        "FROM sheet_files WHERE status='active'"
    ).fetchall()

changes = []
uploader_fixes = []

for r in rows:
    orig = r["original_filename"]
    clean_title, new_kr, new_km, new_page, info = _parse_sheet_filename(orig)
    new_title = f"{clean_title} {info}".strip() if info else clean_title

    # key 없는 파일: 빈 문자열로 (사용자 요청: 기존 key도 초기화)
    new_kr = new_kr or ""
    new_km = new_km or ""

    new_title_key = normalize_title(clean_title)

    changed = (
        new_title != r["display_title"]
        or new_kr != r["key_root"]
        or new_km != r["key_mode"]
        or new_page != r["page_number"]
        or new_title_key != r["song_title_key"]
    )
    if changed:
        changes.append({
            "id": r["id"],
            "orig": orig,
            "old_title": r["display_title"],
            "new_title": new_title,
            "clean_title": clean_title,
            "new_title_key": new_title_key,
            "old_kr": r["key_root"],
            "new_kr": new_kr,
            "old_km": r["key_mode"],
            "new_km": new_km,
            "old_page": r["page_number"],
            "new_page": new_page,
        })

    if r["uploaded_by"] == "gdrive_sync":
        uploader_fixes.append(r["id"])

print(f"메타 수정: {len(changes)}개")
print(f"업로더 수정 ('gdrive_sync' → '드라이브'): {len(uploader_fixes)}개")
print()

for c in changes:
    lines = [f"파일: {c['orig']}"]
    if c["old_title"] != c["new_title"]:
        lines.append(f"  제목: [{c['old_title']}] → [{c['new_title']}]")
    old_k = c["old_kr"] + ("m" if c["old_km"] == "minor" else "")
    new_k = c["new_kr"] + ("m" if c["new_km"] == "minor" else "")
    if old_k != new_k:
        lines.append(f"  key : {old_k or '(없음)'} → {new_k or '(없음)'}")
    if c["old_page"] != c["new_page"]:
        lines.append(f"  page: {c['old_page']} → {c['new_page']}")
    print("\n".join(lines))
    print()

if DRY_RUN:
    print("== 미리보기 완료. 실제 반영하려면 --apply 옵션을 추가하세요 ==")
    sys.exit(0)

confirm = input(f"\n총 {len(changes)}개 메타 수정 + {len(uploader_fixes)}개 업로더 수정을 적용하시겠습니까? (y/N): ").strip().lower()
if confirm != "y":
    print("취소됨.")
    sys.exit(0)

with sqlite3.connect(db) as conn:
    conn.row_factory = sqlite3.Row
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    for c in changes:
        ensure_song_exists(conn, c["clean_title"])
        conn.execute(
            """UPDATE sheet_files SET
               display_title=?, normalized_title=?, song_title_key=?,
               key_root=?, key_mode=?, page_number=?, updated_at=?
               WHERE id=?""",
            (
                c["new_title"], normalize_title(c["new_title"]),
                c["new_title_key"],
                c["new_kr"], c["new_km"], c["new_page"],
                now, c["id"],
            ),
        )

    if uploader_fixes:
        conn.execute(
            f"UPDATE sheet_files SET uploaded_by='드라이브' WHERE id IN ({','.join('?'*len(uploader_fixes))})",
            uploader_fixes,
        )

    conn.commit()

print(f"\n완료: {len(changes)}개 메타 수정, {len(uploader_fixes)}개 업로더 수정")
