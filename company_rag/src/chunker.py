# src/chunker.py
import re

# 패턴 두 개 (이게 경계 감지의 핵심)
ARTICLE_RE = re.compile(r"^제(\d+)조\s*\((.+?)\)")   # 제5조 (수습기간)
CHAPTER_RE = re.compile(r"^(제\d+장.*|부칙)")          # 제2장 채용... / 부칙
CLAUSE_RE  = re.compile(r"^(\d+)\.\s")               # 항: "1. 1년간 80% 이상..."

# 조 단위 청킹은 길이 상한이 없다. 조항이 길면 ① 임베딩이 평균값으로 뭉개져
# 검색 정확도가 떨어지고 ② 프롬프트(num_ctx)를 밀어내 규정 컨텍스트가 잘린다.
# 이 길이를 넘는 조만 항 단위로 쪼갠다. 샘플 취업규칙은 최장 240자라 해당 없음.
MAX_CHARS = 800

def chunk_by_article(paragraphs: list[str]) -> list[dict]:
    chunks = []
    current_chapter = ""
    current = None          # 지금 채우는 중인 조(청크). 아직 없으면 None

    for para in paragraphs:
        ch = CHAPTER_RE.match(para)
        art = ARTICLE_RE.match(para)

        if ch:
            # TODO-1) 장 헤딩을 만남 → current_chapter 를 이 문단으로 갱신
            #         (청크엔 넣지 않는다. continue 로 넘어가기)
            current_chapter = para
            continue

        elif art:
            # TODO-2) 새 조 시작.
            #  a) 직전에 만들던 current 가 있으면 chunks 에 append (저장)
            #  b) 새 current 딕셔너리 생성:
            #     article_no    = int(art.group(1))
            #     article_title = art.group(2)
            #     chapter       = current_chapter
            #     text          = 이 헤딩 문단(para)  ← 출처 표기용으로 헤딩도 본문에 포함
            if current:                      # 이전에 만들던 조가 있으면
                chunks.append(current)       # 먼저 저장 (current_chapter 아님!)
            current = {                      # 그 다음, 새 조 시작
                "article_no": int(art.group(1)),
                "article_title": art.group(2),
                "chapter": current_chapter,
                "text": para,                # 헤딩 문단으로 본문 시작 (주석 말고 para)
            }     


        else:
            # TODO-3) 항(項) 같은 일반 문단 → current 가 있으면 text 에 이어붙임
            #         (제1조 앞의 제목/시행일 줄은 current 가 None 이라 자동 무시됨)
            if current:                          # 조를 만드는 중이면
                current["text"] += "\n" + para   # 항을 본문에 이어붙임

    # 반복 끝: 마지막으로 만들던 조가 남아있으면 저장
    if current:
        chunks.append(current)
    return chunks


def _clause_units(body: list[str]) -> list[list[str]]:
    """본문 줄들을 항 단위 덩어리로 묶는다.

    항 번호가 없는 줄(표 행, 이어지는 문장 등)은 직전 항에 붙여서
    항이 중간에 끊기지 않게 한다.
    """
    units: list[list[str]] = []
    for line in body:
        if CLAUSE_RE.match(line) or not units:
            units.append([line])
        else:
            units[-1].append(line)
    return units


def split_long_articles(chunks: list[dict], max_chars: int = MAX_CHARS) -> list[dict]:
    """길이 상한을 넘는 조를 항 단위로 나눈다. 짧은 조는 그대로 둔다.

    항을 중간에 자르지 않고, 상한에 닿을 때까지 묶어 담는다(greedy packing).
    조각마다 조 헤딩을 복제하므로 (제N조) 출처 표기가 그대로 유지된다.

    항 하나가 단독으로 상한을 넘으면 더 쪼개지 않고 그대로 둔다 — 문장 중간을
    자르면 검색 품질이 더 나빠지기 때문. 이런 청크는 build_index.py 가 경고한다.
    """
    out: list[dict] = []

    for c in chunks:
        lines = c["text"].split("\n")
        heading, body = lines[0], lines[1:]

        if len(c["text"]) <= max_chars or not body:
            out.append({**c, "part": 1, "n_parts": 1})
            continue

        groups: list[list[str]] = []
        cur: list[str] = []
        for unit in _clause_units(body):
            block = "\n".join(unit)
            candidate = heading + "\n" + "\n".join(cur + [block])
            if cur and len(candidate) > max_chars:
                groups.append(cur)
                cur = []
            cur.append(block)
        if cur:
            groups.append(cur)

        for i, g in enumerate(groups, 1):
            out.append({**c,
                        "text": heading + "\n" + "\n".join(g),
                        "part": i,
                        "n_parts": len(groups)})

    return out