import json
import logging

import anthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 증권사 시니어 애널리스트입니다. 제공된 시장 데이터를 분석하여 매수 추천 5종목을 선정하세요.

규칙:
- 4개 섹터(반도체, 에너지, 배터리, 우주항공) 전체에서 가장 유망한 5종목 선정
- 기술적 지표(RSI, 이동평균), 밸류에이션(PER, PBR), 수급(외국인/기관), 모멘텀을 종합 판단
- 상한가(목표가)는 현실적 근거 기반으로 제시
- 한국어로 작성

반드시 아래 JSON 형식으로만 응답하세요:
{
  "market_summary": "오늘 시장 종합 요약 (3문장 이내)",
  "sector_briefs": {
    "반도체": "핵심 동향 1~2문장",
    "에너지": "핵심 동향 1~2문장",
    "배터리": "핵심 동향 1~2문장",
    "우주항공": "핵심 동향 1~2문장"
  },
  "recommendations": [
    {
      "rank": 1,
      "ticker": "005930",
      "name": "삼성전자",
      "sector": "반도체",
      "current_price": 360000,
      "target_price": 500000,
      "target_date": "2026년 Q4",
      "upside_pct": 38.9,
      "rating": "Strong Buy",
      "rationale": "추천 근거 (2~3문장, 구체적 수치 포함)",
      "risk": "핵심 리스크 1문장"
    }
  ]
}"""


def _format_market_data(market_data: dict) -> str:
    lines = [f"## 기준일: {market_data['date']}\n"]

    for sector, stocks in market_data["sectors"].items():
        lines.append(f"### {sector}")
        lines.append("| 종목 | 현재가 | 등락률 | 거래량 | MA20 | MA50 | MA200 | RSI | PER | PBR | 외국인순매수 | 기관순매수 | 52주고가 | 52주저가 |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for s in stocks:
            def v(key, fmt=","):
                val = s.get(key)
                if val is None:
                    return "-"
                if fmt == ",":
                    return f"{val:,}"
                if fmt == ",.0f":
                    return f"{val:,.0f}"
                return str(val)

            row = (
                f"| {s['name']}({s['ticker']}) "
                f"| {v('current_price')} "
                f"| {s['change_pct']:+.1f}% "
                f"| {v('volume')} "
                f"| {v('ma20', ',.0f')} "
                f"| {v('ma50', ',.0f')} "
                f"| {v('ma200', ',.0f')} "
                f"| {s['rsi']} "
                f"| {v('per')} "
                f"| {v('pbr')} "
                f"| {v('foreign_net')} "
                f"| {v('inst_net')} "
                f"| {v('high_52w')} "
                f"| {v('low_52w')} |"
            )
            lines.append(row)
        lines.append("")

    return "\n".join(lines)


def analyze(market_data: dict) -> dict:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY가 .env에 설정되지 않았습니다.")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    user_prompt = _format_market_data(market_data)
    user_prompt += "\n위 데이터를 분석하여 매수 추천 5종목을 JSON으로 응답하세요."

    logger.info("Calling Claude API (%s)...", CLAUDE_MODEL)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.BadRequestError as e:
        if "credit balance" in str(e):
            raise RuntimeError(
                "Anthropic API 크레딧 잔액 부족! "
                "https://console.anthropic.com 에서 크레딧을 충전하세요."
            ) from e
        raise

    raw = response.content[0].text
    logger.info(
        "API usage: input=%d, output=%d tokens, stop=%s",
        response.usage.input_tokens,
        response.usage.output_tokens,
        response.stop_reason,
    )

    if response.stop_reason == "max_tokens":
        logger.warning("Response truncated (max_tokens reached). Attempting JSON repair.")
        raw = _repair_truncated_json(raw)

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("Claude response does not contain valid JSON")

    result = json.loads(raw[start:end])
    return result


def _repair_truncated_json(raw: str) -> str:
    start = raw.find("{")
    if start == -1:
        return raw

    text = raw[start:]
    open_braces = text.count("{") - text.count("}")
    open_brackets = text.count("[") - text.count("]")

    if text.rstrip().endswith(","):
        text = text.rstrip().rstrip(",")

    text += "]" * open_brackets
    text += "}" * open_braces

    return text


def analyze_local_fallback(market_data: dict) -> dict:
    """Claude API 없이 수집된 데이터만으로 기본 추천을 생성합니다."""
    all_stocks = []
    for sector, stocks in market_data["sectors"].items():
        for s in stocks:
            s["sector"] = sector
            all_stocks.append(s)

    def score(s):
        pts = 0
        if s.get("change_pct", 0) > 0:
            pts += 1
        rsi = s.get("rsi", 50)
        if 30 < rsi < 70:
            pts += 1
        if rsi <= 30:
            pts += 2
        ma20 = s.get("ma20")
        if ma20 and s["current_price"] > ma20:
            pts += 1
        ma50 = s.get("ma50")
        if ma50 and s["current_price"] > ma50:
            pts += 1
        if s.get("foreign_net", 0) > 0:
            pts += 1
        per = s.get("per")
        if per and 0 < per < 15:
            pts += 1
        return pts

    ranked = sorted(all_stocks, key=score, reverse=True)[:5]

    recs = []
    for i, s in enumerate(ranked, 1):
        high = s.get("high_52w", s["current_price"])
        target = max(high, int(s["current_price"] * 1.2))
        upside = round((target - s["current_price"]) / s["current_price"] * 100, 1)
        recs.append({
            "rank": i,
            "ticker": s["ticker"],
            "name": s["name"],
            "sector": s["sector"],
            "current_price": s["current_price"],
            "target_price": target,
            "target_date": "6개월 내",
            "upside_pct": upside,
            "rating": "Buy",
            "rationale": f"RSI {s['rsi']}, 등락률 {s['change_pct']:+.1f}%, 외국인 순매수 {s.get('foreign_net', 0):,}주",
            "risk": "로컬 분석(AI 미사용)으로 정확도 제한적",
        })

    sector_briefs = {}
    for sector, stocks in market_data["sectors"].items():
        if stocks:
            avg_chg = sum(s["change_pct"] for s in stocks) / len(stocks)
            sector_briefs[sector] = f"평균 등락률 {avg_chg:+.1f}%"
        else:
            sector_briefs[sector] = "데이터 없음"

    return {
        "market_summary": f"[로컬 분석] 기준일 {market_data['date']}, AI 분석 없이 기술적 지표 기반으로 선정",
        "sector_briefs": sector_briefs,
        "recommendations": recs,
    }
