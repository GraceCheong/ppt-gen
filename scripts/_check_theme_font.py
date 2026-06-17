import sys
sys.path.insert(0, "src")
from pptx import Presentation
from pptx.oxml.ns import qn, nsmap
from lxml import etree

prs = Presentation(r"assets/templates/songlist_template.pptx")

# Check theme font scheme in slide masters
for i, master in enumerate(prs.slide_masters):
    theme_elem = master._element.find(".//" + qn("a:fontScheme"))
    if theme_elem is not None:
        print(f"=== slide master {i} fontScheme ===")
        print(etree.tostring(theme_elem, pretty_print=True).decode())
    else:
        print(f"=== slide master {i}: no fontScheme found ===")

# Also check presentation-level theme
import zipfile, os
template_path = r"assets/templates/songlist_template.pptx"
with zipfile.ZipFile(template_path) as z:
    theme_files = [n for n in z.namelist() if "theme" in n.lower() and n.endswith(".xml")]
    print("\n=== Theme files in PPTX ===")
    for tf in theme_files:
        print(f"\n--- {tf} ---")
        content = z.read(tf).decode("utf-8")
        root = etree.fromstring(content.encode("utf-8"))
        font_scheme = root.find(".//" + qn("a:fontScheme"))
        if font_scheme is not None:
            print(etree.tostring(font_scheme, pretty_print=True).decode())
        else:
            print("(no fontScheme)")
