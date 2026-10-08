"""MCP 서버 자가 검증 — mcp_server.py 를 stdio 로 실제 띄워 도구를 호출한다.

서버를 import 해서 함수를 직접 부르면 MCP 계층(직렬화·스키마·전송)을 건너뛰게 된다.
그래서 진짜 클라이언트로 붙어서 list_tools / call_tool 을 거쳐 검증한다.
※ 임베더 필요 (Ollama 는 불필요 — 서버가 LLM 을 호출하지 않기 때문).
"""
import asyncio
import json
import os
import sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, BASE)

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def payload(result):
    """CallToolResult → dict"""
    for block in result.content:
        if getattr(block, "type", None) == "text":
            return json.loads(block.text)
    raise AssertionError("텍스트 응답이 없음")


async def main():
    env = dict(os.environ, PYTHONIOENCODING="utf-8", HF_HUB_OFFLINE="1")
    params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(BASE, "mcp_server.py")],
        cwd=BASE,
        env=env,
    )

    results = []

    def mark(ok, label, detail=""):
        print(f"  {'✅' if ok else '❌'} {label}")
        if detail:
            print(f"      {detail}")
        results.append(ok)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()

            print("[도구 노출]")
            tools = {t.name for t in (await s.list_tools()).tools}
            want = {"search_regulations", "get_article", "calculate_leave"}
            mark(want <= tools, f"도구 3종 등록", f"{sorted(tools)}")

            print("\n[검색 — 근거 있음]")
            r = payload(await s.call_tool("search_regulations",
                                          {"query": "연차 며칠 쓸 수 있어?"}))
            mark(r["has_evidence"] and r["articles"][0]["article_no"] == 12,
                 "제12조를 근거로 반환, has_evidence=true",
                 f"유사도 {r.get('top_similarity')} / 임계값 {r.get('threshold')}")

            print("\n[검색 — 근거 없음 → 가드가 응답에 실림]")
            r = payload(await s.call_tool("search_regulations",
                                          {"query": "스톡옵션 언제 받아?"}))
            mark(r["has_evidence"] is False and "instruction" in r,
                 "has_evidence=false + 호스트용 지시문 포함",
                 r.get("instruction", "")[:70] + "...")

            print("\n[검색 — 번호 질문은 정규식 조회로]")
            r = payload(await s.call_tool("search_regulations",
                                          {"query": "제27조가 뭐야?"}))
            mark(r["matched_by"] == "article_number"
                 and r["articles"][0].get("match") == "exact",
                 "matched_by=article_number, match=exact",
                 f"제{r['articles'][0]['article_no']}조 "
                 f"({r['articles'][0]['article_title']})")

            print("\n[조항 조회]")
            r = payload(await s.call_tool("get_article", {"article_no": 12}))
            mark(r["found"] and "연차" in r["parts"][0]["article_title"],
                 "제12조 조문 반환")
            r = payload(await s.call_tool("get_article", {"article_no": 99}))
            mark(r["found"] is False and "available_articles" in r,
                 "없는 조는 found=false + 범위 안내", r.get("available_articles"))

            print("\n[연차 계산 — 코드가 계산]")
            r = payload(await s.call_tool("calculate_leave",
                                          {"hire_date": "2025-12-01",
                                           "as_of": "2026-09-03"}))
            mark(r["ok"] and r["days"] == 9 and r["months"] == 9,
                 "2025-12-01 기준 2026-09-03 → 9개월 / 9일", r["basis"])
            r = payload(await s.call_tool("calculate_leave",
                                          {"hire_date": "작년 12월"}))
            mark(r["ok"] and r["days"] >= 0, "상대 표현('작년 12월')도 해석",
                 f"{r['hire_date']} → {r['days']}일")
            r = payload(await s.call_tool("calculate_leave",
                                          {"hire_date": "엉터리입력"}))
            mark(r["ok"] is False and "hint" in r, "해석 실패 시 ok=false + 힌트")

            print("\n[리소스]")
            uris = {str(x.uri) for x in (await s.list_resources()).resources}
            mark("regulation://articles" in uris, "조항 목록 리소스 노출", f"{sorted(uris)}")
            content = (await s.read_resource("regulation://articles")).contents[0]
            mark(content.text.count("\n") + 1 == 31, "목록에 31개 조항",
                 content.text.splitlines()[0])
            content = (await s.read_resource("regulation://article/12")).contents[0]
            mark("연차유급휴가" in content.text, "조항 원문 리소스 읽기")

    print(f"\n{sum(results)}/{len(results)} 통과 —",
          "✅ MCP 서버 완성" if all(results) else "⚠️ 위 ❌ 지점 확인")


if __name__ == "__main__":
    asyncio.run(main())
