"""
Conservative CSP screener – large-cap universe (US, market cap ≥ $20B, liquid).
Used as the starting list; csp_screener filters by market cap and ADV via yfinance.
"""
# S&P 100–style large caps + major names (US, NYSE/NASDAQ). Screener filters by market cap ≥ $20B and ADV ≥ 2M.
LARGE_CAP_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "BRK-B", "TSLA", "UNH", "JNJ",
    "JPM", "V", "PG", "XOM", "HD", "MA", "CVX", "MRK", "ABBV", "KO",
    "PEP", "COST", "LLY", "WMT", "MCD", "CSCO", "ACN", "ABT", "DHR", "TMO",
    "AVGO", "NEE", "PM", "BMY", "UNP", "RTX", "HON", "INTC", "AMD", "AMGN",
    "LOW", "UPS", "INTU", "SPGI", "AXP", "BKNG", "CAT", "DE", "SBUX", "GS",
    "ADBE", "CRM", "AMAT", "GILD", "VZ", "T", "QCOM", "CMCSA", "ISRG", "MDLZ",
    "REGN", "LMT", "PLD", "SYK", "TJX", "CB", "CI", "SO", "DUK", "BDX",
    "BSX", "EOG", "SLB", "MMC", "EQIX", "CL", "HCA", "ZTS", "APD", "ITW",
    "MO", "PGR", "AON", "WM", "ECL", "NOC", "APTV", "KLAC", "SNPS", "CDNS",
    "SHW", "ORLY", "MCK", "ADI", "MDT", "CME", "NXPI", "AIG", "PSA", "MAR",
    "CTAS", "FIS", "GE", "C", "BLK", "USB", "PNC", "TGT", "MMM", "SCHW",
]
