"""로더 표 대응 검증 — v1 31조 유지 + v2 표 내용 복구 확인."""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
D = os.path.join(os.path.dirname(__file__), "..", "data")

def check():
    from src.loader import load_docx

    # v1: 기존 31조 여전히 온전한가 (하위호환)
    v1 = "\n".join(load_docx(os.path.join(D, "사규_취업규칙_샘플.docx")))
    arts = len({int(x) for x in re.findall(r"제(\d+)조", v1)})
    print(f"[v1 하위호환] 조 개수: {arts}/31", "✅" if arts == 31 else "❌")

    # v2: 표 안 내용이 이제 잡히나
    v2 = "\n".join(load_docx(os.path.join(D, "사규_취업규칙_샘플_v2.docx")))
    keys = ["식대", "교통보조비", "직책수당", "야간근로수당", "2,800,000", "200,000", "장기근속수당"]
    print("\n[v2 표 복구]")
    hit = 0
    for k in keys:
        ok = k in v2
        hit += ok
        print(f"  \"{k}\" → {'✅' if ok else '❌ 여전히 증발'}")
    print(f"\n{hit}/{len(keys)} 복구", "— ✅ 로더 표 대응 완성" if hit == len(keys) else "— ⚠️ TODO 확인")

if __name__ == "__main__":
    check()
