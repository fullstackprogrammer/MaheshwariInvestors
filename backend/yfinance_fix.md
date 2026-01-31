# yfinance API Issues - Troubleshooting Guide

## Common Issues

### "Expecting value: line 1 column 1 (char 0)"
This error indicates yfinance is receiving an empty or invalid response from Yahoo Finance API.

### "No timezone found, symbol may be delisted"
This suggests the API call failed or the symbol data isn't available.

## Solutions

### 1. Update yfinance
```bash
pip install --upgrade yfinance
```

### 2. Check Network/Firewall
- Ensure you have internet connectivity
- Check if corporate firewall is blocking Yahoo Finance API
- Try accessing https://finance.yahoo.com in your browser

### 3. Use Alternative Date Range
The code now automatically falls back to the last 30 days if 2026 data isn't available. This handles:
- Cases where we're not yet in 2026
- API limitations with future dates
- Market holidays/weekends

### 4. Add Retry Logic
The code now includes better error handling and fallback date ranges.

### 5. Check Symbol Validity
Some symbols in the CSV might be invalid. Check the backend console for specific errors.

### 6. Rate Limiting
If you're fetching many stocks, yfinance might rate-limit. The code includes caching to minimize API calls.

## Testing Individual Symbols

Test if yfinance works for a single symbol:
```python
import yfinance as yf
ticker = yf.Ticker("AAPL")
hist = ticker.history(period="1mo")
print(hist.head())
```

## Alternative: Use Different Data Source

If yfinance continues to fail, consider:
- Alpha Vantage API (requires API key)
- IEX Cloud (requires API key)
- Polygon.io (requires API key)
- Yahoo Finance API directly (more complex)

## Current Implementation

The code now:
1. Tries the configured start date (2026-01-01)
2. Falls back to last 30 days if that fails
3. Handles errors gracefully
4. Caches results to minimize API calls
5. Logs detailed error messages
