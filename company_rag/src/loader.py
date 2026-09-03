# src/loader.py
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

def iter_blocks(doc):
    """문단과 표를 '문서에 나온 순서 그대로' 하나씩 내보낸다."""
    for child in doc.element.body.iterchildren():
        if child.tag.endswith('}p'):
            yield Paragraph(child, doc)
        elif child.tag.endswith('}tbl'):
            yield Table(child, doc)

def load_docx(path: str) -> list[str]:
    doc = Document(path)
    out = []
    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if t:
                out.append(t)
        else:  # Table
            for row in block.rows:
                # TODO) 한 행의 셀들을 " | " 로 이어붙여 한 줄로 만들기
                #  힌트: cells = [c.text.strip() for c in row.cells]
                #        line = " | ".join(cells)
                cells = [c.text.strip() for c in row.cells]
                line = " | ".join(cells)
                if line.strip(" |"):
                    out.append(line)
    return out