# Financial Data MCP Server

A remote MCP (Model Context Protocol) server that exposes stock market and
company financial data as tools, callable by any MCP client (Claude Desktop,
Claude.ai, custom agents). Built to demonstrate MCP protocol design, remote
HTTP transport, cloud deployment, and production concerns like caching and
structured logging.

**Live server:** `https://financial-data-server.fastmcp.app/mcp`
(authenticated — see [Authentication](#authentication) below)

## Tech Stack

- **Language:** Python 3.12, managed with [uv](https://docs.astral.sh/uv/)
- **Framework:** [FastMCP](https://gofastmcp.com) 4.0.3
- **Data source:** [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance)
- **Deployment:** FastMCP Cloud 
- **Transport:** `streamable-http` 

## Architecture

The codebase is split into two layers with a single responsibility each:

- **`data_fetcher.py`** — all yfinance calls, isolated from any MCP concern.
  Raises a single `DataFetchError` for any failure (invalid ticker, network
  issue, empty data) so the tool layer has one exception type to handle.
  Has zero dependency on FastMCP, so it can be reused standalone in another
  project without pulling in MCP at all.
- **`server.py`** — the MCP tool layer only: schemas (inferred from type
  hints), docstrings (what the client LLM reads to decide when to call a
  tool), and translating `DataFetchError` into a clean
  `{"error": true, "message": ...}` dict instead of letting a raw traceback
  reach the client.

This separation means the data-fetching logic could later be lifted
straight into a different project (e.g. a RAG platform) that also needs
stock data, with no MCP-specific code coming along for the ride.

## Tools

| Tool | Description |
|---|---|
| `search_ticker` | Resolve a company name to candidate ticker symbols |
| `get_stock_quote_tool` | Current price, day change %, volume |
| `get_company_overview_tool` | Sector, industry, market cap, short description |
| `get_financial_ratios_tool` | P/E, EPS, ROE, debt-to-equity |
| `get_historical_prices_tool` | Historical OHLC data for a given period |
| `get_income_statement_tool` | Revenue, net income, margins (annual/quarterly) |
| `compare_stocks_tool` | Side-by-side comparison of 2-3 tickers |

Every tool validates its input and never lets a raw exception reach the
client — failures come back as a structured `{"error": true, "message": str}`
so an LLM client can reason about what went wrong.

## Local Setup

```bash
git clone https://github.com/Kanishka-dabas/financial-data-mcp-server.git
cd financial-data-mcp-server
uv sync
```

### Run locally with MCP Inspector

```bash
uv run fastmcp dev inspector server.py
```

Opens a browser UI to call each tool directly and inspect its schema/response.

## Deployment

Deployed on [FastMCP Cloud](https://fastmcp.cloud), which builds the
repo on every push to `main` and serves it over HTTPS with `streamable-http`
transport.

```python
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
```

FastMCP Cloud manages host/port binding at the platform level, so no
hardcoded host/port is needed in the entrypoint.

## Authentication

Access to the deployed server requires authentication via FastMCP Cloud's
built-in (Horizon) auth layer — a client must log in and be a member of
the hosting organization to connect.

## Reliability & Performance

- **Caching:** An in-memory TTL cache (60s) sits in front of the Yahoo
  Finance `.info` call, since `get_stock_quote`, `get_company_overview`,
  and `get_financial_ratios` all read from the same underlying data.
  Measured ~2000x speedup on a cache hit (2s → <1ms) and reduces load
  against Yahoo's unofficial, rate-limit-sensitive endpoint.
  *(Note: in-memory only — resets on restart and isn't shared across
  multiple replicas. A multi-instance production deployment would use a
  shared cache like Redis.)*
- **Structured logging:** Every tool logs on call, success, and failure,
  with `INFO` for normal operation, `WARNING` for expected failures (e.g.
  invalid ticker), and `ERROR` for unexpected exceptions — keeping
  monitoring noise separate from real bugs.

## Known Limitations

- The in-memory cache is per-instance and non-persistent.
- Authentication is enforced by FastMCP Cloud's platform-level auth rather
  than a custom OAuth provider wired into the server code.

## What This Project Demonstrates

- Designing MCP tools with clear schemas and LLM-readable docstrings
- Separating protocol-layer code from business/data logic
- Remote MCP transport (`streamable-http`) vs local (`stdio`)
- Cloud deployment and debugging real build-time vs runtime environment
  differences (e.g. env vars not available during a build-time inspection
  step)
- Practical reliability engineering: caching with measured impact,
  structured logging with intentional log-level discipline