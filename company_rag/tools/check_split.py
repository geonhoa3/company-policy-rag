"""항 분할 자가 검증 — src/chunker.py의 split_long_articles() 채점. (모델 불필요)

실제 샘플 문서는 최장 240자라 분할 경로를 타지 않는다.
→ 합성 조항으로 경로를 강제 실행하고, 실제 문서는 '분할되지 않음'을 회귀 검증한다.
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
DOCX = os.path.join(os.path.dirname(__file__), "..", "data", "사규_취업규칙_샘플.docx")


def check():
    from src.loader import load_docx
    from src.chunker import chunk_by_article, split_long_articles, MAX_CHARS, CLAUSE_RE

    results = []

    # 1) 회귀: 실제 문서는 짧으므로 분할되면 안 된다
    arts = chunk_by_article(load_docx(DOCX))
    real = split_long_articles(arts)
    no_split = len(real) == len(arts) == 31 and all(c["n_parts"] == 1 for c in real)
    print(f"[회귀] 실제 문서 {len(arts)}조 → {len(real)}청크, 분할 0건",
          "✅" if no_split else "❌")
    results.append(no_split)

    # 2) 합성 긴 조 — 12개 항, 각 ~120자
    clauses = [f"{i}. " + "가" * 90 + " 경우에는 그러하지 아니하다." for i in range(1, 13)]
    long_art = {
        "article_no": 99, "article_title": "초장문조항",
        "chapter": "제9장 시험", "text": "제99조 (초장문조항)\n" + "\n".join(clauses),
    }
    parts = split_long_articles([long_art])
    print(f"\n[분할] {len(long_art['text'])}자 조항 → {len(parts)}조각 (상한 {MAX_CHARS}자)")

    split_ok = len(parts) > 1
    print("  여러 조각으로 나뉨:", "✅" if split_ok else "❌")
    results.append(split_ok)

    within = [len(p["text"]) for p in parts]
    size_ok = all(n <= MAX_CHARS for n in within)
    print(f"  모든 조각이 상한 이내 {within}:", "✅" if size_ok else "❌")
    results.append(size_ok)

    head_ok = all(p["text"].startswith("제99조 (초장문조항)") for p in parts)
    print("  조각마다 조 헤딩 복제 (출처 표기 유지):", "✅" if head_ok else "❌")
    results.append(head_ok)

    meta_ok = ([p["part"] for p in parts] == list(range(1, len(parts) + 1))
               and all(p["n_parts"] == len(parts) for p in parts)
               and all(p["article_no"] == 99 and p["chapter"] == "제9장 시험" for p in parts))
    print("  part/n_parts·조 메타데이터 유지:", "✅" if meta_ok else "❌")
    results.append(meta_ok)

    # 3) 항이 유실되거나 중간에 끊기지 않았나
    seen = []
    for p in parts:
        for line in p["text"].split("\n")[1:]:
            m = CLAUSE_RE.match(line)
            if m:
                seen.append(int(m.group(1)))
    intact = seen == list(range(1, 13))
    print(f"  항 1~12 전부 보존·순서 유지 (발견 {len(seen)}개):", "✅" if intact else "❌")
    results.append(intact)

    joined = "".join(re.sub(r"^제99조 \(초장문조항\)\n", "", p["text"]) for p in parts)
    lossless = joined.replace("\n", "") == "".join(clauses).replace("\n", "")
    print("  본문 무손실 (조각 합치면 원문과 동일):", "✅" if lossless else "❌")
    results.append(lossless)

    # 4) 항 하나가 단독으로 상한 초과 → 더 못 쪼개고 그대로 둔다 (경고 대상)
    huge = {"article_no": 98, "article_title": "단일항초과", "chapter": "부칙",
            "text": "제98조 (단일항초과)\n1. " + "나" * 1500}
    hp = split_long_articles([huge])
    huge_ok = len(hp) == 1 and len(hp[0]["text"]) > MAX_CHARS
    print(f"\n[한계] 단일 항 {len(huge['text'])}자 → {len(hp)}조각, 문장 중간 안 자름:",
          "✅" if huge_ok else "❌")
    results.append(huge_ok)

    print(f"\n{sum(results)}/{len(results)} 통과 —",
          "✅ 항 분할 완성" if all(results) else "⚠️ 위 ❌ 지점 확인")


if __name__ == "__main__":
    check()
