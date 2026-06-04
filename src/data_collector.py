from datetime import datetime, timedelta
import logging
import os

import pandas as pd

from src.config import WATCHLIST

logger = logging.getLogger(__name__)

OHLCV_DAYS = 250


def _get_stock_module():
    os.environ.setdefault("KRX_ID", "")
    os.environ.setdefault("KRX_PW", "")
    from pykrx import stock
    return stock


def _latest_trading_date() -> str:
    stock = _get_stock_module()
    today = datetime.now()
    for offset in range(7):
        candidate = (today - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            data = stock.get_market_ohlcv(candidate, candidate, "005930")
            if not data.empty:
                return candidate
        except Exception:
            continue
    return today.strftime("%Y%m%d")


def _calc_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(val, 1) if pd.notna(val) else 50.0


def _collect_single_stock(stock_mod, ticker: str, name: str, ref_date: str) -> dict | None:
    try:
        end_dt = datetime.strptime(ref_date, "%Y%m%d")
        start_dt = end_dt - timedelta(days=OHLCV_DAYS)
        start_str = start_dt.strftime("%Y%m%d")

        ohlcv = stock_mod.get_market_ohlcv(start_str, ref_date, ticker)
        if ohlcv.empty or len(ohlcv) < 5:
            return None

        closes = ohlcv["종가"]
        current = int(closes.iloc[-1])
        prev = int(closes.iloc[-2]) if len(closes) > 1 else current
        change_pct = round((current - prev) / prev * 100, 2) if prev else 0

        high_52w = int(closes.tail(min(len(closes), 250)).max())
        low_52w = int(closes.tail(min(len(closes), 250)).min())

        ma20 = round(closes.rolling(20).mean().iloc[-1]) if len(closes) >= 20 else None
        ma50 = round(closes.rolling(50).mean().iloc[-1]) if len(closes) >= 50 else None
        ma200 = round(closes.rolling(200).mean().iloc[-1]) if len(closes) >= 200 else None

        rsi = _calc_rsi(closes)
        volume = int(ohlcv["거래량"].iloc[-1])
        vol_avg20 = int(ohlcv["거래량"].tail(20).mean()) if len(ohlcv) >= 20 else volume

        per = None
        pbr = None
        try:
            fund = stock_mod.get_market_fundamental(ref_date, ref_date, ticker)
            if not fund.empty:
                per_val = fund["PER"].iloc[0]
                pbr_val = fund["PBR"].iloc[0]
                per = round(float(per_val), 1) if per_val else None
                pbr = round(float(pbr_val), 2) if pbr_val else None
        except Exception as e:
            logger.debug("Fundamental fetch failed for %s: %s", ticker, e)

        market_cap = None
        try:
            cap_df = stock_mod.get_market_cap(ref_date, ref_date, ticker)
            if not cap_df.empty:
                market_cap = int(cap_df["시가총액"].iloc[0])
        except Exception as e:
            logger.debug("Market cap fetch failed for %s: %s", ticker, e)

        foreign_net = 0
        inst_net = 0
        try:
            inv_start = (end_dt - timedelta(days=5)).strftime("%Y%m%d")
            inv = stock_mod.get_market_trading_volume_by_investor(inv_start, ref_date, ticker)
            if not inv.empty:
                if "외국인합계" in inv.index:
                    foreign_net = int(inv.loc["외국인합계", "순매수"])
                if "기관합계" in inv.index:
                    inst_net = int(inv.loc["기관합계", "순매수"])
        except Exception as e:
            logger.debug("Investor data skipped for %s: %s", ticker, e)

        return {
            "ticker": ticker,
            "name": name,
            "current_price": current,
            "change_pct": change_pct,
            "volume": volume,
            "vol_avg20": vol_avg20,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "ma20": ma20,
            "ma50": ma50,
            "ma200": ma200,
            "rsi": rsi,
            "per": per,
            "pbr": pbr,
            "market_cap_billion": round(market_cap / 1_0000_0000, 0) if market_cap else None,
            "foreign_net": foreign_net,
            "inst_net": inst_net,
        }
    except Exception as e:
        logger.warning("Failed to collect %s(%s): %s", name, ticker, e)
        return None


def collect_all() -> dict:
    stock_mod = _get_stock_module()
    ref_date = _latest_trading_date()
    logger.info("Collecting data for ref_date=%s", ref_date)

    result = {"date": ref_date, "sectors": {}}

    for sector, tickers in WATCHLIST.items():
        sector_data = []
        for ticker, name in tickers.items():
            data = _collect_single_stock(stock_mod, ticker, name, ref_date)
            if data:
                sector_data.append(data)
                logger.info("  Collected: %s %s = %s", ticker, name, data["current_price"])
        result["sectors"][sector] = sector_data

    return result
