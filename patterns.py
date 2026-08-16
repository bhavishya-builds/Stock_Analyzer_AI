# patterns.py (Example content - your actual file might vary)

import pandas as pd
import numpy as np

def is_hammer(open_p, high, low, close):
    """
    Checks for a Hammer candlestick pattern.
    A hammer is a bullish reversal pattern.
    - Small body (open and close are close)
    - Long lower shadow (at least twice the body length)
    - Little or no upper shadow
    """
    body = abs(close - open_p)
    lower_shadow = min(open_p, close) - low
    upper_shadow = high - max(open_p, close)

    return (body > 0 and
            lower_shadow >= 2 * body and
            upper_shadow < 0.2 * body)

def is_doji(open_p, high, low, close, tolerance=0.001):
    """
    Checks for a Doji candlestick pattern.
    Open and Close prices are very close, indicating indecision.
    """
    return abs(open_p - close) <= (open_p * tolerance)

def is_dragonfly_doji(open_p, high, low, close, tolerance=0.001):
    """
    Checks for a Dragonfly Doji candlestick pattern.
    Open, high, and close are very close to each other, with a long lower shadow.
    Bullish reversal pattern.
    """
    body_is_doji = abs(open_p - close) <= (open_p * tolerance)
    no_upper_shadow = high - max(open_p, close) < (open_p * tolerance)
    long_lower_shadow = min(open_p, close) - low > 2 * abs(open_p - close) # Lower shadow significantly larger than body

    return body_is_doji and no_upper_shadow and long_lower_shadow

def is_gravestone_doji(open_p, high, low, close, tolerance=0.001):
    """
    Checks for a Gravestone Doji candlestick pattern.
    Open, low, and close are very close to each other, with a long upper shadow.
    Bearish reversal pattern.
    """
    body_is_doji = abs(open_p - close) <= (open_p * tolerance)
    no_lower_shadow = min(open_p, close) - low < (open_p * tolerance)
    long_upper_shadow = high - max(open_p, close) > 2 * abs(open_p - close) # Upper shadow significantly larger than body

    return body_is_doji and no_lower_shadow and long_upper_shadow

def find_stop_loss(data, num_candles=10):
    """
    Calculates a simple stop loss based on the lowest low of the last N candles.
    """
    if data.empty or len(data) < num_candles:
        return np.nan # Not enough data

    # Get the 'Low' prices for the last 'num_candles'
    recent_lows = data['Low'].iloc[-num_candles:]

    # Ensure all values in recent_lows are numeric before finding min
    recent_lows = pd.to_numeric(recent_lows, errors='coerce').dropna()

    if recent_lows.empty:
        return np.nan # No valid lows

    return recent_lows.min()