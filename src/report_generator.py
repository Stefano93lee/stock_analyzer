import os
from datetime import datetime

from src.config import REPORT_DIR


def generate_report(market_data: dict, analysis: dict) -> str:
    date_str = market_data["date"]
    today = datetime.now().strftime("%Y-%m-%d")

    recs = analysis.get("recommendations", [])

    lines = [
        f"# Daily Market Analysis Report",
        f"**기준일**: {date_str} | **생성**: {today} 10:00 KST\n",
        "---\n",
        "## 1. 시장 종합",
        analysis.get("market_summary", ""),
        "\n## 2. 섹터별 동향\n",
    ]

    for sector, brief in analysis.get("sector_briefs", {}).items():
        lines.append(f"### {sector}")
        lines.append(brief)

        sector_stocks = market_data["sectors"].get(sector, [])
        if sector_stocks:
            lines.append("\n| 종목 | 현재가 | 등락률 | RSI | PER |")
            lines.append("|---|---|---|---|---|")
            for s in sector_stocks:
                per_str = str(s["per"]) if s.get("per") else "-"
                lines.append(
                    f"| {s['name']} | {s['current_price']:,}원 "
                    f"| {s['change_pct']:+.1f}% | {s['rsi']} | {per_str} |"
                )
        lines.append("")

    lines.append("---\n")
    lines.append("## 3. 매수 추천 TOP 5\n")

    lines.append("| 순위 | 종목 | 섹터 | 현재가 | 상한가 전망 | 상승여력 | 도달 시점 | 투자의견 |")
    lines.append("|------|------|------|--------|-----------|---------|----------|---------|")
    for r in recs:
        lines.append(
            f"| {r['rank']} | **{r['name']}** | {r['sector']} "
            f"| {r['current_price']:,}원 | **{r['target_price']:,}원** "
            f"| +{r['upside_pct']:.1f}% | {r['target_date']} | {r['rating']} |"
        )

    lines.append("")

    for r in recs:
        lines.append(f"### {r['rank']}. {r['name']} ({r['ticker']}) - {r['rating']}")
        lines.append(f"- **현재가**: {r['current_price']:,}원")
        lines.append(f"- **상한가 전망**: {r['target_price']:,}원 (+{r['upside_pct']:.1f}%)")
        lines.append(f"- **도달 시점**: {r['target_date']}")
        lines.append(f"- **추천 근거**: {r['rationale']}")
        lines.append(f"- **리스크**: {r['risk']}")
        lines.append("")

    lines.append("---\n")
    lines.append(
        "*Disclaimer: 본 분석은 AI가 생성한 것으로 투자 자문이 아닙니다. "
        "투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.*"
    )

    return "\n".join(lines)


def generate_telegram_summary(analysis: dict) -> str:
    recs = analysis.get("recommendations", [])
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"<b>[Daily Stock Pick] {today}</b>\n",
        f"<b>시장 요약</b>: {analysis.get('market_summary', '')}\n",
    ]

    for sector, brief in analysis.get("sector_briefs", {}).items():
        lines.append(f"<b>{sector}</b>: {brief}")
    lines.append("")

    lines.append("<b>== 매수 추천 TOP 5 ==</b>\n")
    for r in recs:
        lines.append(
            f"<b>{r['rank']}. {r['name']}</b> ({r['sector']})\n"
            f"   현재가: {r['current_price']:,}원\n"
            f"   상한가: <b>{r['target_price']:,}원</b> (+{r['upside_pct']:.1f}%)\n"
            f"   도달시점: {r['target_date']}\n"
            f"   의견: {r['rating']}\n"
            f"   근거: {r['rationale']}\n"
        )

    lines.append("<i>AI 생성 분석, 투자 자문 아님</i>")
    return "\n".join(lines)


def _md_to_html(md_text: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    body = md_text

    import re
    body = re.sub(r"^### (.+)$", r"<h3>\1</h3>", body, flags=re.MULTILINE)
    body = re.sub(r"^## (.+)$", r"<h2>\1</h2>", body, flags=re.MULTILINE)
    body = re.sub(r"^# (.+)$", r"<h1>\1</h1>", body, flags=re.MULTILINE)
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)
    body = re.sub(r"\*(.+?)\*", r"<i>\1</i>", body)
    body = re.sub(r"^- (.+)$", r"<li>\1</li>", body, flags=re.MULTILINE)
    body = re.sub(r"^---+$", "<hr>", body, flags=re.MULTILINE)

    table_lines = body.split("\n")
    result = []
    in_table = False
    for line in table_lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-| ") for c in cells):
                continue
            if not in_table:
                result.append("<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;width:100%;font-size:14px;'>")
                result.append("<tr>" + "".join(f"<th style='background:#f0f0f0;'>{c}</th>" for c in cells) + "</tr>")
                in_table = True
            else:
                result.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        else:
            if in_table:
                result.append("</table><br>")
                in_table = False
            if stripped:
                result.append(line)
            else:
                result.append("<br>")
    if in_table:
        result.append("</table>")

    body_html = "\n".join(result)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Stock Report {today}</title>
<style>
body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }}
h1 {{ color: #1a237e; border-bottom: 2px solid #1a237e; padding-bottom: 8px; }}
h2 {{ color: #283593; margin-top: 24px; }}
h3 {{ color: #3949ab; }}
b {{ color: #1a237e; }}
li {{ margin: 4px 0; }}
hr {{ border: 1px solid #ddd; margin: 20px 0; }}
</style>
</head>
<body>
{body_html}
</body>
</html>"""


def save_report(report_text: str, date_str: str) -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)

    md_path = os.path.join(REPORT_DIR, f"daily_picks_{date_str}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    html_path = os.path.join(REPORT_DIR, f"daily_picks_{date_str}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_md_to_html(report_text))

    return html_path
