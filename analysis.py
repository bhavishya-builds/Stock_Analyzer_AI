import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import numpy as np
import datetime as dt

# Make sure patterns.py is in the same directory or accessible
from patterns import is_hammer, is_doji, is_dragonfly_doji, is_gravestone_doji, find_stop_loss

# --- NEW: Educational Content Database ---
# We store all our teaching content here
EDUCATION_CONTENT = {
    "RSI": {
        "image_url": "https://i.imgur.com/L7bV9jN.png",  # Placeholder image for RSI
        "education": "RSI stands for Relative Strength Index. It's a momentum indicator that measures the speed and change of price movements. It moves between 0 and 100.",
        "how_to_use": "Traders look for two key levels: <b>70 (Overbought)</b> and <b>30 (Oversold)</b>. A stock at 70 might be too expensive and due for a drop. A stock at 30 might be too cheap and due for a rise. We show this on the 'Pro View' chart."
    },
    "EMA": {
        "image_url": "https://i.imgur.com/v1k1A8A.png",  # Placeholder image for EMA Crossover
        "education": "EMA stands for Exponential Moving Average. It's a line on the chart that smooths out price data to show the trend. We use a fast line (9-period) and a slow line (21-period).",
        "how_to_use": "When the <b>Fast (yellow) line crosses ABOVE the Slow (blue) line</b>, it's a 'Bullish Crossover' (a buy signal). When it crosses <b>BELOW</b>, it's a 'Bearish Crossover' (a sell signal). You can see this on the 'Pro View' chart."
    },
    "PATTERN": {
        "image_url": "https://i.imgur.com/G3GvQyv.png",  # Placeholder image for Candlestick
        "education": "A candlestick shows 4 pieces of data: the Open, High, Low, and Close price for a time period. A green 'body' means the price closed higher than it opened. A red 'body' means it closed lower.",
        "how_to_use": "Traders look for special shapes, or 'patterns', that can hint at where the price might go next."
    },
    "HAMMER": {
        "image_url": "https://i.imgur.com/nIo0bY8.png",  # Placeholder image for Hammer
        "education": "A Hammer is a bullish reversal pattern. It has a small body at the top and a long lower 'wick' (at least 2x the body).",
        "how_to_use": "This pattern shows that sellers tried to push the price way down, but a strong wave of buyers stepped in and pushed the price all the way back up. This is a sign of strength and suggests a potential upward move."
    },
    "GRAVESTONE_DOJI": {
        "image_url": "https://i.imgur.com/p8xN87w.png",  # Placeholder image for Gravestone
        "education": "A Gravestone Doji is a bearish reversal pattern. It looks like an upside-down 'T'. The open, low, and close prices are all near the low of the day.",
        "how_to_use": "This pattern shows that buyers pushed the price up, but sellers took control and pushed it all the way back down. This is a sign of weakness and suggests a potential downward move."
    },
    "DRAGONFLY_DOJI": {
        "image_url": "https://i.imgur.com/nIo0bY8.png",
        "education": "A Dragonfly Doji is a bullish reversal pattern. The open, high, and close are all near the top, with a long lower 'wick' below.",
        "how_to_use": "Sellers pushed the price down hard, but buyers fought back and closed the price right where it opened. After a downtrend, this hints the price may reverse upward."
    },
    "DOJI": {
        "image_url": "https://i.imgur.com/G3GvQyv.png",
        "education": "A Doji forms when the open and close prices are nearly equal, creating a very thin body. It signals indecision in the market.",
        "how_to_use": "Neither buyers nor sellers won this round. A Doji alone isn't a buy or sell signal — wait for the next candle to confirm the direction."
    },
}


# ===== Prediction Model (MORE ACCURATE) =====
def predict_price(symbol):
    """
    (NEW) This model is now DECOUPLED from the chart data.
    It *always* trains on a stable 5-year daily dataset for better accuracy.
    """
    try:
        # 1. Fetch a stable, 5-year daily dataset for the model
        end_date = dt.datetime.now()
        start_date = end_date - dt.timedelta(days=5 * 365)

        model_data = yf.Ticker(symbol).history(start=start_date, end=end_date, interval="1d")

        if model_data.empty or len(model_data) < 100:  # Need significant data
            print(f"DEBUG: predict_price - Not enough 5y data for {symbol}.")
            return None

        df = model_data.copy()

        # 2. Feature Engineering
        df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
        df['EMA9'] = EMAIndicator(df['Close'], window=9).ema_indicator()
        df['EMA21'] = EMAIndicator(df['Close'], window=21).ema_indicator()
        df['Prediction_Target'] = df['Close'].shift(-1)
        df.dropna(inplace=True)

        if len(df) < 50:
            print("DEBUG: predict_price - Not enough valid 5y data after indicators.")
            return None

        features = ['Close', 'RSI', 'EMA9', 'EMA21']
        X = np.array(df[features])
        y = np.array(df['Prediction_Target'])

        # 3. Train Model
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)
        model = LinearRegression()
        model.fit(X_train, y_train)

        # 4. Predict based on the *very latest* data
        latest_features = np.array(df.iloc[-1][features]).reshape(1, -1)

        if np.isnan(latest_features).any():
            print("DEBUG: predict_price - NaN values in latest features.")
            return None

        predicted_price = model.predict(latest_features)[0]
        return predicted_price

    except Exception as e:
        print(f"DEBUG: Error in predict_price for {symbol}: {e}")
        return None


