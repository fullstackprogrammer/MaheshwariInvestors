"""
Conservative CSP screener – large-cap universe (US, market cap ≥ $20B, liquid).
Sector-specific symbol lists used when user selects a sector (takes precedence over default universe).
"""
from typing import Dict, List

# Sector -> list of S&P 500 symbols in that GICS sector. Source: same as LARGE_CAP_UNIVERSE.
SECTOR_SYMBOLS: Dict[str, List[str]] = {
    "Energy": [
        "APA", "BKR", "COP", "CTRA", "CVX", "DVN", "EOG", "EQT", "EXE", "FANG", "HAL", "KMI",
        "MPC", "OKE", "OXY", "PSX", "SLB", "TPL", "TRGP", "VLO", "WMB", "XOM",
    ],
    "Technology": [
        "AAPL", "ACN", "ADBE", "ADI", "ADSK", "AKAM", "AMAT", "AMD", "ANET", "APH", "AVGO", "CDNS",
        "CDW", "CRM", "CRWD", "CSCO", "CTSH", "DDOG", "DELL", "ENPH", "EPAM", "FFIV", "FICO", "FSLR",
        "FTNT", "GDDY", "GEN", "GLW", "HPE", "HPQ", "IBM", "INTC", "INTU", "IT", "JBL", "KEYS",
        "KLAC", "LRCX", "MCHP", "MPWR", "MSFT", "MSI", "MU", "NOW", "NTAP", "NVDA", "NXPI", "ON",
        "ORCL", "PANW", "PLTR", "PTC", "QCOM", "ROP", "SMCI", "SNPS", "STX", "SWKS", "TDY", "TEL",
        "TER", "TRMB", "TXN", "TYL", "VRSN", "WDAY", "WDC", "ZBRA",
    ],
    "Healthcare": [
        "A", "ABBV", "ABT", "ALGN", "AMGN", "BAX", "BDX", "BIIB", "BMY", "BSX", "CAH", "CI",
        "CNC", "COO", "COR", "CRL", "CVS", "DGX", "DHR", "DVA", "DXCM", "ELV", "EW", "GEHC",
        "GILD", "HCA", "HOLX", "HSIC", "HUM", "IDXX", "INCY", "IQV", "ISRG", "JNJ", "LH", "LLY",
        "MCK", "MDT", "MOH", "MRK", "MRNA", "MTD", "PFE", "PODD", "REGN", "RMD", "RVTY", "SOLV",
        "STE", "SYK", "TECH", "TMO", "UHS", "UNH", "VRTX", "VTRS", "WAT", "WST", "ZBH", "ZTS",
    ],
    "Financial Services": [
        "ACGL", "AFL", "AIG", "AIZ", "AJG", "ALL", "AMP", "AON", "APO", "AXP", "BAC", "BEN",
        "BK", "BLK", "BRK-B", "BRO", "BX", "C", "CB", "CBOE", "CFG", "CINF", "CME", "COF",
        "COIN", "CPAY", "EG", "ERIE", "FDS", "FI", "FIS", "FITB", "GL", "GPN", "GS", "HBAN",
        "HIG", "ICE", "IVZ", "JKHY", "JPM", "KEY", "KKR", "L", "MA", "MCO", "MET", "MKTX",
        "MMC", "MS", "MSCI", "MTB", "NDAQ", "NTRS", "PFG", "PGR", "PNC", "PRU", "PYPL", "RF",
        "RJF", "SCHW", "SPGI", "STT", "SYF", "TFC", "TROW", "TRV", "USB", "V", "WFC", "WRB",
        "WTW", "XYZ",
    ],
    "Consumer Cyclical": [
        "ABNB", "AMZN", "APTV", "AZO", "BBY", "BKNG", "CCL", "CMG", "CZR", "DASH", "DECK", "DHI",
        "DPZ", "DRI", "EBAY", "EXPE", "F", "GM", "GPC", "GRMN", "HAS", "HD", "HLT", "KMX",
        "LEN", "LKQ", "LOW", "LULU", "LVS", "MAR", "MCD", "MGM", "MHK", "NCLH", "NKE", "NVR",
        "ORLY", "PHM", "POOL", "RCL", "RL", "ROST", "SBUX", "TJX", "TPR", "TSCO", "TSLA", "ULTA",
        "WSM", "WYNN", "YUM",
    ],
    "Consumer Defensive": [
        "ADM", "BF-B", "BG", "CAG", "CHD", "CL", "CLX", "COST", "CPB", "DG", "DLTR", "EL",
        "GIS", "HRL", "HSY", "K", "KDP", "KHC", "KMB", "KO", "KR", "KVUE", "LW", "MDLZ",
        "MKC", "MNST", "MO", "PEP", "PG", "PM", "SJM", "STZ", "SYY", "TAP", "TGT", "TSN",
        "WBA", "WMT",
    ],
    "Industrials": [
        "ADP", "ALLE", "AME", "AOS", "AXON", "BA", "BLDR", "BR", "CARR", "CAT", "CHRW", "CMI",
        "CPRT", "CSX", "CTAS", "DAL", "DAY", "DE", "DOV", "EFX", "EMR", "ETN", "EXPD", "FAST",
        "FDX", "FTV", "GD", "GE", "GEV", "GNRC", "GWW", "HII", "HON", "HUBB", "HWM", "IEX",
        "IR", "ITW", "J", "JBHT", "JCI", "LDOS", "LHX", "LII", "LMT", "LUV", "MAS", "MMM",
        "NDSN", "NOC", "NSC", "ODFL", "OTIS", "PAYC", "PAYX", "PCAR", "PH", "PNR", "PWR", "ROK",
        "ROL", "RSG", "RTX", "SNA", "SWK", "TDG", "TT", "TXT", "UAL", "UBER", "UNP", "UPS",
        "URI", "VLTO", "VRSK", "WAB", "WM", "XYL",
    ],
    "Utilities": [
        "AEE", "AEP", "AES", "ATO", "AWK", "CEG", "CMS", "CNP", "D", "DTE", "DUK", "ED",
        "EIX", "ES", "ETR", "EVRG", "EXC", "FE", "LNT", "NEE", "NI", "NRG", "PCG", "PEG",
        "PNW", "PPL", "SO", "SRE", "VST", "WEC", "XEL",
    ],
    "Real Estate": [
        "AMT", "ARE", "AVB", "BXP", "CBRE", "CCI", "CPT", "CSGP", "DLR", "DOC", "EQIX", "EQR",
        "ESS", "EXR", "FRT", "HST", "INVH", "IRM", "KIM", "MAA", "O", "PLD", "PSA", "REG",
        "SBAC", "SPG", "UDR", "VICI", "VTR", "WELL", "WY",
    ],
    "Basic Materials": [
        "ALB", "AMCR", "APD", "AVY", "BALL", "CF", "CTVA", "DD", "DOW", "ECL", "EMN", "FCX",
        "IFF", "IP", "LIN", "LYB", "MLM", "MOS", "NEM", "NUE", "PKG", "PPG", "SHW", "STLD",
        "SW", "VMC",
    ],
    "Communication Services": [
        "CHTR", "CMCSA", "DIS", "EA", "FOX", "FOXA", "GOOG", "GOOGL", "IPG", "LYV", "META", "MTCH",
        "NFLX", "NWS", "NWSA", "OMC", "PSKY", "T", "TKO", "TMUS", "TTD", "TTWO", "VZ", "WBD",
    ],
}

