import argparse
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("stock_analyzer.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def run_daily_analysis(use_ai: bool = True):
    from src.data_collector import collect_all
    from src.analyzer import analyze, analyze_local_fallback
    from src.report_generator import generate_report, generate_telegram_summary, save_report
    from src.telegram_bot import send_message, send_document

    logger.info("=== Daily Analysis Started (AI=%s) ===", use_ai)
    start = datetime.now()

    try:
        logger.info("Step 1/4: Collecting market data...")
        market_data = collect_all()
        total_stocks = sum(len(v) for v in market_data["sectors"].values())
        logger.info("Collected %d stocks across %d sectors", total_stocks, len(market_data["sectors"]))

        if total_stocks == 0:
            raise RuntimeError("No stock data collected. Check network or KRX availability.")

        logger.info("Step 2/4: Analyzing...")
        if use_ai:
            try:
                analysis = analyze(market_data)
            except RuntimeError as e:
                logger.warning("AI analysis failed: %s — falling back to local", e)
                analysis = analyze_local_fallback(market_data)
        else:
            analysis = analyze_local_fallback(market_data)
        rec_count = len(analysis.get("recommendations", []))
        logger.info("Generated %d recommendations", rec_count)

        logger.info("Step 3/4: Generating report...")
        report = generate_report(market_data, analysis)
        filepath = save_report(report, market_data["date"])
        logger.info("Report saved: %s", filepath)

        logger.info("Step 4/4: Sending to Telegram...")
        summary = generate_telegram_summary(analysis)
        try:
            msg_ok = send_message(summary)
            doc_ok = send_document(filepath, caption=f"Daily Report {market_data['date']}")
            logger.info("Telegram: message=%s, document=%s", msg_ok, doc_ok)
        except Exception as te:
            logger.warning("Telegram send failed (report still saved): %s", te)

    except Exception as e:
        logger.exception("Daily analysis failed: %s", e)
        try:
            from src.telegram_bot import send_message as _sm
            _sm(f"<b>[ERROR]</b> {e}")
        except Exception:
            pass
        return

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("=== Completed in %.1f seconds ===", elapsed)


def main():
    parser = argparse.ArgumentParser(description="Stock Analyzer - Daily Market Analysis")
    parser.add_argument("--now", action="store_true", help="Run analysis immediately")
    parser.add_argument("--dry-run", action="store_true", help="Run without Claude API (local analysis only)")
    parser.add_argument("--schedule", action="store_true", help="Run on schedule (daily 10:00 KST)")
    parser.add_argument("--chat-id", action="store_true", help="Find your Telegram chat ID")
    args = parser.parse_args()

    if args.chat_id:
        from src.telegram_bot import get_chat_id
        get_chat_id()
        return

    if args.dry_run:
        run_daily_analysis(use_ai=False)
        return

    if args.now:
        run_daily_analysis(use_ai=True)
        return

    if args.schedule:
        from apscheduler.schedulers.blocking import BlockingScheduler
        scheduler = BlockingScheduler(timezone="Asia/Seoul")
        scheduler.add_job(run_daily_analysis, "cron", hour=10, minute=0)
        logger.info("Scheduler started. Next run: daily 10:00 KST. Press Ctrl+C to stop.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")
        return

    parser.print_help()


if __name__ == "__main__":
    sys.path.insert(0, ".")
    main()