# ===== Fetch and Analyze (UPDATED with Educational Content) =====
def fetch_and_analyze(symbol, timeframe_selection='7d_1d'):
    try:
        period, interval = timeframe_selection.split('_')
    except ValueError:
        period = "7d"
        interval = "1d"
    print(f"DEBUG: Fetching chart data for {symbol} with period={period}, interval={interval}")

    stop_loss_candles = 10

    try:
        # 1. Fetch CHART data (for user to see)
        data = yf.Ticker(symbol).history(interval=interval, period=period)
        if data.empty:
            raise Exception(f"No chart data found for {symbol} with {interval} interval over {period} period.")
    except Exception as e:
        print(f"DEBUG: Failed to fetch chart data for {symbol}: {e}")
        raise Exception(f"Failed to fetch chart data: {e}. Please check the symbol or timeframe.")

    data = data.sort_index()
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors='coerce')
    data.dropna(subset=numeric_cols, inplace=True)

    if data.empty:
        raise Exception("No valid numerical chart data remaining after cleaning.")

    latest = data.iloc[-1]
    open_p, high, low, close, volume = float(latest['Open']), float(latest['High']), float(latest['Low']), float(
        latest['Close']), float(latest['Volume'])

    # --- RSI Calculation ---
    rsi_values = RSIIndicator(close=data['Close'], window=14).rsi()
    rsi = rsi_values.iloc[-1] if not rsi_values.empty and pd.notna(rsi_values.iloc[-1]) else np.nan
    rsi_education = EDUCATION_CONTENT["RSI"]
    if pd.isna(rsi):
        rsi_signal_pro = "RSI: Not available"
        rsi_analysis_simple = "We don't have enough data to check the stock's momentum."
        rsi_signal_simple = "N/A"
    elif rsi > 70:
        rsi_signal_pro = f"{rsi:.2f} → <b>Overbought!</b>"
        rsi_analysis_simple = "This stock seems 'Overbought' (or expensive) right now. Be cautious."
        rsi_signal_simple = "Overbought 👎"
    elif rsi < 30:
        rsi_signal_pro = f"{rsi:.2f} → <b>Oversold!</b>"
        rsi_analysis_simple = "This stock seems 'Oversold' (or cheap) right now. It might be a potential opportunity."
        rsi_signal_simple = "Oversold 👍"
    else:
        rsi_signal_pro = f"{rsi:.2f} → Neutral"
        rsi_analysis_simple = "The stock's price momentum is neutral (not too hot, not too cold)."
        rsi_signal_simple = "Neutral 😐"

    # --- EMA Calculation ---
    ema9_values = EMAIndicator(close=data['Close'], window=9).ema_indicator()
    ema21_values = EMAIndicator(close=data['Close'], window=21).ema_indicator()
    ema9 = ema9_values.iloc[-1] if not ema9_values.empty and pd.notna(ema9_values.iloc[-1]) else np.nan
    ema21 = ema21_values.iloc[-1] if not ema21_values.empty and pd.notna(ema21_values.iloc[-1]) else np.nan
    ema_education = EDUCATION_CONTENT["EMA"]
    if pd.isna(ema9) or pd.isna(ema21):
        ema_signal_pro = "EMA: Not available"
        ema_analysis_simple = "We don't have enough data to see the stock's trend."
        ema_signal_simple = "N/A"
    elif ema9 > ema21:
        ema_signal_pro = "<b>Bullish trend!</b> ✅ (EMA9 > EMA21)"
        ema_analysis_simple = "The stock is in an 'Upward Trend,' which is a good sign."
        ema_signal_simple = "Upward Trend ✅"
    else:
        ema_signal_pro = "<b>Bearish trend!</b> ❌ (EMA9 < EMA21)"
        ema_analysis_simple = "The stock is in a 'Downward Trend,' which is a warning sign."
        ema_signal_simple = "Downward Trend ❌"

    # --- Stop Loss Calculation ---
    stop_loss = find_stop_loss(data, num_candles=stop_loss_candles)
    if pd.isna(stop_loss) or stop_loss <= 0:
        stop_loss = close * 0.95
    stop_loss_analysis_pro = f"This is the lowest low of the last {stop_loss_candles} candles, a common quick exit point for risk management."
    stop_loss_analysis_simple = "A suggested 'safety net' price. If the stock falls to this level, selling can help prevent further losses."

    # --- Candlestick Pattern Detection ---
    pattern_education = EDUCATION_CONTENT["PATTERN"]  # Default
    pattern_name = "None"
    pattern_signal_pro = "No strong candle pattern detected."
    pattern_signal_simple = "No special pattern."
    if is_hammer(open_p, high, low, close):
        pattern_name = "Hammer"
        pattern_signal_pro = "Hammer pattern detected! (Bullish)"
        pattern_signal_simple = "Hammer (Bullish) 👍"
        pattern_education = EDUCATION_CONTENT["HAMMER"]
    elif is_dragonfly_doji(open_p, high, low, close):
        pattern_name = "Dragonfly Doji"
        pattern_signal_pro = "Dragonfly Doji detected! (Bullish)"
        pattern_signal_simple = "Dragonfly Doji (Bullish) 👍"
        pattern_education = EDUCATION_CONTENT["DRAGONFLY_DOJI"]
    elif is_gravestone_doji(open_p, high, low, close):
        pattern_name = "Gravestone Doji"
        pattern_signal_pro = "Gravestone Doji detected! (Bearish)"
        pattern_signal_simple = "Gravestone Doji (Bearish) 👎"
        pattern_education = EDUCATION_CONTENT["GRAVESTONE_DOJI"]
    elif is_doji(open_p, high, low, close):
        pattern_name = "Doji"
        pattern_signal_pro = "Doji detected! (Indecision)"
        pattern_signal_simple = "Doji (Indecision) 😐"
        pattern_education = EDUCATION_CONTENT["DOJI"]

    # --- Volume Analysis ---
    volume_analysis_pro = ""
    volume_analysis_simple = ""
    if not data['Volume'].empty and pd.notna(volume) and volume > 0:
        avg_volume = data['Volume'].mean()
        if avg_volume == 0:
            volume_analysis_pro = "Average volume is zero; cannot perform comparative analysis."
            volume_analysis_simple = "No volume data to compare."
        elif volume > 1.5 * avg_volume:
            volume_analysis_pro = f"Current volume ({volume:,.0f}) is significantly higher than average ({avg_volume:,.0f}), indicating strong interest/activity."
            volume_analysis_simple = f"Volume is {((volume / avg_volume) - 1):.0%} higher than average. (High interest)"
        elif volume < 0.5 * avg_volume:
            volume_analysis_pro = f"Current volume ({volume:,.0f}) is significantly lower than average ({avg_volume:,.0f}), indicating low interest/activity."
            volume_analysis_simple = f"Volume is {((avg_volume - volume) / avg_volume):.0%} lower than average. (Low interest)"
        else:
            volume_analysis_pro = f"Current volume ({volume:,.0f}) is near average ({avg_volume:,.0f}), indicating normal activity."
            volume_analysis_simple = "Volume is about average."
    else:
        volume_analysis_pro = "Volume data not available for analysis or is zero."
        volume_analysis_simple = "No volume data."

    # --- Price Prediction (NOW MORE ACCURATE) ---
    # We call the *new* predict_price function which uses 5Y of data
    predicted_price = predict_price(symbol)

    prediction_text = f"₹{predicted_price:.2f}" if predicted_price is not None else "Prediction not available."
    prediction_analysis_pro = ""
    prediction_analysis_simple = ""
    if predicted_price is not None and close > 0:
        price_difference = predicted_price - close
        percentage_change = (price_difference / close) * 100
        direction_text = "upward" if percentage_change >= 0 else "downward"
        direction_arrow = "↑" if percentage_change >= 0 else "↓"

        prediction_analysis_pro = f"Stable 5-year regression model predicts a change by <span class='{'positive' if percentage_change >= 0 else 'negative'}'>{direction_arrow}{abs(percentage_change):.2f}%</span>. This suggests a potential {direction_text} movement for the next daily candle."
        prediction_analysis_simple = f"Our model (trained on 5 years of data) suggests the price might move {direction_text} next. (This is just a guess, not a guarantee!)"
    else:
        prediction_analysis_pro = "Prediction model requires more historical data or could not be calculated for this stock."
        prediction_analysis_simple = "We don't have enough data to make a price prediction."

    return {
        "latest_price": close,
        "data": data,  # Full dataframe for charting
        "rsi_values": rsi_values,  # Full RSI series for charting
        "ema9_values": ema9_values,  # Full EMA9 series for charting
        "ema21_values": ema21_values,  # Full EMA21 series for charting

        "rsi_signal_pro": rsi_signal_pro,
        "rsi_signal_simple": rsi_signal_simple,
        "rsi_analysis_simple": rsi_analysis_simple,
        "rsi_education": rsi_education,

        "ema_signal_pro": ema_signal_pro,
        "ema_signal_simple": ema_signal_simple,
        "ema_analysis_simple": ema_analysis_simple,
        "ema_education": ema_education,

        "pattern_name": pattern_name,  # "Hammer", "Doji", etc.
        "pattern_signal_pro": pattern_signal_pro,
        "pattern_signal_simple": pattern_signal_simple,
        "pattern_education": pattern_education,

        "stop_loss": stop_loss,
        "stop_loss_analysis_pro": stop_loss_analysis_pro,
        "stop_loss_analysis_simple": stop_loss_analysis_simple,

        "predicted_price_text": prediction_text,
        "prediction_analysis_pro": prediction_analysis_pro,
        "prediction_analysis_simple": prediction_analysis_simple,

        "volume_text": f"{volume:,.0f}",
        "volume_analysis_pro": volume_analysis_pro,
        "volume_analysis_simple": volume_analysis_simple,
    }