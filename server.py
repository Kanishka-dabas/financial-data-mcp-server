from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from data_fetcher import DataFetchError
from data_fetcher import compare_stocks as fetch_stock_comparison
from data_fetcher import get_company_overview as fetch_company_overview
from data_fetcher import get_financial_ratios as fetch_financial_ratios
from data_fetcher import get_historical_prices as fetch_historical_prices
from data_fetcher import get_income_statement as fetch_income_statement
from data_fetcher import get_stock_quote as fetch_stock_quote
from data_fetcher import search_ticker as fetch_ticker_matches

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("financial-data-server")



import os

auth_provider = StaticTokenVerifier(
    tokens={
        os.environ["MCP_AUTH_TOKEN"]: {"client_id": "investor-intel-agent"}
    }
)

mcp = FastMCP(
    name="financial-data-server",
    instructions=(
        "Provides stock market and company financial data tools backed by "
        "Yahoo Finance. Use search_ticker to resolve a company name to a "
        "ticker symbol before calling other tools if you don't already "
        "have the exact ticker."
    ),
    auth=auth_provider,
)

def _error(message: str) -> dict[str, Any]:
    """Uniform error shape returned to the client instead of raising."""
    return {"error": True, "message": message}


@mcp.tool
def search_ticker(company_name: str) -> dict[str, Any]:
    """Resolve a company name to its stock ticker symbol(s).

    Use this first when you have a company name (e.g. "Apple", "Tata
    Motors") rather than an exact ticker. Returns up to 5 candidate
    matches with symbol, name, exchange, and security type, ranked by
    relevance.

    Args:
        company_name: Full or partial company name, e.g. "Apple" or
            "Microsoft Corporation".

    Returns:
        {"matches": [{"symbol": str, "name": str, "exchange": str|None,
        "quote_type": str|None}, ...]} on success, or
        {"error": True, "message": str} if nothing matched.
    """
    logger.info(f"search_ticker called with company_name={company_name!r}")
    try:
        matches = fetch_ticker_matches(company_name)
        logger.info(f"search_ticker: found {len(matches)} match(es) for {company_name!r}")
        return {"matches": [asdict(m) for m in matches]}
    except DataFetchError as exc:
        logger.warning(f"search_ticker failed for {company_name!r}: {exc}")
        return _error(str(exc))
    except Exception as exc:
        logger.error(f"search_ticker unexpected error for {company_name!r}: {exc}")
        return _error(f"Unexpected error resolving '{company_name}': {exc}")


@mcp.tool
def get_stock_quote_tool(ticker: str) -> dict[str, Any]:
    """Get the current stock quote for a ticker symbol.

    Returns live/latest price, previous close, day's change (absolute
    and percent), day high/low, volume, and market state (e.g. REGULAR,
    CLOSED, PRE).

    Args:
        ticker: Exact stock ticker symbol, e.g. "AAPL", "MSFT",
            "RELIANCE.NS". If you only have a company name, call
            search_ticker first.

    Returns:
        A structured quote dict, or {"error": True, "message": str}
        if the ticker is invalid or data is unavailable.
    """
    logger.info(f"get_stock_quote_tool called with ticker={ticker!r}")
    try:
        result = fetch_stock_quote(ticker)
        logger.info(f"get_stock_quote_tool: success for {ticker!r}")
        return result
    except DataFetchError as exc:
        logger.warning(f"get_stock_quote_tool failed for {ticker!r}: {exc}")
        return _error(str(exc))
    except Exception as exc:
        logger.error(f"get_stock_quote_tool unexpected error for {ticker!r}: {exc}")
        return _error(f"Unexpected error fetching quote for '{ticker}': {exc}")


@mcp.tool
def get_company_overview_tool(ticker: str) -> dict[str, Any]:
    """Get a company profile overview for a ticker symbol.

    Returns sector, industry, country, market cap, employee count,
    website, and a short (truncated) business description.

    Args:
        ticker: Exact stock ticker symbol, e.g. "AAPL". If you only
            have a company name, call search_ticker first.

    Returns:
        A structured company overview dict, or {"error": True,
        "message": str} if the ticker is invalid or data is
        unavailable.
    """
    logger.info(f"get_company_overview_tool called with ticker={ticker!r}")
    try:
        result = fetch_company_overview(ticker)
        logger.info(f"get_company_overview_tool: success for {ticker!r}")
        return result
    except DataFetchError as exc:
        logger.warning(f"get_company_overview_tool failed for {ticker!r}: {exc}")
        return _error(str(exc))
    except Exception as exc:
        logger.error(f"get_company_overview_tool unexpected error for {ticker!r}: {exc}")
        return _error(f"Unexpected error fetching overview for '{ticker}': {exc}")
    

