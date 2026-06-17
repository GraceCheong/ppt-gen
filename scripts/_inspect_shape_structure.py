"""
템플릿과 생성된 PPTX의 shape 구조 비교
LibreOffice가 다른 폰트를 사용하는 원인 파악
"""
import zipfile
from lxml import etree
from pptx.oxml.ns import qn

def inspect_shapes(pptx_path, label):
    print(f"\n{'='*60}")
    print(f"FILE: {label}")
    print(f"{'='*60}")
    with zipfile.ZipFile(pptx_path) as z:
        with z.open('ppt/slides/slide1.xml') as f:
            root = etree.fromstring(f.read())

    for sp in root.iter(qn('p:sp')):
        descr = ''
        for el in sp.iter():
            if el.tag.endswith('}cNvPr'):
                descr = el.get('descr', '')
                break
        if not descr.startswith('곡 1'):
            continue
        print(f"\n--- Shape: {descr} ---")

        # placeholder?
        ph = sp.find('.//' + qn('p:ph'))
        print(f"placeholder: {etree.tostring(ph).decode() if ph is not None else 'None'}")

        # lstStyle
        lstStyle = sp.find('.//' + qn('a:lstStyle'))
        if lstStyle is not None and len(list(lstStyle)):
            print(f"lstStyle: {etree.tostring(lstStyle, pretty_print=True).decode()[:400]}")
        else:
            print("lstStyle: empty/None")

        # txBody bodyPr
        bodyPr = sp.find('.//' + qn('a:bodyPr'))
        if bodyPr is not None:
            print(f"bodyPr: {etree.tostring(bodyPr).decode()[:200]}")

        # each paragraph
        for i, para in enumerate(sp.iter(qn('a:p'))):
            pPr = para.find(qn('a:pPr'))
            endParaRPr = para.find(qn('a:endParaRPr'))
            runs = para.findall(qn('a:r'))
            print(f"\n  Para[{i}]: {len(runs)} run(s)")
            if pPr is not None:
                print(f"    pPr: {etree.tostring(pPr).decode()[:200]}")
            if endParaRPr is not None:
                print(f"    endParaRPr: {etree.tostring(endParaRPr, pretty_print=True).decode()[:300]}")
            for j, r in enumerate(runs):
                rPr = r.find(qn('a:rPr'))
                t = r.find(qn('a:t'))
                txt = t.text if t is not None else ''
                print(f"    Run[{j}] text={repr(txt[:20])}")
                if rPr is not None:
                    la = rPr.find(qn('a:latin'))
                    ea = rPr.find(qn('a:ea'))
                    print(f"      latin={la.get('typeface') if la is not None else 'MISSING'}")
                    print(f"      ea=   {ea.get('typeface') if ea is not None else 'MISSING'}")
                    print(f"      lang= {rPr.get('lang')}")
                else:
                    print(f"      rPr: NONE")
        break


inspect_shapes('assets/templates/songlist_template.pptx', 'TEMPLATE')
inspect_shapes('out/test_songlist.pptx', 'GENERATED')
