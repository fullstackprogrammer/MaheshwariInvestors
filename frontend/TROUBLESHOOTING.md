# Frontend Troubleshooting Guide

## Issue: Frontend Stuck on Loading Screen

If the frontend at http://localhost:5173 keeps showing "Loading...", follow these steps:

### 1. Check Backend is Running

Open a new terminal and verify the backend is running:

```bash
# Check if backend is accessible
curl http://localhost:8000
# Or visit in browser: http://localhost:8000
```

You should see:
```json
{"message":"Investor Stock Analysis API","status":"running"}
```

### 2. Check Browser Console

Open browser DevTools (F12) and check the Console tab for errors:
- CORS errors
- Network errors
- API timeout errors

### 3. Check Network Tab

In DevTools, go to Network tab:
- Look for requests to `http://localhost:8000/metrics`
- Check if they're pending, failed, or timing out
- Check the response status code

### 4. Common Issues

#### Backend Not Running
**Solution**: Start the backend server
```bash
cd backend
venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

#### Backend Taking Too Long
The backend might be slow because:
- yfinance API is slow or failing
- First request fetches all stock data (can take 30+ seconds)

**Solution**: 
- Wait a bit longer (first load can take 30-60 seconds)
- Check backend console for errors
- The frontend has a 30-second timeout

#### CORS Errors
**Solution**: Ensure backend CORS is configured correctly in `backend/main.py`

#### Port Conflicts
**Solution**: 
- Check if port 8000 is already in use
- Check if port 5173 is already in use
- Change ports if needed

### 5. Quick Test

Test the API directly:
```bash
# Test root endpoint
curl http://localhost:8000

# Test metrics endpoint (may take a while)
curl http://localhost:8000/metrics
```

### 6. Reset Everything

If nothing works:
1. Stop both frontend and backend (Ctrl+C)
2. Restart backend first
3. Wait for "Loaded X investors" message
4. Restart frontend
5. Wait 30-60 seconds for first load

### 7. Check Backend Logs

Look at the backend terminal for:
- "Loaded X investors" message
- yfinance errors
- Any Python exceptions

The backend should show:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
Loaded 15 investors
```

If you see yfinance errors, the backend is still working but some stocks may fail to load.
