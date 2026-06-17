"""
슬라이드 마스터의 txStyles와 레이아웃 폰트 설정 확인
"""
import zipfile
from lxml import etree
from pptx.oxml.ns import qn

TEMPLATE = 'assets/templates/songlist_template.pptx'

with zipfile.ZipFile(TEMPLATE) as z:
    names = z.namelist()
    masters = [n for n in names if n.startswith('ppt/slideMasters/')]
    layouts = [n for n in names if n.startswith('ppt/slideLayouts/')]

    print("Masters:", masters)
    print("Layouts:", layouts[:3])

    if masters:
        with z.open(masters[0]) as f:
            master_root = etree.fromstring(f.read())

    # txStyles
    txStyles = master_root.find('.//' + qn('p:txStyles'))
    if txStyles is not None:
        # 각 레벨의 폰트 설정
        for child in txStyles:
            tag = child.tag.split('}')[-1]
            print(f"\n--- {tag} ---")
            for lvl in child.findall('.//' + qn('a:lvl1pPr')) or []:
                defRPr = lvl.find(qn('a:defRPr'))
                if defRPr is not None:
                    la = defRPr.find(qn('a:latin'))
                    ea = defRPr.find(qn('a:ea'))
                    cs = defRPr.find(qn('a:cs'))
                    print(f"  lvl1pPr defRPr: latin={la.get('typeface') if la is not None else 'N/A'} ea={ea.get('typeface') if ea is not None else 'N/A'} cs={cs.get('typeface') if cs is not None else 'N/A'}")
            # Any font in any element
            for el in child.iter():
                tag2 = el.tag.split('}')[-1]
                if tag2 in ('latin', 'ea', 'cs'):
                    tf = el.get('typeface', '')
                    if tf and tf not in ('+mj-lt', '+mn-lt', '+mj-ea', '+mn-ea', ''):
                        print(f"  Font: {tag2}={tf!r} (parent={el.getparent().tag.split('}')[-1]})")
    else:
        print("txStyles: None")

    print("\n\n--- Master theme fonts (fontScheme) ---")
    for sp in master_root.iter(qn('p:sp')):
        # look for shapes with Korean text
        for t in sp.iter(qn('a:t')):
            if t.text and any('\uAC00' <= c <= '\uD7A3' for c in (t.text or '')):
                descr = ''
                for el in sp.iter():
                    if el.tag.endswith('}cNvPr'):
                        descr = el.get('name', el.get('descr', ''))
                        break
                print(f"  Master shape with Korean: {descr!r} text={t.text!r}")
                break
