"""
FastAPI Backend for Maheshwari Investor Stock Analysis
Analyzes investor stock picks and tracks 2026 performance using live market data.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, date
from typing import List, Dict, Optional, Set
import pandas as pd
import yfinance as yf
from collections import defaultdict
import os
import time
import threading
from pathlib import Path

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

# In-memory data storage
investors_data = []
stock_cache = {}
alias_mapping = {}

# Auto-refresh: interval in seconds (5 minutes)
CACHE_REFRESH_INTERVAL_SEC = 300
_cache_refresh_lock = threading.Lock()

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
    
    print(f"Loaded {len(investors_data)} investors from {csv_path.name}")
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
                except Exception:
                    continue
            if hist is None or hist.empty:
                if attempt < 2:
                    time.sleep(1)
                    continue
                return None
            info = {}
            try:
                info = ticker.info or {}
            except Exception:
                pass
            prices = hist["Adj Close"].tolist() if "Adj Close" in hist.columns else hist["Close"].tolist()
            current_price = float(prices[-1])
            dates = hist.index.tolist()
            return {
                "symbol": symbol,
                "company_name": info.get("longName", symbol),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "current_price": current_price,
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "prices": prices,
                "dates": [d.strftime("%Y-%m-%d") for d in dates],
                "hist_data": hist,
            }
        except Exception:
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


def _refresh_cache_background_impl():
    """
    Build a new cache from yfinance, then hot-swap with the live cache.
    Does not block or clear the live cache until the new one is ready.
    """
    global stock_cache
    symbols = get_all_symbols()
    if not symbols:
        return
    new_cache = {}
    for i, symbol in enumerate(symbols):
        data = _fetch_one_stock_from_api(symbol)
        if data:
            new_cache[symbol] = data
    with _cache_refresh_lock:
        stock_cache = new_cache
    print(f"[Cache refresh] Hot-swap complete: {len(new_cache)} symbols updated at {datetime.now().strftime('%H:%M:%S')}")


def _background_refresh_loop():
    """Run cache refresh every CACHE_REFRESH_INTERVAL_SEC. Does not block request handlers."""
    time.sleep(60)  # Wait 1 min after startup before first refresh
    while True:
        try:
            _refresh_cache_background_impl()
        except Exception as e:
            print(f"[Cache refresh] Error: {e}")
        time.sleep(CACHE_REFRESH_INTERVAL_SEC)


def fetch_stock_data(symbol: str) -> Optional[Dict]:
    """Fetch stock data from yfinance with caching and retry logic."""
    # Normalize symbol first
    symbol = normalize_symbol(symbol)
    
    # Check cache - use only if data is from today or yesterday
    if symbol in stock_cache:
        cached = stock_cache[symbol]
        if not _is_cache_stale(cached):
            return cached
        # Stale: remove and refetch
        del stock_cache[symbol]
    
    # Skip obviously invalid symbols
    if not symbol or len(symbol) < 1 or len(symbol) > 10:
        return None
    
    # Fetch from API (same logic as background refresh); store into live cache
    stock_data = _fetch_one_stock_from_api(symbol)
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

def calculate_portfolio_metrics(investor: Dict) -> Dict:
    """Calculate portfolio-level metrics for an investor."""
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
        stock_data = fetch_stock_data(symbol)
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
    """Load data on startup and start background cache refresh."""
    load_investors_from_csv()
    print(f"Loaded {len(investors_data)} investors")
    # Start background thread: refresh cache every 5 minutes; hot-swap when done (no impact on users)
    refresh_thread = threading.Thread(target=_background_refresh_loop, daemon=True)
    refresh_thread.start()
    print("Background cache refresh started (every 5 minutes, hot-swap when complete)")

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Maheshwari Investor Stock Analysis API", "status": "running"}

@app.get("/health")
async def health():
    """Fast health check - no stock data fetching. Use this to verify backend is running."""
    return {"status": "ok", "investors_loaded": len(investors_data)}

@app.get("/investors")
async def get_investors():
    """Get all investors with their stock picks."""
    return [{"alias": inv["alias"], "stocks": inv["stocks"]} for inv in investors_data]

@app.get("/investors/rankings")
async def get_investor_rankings():
    """Get investor rankings with performance metrics."""
    rankings = []
    
    for investor in investors_data:
        metrics = calculate_portfolio_metrics(investor)
        rankings.append({
            "alias": investor["alias"],
            "stocks": investor["stocks"],
            **metrics
        })
    
    # Sort by YTD return (descending)
    rankings.sort(key=lambda x: x["ytd"], reverse=True)
    
    # Add rank
    for idx, ranking in enumerate(rankings, 1):
        ranking["rank"] = idx
    
    return rankings

@app.get("/stocks")
async def get_stocks():
    """Get all unique stocks across all investors with metrics."""
    # Collect all unique stocks
    all_stocks = set()
    stock_to_investors = defaultdict(list)
    
    for investor in investors_data:
        for symbol in investor["stocks"]:
            all_stocks.add(symbol)
            stock_to_investors[symbol].append(investor["alias"])
    
    stocks_data = []
    
    for symbol in sorted(all_stocks):
        stock_data = fetch_stock_data(symbol)
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
    
    return stocks_data

@app.get("/metrics")
async def get_metrics():
    """Get aggregated metrics."""
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
    
    return {
        "top_investors": top_investors,
        "top_stocks": top_stocks,
        "total_investors": len(investors_data),
        "total_stocks": len(stocks),
        "aggregate_ytd_return": round(aggregate_ytd, 2),
        "last_updated": datetime.now().isoformat()
    }

@app.post("/refresh-data")
async def refresh_data():
    """Clear cache and refresh stock data."""
    global stock_cache
    stock_cache.clear()
    return {"message": "Cache cleared. Data will be refreshed on next request."}
