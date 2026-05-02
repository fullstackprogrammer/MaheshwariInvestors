"""
FastAPI Backend for Maheshwari Investor Stock Analysis
Analyzes investor stock picks and tracks 2026 performance using live market data.
"""

import logging
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, date, timezone
from typing import List, Dict, Optional, Set
import pandas as pd
import yfinance as yf
from collections import defaultdict
import os
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

# Logging: INFO only; cache refresh and errors
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)
log = logging.getLogger(__name__)

app = FastAPI(title="Maheshwari Investor Stock Analysis API")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow any origin (e.g. LAN dev: http://192.168.x.x:5173)
    allow_credentials=False,  # Must be False when allow_origins is "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
# CSV path relative to project root (not backend directory)
# Use DFWInvestors2026StockPicks.csv if it exists, otherwise fall back to data/investors.csv
DFW_CSV_PATH = os.path.join(Path(__file__).parent.parent, "DFWInvestors2026StockPicks.csv")
DEFAULT_CSV_PATH = os.path.join(Path(__file__).parent.parent, "data", "investors.csv")

if Path(DFW_CSV_PATH).exists():
    CSV_FILE_PATH = DFW_CSV_PATH
else:
    CSV_FILE_PATH = DEFAULT_CSV_PATH

# Date configuration - use last 30 days if 2026 data isn't available yet
# This handles cases where yfinance doesn't have future data
from datetime import timedelta

try:
    # Try to use 2026-01-01 as start date if we're in 2026
    test_date = datetime(2026, 1, 1)
    current_date = datetime.now()
    if test_date <= current_date:
        START_DATE = "2026-01-01"
    else:
        # If we're not in 2026 yet, use last 30 days
        START_DATE = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
except Exception as e:
    # Fallback to last 30 days
    START_DATE = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

# END_DATE is computed at fetch time so we always get through "today"
def get_end_date():
    """Return end date for history fetch (today + 1 day so we include latest trading day)."""
    return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

INITIAL_PORTFOLIO_VALUE = 10000

# Finance movie character aliases (expanded for 55+ investors) - must be unique
FINANCE_ALIASES_RAW = [
    "Gordon Gecko", "Jordan Belfort", "Bud Fox", "Mark Baum", "Michael Burry",
    "Nick Leeson", "Bobby Axelrod", "Chuck Rhoades", "Larry Fink", "Ray Dalio",
    "Warren Buffett", "Carl Icahn", "Jamie Dimon", "Lloyd Blankfein", "John Paulson",
    "David Einhorn", "Bill Ackman", "Dan Loeb", "Paul Tudor Jones", "George Soros",
    "Stanley Druckenmiller", "Julian Robertson", "Steve Cohen", "Ken Griffin", "Jim Simons",
    "Peter Lynch", "Benjamin Graham", "John Bogle", "Jack Bogle", "Charlie Munger",
    "David Swensen", "John Templeton", "Philip Fisher", "Joel Greenblatt", "Mohnish Pabrai",
    "Seth Klarman", "Howard Marks", "Jeremy Grantham", "David Tepper", "Leon Cooperman",
    "Mario Gabelli", "Bruce Berkowitz", "Tom Gayner", "Lou Simpson", "Eddie Lampert",
    "Richard Pzena", "Whitney Tilson", "Guy Spier", "Mason Hawkins", "Glenn Greenberg",
    "Robert Rodriguez", "Jeffrey Gundlach", "Barry Rosenstein", "Nelson Peltz",
    "Pershing Square", "Third Point", "Trian Partners", "Icahn Enterprises", "Elliott Management"
]
# Deduplicate so each investor gets a unique alias (fixes duplicate rows / wrong sort in UI)
FINANCE_ALIASES = list(dict.fromkeys(FINANCE_ALIASES_RAW))

# Symbol mapping for common incorrect symbols
SYMBOL_MAPPING = {
    "TSMC": "TSM",  # Taiwan Semiconductor Manufacturing Company
    "GOOG": "GOOGL",  # Google Class C -> Class A (more commonly traded)
    "OIL": "USO",  # Oil ETF - map to USO (United States Oil Fund)
    # Note: Some symbols like FBTC, FETH, XYZ may be invalid - will be handled gracefully
}

def normalize_symbol(symbol: str) -> str:
    """Normalize and correct stock symbols."""
    symbol = symbol.strip().upper()
    # Remove common prefixes/suffixes
    symbol = symbol.replace("$", "").replace(".", "")
    # Apply mapping
    return SYMBOL_MAPPING.get(symbol, symbol)

# In-memory data storage (shared by all users - no per-user cache)
investors_data = []
# Main-app cache: used ONLY by Dashboard, Investor Rankings, Stocks Overview, and Index Performance.
# Built at server start and refreshed periodically. Those endpoints read from this cache only (no on-demand fetch).
# Symbol list comes solely from get_all_symbols() (CSV/investors_data). CSP does not touch this cache.
stock_cache = {}  # Single global cache: stocks, indices, prices; refreshed every 15 min
alias_mapping = {}

# Auto-refresh: interval in seconds (15 minutes)
CACHE_REFRESH_INTERVAL_SEC = 900
_cache_refresh_lock = threading.Lock()
# Per-symbol fetch timeout (seconds); prevents yfinance throttle/hang from blocking refresh
YFINANCE_FETCH_TIMEOUT_SEC = 30
# Minimum symbols in new cache before we merge; below this we skip update to keep previous cache
MIN_CACHE_SYMBOLS_TO_UPDATE = 1

def load_investors_from_csv():
    """Load investors from CSV file and generate aliases."""
    global investors_data, alias_mapping
    
    csv_path = Path(CSV_FILE_PATH)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found at {CSV_FILE_PATH}")
    
    # Read CSV - try with header first, fallback to no header
    try:
        df = pd.read_csv(csv_path, header=0)
        # Check if first row looks like a header
        first_col = str(df.columns[0]).strip()
        if first_col.lower() in ['investor', 'investor name', 'name']:
            # Has header row - use column names
            investor_col_name = df.columns[0]
            # Get stock columns (Stock1, Stock2, etc. or columns 1-5)
            stock_col_names = [col for col in df.columns[1:] if 'stock' in str(col).lower() or str(col).startswith('Stock')]
            if not stock_col_names:
                # Fallback: use columns 1-5
                stock_col_names = df.columns[1:6].tolist()
        else:
            # No header, treat first row as data
            df = pd.read_csv(csv_path, header=None)
            investor_col_name = 0
            stock_col_names = [1, 2, 3, 4, 5]
    except Exception as e:
        # Fallback to no header
        df = pd.read_csv(csv_path, header=None)
        investor_col_name = 0
        stock_col_names = [1, 2, 3, 4, 5]
    
    # Use fixed order (no shuffle) so the same CSV row always gets the same alias after restart
    investors_data = []
    alias_mapping = {}
    alias_index = 0  # Position in FINANCE_ALIASES for deterministic assignment
    
    for idx, row in df.iterrows():
        # Get investor name
        if isinstance(investor_col_name, str):
            original_name = str(row[investor_col_name]).strip()
        else:
            original_name = str(row.iloc[investor_col_name]).strip()
        
        # Skip if this looks like a header row
        if original_name.lower() in ['investor', 'investor name', 'name']:
            continue
        
        # Extract stocks and normalize symbols
        stocks = []
        for col in stock_col_names:
            if isinstance(col, str):
                val = row[col]
            else:
                val = row.iloc[col] if col < len(row) else None
            
            if pd.notna(val) and str(val).strip():
                normalized_symbol = normalize_symbol(str(val))
                if normalized_symbol:  # Only add if symbol is not empty after normalization
                    stocks.append(normalized_symbol)
        
        if not stocks:
            continue
        
        # Assign alias deterministically by position so it never changes after restart
        if alias_index < len(FINANCE_ALIASES):
            alias = FINANCE_ALIASES[alias_index]
        else:
            alias = f"Investor_{alias_index + 1}"
        alias_index += 1
        
        alias_mapping[alias] = original_name
        investors_data.append({
            "alias": alias,
            "stocks": stocks,
            "original_name": original_name  # Keep for internal use only
        })
    
    log.info("Loaded %s investors from %s", len(investors_data), csv_path.name)
    return investors_data

def _is_cache_stale(stock_data: Dict) -> bool:
    """True if cached data is from a previous day (not today or yesterday)."""
    if not stock_data or not stock_data.get("dates"):
        return True
    last_date_str = stock_data["dates"][-1]
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    # Stale if latest data is before yesterday (e.g. weekend or old cache)
    return last_date_str not in (today, yesterday)


def _fetch_one_stock_from_api(symbol: str) -> Optional[Dict]:
    """
    Fetch one symbol from yfinance and return stock_data dict (or None).
    Does NOT read or write the global cache. Used for background refresh.
    Exceptions are logged and converted to None so refresh loop never crashes.
    """
    symbol = normalize_symbol(symbol)
    if not symbol or len(symbol) < 1 or len(symbol) > 10:
        return None
    for attempt in range(3):
        try:
            ticker = yf.Ticker(symbol)
            end_date = get_end_date()
            hist = None
            for start, end in [(START_DATE, end_date), (None, None)]:
                try:
                    if start and end:
                        hist = ticker.history(start=start, end=end)
                    else:
                        hist = ticker.history(period="1mo")
                    if not hist.empty:
                        break
                except Exception as e:
                    log.debug("[yfinance] %s history attempt %s-%s: %s", symbol, start, end, e)
                    continue
            if hist is None or hist.empty:
                if attempt < 2:
                    time.sleep(1)
                    continue
                log.warning("[yfinance] %s: no history after 3 attempts", symbol)
                return None
            info = {}
            try:
                info = ticker.info or {}
            except Exception as e:
                log.debug("[yfinance] %s info: %s", symbol, e)
            prices = hist["Adj Close"].tolist() if "Adj Close" in hist.columns else hist["Close"].tolist()
            current_price = float(prices[-1])
            dates = hist.index.tolist()
            return {
                "symbol": symbol,
                "company_name": info.get("longName", symbol),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "current_price": current_price,
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "prices": prices,
                "dates": [d.strftime("%Y-%m-%d") for d in dates],
                "hist_data": hist,
            }
        except Exception as e:
            log.warning("[yfinance] %s attempt %d/3: %s", symbol, attempt + 1, e, exc_info=False)
            if attempt < 2:
                time.sleep(2)
                continue
            return None
    return None


def get_all_symbols() -> List[str]:
    """Return sorted list of unique stock symbols across all investors."""
    symbols: Set[str] = set()
    for inv in investors_data:
        for s in inv["stocks"]:
            symbols.add(normalize_symbol(s))
    return sorted(symbols)


# Benchmark indices (DJIA, S&P 500, Nasdaq Composite) - included in cache refresh so Dashboard reuses cache
_BENCHMARK_SYMBOLS_FOR_CACHE = ["^DJI", "^SPX", "^IXIC"]


def _fetch_one_stock_with_timeout(symbol: str, timeout_sec: int = YFINANCE_FETCH_TIMEOUT_SEC) -> Optional[Dict]:
    """Run _fetch_one_stock_from_api in a thread with timeout so yfinance throttle/hang does not block refresh."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_fetch_one_stock_from_api, symbol)
        try:
            return future.result(timeout=timeout_sec)
        except FuturesTimeoutError:
            log.warning("[Cache refresh] %s timed out after %ds (yfinance may be throttling)", symbol, timeout_sec)
            return None
        except Exception as e:
            log.warning("[Cache refresh] %s failed: %s", symbol, e)
            return None


def _refresh_cache_background_impl():
    """
    Fetch symbols from yfinance (with per-symbol timeout), then MERGE into cache.
    Symbol list = all unique symbols from investors (get_all_symbols()) + benchmarks; no limit.
    We never replace the cache with empty or worse data: only add/update entries we successfully fetched.
    Failed symbols are retried once so more symbols (e.g. all 110) make it into the cache.
    """
    global stock_cache
    investor_symbols = get_all_symbols()
    symbols = list(investor_symbols) + [s for s in _BENCHMARK_SYMBOLS_FOR_CACHE if s not in set(investor_symbols)]
    if not symbols:
        log.info("[Cache refresh] No symbols to fetch; skipping.")
        return
    log.info("[Cache refresh] Starting fetch for %s symbols (%s from investors); timeout %ds each.", len(symbols), len(investor_symbols), YFINANCE_FETCH_TIMEOUT_SEC)
    t0 = time.perf_counter()
    fetched = 0
    failed_list: List[str] = []
    for symbol in symbols:
        data = _fetch_one_stock_with_timeout(symbol)
        if data:
            fetched += 1
            with _cache_refresh_lock:
                stock_cache[symbol] = data
        else:
            failed_list.append(symbol)
    # Retry failed symbols once (helps get to full count when yfinance is slow)
    if failed_list:
        time.sleep(2)
        for symbol in list(failed_list):
            data = _fetch_one_stock_with_timeout(symbol)
            if data:
                fetched += 1
                failed_list.remove(symbol)
                with _cache_refresh_lock:
                    stock_cache[symbol] = data
    elapsed = time.perf_counter() - t0
    with _cache_refresh_lock:
        cache_size = len(stock_cache)
    log.info("[Cache refresh] Done in %.1fs: fetched %s, failed %s, cache size %s", elapsed, fetched, len(failed_list), cache_size)
    if fetched == 0 and cache_size == 0:
        log.warning("[Cache refresh] No data fetched and cache empty; app may return 503 until next refresh.")


def _background_refresh_loop():
    """Run cache refresh every CACHE_REFRESH_INTERVAL_SEC. Never exits; exceptions are logged and loop continues."""
    log.info("[Cache refresh] Background loop started; interval=%ds", CACHE_REFRESH_INTERVAL_SEC)
    while True:
        try:
            _refresh_cache_background_impl()
        except Exception as e:
            log.exception("[Cache refresh] Error (cache unchanged): %s", e)
        try:
            time.sleep(CACHE_REFRESH_INTERVAL_SEC)
        except Exception as e:
            log.warning("[Cache refresh] sleep interrupted: %s", e)


def fetch_stock_data(symbol: str, cache_only: bool = False) -> Optional[Dict]:
    """
    Get stock data for the main app (Dashboard, Rankings, Stocks, Index).
    When cache_only=True: return only from stock_cache (used by rankings/stocks/metrics/index).
    When cache_only=False: return from cache or fetch on miss.
    """
    symbol = normalize_symbol(symbol)
    if not symbol or len(symbol) < 1 or len(symbol) > 10:
        return None
    if symbol in stock_cache:
        return stock_cache[symbol]
    if cache_only:
        return None
    # Cache miss and not cache_only: fetch with timeout (e.g. refresh flow or one-off)
    t0 = time.perf_counter()
    stock_data = _fetch_one_stock_with_timeout(symbol)
    elapsed = time.perf_counter() - t0
    log.info("[Rankings] fetch_stock_data MISS %s took %.2fs (symbol not in cache)", symbol, elapsed)
    if stock_data:
        with _cache_refresh_lock:
            stock_cache[symbol] = stock_data
        return stock_data
    return None

def calculate_returns(prices: List[float], dates: List[str]) -> Dict[str, float]:
    """Calculate various return metrics."""
    if not prices or len(prices) < 2:
        return {
            "daily": 0.0,
            "1m": 0.0,
            "3m": 0.0,
            "ytd": 0.0,
            "cagr": 0.0
        }
    
    current_price = prices[-1]
    start_price = prices[0]
    
    # Daily return
    daily_return = ((current_price - prices[-2]) / prices[-2] * 100) if len(prices) >= 2 else 0.0
    
    # YTD return (from start date)
    ytd_return = ((current_price - start_price) / start_price * 100) if start_price > 0 else 0.0
    
    # 1 Month return (approximately 20 trading days)
    days_1m = min(20, len(prices) - 1)
    price_1m = prices[-days_1m] if days_1m > 0 else start_price
    return_1m = ((current_price - price_1m) / price_1m * 100) if price_1m > 0 else 0.0
    
    # 3 Month return (approximately 60 trading days)
    days_3m = min(60, len(prices) - 1)
    price_3m = prices[-days_3m] if days_3m > 0 else start_price
    return_3m = ((current_price - price_3m) / price_3m * 100) if price_3m > 0 else 0.0
    
    # CAGR (annualized) - assuming 252 trading days per year
    days_elapsed = len(prices)
    if days_elapsed > 1 and start_price > 0:
        total_return = (current_price / start_price) - 1
        years = days_elapsed / 252.0
        cagr = ((1 + total_return) ** (1 / years) - 1) * 100 if years > 0 else 0.0
    else:
        cagr = 0.0
    
    return {
        "daily": round(daily_return, 2),
        "1m": round(return_1m, 2),
        "3m": round(return_3m, 2),
        "ytd": round(ytd_return, 2),
        "cagr": round(cagr, 2)
    }

def calculate_portfolio_metrics(investor: Dict, cache_only: bool = True) -> Dict:
    """Calculate portfolio-level metrics. cache_only=True: use only stock_cache (for rankings/metrics)."""
    stocks = investor["stocks"]
    if not stocks:
        # Return zero metrics if no valid stocks
        return {
            "portfolio_value": INITIAL_PORTFOLIO_VALUE,
            "daily": 0.0,
            "1m": 0.0,
            "3m": 0.0,
            "ytd": 0.0,
            "cagr": 0.0,
            "value_change": 0.0,
            "value_change_pct": 0.0
        }
    
    num_stocks = len(stocks)
    allocation_per_stock = INITIAL_PORTFOLIO_VALUE / num_stocks
    
    portfolio_value = 0.0
    stock_returns = []
    valid_stocks_count = 0
    
    for symbol in stocks:
        stock_data = fetch_stock_data(symbol, cache_only=cache_only)
        if stock_data and stock_data.get("prices"):
            prices = stock_data["prices"]
            if len(prices) >= 2:
                start_price = prices[0]
                current_price = stock_data["current_price"]  # Use the stored current_price
                shares = allocation_per_stock / start_price if start_price > 0 else 0
                current_value = shares * current_price
                portfolio_value += current_value
                valid_stocks_count += 1
            
            returns = calculate_returns(prices, stock_data["dates"])
            stock_returns.append(returns)
        else:
            # If stock data unavailable, allocate value remains at initial allocation
            portfolio_value += allocation_per_stock
    
    # Portfolio-level returns (weighted average of valid stocks)
    if stock_returns:
        daily_avg = sum(r["daily"] for r in stock_returns) / len(stock_returns)
        return_1m_avg = sum(r["1m"] for r in stock_returns) / len(stock_returns)
        return_3m_avg = sum(r["3m"] for r in stock_returns) / len(stock_returns)
        ytd_avg = sum(r["ytd"] for r in stock_returns) / len(stock_returns)
        cagr_avg = sum(r["cagr"] for r in stock_returns) / len(stock_returns)
    else:
        daily_avg = return_1m_avg = return_3m_avg = ytd_avg = cagr_avg = 0.0
    
    value_change = portfolio_value - INITIAL_PORTFOLIO_VALUE
    value_change_pct = (value_change / INITIAL_PORTFOLIO_VALUE * 100) if INITIAL_PORTFOLIO_VALUE > 0 else 0.0
    
    return {
        "portfolio_value": round(portfolio_value, 2),
        "daily": round(daily_avg, 2),
        "1m": round(return_1m_avg, 2),
        "3m": round(return_3m_avg, 2),
        "ytd": round(ytd_avg, 2),
        "cagr": round(cagr_avg, 2),
        "value_change": round(value_change, 2),
        "value_change_pct": round(value_change_pct, 2)
    }

@app.on_event("startup")
async def startup_event():
    """Load data, start server immediately; warm cache in background so /health responds right away."""
    load_investors_from_csv()
    refresh_thread = threading.Thread(target=_background_refresh_loop, daemon=True)
    refresh_thread.start()
    log.info("Startup complete; server ready. Cache warming in background (2-3 min); /health and data endpoints will return 503 until then.")

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Maheshwari Investor Stock Analysis API", "status": "running"}

@app.get("/health")
async def health():
    """Fast health check - no stock data fetching. cache_ready=True when dashboard data can be served from cache."""
    cache_ready = len(stock_cache) > 0
    log.info("GET /health cache_ready=%s cache_symbols=%s", cache_ready, len(stock_cache))
    return {
        "status": "ok",
        "investors_loaded": len(investors_data),
        "cache_ready": cache_ready,
        "cache_symbols": len(stock_cache),
    }

@app.get("/investors")
async def get_investors():
    """Get all investors with their stock picks."""
    return [{"alias": inv["alias"], "stocks": inv["stocks"]} for inv in investors_data]

def _ensure_cache_ready():
    """Raise 503 if cache is empty so frontend can retry instead of blocking for minutes."""
    if len(stock_cache) == 0:
        log.info("Stock data requested but cache empty (still warming); returning 503")
        raise HTTPException(
            status_code=503,
            detail="Cache warming; retry in a few seconds. First load after restart takes 2–3 minutes.",
        )


@app.get("/investors/rankings")
async def get_investor_rankings():
    """Get investor rankings with performance metrics. Uses main-app cache only (no on-demand fetch)."""
    t0 = time.perf_counter()
    _ensure_cache_ready()
    rankings = []
    for investor in investors_data:
        metrics = calculate_portfolio_metrics(investor, cache_only=True)
        rankings.append({
            "alias": investor["alias"],
            "stocks": investor["stocks"],
            **metrics
        })
    loop_elapsed = time.perf_counter() - t0
    log.info("[Rankings] loop %.2fs for %d investors", loop_elapsed, len(investors_data))
    # Sort by YTD return (descending)
    rankings.sort(key=lambda x: x["ytd"], reverse=True)
    for idx, ranking in enumerate(rankings, 1):
        ranking["rank"] = idx
    total_elapsed = time.perf_counter() - t0
    log.info("[Rankings] total %.2fs, %d rows (cache_symbols=%d)", total_elapsed, len(rankings), len(stock_cache))
    return rankings

@app.get("/stocks")
async def get_stocks():
    """Get all unique stocks across all investors with metrics."""
    _ensure_cache_ready()
    # Collect all unique stocks
    all_stocks = set()
    stock_to_investors = defaultdict(list)
    
    for investor in investors_data:
        for symbol in investor["stocks"]:
            all_stocks.add(symbol)
            stock_to_investors[symbol].append(investor["alias"])
    
    stocks_data = []
    
    for symbol in sorted(all_stocks):
        stock_data = fetch_stock_data(symbol, cache_only=True)
        if stock_data:
            returns = calculate_returns(stock_data["prices"], stock_data["dates"])
            
            # Calculate total value held by all investors
            total_value = 0.0
            for investor in investors_data:
                if symbol in investor["stocks"]:
                    num_stocks = len(investor["stocks"])
                    allocation = INITIAL_PORTFOLIO_VALUE / num_stocks
                    if stock_data["prices"]:
                        start_price = stock_data["prices"][0]
                        shares = allocation / start_price if start_price > 0 else 0
                        total_value += shares * stock_data["current_price"]
            
            stocks_data.append({
                "symbol": symbol,
                "company_name": stock_data["company_name"],
                "sector": stock_data["sector"],
                "industry": stock_data["industry"],
                "current_price": round(stock_data["current_price"], 2),
                "market_cap": stock_data.get("market_cap"),
                "daily": returns["daily"],
                "1m": returns["1m"],
                "3m": returns["3m"],
                "ytd": returns["ytd"],
                "pe_ratio": stock_data["pe_ratio"],
                "forward_pe": stock_data["forward_pe"],
                "investors_holding": len(stock_to_investors[symbol]),
                "total_value": round(total_value, 2),
                "value_pct": round((total_value / (len(investors_data) * INITIAL_PORTFOLIO_VALUE)) * 100, 2) if investors_data else 0.0
            })
    
    log.info("Served /stocks (%d symbols)", len(stocks_data))
    return stocks_data

@app.get("/metrics")
async def get_metrics():
    """Get aggregated metrics. Returns 503 while cache is warming so frontend can retry instead of blocking."""
    _ensure_cache_ready()
    rankings = await get_investor_rankings()
    stocks = await get_stocks()
    
    # Top 5 investors by YTD
    top_investors = rankings[:5]
    
    # Top 5 stocks by YTD
    stocks_sorted = sorted(stocks, key=lambda x: x["ytd"], reverse=True)
    top_stocks = stocks_sorted[:5]
    
    # Aggregated YTD return across all investors (average)
    aggregate_ytd = (
        sum(r["ytd"] for r in rankings) / len(rankings)
        if rankings else 0.0
    )
    # Average portfolio value across ALL investors (consistent with aggregate_ytd; each starts at INITIAL_PORTFOLIO_VALUE)
    average_portfolio_value = (
        sum(r["portfolio_value"] for r in rankings) / len(rankings)
        if rankings else float(INITIAL_PORTFOLIO_VALUE)
    )
    
    log.info("Served /metrics")
    return {
        "top_investors": top_investors,
        "top_stocks": top_stocks,
        "total_investors": len(investors_data),
        "total_stocks": len(stocks),
        "average_portfolio_value": round(average_portfolio_value, 2),
        "aggregate_ytd_return": round(aggregate_ytd, 2),
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

@app.post("/refresh-data")
async def refresh_data():
    """Clear cache and refresh stock data."""
    global stock_cache
    stock_cache.clear()
    return {"message": "Cache cleared. Data will be refreshed on next request."}


# --- MAI (Maheshwari AI) Index vs Benchmarks ---
# Benchmarks: Dow Jones (^DJI), S&P 500 (^SPX), NASDAQ Composite (^IXIC)
BENCHMARK_SYMBOLS = ["^DJI", "^SPX", "^IXIC"]

def _get_price_on_date(stock_data: Optional[Dict], target_date: str) -> Optional[float]:
    """Return price on target_date (YYYY-MM-DD) from stock_data, or first available if before target."""
    if not stock_data or not stock_data.get("prices") or not stock_data.get("dates"):
        return None
    dates = stock_data["dates"]
    prices = stock_data["prices"]
    for i, d in enumerate(dates):
        if d >= target_date:
            return float(prices[i])
    return float(prices[0]) if prices else None

def _fetch_benchmark(symbol: str, cache_only: bool = True) -> Optional[Dict]:
    """Get benchmark data. cache_only=True: index uses cache only (benchmarks are in refresh list)."""
    if symbol in stock_cache:
        return stock_cache[symbol]
    if cache_only:
        return None
    log.info("[Index] benchmark %s cache miss; fetching with timeout", symbol)
    data = _fetch_one_stock_with_timeout(symbol)
    if data:
        with _cache_refresh_lock:
            stock_cache[symbol] = data
        return data
    return None

@app.get("/index-performance")
async def get_index_performance():
    """
    MAI (Maheshwari AI) index vs benchmarks for January 2026 performance.
    MAI = sum of current (and start) prices of all unique stocks held by investors.
    Benchmarks: Dow Jones (^DJI), S&P 500 (^SPX), NASDAQ Composite (^IXIC).
    Returns: price on 1/1/2026, current price, gain/loss $, gain/loss %, MAI vs other (% diff, sign = MAI better + / worse -).
    """
    _ensure_cache_ready()
    start_date = "2026-01-01"
    symbols = get_all_symbols()

    # MAI: sum of prices across unique stocks (only stocks with valid start price)
    mai_start = 0.0
    mai_current = 0.0
    for symbol in symbols:
        data = fetch_stock_data(symbol, cache_only=True)
        if data and data.get("prices") and data.get("dates"):
            start_p = _get_price_on_date(data, start_date)
            if start_p is not None:
                mai_start += start_p
                mai_current += float(data["current_price"])

    # Benchmarks
    rows = []
    mai_gain_pct = 0.0
    if mai_start and mai_start > 0:
        mai_gain = mai_current - mai_start
        mai_gain_pct = (mai_gain / mai_start) * 100
        rows.append({
            "index": "MAI",
            "index_label": "Maheshwari AI Index",
            "price_start": round(mai_start, 2),
            "price_current": round(mai_current, 2),
            "gain_loss_dollars": round(mai_gain, 2),
            "gain_loss_pct": round(mai_gain_pct, 2),
            "mai_vs_other_pct": None,
        })

    # Benchmarks: try cache first; fetch on miss so DJIA/S&P 500/NASDAQ always show (cache may not have them yet)
    for sym in BENCHMARK_SYMBOLS:
        data = _fetch_benchmark(sym, cache_only=True)
        if not data or not data.get("prices") or not data.get("dates"):
            continue
        start_p = _get_price_on_date(data, start_date)
        if start_p is None:
            continue
        current_p = float(data["current_price"])
        gain = current_p - start_p
        gain_pct = (gain / start_p) * 100
        # MAI vs other: % difference with correct sign.
        # Magnitude = relative % ((MAI/benchmark) - 1) * 100; sign = outperformance (MAI better -> +).
        if gain_pct == 0:
            mai_vs = None
        else:
            raw_pct = ((mai_gain_pct / gain_pct) - 1) * 100
            sign = 1 if (mai_gain_pct - gain_pct) >= 0 else -1
            mai_vs = sign * abs(raw_pct)
        label = {"^DJI": "DJIA", "^SPX": "S&P 500", "^IXIC": "NASDAQ"}.get(sym, sym)
        rows.append({
            "index": label,
            "index_label": label,
            "price_start": round(start_p, 2),
            "price_current": round(current_p, 2),
            "gain_loss_dollars": round(gain, 2),
            "gain_loss_pct": round(gain_pct, 2),
            "mai_vs_other_pct": round(mai_vs, 1) if mai_vs is not None else None,
        })

    log.info("Served /index-performance (%d rows)", len(rows))
    return {
        "rows": rows,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


# --- CSP (Cash-Secured Puts) Strategy: separate from main-app cache ---
# This endpoint does NOT use stock_cache. It uses csp_screener.run_screener(), which
# fetches its own data via yfinance (options, fundamentals, etc.). Dashboard, Rankings,
# Stocks Overview, and Index Performance are unaffected and use only the main cache above.

@app.get("/csp-filters")
async def get_csp_filters():
    """Return default screener filter values so the UI can display and adjust them."""
    try:
        from csp_screener import DEFAULT_FILTERS
        return DEFAULT_FILTERS
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/csp-ideas")
async def get_csp_ideas(
    max_results: int = 50,
    symbols: Optional[str] = None,
    use_community_universe: Optional[bool] = None,
    max_dte: Optional[int] = None,
    sector: Optional[str] = None,
    strike_pct_min: Optional[float] = None,
    strike_pct_max: Optional[float] = None,
    max_bid_ask_pct: Optional[float] = None,
    min_annualized_return_pct: Optional[float] = None,
    target_upside_min: Optional[float] = None,
    min_market_cap_b: Optional[float] = None,
    max_symbols: Optional[int] = None,
):
    """
    Conservative cash-secured put ideas. Pass optional query params to adjust screener filters.
    symbols: comma-separated tickers (e.g. AAPL,MSFT,SPY); if provided, only those are scanned.
    use_community_universe: if True and no symbols provided, use stocks selected by the community (from investor data).
    Data is fetched independently by the CSP screener; not from the main cache.
    """
    try:
        from csp_screener import run_screener
        symbol_list = None
        if symbols and symbols.strip():
            symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        elif use_community_universe in (True, "true", "1", 1):
            symbol_list = get_all_symbols()
        overrides = {}
        if max_dte is not None: overrides["max_dte"] = max_dte
        if sector and sector.strip(): overrides["sector"] = sector.strip()
        if strike_pct_min is not None: overrides["strike_pct_min"] = strike_pct_min
        if strike_pct_max is not None: overrides["strike_pct_max"] = strike_pct_max
        if max_bid_ask_pct is not None: overrides["max_bid_ask_pct"] = max_bid_ask_pct
        if min_annualized_return_pct is not None: overrides["min_annualized_return_pct"] = min_annualized_return_pct
        if target_upside_min is not None: overrides["target_upside_min"] = target_upside_min
        if min_market_cap_b is not None: overrides["min_market_cap_b"] = min_market_cap_b
        if max_symbols is not None: overrides["max_symbols"] = min(max_symbols, 10)
        if max_results is not None: overrides["max_results"] = min(max(max_results, 1), 100)

        result = run_screener(
            symbols=symbol_list,
            max_results=min(max(max_results or 50, 1), 100),
            overrides=overrides if overrides else None,
        )
        opportunities = result.get("opportunities", result) if isinstance(result, dict) else result
        return {
            "opportunities": opportunities,
            "count": len(opportunities),
            "as_of": datetime.now(timezone.utc).isoformat(),
            "market_open": result.get("market_open", True) if isinstance(result, dict) else True,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSP screener error: {str(e)}")


@app.get("/covered-calls-filters")
async def get_covered_calls_filters():
    """Return default covered calls screener filter values for the UI."""
    try:
        from covered_calls_screener import DEFAULT_FILTERS
        return DEFAULT_FILTERS
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/covered-calls-ideas")
async def get_covered_calls_ideas(
    max_results: int = 50,
    symbols: Optional[str] = None,
    use_community_universe: Optional[bool] = None,
    max_dte: Optional[int] = None,
    sector: Optional[str] = None,
    strike_pct_min: Optional[float] = None,
    strike_pct_max: Optional[float] = None,
    max_bid_ask_pct: Optional[float] = None,
    min_annualized_return_pct: Optional[float] = None,
    min_market_cap_b: Optional[float] = None,
    max_symbols: Optional[int] = None,
):
    """
    Covered call ideas. Pass optional query params to adjust screener filters.
    symbols: comma-separated tickers; if provided, only those are scanned.
    use_community_universe: if True and no symbols provided, use MAI community stocks.
    """
    try:
        from covered_calls_screener import run_screener
        symbol_list = None
        if symbols and symbols.strip():
            symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        elif use_community_universe in (True, "true", "1", 1):
            symbol_list = get_all_symbols()
        overrides = {}
        if max_dte is not None: overrides["max_dte"] = max_dte
        if sector and sector.strip(): overrides["sector"] = sector.strip()
        if strike_pct_min is not None: overrides["strike_pct_min"] = strike_pct_min
        if strike_pct_max is not None: overrides["strike_pct_max"] = strike_pct_max
        if max_bid_ask_pct is not None: overrides["max_bid_ask_pct"] = max_bid_ask_pct
        if min_annualized_return_pct is not None: overrides["min_annualized_return_pct"] = min_annualized_return_pct
        if min_market_cap_b is not None: overrides["min_market_cap_b"] = min_market_cap_b
        if max_symbols is not None: overrides["max_symbols"] = min(max_symbols, 10)
        if max_results is not None: overrides["max_results"] = min(max(max_results, 1), 100)

        opportunities = run_screener(
            symbols=symbol_list,
            max_results=min(max(max_results or 50, 1), 100),
            overrides=overrides if overrides else None,
        )
        return {
            "opportunities": opportunities,
            "count": len(opportunities),
            "as_of": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Covered calls screener error: {str(e)}")
