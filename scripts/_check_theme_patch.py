"""
테마 폰트 패치 결과 확인 스크립트
"""
import sys, os, tempfile, zipfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from lxml import etree
from pptx.oxml.ns import qn
from songlist_builder import build_songlist_pptx

TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "templates", "songlist_template.pptx")
TITLES = ["믿음이 없이는", "주님 마음 내게 주소서", "주의 자녀로 산다는 것은"]

with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
    out = tmp.name
try:
    build_songlist_pptx(TEMPLATE, TITLES, out)
    with zipfile.ZipFile(out) as z:
        theme_files = [n for n in z.namelist() if "theme" in n.lower() and n.endswith(".xml")]
        for tf in theme_files:
            root = etree.fromstring(z.read(tf))
            fs = root.find(".//" + qn("a:fontScheme"))
            if fs is None:
                continue
            print(f"=== {tf} ===")
            for tag in ("a:majorFont", "a:minorFont"):
                sec = fs.find(qn(tag))
                if sec is None:
                    continue
                ea = sec.find(qn("a:ea"))
                hang = next((e for e in sec.findall(qn("a:font")) if e.get("script") == "Hang"), None)
                print(f"  {tag}:")
                print(f"    ea typeface   = {ea.get('typeface') if ea is not None else '(없음)'}")
                print(f"    Hang typeface = {hang.get('typeface') if hang is not None else '(없음)'}")
finally:
    try:
        os.remove(out)
    except OSError:
        pass
