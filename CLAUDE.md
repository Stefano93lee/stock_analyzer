# Stock Analyzer - AI Equity Research Agent

## Project Overview
AI-powered stock analysis agent system using Claude sub-agents in orchestration pattern.
Analyzes stocks like a professional securities analyst with comprehensive research reports.

## Architecture
Orchestration pattern with 1 orchestrator + 5 specialized sub-agents:

```
orchestrator.md (main coordinator)
  ├── company-overview.md    (business model, products, management)
  ├── financial-analysis.md  (revenue, margins, valuation)
  ├── industry-analysis.md   (market size, competition, regulation)
  ├── momentum-analysis.md   (price action, technicals, catalysts)
  └── risk-analysis.md       (business/financial/market/regulatory risks)
```

## Agent Files Location
All agent definitions: `.claude/agents/`

## Usage
Invoke the orchestrator by asking Claude to analyze a stock:
- "AAPL 종목 분석해줘"
- "삼성전자 투자 분석 리포트 만들어줘"
- "AI 반도체 관련주 추천해줘"

## Output
Reports are saved to `reports/[TICKER]_analysis_[DATE].md`

## Daily Automation System (`src/`)
Automated daily analysis pipeline: data collection → Claude API analysis → report → Telegram.

```
src/
├── config.py            # API keys, watchlist (4 sectors, 17 stocks)
├── data_collector.py    # pykrx로 시세/기술적지표/수급 수집
├── analyzer.py          # Claude API 경량 분석 (단일 호출, ~10K tokens)
├── report_generator.py  # 마크다운 리포트 + 텔레그램 요약 생성
├── telegram_bot.py      # 텔레그램 메시지/파일 전송
└── main.py              # 진입점 (--now | --schedule | --chat-id)
```

### Quick Start
```bash
pip install -r requirements.txt
cp .env.example .env     # API 키 설정
python -m src.main --now  # 즉시 실행
python -m src.main --schedule  # 매일 10시 자동 실행
```

## Disclaimer
All analysis is AI-generated for informational purposes only. Not financial advice.
