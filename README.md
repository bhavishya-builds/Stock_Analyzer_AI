# StockWise AI — Setup & Run

## Fastest way (Windows)
Double-click **run.bat**. It creates a `.venv`, installs everything from `requirements.txt`, and starts the server. Then open **http://127.0.0.1:5000** in your browser.

## Running from PyCharm (fixing the most common error)
Your project screenshot shows the interpreter is the base **Python 3.11** system install, which does not have flask / yfinance / ta / plotly / scikit-learn. That causes `ModuleNotFoundError` when you press Run. Fix it like this:

1. File → Settings → Project: PythonProject1 → **Python Interpreter**
2. Click the gear → **Add Interpreter** → **Add Local Interpreter** → Virtualenv → New (location: the `.venv` folder inside this project) → OK
3. Open the PyCharm Terminal (it should show `(.venv)` at the start) and run:
   ```
   pip install -r requirements.txt
   ```
4. Right-click `app.py` → Run.

## Common runtime errors and what they mean
- **ModuleNotFoundError: No module named 'flask' (or 'ta', 'yfinance'...)** → packages aren't installed in the interpreter PyCharm is using. Follow the steps above.
- **AttributeError: module 'numpy' has no attribute 'NaN'** → old `ta` library with numpy 2.x. Run `pip install -U ta` (needs ta >= 0.11).
- **"Too Many Requests" / 429** → Yahoo Finance rate limit. Wait a minute; also `pip install -U yfinance` since old versions get blocked more often.
- **"No chart data found"** → wrong symbol or timeframe. Indian stocks need the `.NS` suffix (e.g. `RELIANCE.NS`, `TCS.NS`). Very short intraday timeframes (1 min) only work on trading days.

## Project structure
```
app.py            Flask routes, charts, recommendation engine
analysis.py       Indicators, education content, 5-year prediction model
patterns.py       Candlestick pattern detection + stop loss
templates/        cover.html (strategy select), index.html (dashboard)
static/css/       style.css
```
