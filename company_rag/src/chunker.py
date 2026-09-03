# src/chunker.py
import re

# 패턴 두 개 (이게 경계 감지의 핵심)
ARTICLE_RE = re.compile(r"^제(\d+)조\s*\((.+?)\)")   # 제5조 (수습기간)
CHAPTER_RE = re.compile(r"^(제\d+장.*|부칙)")          # 제2장 채용... / 부칙

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