@mcp.tool
def get_financial_ratios_tool(ticker: str) -> dict[str, Any]:
    """Get key financial ratios for a ticker: P/E, EPS, ROE, debt-to-equity.

    Args:
        ticker: Exact stock ticker symbol, e.g. "AAPL".

    Returns:
        A dict with trailing/forward P/E, EPS, ROE, debt-to-equity,
        price-to-book, and profit margins, or {"error": True, "message": str}.
    """
    logger.info(f"get_financial_ratios_tool called with ticker={ticker!r}")
    try:
        result = fetch_financial_ratios(ticker)
        logger.info(f"get_financial_ratios_tool: success for {ticker!r}")
        return result
    except DataFetchError as exc:
        logger.warning(f"get_financial_ratios_tool failed for {ticker!r}: {exc}")
        return _error(str(exc))
    except Exception as exc:
        logger.error(f"get_financial_ratios_tool unexpected error for {ticker!r}: {exc}")
        return _error(f"Unexpected error fetching ratios for '{ticker}': {exc}")


@mcp.tool
def get_historical_prices_tool(ticker: str, period: str = "1mo") -> dict[str, Any]:
    """Get historical OHLC (Open/High/Low/Close) price data for a ticker.

    Args:
        ticker: Exact stock ticker symbol, e.g. "AAPL".
        period: One of "1d","5d","1mo","3mo","6mo","1y","2y","5y","10y","ytd","max".
            Defaults to "1mo".

    Returns:
        {"symbol": str, "period": str, "candles": [{"date","open","high",
        "low","close","volume"}, ...]}, or {"error": True, "message": str}.
    """
    logger.info(f"get_historical_prices_tool called with ticker={ticker!r}, period={period!r}")
    try:
        result = fetch_historical_prices(ticker, period)
        logger.info(f"get_historical_prices_tool: success for {ticker!r}")
        return result
    except DataFetchError as exc:
        logger.warning(f"get_historical_prices_tool failed for {ticker!r}: {exc}")
        return _error(str(exc))
    except Exception as exc:
        logger.error(f"get_historical_prices_tool unexpected error for {ticker!r}: {exc}")
        return _error(f"Unexpected error fetching history for '{ticker}': {exc}")


@mcp.tool
def get_income_statement_tool(ticker: str, quarterly: bool = False) -> dict[str, Any]:
    """Get revenue, net income, and margins from a company's income statement.

    Args:
        ticker: Exact stock ticker symbol, e.g. "AAPL".
        quarterly: If True, return quarterly statements instead of annual.
            Defaults to False (annual).

    Returns:
        {"symbol": str, "quarterly": bool, "periods": [...]}, or
        {"error": True, "message": str}.
    """
    logger.info(f"get_income_statement_tool called with ticker={ticker!r}, quarterly={quarterly}")
    try:
        result = fetch_income_statement(ticker, quarterly)
        logger.info(f"get_income_statement_tool: success for {ticker!r}")
        return result
    except DataFetchError as exc:
        logger.warning(f"get_income_statement_tool failed for {ticker!r}: {exc}")
        return _error(str(exc))
    except Exception as exc:
        logger.error(f"get_income_statement_tool unexpected error for {ticker!r}: {exc}")
        return _error(f"Unexpected error fetching income statement for '{ticker}': {exc}")
    

@mcp.tool
def compare_stocks_tool(tickers: list[str]) -> dict[str, Any]:
    """Compare key metrics (price, change%, P/E, ROE, debt-to-equity) across 2-3 tickers.

    Args:
        tickers: List of 2-3 exact ticker symbols, e.g. ["AAPL", "MSFT"].

    Returns:
        {"comparisons": [...], "failed": [{"ticker","error"}, ...]}, or
        {"error": True, "message": str} if the whole comparison failed.
    """
    logger.info(f"compare_stocks_tool called with tickers={tickers}")
    try:
        result = fetch_stock_comparison(tickers)
        logger.info(f"compare_stocks_tool: success for {tickers}")
        return result
    except DataFetchError as exc:
        logger.warning(f"compare_stocks_tool failed for {tickers}: {exc}")
        return _error(str(exc))
    except Exception as exc:
        logger.error(f"compare_stocks_tool unexpected error for {tickers}: {exc}")
        return _error(f"Unexpected error comparing {tickers}: {exc}")

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)