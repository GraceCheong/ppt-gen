"""
LibreOffice로 직접 변환해서 실제 렌더링 결과 확인
"""
import sys, os, tempfile, subprocess, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from songlist_builder import build_songlist_pptx, find_libreoffice

TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "templates", "songlist_template.pptx")
TITLES = ["믿음이 없이는", "주님 마음 내게 주소서", "주의 자녀로 산다는 것은"]
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "out")
os.makedirs(OUT_DIR, exist_ok=True)

OUT_PPTX = os.path.join(OUT_DIR, "test_songlist.pptx")
OUT_PNG  = os.path.join(OUT_DIR, "test_songlist.png")

# 1. PPTX 생성
build_songlist_pptx(TEMPLATE, TITLES, OUT_PPTX)
print(f"PPTX 생성됨: {OUT_PPTX}")

# 2. LibreOffice 변환
lo = find_libreoffice()
if not lo:
    print("LibreOffice를 찾을 수 없습니다")
    sys.exit(1)

print(f"LibreOffice: {lo}")
result = subprocess.run(
    [lo, "--headless", "--norestore", "--convert-to", "png", "--outdir", OUT_DIR, OUT_PPTX],
    capture_output=True, timeout=60, text=True
)
print("stdout:", result.stdout)
print("stderr:", result.stderr[:500] if result.stderr else "")
print("returncode:", result.returncode)

generated = os.path.join(OUT_DIR, "test_songlist.png")
if os.path.exists(generated):
    print(f"\n✓ PNG 생성됨: {generated}")
else:
    print("\n✗ PNG 생성 실패")
