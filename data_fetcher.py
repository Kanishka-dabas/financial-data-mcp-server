from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import yfinance as yf


class DataFetchError(Exception):
    """Raised for any failure resolving or fetching financial data."""


@dataclass
class TickerMatch:
    symbol : str
    name : str
    exchange : str | None = None
    quote_type : str | None = None


def _get_ticker(symbol : str)-> yf.Ticker:
    symbol = (symbol or "").strip().upper()
    if not symbol:
        raise DataFetchError("Ticker symbol must not be empty.")
    return yf.Ticker(symbol)


def _validate_info(symbol : str , info : dict[str,Any])->None:
    """yfinance doesn't raise on an unknown ticker - it just returns a
    near-empty info dict. Treat that as the invalid-ticker case."""
    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None and info.get("previousClose") is None and info.get("shortName") is None:
        raise DataFetchError(f"No data found for ticker '{symbol}'. It may be invalid or delisted.")


def search_ticker(company_name:str , max_resuts : int = 5)-> list[TickerMatch]:
    """Resolve a company name to candidate ticker symbols."""  
    company_name = (company_name or "").strip()
    if not company_name:
        raise DataFetchError("company_name must not be empty.")

    try :
        result = yf.Search(company_name , max_results=max_resuts)
        quotes = result.quotes or []
    except Exception as e:
        raise DataFetchError(f"Search failed for '{company_name}': {e}")  

    if not quotes:
        raise DataFetchError(f"No ticker matches found for '{company_name}'.")

    matches = []
    for q in quotes:
        symbol = q.get("symbol")
        if not symbol :
            continue
        matches.append(
            TickerMatch(
                symbol=symbol,
                name=q.get("shortname") or q.get("longname") or symbol,
                exchange=q.get("exchange"),
                quote_type=q.get("quoteType")
            )
        )

        if not matches :
            raise DataFetchError(f"No valid ticker matches found for '{company_name}'.")

    return matches


def get_stock_quote(ticker: str) -> dict[str, Any]:
    """Current price, day change %, and volume for a ticker."""
    symbol = (ticker or "").strip().upper()
    t = _get_ticker(symbol)

    try:
        info = t.info
    except Exception as exc:
        raise DataFetchError(f"Failed to fetch quote for '{symbol}': {exc}") from exc

    _validate_info(symbol, info)

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    prev_close = info.get("previousClose")
    if price is None:
        raise DataFetchError(f"No live price available for '{symbol}'.")

    change = None
    change_pct = None
    if prev_close:
        change = round(price - prev_close, 4)
        change_pct = round((change / prev_close) * 100, 4)

    return {
        "symbol": symbol,
        "price": price,
        "currency": info.get("currency"),
        "previous_close": prev_close,
        "change": change,
        "change_percent": change_pct,
        "day_high": info.get("dayHigh"),
        "day_low": info.get("dayLow"),
        "volume": info.get("volume") or info.get("regularMarketVolume"),
        "market_state": info.get("marketState"),
        "as_of": int(time.time()),
    }


def get_company_overview(ticker: str) -> dict[str, Any]:
    """Sector, industry, market cap, and a short description for a ticker."""
    symbol = (ticker or "").strip().upper()
    t = _get_ticker(symbol)

    try:
        info = t.info
    except Exception as exc:
        raise DataFetchError(f"Failed to fetch overview for '{symbol}': {exc}") from exc

    _validate_info(symbol, info)

    summary = info.get("longBusinessSummary") or ""
    short_description = (summary[:400] + "...") if len(summary) > 400 else summary

    return {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "country": info.get("country"),
        "market_cap": info.get("marketCap"),
        "employees": info.get("fullTimeEmployees"),
        "website": info.get("website"),
        "short_description": short_description,
    }


def get_financial_ratios(ticker: str) -> dict[str, Any]:
    """P/E, EPS, ROE, and debt-to-equity for a ticker."""
    symbol = (ticker or "").strip().upper()
    t = _get_ticker(symbol)

    try:
        info = t.info
    except Exception as exc:
        raise DataFetchError(f"Failed to fetch ratios for '{symbol}': {exc}") from exc

    _validate_info(symbol, info)

    return {
        "symbol": symbol,
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "trailing_eps": info.get("trailingEps"),
        "forward_eps": info.get("forwardEps"),
        "return_on_equity": info.get("returnOnEquity"),
        "debt_to_equity": info.get("debtToEquity"),
        "price_to_book": info.get("priceToBook"),
        "profit_margins": info.get("profitMargins"),
    }


def get_historical_prices(ticker: str, period: str = "1mo") -> dict[str, Any]:
    """Historical OHLC (Open, High, Low, Close) data for a ticker.

    period: one of "1d","5d","1mo","3mo","6mo","1y","2y","5y","10y","ytd","max"
    """
    symbol = (ticker or "").strip().upper()
    t = _get_ticker(symbol)

    try:
        hist = t.history(period=period)
    except Exception as exc:
        raise DataFetchError(f"Failed to fetch history for '{symbol}': {exc}") from exc

    if hist.empty:
        raise DataFetchError(f"No historical data found for '{symbol}' with period '{period}'.")

    records = []
    for date, row in hist.iterrows():
        records.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(row["Open"], 4),
            "high": round(row["High"], 4),
            "low": round(row["Low"], 4),
            "close": round(row["Close"], 4),
            "volume": int(row["Volume"]),
        })

    return {"symbol": symbol, "period": period, "candles": records}


def get_income_statement(ticker: str, quarterly: bool = False) -> dict[str, Any]:
    """Revenue, net income, and margins from the income statement.

    quarterly: if True, return quarterly statements; otherwise annual.
    """
    symbol = (ticker or "").strip().upper()
    t = _get_ticker(symbol)

    try:
        stmt = t.quarterly_financials if quarterly else t.financials
    except Exception as exc:
        raise DataFetchError(f"Failed to fetch income statement for '{symbol}': {exc}") from exc

    if stmt is None or stmt.empty:
        raise DataFetchError(f"No income statement data found for '{symbol}'.")

    periods = []
    for col in stmt.columns:
        period_data = {"period_end": col.strftime("%Y-%m-%d")}
        for row_name in ["Total Revenue", "Net Income", "Gross Profit", "Operating Income"]:
            if row_name in stmt.index:
                value = stmt.loc[row_name, col]
                period_data[row_name.lower().replace(" ", "_")] = (
                    None if value != value else float(value)  # NaN check
                )
        periods.append(period_data)

    return {"symbol": symbol, "quarterly": quarterly, "periods": periods}


def compare_stocks(tickers: list[str]) -> dict[str, Any]:
    """Side-by-side comparison of key metrics for 2-3 tickers."""
    if not tickers or len(tickers) < 2:
        raise DataFetchError("Provide at least 2 tickers to compare.")
    if len(tickers) > 3:
        raise DataFetchError("Provide at most 3 tickers to compare.")

    comparisons = []
    errors = []
    for symbol in tickers:
        try:
            quote = get_stock_quote(symbol)
            ratios = get_financial_ratios(symbol)
            comparisons.append({
                "symbol": quote["symbol"],
                "price": quote["price"],
                "change_percent": quote["change_percent"],
                "trailing_pe": ratios["trailing_pe"],
                "return_on_equity": ratios["return_on_equity"],
                "debt_to_equity": ratios["debt_to_equity"],
            })
        except DataFetchError as exc:
            errors.append({"ticker": symbol, "error": str(exc)})

    if not comparisons:
        raise DataFetchError(f"Could not fetch data for any of the given tickers: {tickers}")

    return {"comparisons": comparisons, "failed": errors}


