# Quick Start Guide

## Prerequisites Check

Before starting, ensure you have:
- ✅ Python 3.8+ installed (`python --version`)
- ✅ Node.js 18+ installed (`node --version`)
- ✅ npm or yarn installed

## Step-by-Step Setup

### 1. Backend Setup (Terminal 1)

```bash
# Navigate to backend directory
cd backend

# Create virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# Create virtual environment (macOS/Linux)
python3 -m venv venv
source venv/bin/activate

# Upgrade pip first (important for Windows)
python -m pip install --upgrade pip

# Install dependencies (use --only-binary to avoid building from source)
pip install --only-binary :all: -r requirements.txt

# Start the server
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 2. Frontend Setup (Terminal 2)

Open a new terminal window:

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

You should see:
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

### 3. Access the Application

Open your browser and navigate to:
- **Frontend**: http://localhost:5173
- **Backend API Docs**: http://localhost:8000/docs

## Verify Everything Works

1. Check backend is running: Visit http://localhost:8000 - you should see a JSON response
2. Check frontend loads: Visit http://localhost:5173 - you should see the dashboard
3. Check data loads: The dashboard should display investor and stock data

## Troubleshooting

### Backend won't start
- Check if port 8000 is already in use
- Verify Python version: `python --version` (needs 3.8+)
- Check CSV file exists at `data/investors.csv`

### Frontend won't start
- Check if port 5173 is already in use
- Verify Node.js version: `node --version` (needs 18+)
- Try deleting `node_modules` and running `npm install` again

### No data showing
- Check browser console for errors (F12)
- Verify backend is running and accessible
- Check network tab for API call failures
- Some stock symbols might be invalid - check backend console for errors

### CORS errors
- Ensure backend is running on port 8000
- Check CORS settings in `backend/main.py`

## Next Steps

- Customize the CSV file in `data/investors.csv` with your own investor data
- Explore the API at http://localhost:8000/docs
- Check the README.md for detailed documentation
