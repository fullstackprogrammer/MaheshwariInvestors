# Investor Stock Analysis Dashboard

A responsive full-stack web application that analyzes investor stock picks and tracks 2026 performance using live market data from yfinance.

## Features

- **Dashboard**: Overview with top 5 investors and stocks by YTD performance
- **Investor Rankings**: Sortable table showing all investors with portfolio metrics
- **Stocks Overview**: Comprehensive stock analysis with filtering and sorting
- **Real-time Data**: Live market data from yfinance API
- **Dark Theme**: Beautiful dark mode interface by default
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## Tech Stack

### Backend
- Python 3.8+
- FastAPI
- yfinance (for stock data)
- pandas

### Frontend
- React 18
- Vite
- TailwindCSS
- Recharts (for future chart enhancements)

## Project Structure

```
MaheshwariInvestors/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── requirements.txt     # Python dependencies
│   └── .gitignore
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API service layer
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── index.html
├── data/
│   └── investors.csv        # Investor data (local file)
└── README.md
```

## Quick commit to GitHub

**Option 1 – Git aliases (set once, use in any repo)**

Run once (PowerShell or Git Bash):

```bash
# Add + commit (message is the next argument)
git config --global alias.ac "!git add -A && git commit -m \"$1\""

# Add + commit + push
git config --global alias.acp "!git add -A && git commit -m \"$1\" && git push"
```

Then from the repo root:

```bash
git ac "Fix API URL for maheshai.com"
git acp "Update deploy docs"
```

On Windows CMD/PowerShell, if the alias fails, use the script (Option 2) instead.

**Option 2 – Script (one command from repo root)**

```powershell
# PowerShell (Windows)
.\scripts\quick-commit.ps1 "Your commit message"
```

```bash
# Bash (WSL / Git Bash / macOS)
./scripts/quick-commit.sh "Your commit message"
```

**Option 3 – Cursor / VS Code**

- **Ctrl+Shift+G** → Source Control → stage all (click **+** next to Changes) → type message → **Ctrl+Enter** to commit → **Sync** or **Push**.

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Node.js 18 or higher
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (recommended):
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. Upgrade pip first (important for Windows):
```bash
python -m pip install --upgrade pip
```

4. Install dependencies:
```bash
# For Windows (use pre-built wheels to avoid compilation issues)
pip install --only-binary :all: -r requirements.txt

# For macOS/Linux (can build from source if needed)
pip install -r requirements.txt
```

4. Ensure the CSV file exists at `data/investors.csv` (relative to project root)

5. Start the FastAPI server:
```bash
uvicorn main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## CSV File Format

The `data/investors.csv` file should have the following format:

```
Investor Name,Stock1,Stock2,Stock3,Stock4,Stock5
Investor A,AAPL,MSFT,GOOGL,AMZN,TSLA
Investor B,MSFT,GOOGL,NVDA,AMD,INTC
...
```

**Important Notes:**
- Column 1: Original Investor Name (will be replaced with aliases)
- Columns 2-6: Stock symbols (some investors may have fewer than 5)
- Stock symbols should be valid ticker symbols
- The original investor names are never displayed in the UI

## API Endpoints

- `GET /` - API status
- `GET /investors` - Get all investors
- `GET /investors/rankings` - Get investor rankings with metrics
- `GET /stocks` - Get all stocks with metrics
- `GET /metrics` - Get aggregated dashboard metrics
- `POST /refresh-data` - Clear cache and refresh data

## Performance Metrics

The application calculates the following metrics:

- **Daily Return**: Percentage change from previous day
- **1 Month Return**: Percentage change over ~20 trading days
- **3 Month Return**: Percentage change over ~60 trading days
- **YTD Return**: Percentage change from January 1, 2026
- **CAGR**: Compound Annual Growth Rate (annualized)
- **Portfolio Value**: Current portfolio value in USD
- **Value Change**: Absolute and percentage change from initial $10,000

## Portfolio Logic

- Each investor starts with **$10,000**
- **Equal-weight portfolio**: Funds divided equally among selected stocks
- If an investor has fewer than 5 stocks, funds are divided among available stocks only
- Stock prices are tracked from **January 1, 2026** to current date
- Data is cached to minimize API calls

## Privacy

- Original investor names are **never displayed** in the UI
- Investor names are replaced with finance movie character aliases
- Alias mapping is stored in memory only (not persisted)
- CSV file remains local and static

## Future Enhancements

- Toggle between % and $ values
- Export tables as CSV
- Mini sparklines for stock prices
- Light mode toggle (dark mode is default)
- Additional chart visualizations

## Troubleshooting

### Backend Issues

- **CSV file not found**: Ensure `data/investors.csv` exists relative to the project root
- **yfinance errors**: Some stock symbols may be invalid or delisted. Check the console for error messages.
- **Port already in use**: Change the port in the uvicorn command: `--port 8001`

### Frontend Issues

- **CORS errors**: Ensure backend is running on port 8000 and CORS is configured correctly
- **API connection failed**: Check that backend is running and accessible at `http://localhost:8000`
- **Build errors**: Clear node_modules and reinstall: `rm -rf node_modules && npm install`

## License

This project is for educational and demonstration purposes.
