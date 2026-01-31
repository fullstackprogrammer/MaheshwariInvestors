# Windows Installation Guide

If you're encountering build errors when installing dependencies on Windows, follow these steps:

## Problem
Windows may try to build numpy/pandas from source, which requires C compilers (Visual Studio Build Tools). This often fails with errors like:
```
error: metadata-generation-failed
Running `clang-cl /?` gave "[WinError 2] The system cannot find the file specified"
```

## Solution

### Option 1: Use Pre-built Wheels (Recommended)

```bash
# Navigate to backend directory
cd backend

# Activate virtual environment
venv\Scripts\activate

# Upgrade pip first
python -m pip install --upgrade pip

# Install using pre-built wheels only (no compilation needed)
pip install --only-binary :all: -r requirements.txt
```

### Option 2: Install Individual Packages

If Option 1 doesn't work, install packages individually:

```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install numpy first (has pre-built wheels)
pip install numpy

# Install pandas (depends on numpy)
pip install pandas

# Install other packages
pip install fastapi uvicorn[standard] yfinance python-multipart
```

### Option 3: Use Conda (Alternative)

If you have Anaconda/Miniconda installed:

```bash
# Create conda environment
conda create -n investor-analysis python=3.10
conda activate investor-analysis

# Install packages via conda (handles Windows builds better)
conda install pandas numpy
pip install fastapi uvicorn[standard] yfinance python-multipart
```

### Option 4: Install Visual Studio Build Tools

If you need to build from source (not recommended):

1. Download and install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)
2. Select "Desktop development with C++" workload
3. Then run: `pip install -r requirements.txt`

## Verify Installation

After installation, verify everything works:

```bash
python -c "import pandas; import numpy; import fastapi; print('All packages installed successfully!')"
```

## Still Having Issues?

- Make sure you're using Python 3.8 or higher
- Try using Python 3.10 or 3.11 (better wheel support)
- Check that you're in the virtual environment
- Try installing packages one at a time to identify the problematic package