# S&P 500 constituents. Used when no sector selected. Source: datasets/s-and-p-500-companies (GitHub).
# To refresh: download constituents.csv and run the script in backend/ that parses Symbol column (BRK.B→BRK-B, BF.B→BF-B).
LARGE_CAP_UNIVERSE = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A", "APD", "ABNB",
    "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL", "GOOG", "MO", "AMZN", "AMCR",
    "AEE", "AEP", "AXP", "AIG", "AMT", "AWK", "AMP", "AME", "AMGN", "APH", "ADI", "AON",
    "APA", "APO", "AAPL", "AMAT", "APTV", "ACGL", "ADM", "ANET", "AJG", "AIZ", "T", "ATO",
    "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX", "BDX", "BRK-B",
    "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BK", "BA", "BKNG", "BSX", "BMY", "AVGO",
    "BR", "BRO", "BF-B", "BLDR", "BG", "BXP", "CHRW", "CDNS", "CZR", "CPT", "CPB", "COF",
    "CAH", "KMX", "CCL", "CARR", "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF",
    "CRL", "SCHW", "CHTR", "CVX", "CMG", "CB", "CHD", "CI", "CINF", "CTAS", "CSCO", "C",
    "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COIN", "CL", "CMCSA", "CAG", "COP", "ED",
    "STZ", "CEG", "COO", "CPRT", "GLW", "CPAY", "CTVA", "CSGP", "COST", "CTRA", "CRWD", "CCI",
    "CSX", "CMI", "CVS", "DHR", "DRI", "DDOG", "DVA", "DAY", "DECK", "DE", "DELL", "DAL",
    "DVN", "DXCM", "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI",
    "DTE", "DUK", "DD", "EMN", "ETN", "EBAY", "ECL", "EIX", "EW", "EA", "ELV", "EMR",
    "ENPH", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR", "ERIE", "ESS", "EL", "EG",
    "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD", "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST",
    "FRT", "FDX", "FIS", "FITB", "FSLR", "FE", "FI", "F", "FTNT", "FTV", "FOXA", "FOX",
    "BEN", "FCX", "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM",
    "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA", "DOC", "HSIC",
    "HSY", "HPE", "HLT", "HOLX", "HD", "HON", "HRL", "HST", "HWM", "HPQ", "HUBB", "HUM",
    "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY", "IR", "PODD", "INTC", "ICE", "IFF",
    "IP", "IPG", "INTU", "ISRG", "IVZ", "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J",
    "JNJ", "JCI", "JPM", "K", "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR",
    "KLAC", "KHC", "KR", "LHX", "LH", "LRCX", "LW", "LVS", "LDOS", "LEN", "LII", "LLY",
    "LIN", "LYV", "LKQ", "LMT", "L", "LOW", "LULU", "LYB", "MTB", "MPC", "MKTX", "MAR",
    "MMC", "MLM", "MAS", "MA", "MTCH", "MKC", "MCD", "MCK", "MDT", "MRK", "META", "MET",
    "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "MHK", "MOH", "TAP", "MDLZ", "MPWR",
    "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX", "NEM", "NWSA", "NWS",
    "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC", "NCLH", "NRG", "NUE", "NVDA", "NVR",
    "NXPI", "ORLY", "OXY", "ODFL", "OMC", "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR",
    "PANW", "PSKY", "PH", "PAYX", "PAYC", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX",
    "PNW", "PNC", "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC",
    "PSA", "PHM", "PWR", "QCOM", "DGX", "RL", "RJF", "RTX", "O", "REG", "REGN", "RF",
    "RSG", "RMD", "RVTY", "ROK", "ROL", "ROP", "ROST", "RCL", "SPGI", "CRM", "SBAC", "SLB",
    "STX", "SRE", "NOW", "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV",
    "SWK", "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS", "TROW",
    "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN", "TPL", "TXT", "TMO",
    "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV", "TRMB", "TFC", "TYL", "TSN", "USB",
    "UBER", "UDR", "ULTA", "UNP", "UAL", "UPS", "URI", "UNH", "UHS", "VLO", "VTR", "VLTO",
    "VRSN", "VRSK", "VZ", "VRTX", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW", "WAB",
    "WBA", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST", "WDC", "WY",
    "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM", "ZBRA", "ZBH", "ZTS",
]
