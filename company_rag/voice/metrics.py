"""CER(문자 오류율) 계산. 외부 의존성 없이 편집거리로 직접 구현한다.

계산 기준 (docs/stt-plan.md 결정 7):
  - 공백과 문장부호를 제거한 뒤 문자 단위로 센다.
    정답 "연차 며칠 쓸 수 있어?" 에 대해 STT 가 물음표를 안 붙였다고
    오류로 세면 STT 품질이 아니라 표기 습관을 재게 된다.
  - 숫자 정규화 '전' 원본 텍스트로 측정한다.
    STT 자체의 품질과 정규화 효과를 분리해서 보기 위해서다.

CER = 편집거리(삽입+삭제+치환) / 정답 문자 수
"""
import re
import unicodedata

_STRIP = re.compile(r"[\s" + re.escape("".join(
    c for c in map(chr, range(0x20, 0x3000))
    if unicodedata.category(c).startswith("P")
)) + r"]+")


def normalize_for_cer(s: str) -> str:
    """공백·문장부호 제거. 비교의 기준을 맞춘다."""
    return _STRIP.sub("", s)


def edit_distance(a: str, b: str) -> int:
    """레벤슈타인 거리 (삽입·삭제·치환 각 1)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1,          # 삭제
                           cur[j - 1] + 1,       # 삽입
                           prev[j - 1] + (ca != cb)))   # 치환
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    """문자 오류율. 정답이 비면 가설이 있을 때 1.0, 둘 다 비면 0.0."""
    r = normalize_for_cer(reference)
    h = normalize_for_cer(hypothesis)
    if not r:
        return 0.0 if not h else 1.0
    return edit_distance(r, h) / len(r)


def corpus_cer(pairs) -> float:
    """전체 편집거리 합 / 전체 정답 길이 합.

    문항별 CER 의 평균이 아니다. 짧은 문장의 오류 하나가 과대평가되는 걸 막는다.
    """
    dist = total = 0
    for ref, hyp in pairs:
        r = normalize_for_cer(ref)
        dist += edit_distance(r, normalize_for_cer(hyp))
        total += len(r)
    return dist / total if total else 0.0


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    # 손으로 센 값과 맞는지 먼저 검증한다
    cases = [
        # (정답, 가설, 기대 CER, 설명)
        ("연차 며칠 쓸 수 있어?", "연차 며칠 쓸 수 있어",
         0.0, "물음표만 차이 → 정규화로 제거되어 0"),
        ("연차 며칠 쓸 수 있어?", "연차며칠쓸수있어",
         0.0, "띄어쓰기만 차이 → 0"),
        # '제27조가뭐야' 는 7자다 (제·2·7·조·가·뭐·야). 숫자도 한 글자씩 센다
        ("제27조가 뭐야?", "제27조가 머야?",
         1 / 7, "'뭐'→'머' 치환 1 / 7자"),
        ("제27조가 뭐야?", "제27조가 뭐",
         1 / 7, "'야' 삭제 1 / 7자"),
        ("제27조가 뭐야?", "제2조가 뭐야?",
         1 / 7, "'7' 삭제 1 / 7자 — 번호 오인식도 CER 로는 1자일 뿐"),
        ("육아휴직", "육아휴직입니다",
         3 / 4, "3자 삽입 / 4자"),
        ("안녕", "", 1.0, "전부 누락"),
        ("안녕", "안녕", 0.0, "완전 일치"),
    ]
    ok = 0
    for ref, hyp, want, why in cases:
        got = cer(ref, hyp)
        good = abs(got - want) < 1e-9
        ok += good
        print(f"  {'✅' if good else '❌'} CER={got:.4f} (기대 {want:.4f})  {why}")
        if not good:
            print(f"      정답={normalize_for_cer(ref)!r} 가설={normalize_for_cer(hyp)!r}")
    print(f"\n{ok}/{len(cases)} 통과")

    print("\n[corpus_cer] 문항별 평균이 아니라 전체 합으로 계산")
    pairs = [("제27조가 뭐야?", "제27조가 머야?"), ("안녕", "안녕")]
    per_item = sum(cer(r, h) for r, h in pairs) / len(pairs)
    print(f"  문항별 평균 {per_item:.4f} / 전체 합 기준 {corpus_cer(pairs):.4f}")
