"""
Conservative CSP screener – large-cap universe (US, market cap ≥ $20B, liquid).
Sector-specific symbol lists used when user selects a sector (takes precedence over default universe).
"""
from typing import Dict, List

# Sector -> list of symbols to scan when that sector is selected (precedence over LARGE_CAP_UNIVERSE)
SECTOR_SYMBOLS: Dict[str, List[str]] = {
    "Energy": [
        "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "VLO", "PSX", "OXY", "HAL", "DVN", "HES",
        "PXD", "FANG", "OKE", "KMI", "WMB", "VICI", "EQT", "APA", "CTRA", "OVV", "CHRD",
        "HFC", "MTDR", "MGY", "SM", "CPE", "PR", "RRC", "SWN", "AR", "CHK", "DVN",
    ],
    "Technology": [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "AVGO", "ORCL", "CRM", "ADBE",
        "CSCO", "ACN", "AMD", "INTC", "QCOM", "TXN", "AMAT", "LRCX", "KLAC", "MU",
        "INTU", "IBM", "NOW", "SNOW", "PANW", "CRWD", "FTNT", "ADSK", "SNPS", "CDNS",
        "TEAM", "WDAY", "VEEV", "DDOG", "NET", "ZS", "MCHP", "MRVL", "LRCX", "ARM",
    ],
    "Healthcare": [
        "UNH", "JNJ", "LLY", "MRK", "ABBV", "TMO", "ABT", "DHR", "AMGN", "GILD",
        "BMY", "REGN", "MDT", "SYK", "BSX", "ZTS", "BDX", "HCA", "CI", "ISRG",
        "DXCM", "IDXX", "IQV", "EW", "HOLX", "MTD", "ALGN", "MOH", "CNC", "HUM",
    ],
    "Financial Services": [
        "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "SPGI", "BLK",
        "C", "AXP", "SCHW", "CB", "PGR", "MMC", "AON", "MET", "AIG", "TRV",
        "USB", "PNC", "COF", "BK", "STT", "NDAQ", "CME", "ICE", "MCO", "AFL",
    ],
    "Consumer Cyclical": [
        "AMZN", "TSLA", "HD", "NKE", "MCD", "SBUX", "LOW", "BKNG", "TJX", "ORLY",
        "GM", "F", "LEN", "DHI", "NVR", "PHM", "ROST", "DRI", "CMG", "YUM",
        "MAR", "HLT", "ABNB", "CCL", "RCL", "NCLH", "EXPE", "WYNN", "LVS", "EBAY",
    ],
    "Consumer Defensive": [
        "PG", "KO", "PEP", "COST", "WMT", "PM", "MDLZ", "CL", "KMB", "KHC",
        "GIS", "SJM", "HSY", "K", "CPB", "MKC", "STZ", "TAP", "BF-B", "LW",
    ],
    "Industrials": [
        "UNP", "HON", "UPS", "CAT", "DE", "RTX", "LMT", "GE", "BA", "ADP",
        "NOC", "GD", "EMR", "ITW", "MMM", "WM", "ETN", "ROK", "CARR", "OTIS",
        "PCAR", "FDX", "CSX", "NSC", "DOV", "IR", "TT", "GNRC", "PWR", "JCI",
    ],
    "Utilities": [
        "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "WEC", "ES",
        "ED", "AWK", "DTE", "EIX", "AEE", "CNP", "CMS", "NI", "NRG", "PEG",
        "EVRG", "LNT", "AES", "VST", "CEG", "PCG", "ETR", "FE", "ATO", "WTRG",
    ],
    "Real Estate": [
        "PLD", "AMT", "EQIX", "PSA", "CCI", "SPG", "O", "WELL", "DLR", "SBAC",
        "VTR", "ARE", "AVB", "EQR", "MAA", "UDR", "ESS", "INVH", "AMH", "SUI",
        "EXR", "FRT", "KIM", "REG", "NNN", "WPC", "IRM", "ADC", "HR", "VICI",
    ],
    "Basic Materials": [
        "LIN", "APD", "SHW", "ECL", "FCX", "NEM", "NUE", "STLD", "DD", "DOW",
        "PPG", "ALB", "CE", "EMN", "FMC", "CF", "MOS", "NTR", "LYB", "IP",
        "PKG", "WRK", "SEE", "VVV", "CBT", "AXTA", "CE", "WLK", "SMG", "IFF",
    ],
    "Communication Services": [
        "META", "GOOGL", "NFLX", "DIS", "CMCSA", "VZ", "T", "CHTR", "TMUS",
        "EA", "TTWO", "WBD", "PARA", "FOX", "FOXA", "NWS", "NWSA", "LUMN", "DISH",
    ],
}

# S&P 500–style large caps (US, NYSE/NASDAQ). Used when no sector selected.
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
    # Additional large caps to reach 300+ symbols
    "DIS", "NKE", "BA", "IBM", "COP", "PM", "LIN", "NOW", "ORCL", "MU",
    "AMAT", "LRCX", "PANW", "UBER", "NET", "CRWD", "ADSK", "SNOW", "FTNT", "CDNS",
    "ABNB", "MRVL", "MNST", "DXCM", "CPRT", "MCHP", "KLAC", "KDP", "AZO", "PCAR",
    "AEP", "DD", "EMR", "GM", "F", "VRSK", "ROST", "O", "CMG", "APD",
    "HLT", "MET", "PSX", "EOG", "SLB", "HES", "MPC", "VLO", "HAL", "DVN",
    "FCX", "NEM", "NUE", "STLD", "CEG", "AFL", "TRP", "APTV", "IQV", "IDXX",
    "FAST", "ODFL", "PAYX", "EXC", "XEL", "WEC", "ES", "ED", "AWK", "DTE",
    "EIX", "AEE", "CNP", "CMS", "NI", "NRG", "EBAY", "ETSY", "MELI", "BIDU",
    "JD", "PDD", "PYPL", "SQ", "COIN", "HOOD", "RBLX", "U", "DDOG", "ZS",
    "TEAM", "WDAY", "VEEV", "HUBS", "DOCU", "ZM", "OKTA", "MDB", "PLTR", "PATH",
    "NFLX", "CMCSA", "CHTR", "DIS", "WBD", "PARA", "FOX", "FOXA", "NWS", "NWSA",
    "TGT", "LOW", "HD", "COST", "WMT", "KR", "SYY", "TSCO", "BBY", "DKS",
    "ULTA", "ROST", "TJX", "DG", "DLTR", "FIVE", "BURL", "GPS", "ANF", "AEO",
    "M", "KSS", "JWN", "DILL", "WSM", "RH", "LEN", "DHI", "PHM", "NVR",
    "TOL", "MTH", "KBH", "MDC", "RYL", "HOV", "BECN", "BLD", "JCI", "CARR",
    "OTIS", "TT", "IR", "ETN", "ROK", "DOV", "ITW", "EMR", "GE", "HON",
    "CAT", "DE", "CNHI", "AGCO", "PWR", "GNRC", "J", "MMC", "AON", "WTW",
    "CB", "TRV", "ALL", "CINF", "AFG", "AIZ", "GL", "WRB", "BRO", "PGR",
    "AIG", "PRU", "MET", "AFL", "L", "C", "BAC", "WFC", "JPM", "GS", "MS",
    "SCHW", "BK", "STT", "NTRS", "FITB", "KEY", "HBAN", "CFG", "MTB", "ZION",
    "RF", "FHN", "CMA", "USB", "PNC", "COF", "AXP", "DFS", "SYF", "ALLY",
    "NDAQ", "CME", "ICE", "CBOE", "MSCI", "SPGI", "MCO", "FDS", "DUN", "VRSK",
    "BR", "ICE", "FIS", "GPN", "ADP", "PAYX", "EFX", "FLT", "WU", "PYPL",
    "V", "MA", "AXP", "COF", "DFS", "SYF", "NAVI", "SOFI", "UPST", "AFRM",
    "BX", "KKR", "APO", "CG", "ARES", "STEP", "GSBD", "OCSL", "FSK", "MAIN",
    "AMT", "PLD", "EQIX", "PSA", "CCI", "SBAC", "DLR", "WELL", "O", "SPG",
    "VTR", "ARE", "AVB", "EQR", "MAA", "UDR", "ESS", "INVH", "AMH", "SUI",
    "EXR", "LSI", "FRT", "KIM", "REG", "HR", "NNN", "ADC", "WPC", "IRM",
    "IP", "PKG", "WRK", "SEE", "AMCR", "IPGP", "GLW", "CE", "EMN", "DD",
    "DOW", "LYB", "PPG", "SHW", "ECL", "ALB", "FMC", "CF", "MOS", "NTR",
    "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "WEC", "ES",
    "ED", "AWK", "DTE", "EIX", "AEE", "CNP", "CMS", "NI", "NRG", "PEG",
    "EVRG", "LNT", "AES", "VST", "CEG", "PCG", "ETR", "FE", "AEE", "ATO",
    "HII", "LDOS", "NOC", "LMT", "RTX", "GD", "BA", "HWM", "TXT", "LHX",
    "CACI", "SAIC", "LDOS", "BAH", "FFIV", "AKAM", "GDDY", "WIX", "SHOP",
    "SQ", "ADBE", "CRM", "ORCL", "NOW", "SNOW", "WDAY", "TEAM", "VEEV", "HUBS",
    "DDOG", "NET", "ZS", "CRWD", "PANW", "FTNT", "CHKP", "OKTA", "CYBR", "TENB",
    "MCHP", "SWKS", "QRVO", "ON", "MPWR", "MRVL", "LSCC", "ALGM", "ARM", "AVGO",
    "TXN", "ADI", "INTC", "AMD", "QCOM", "NVDA", "AMAT", "LRCX", "KLAC", "ASML",
]
