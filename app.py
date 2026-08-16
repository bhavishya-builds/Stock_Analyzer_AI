from flask import Flask, render_template, request, jsonify
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import yfinance as yf
import traceback

# Make sure analysis.py is in the same directory or accessible in PYTHONPATH
from analysis import fetch_and_analyze
from patterns import find_stop_loss  # Import explicitly for consistency

app = Flask(__name__)

# Global stores for persistent state
initial_price_store = {}
alarm_triggered_store = {}
alarm_price_store = {}


# --- Helper Function for Take Profit ---
def find_take_profit(entry_price, stop_loss, rr_ratio=1.5):
    """
    Calculates a simple take-profit based on a Risk-Reward ratio.
    """
    if pd.isna(entry_price) or pd.isna(stop_loss):
        return np.nan
    risk = entry_price - stop_loss
    if risk <= 0:
        return entry_price * 1.05
    take_profit = entry_price + (risk * rr_ratio)
    return round(take_profit, 2)


# --- End Helper Function ---


@app.route('/')
def cover_page():
    return render_template('cover.html')


@app.route('/analyzer')
def analyzer_page():
    strategy = request.args.get('strategy', 'day_trading')
    return render_template('index.html', initial_strategy=strategy)


@app.route('/validate_symbol', methods=['GET'])
def validate_symbol():
    # This function is unchanged
    symbol = request.args.get('symbol', '').upper()
    if not symbol:
        return jsonify({'valid': False, 'message': 'Symbol cannot be empty'})
    try:
        ticker = yf.Ticker(symbol)
        # ticker.info is unreliable in newer yfinance versions; a tiny
        # history call is the most robust way to validate a symbol.
        hist = ticker.history(period="5d", interval="1d")
        if hist is not None and not hist.empty:
            return jsonify({'valid': True, 'message': f'Symbol "{symbol}" is valid.'})
        return jsonify({'valid': False, 'message': f'Symbol "{symbol}" not found or invalid.'})
    except Exception:
        return jsonify({'valid': False, 'message': f'Symbol "{symbol}" not found or invalid.'})


@app.route('/analyze_stock', methods=['GET'])
def analyze_stock():
    symbol = request.args.get('symbol', '').upper()
    timeframe_selection = request.args.get('timeframe_selection', '7d_1d')
    alarm_price_str = request.args.get('alarm_price')
    investment_amount_str = request.args.get('investment_amount')

    investment_amount = None
    try:
        if investment_amount_str:
            investment_amount = float(investment_amount_str)
            if investment_amount <= 0:
                investment_amount = None
    except ValueError:
        investment_amount = None

    if symbol not in initial_price_store:
        initial_price_store[symbol] = None
        alarm_triggered_store[symbol] = False

    try:
        alarm_price_store[symbol] = float(alarm_price_str) if alarm_price_str else None
    except ValueError:
        alarm_price_store[symbol] = None

    try:
        # 1. FETCH ALL ANALYSIS DATA (Simple, Pro, Education)
        result = fetch_and_analyze(symbol, timeframe_selection)
        price = result["latest_price"]
        stop_loss = result["stop_loss"]

        take_profit = find_take_profit(price, stop_loss, rr_ratio=1.5)
        recommendation_obj = get_recommendation_text(result, price)  # Get Simple/Pro text

        # 2. POSITION SIZING
        suggested_shares = "N/A"
        position_sizing_analysis_pro = "Enter an investment amount and get a 'Strong Bullish' signal to calculate shares."
        position_sizing_analysis_simple = "Enter an investment amount to see how many shares you could consider."
        profit_loss_estimate = "N/A"

        if investment_amount is not None and ('Strong Bullish' in recommendation_obj["pro"]):
            risk_per_share = price - stop_loss
            if risk_per_share > 0:
                max_risk_amount = investment_amount * 0.02
                shares_to_buy = int(np.floor(max_risk_amount / risk_per_share))
                max_shares_by_amount = int(np.floor(investment_amount / price))
                final_shares = min(shares_to_buy, max_shares_by_amount)

                if final_shares > 0:
                    suggested_shares = f"{final_shares:,} shares"
                    total_cost = final_shares * price
                    risk_at_stop_loss = final_shares * risk_per_share
                    profit_at_target = final_shares * (take_profit - price) if not pd.isna(take_profit) else 0.0

                    position_sizing_analysis_pro = (
                        f"Based on your ₹{investment_amount:,.0f} and a recommended 2% risk rule (₹{max_risk_amount:,.2f}), "
                        f"you can purchase <strong>{final_shares:,} shares</strong> at a cost of ₹{total_cost:,.2f}. "
                        f"Your maximum risk at the Stop Loss is ₹{risk_at_stop_loss:,.2f}."
                    )
                    position_sizing_analysis_simple = (
                        f"With ₹{investment_amount:,.0f}, you could consider buying <strong>{final_shares:,} shares</strong> (based on a 2% risk rule)."
                    )
                    profit_loss_estimate = (
                        f"Est. Loss (Stop Loss @ ₹{stop_loss:.2f}): <span class='negative'>-₹{risk_at_stop_loss:,.2f}</span> / "
                        f"Est. Profit (Target @ ₹{take_profit:.2f}): <span class='positive'>+₹{profit_at_target:,.2f}</span>"
                    )
                else:
                    suggested_shares = "0 shares"
                    position_sizing_analysis_pro = "Risk per share is too high, or investment amount too low to meet the 2% risk rule."
                    position_sizing_analysis_simple = "Risk per share seems too high for your investment amount."
            else:
                position_sizing_analysis_pro = "Cannot calculate position size: Price is below or equal to the calculated stop-loss, indicating high risk."
                position_sizing_analysis_simple = "Cannot calculate shares. The suggested safety net is above the current price."
        elif investment_amount is not None:
            suggested_shares = "0 shares"
            position_sizing_analysis_pro = "Not suggesting purchase: Requires a 'Strong Bullish' signal for position sizing."
            position_sizing_analysis_simple = "Not suggesting a purchase right now. The signal isn't strong enough."

        # 3. ALARM STATUS
        alarm_status = "No alarm"
        if initial_price_store[symbol] is None:
            initial_price_store[symbol] = price
            alarm_triggered_store[symbol] = False
        change = ((price - initial_price_store[symbol]) / initial_price_store[symbol]) * 100 if initial_price_store[
                                                                                                    symbol] not in [0,
                                                                                                                    None] else 0
        if not pd.isna(price) and not pd.isna(initial_price_store[symbol]):
            if abs(change) >= 2.0 and not alarm_triggered_store[symbol]:
                alarm_status = f"Price Alert! Price moved {'UP' if change >= 0 else 'DOWN'} by {abs(change):.2f}%"
                alarm_triggered_store[symbol] = True
            elif abs(change) < 2.0 and alarm_triggered_store[symbol]:
                alarm_triggered_store[symbol] = False
        user_alarm = alarm_price_store.get(symbol)
        if user_alarm is not None:
            if price >= user_alarm:
                alarm_status = f"TARGET PRICE REACHED: {symbol} at ₹{price:.2f}"
            elif alarm_status == "No alarm":
                alarm_status = f"Alarm set at ₹{user_alarm:.2f}"

        # 4. PREPARE JSON RESPONSE
        response_analysis = {
            "latest_price_text": f"{price:.2f}",
            "latest_price_analysis": f"Change since session start: {'↑' if change >= 0 else '↓'}{abs(change):.2f}%",
            "price_change_percent": change,

            "overall_recommendation_pro": recommendation_obj["pro"],
            "overall_recommendation_simple": recommendation_obj["simple"],

            "rsi_signal_pro": result['rsi_signal_pro'],
            "rsi_signal_simple": result['rsi_signal_simple'],
            "rsi_analysis_simple": result['rsi_analysis_simple'],
            "rsi_education": result['rsi_education'],  # Pass education object

            "ema_signal_pro": result['ema_signal_pro'],
            "ema_signal_simple": result['ema_signal_simple'],
            "ema_analysis_simple": result['ema_analysis_simple'],
            "ema_education": result['ema_education'],  # Pass education object

            "stop_loss": f"₹{result['stop_loss']:.2f}",
            "stop_loss_analysis_pro": result['stop_loss_analysis_pro'],
            "stop_loss_analysis_simple": result['stop_loss_analysis_simple'],

            "take_profit": f"₹{take_profit:.2f}" if not pd.isna(take_profit) else "N/A",
            "profit_loss_estimate": profit_loss_estimate,

            "predicted_price_text": result['predicted_price_text'],
            "prediction_analysis_pro": result['prediction_analysis_pro'],
            "prediction_analysis_simple": result['prediction_analysis_simple'],

            "pattern_signal_pro": result['pattern_signal_pro'],
            "pattern_signal_simple": result['pattern_signal_simple'],
            "pattern_education": result['pattern_education'],  # Pass education object

            "volume_text": result['volume_text'],
            "volume_analysis_pro": result['volume_analysis_pro'],
            "volume_analysis_simple": result['volume_analysis_simple'],

            "suggested_shares": suggested_shares,
            "position_sizing_analysis_pro": position_sizing_analysis_pro,
            "position_sizing_analysis_simple": position_sizing_analysis_simple,

            "bullish_stocks_html": get_bullish_stocks_live_data(),
        }

        # 5. CHART GENERATION (NOW WITH 3-PART PRO CHART)
        chart_data = result["data"]
        fig_json_pro = ""
        fig_json_simple = ""

        if not chart_data.empty:
            display_chart_title_part = get_chart_title_part(timeframe_selection)
            chart_title = f"{symbol} ({display_chart_title_part})"

            # --- FIG 1: Pro Chart (Candlestick + Volume + RSI) ---
            fig_pro = make_subplots(
                rows=3, cols=1, shared_xaxes=True,
                vertical_spacing=0.03,
                row_heights=[0.6, 0.2, 0.2]  # 60% Price, 20% Volume, 20% RSI
            )

            # Row 1: Candlestick + EMAs
            fig_pro.add_trace(go.Candlestick(x=chart_data.index, open=chart_data['Open'], high=chart_data['High'],
                                             low=chart_data['Low'], close=chart_data['Close'], name='Candlestick'),
                              row=1, col=1)
            fig_pro.add_trace(go.Scatter(x=chart_data.index, y=result['ema9_values'], mode='lines', name='EMA 9',
                                         line=dict(color='yellow', width=1)), row=1, col=1)
            fig_pro.add_trace(go.Scatter(x=chart_data.index, y=result['ema21_values'], mode='lines', name='EMA 21',
                                         line=dict(color='cyan', width=1)), row=1, col=1)

            # --- NEW: Add Pattern Annotation ---
            pattern_name = result["pattern_name"]
            if pattern_name != "None":
                last_candle_time = chart_data.index[-1]
                last_candle_low = chart_data['Low'].iloc[-1]
                fig_pro.add_annotation(
                    x=last_candle_time,
                    y=last_candle_low,
                    text=f"← {pattern_name}",  # Arrow pointing left
                    showarrow=True, arrowhead=1, ax=60, ay=-20,  # Adjust position
                    font=dict(color="yellow", size=14),
                    bgcolor="#2a3440"
                )

            # Row 2: Volume
            volume_color = ['rgba(16, 185, 129, 0.7)' if c >= o else 'rgba(239, 68, 68, 0.7)' for o, c in
                            zip(chart_data['Open'], chart_data['Close'])]
            fig_pro.add_trace(
                go.Bar(x=chart_data.index, y=chart_data['Volume'], name='Volume', marker_color=volume_color), row=2,
                col=1)

            # --- NEW: Row 3: RSI Chart ---
            fig_pro.add_trace(go.Scatter(x=chart_data.index, y=result['rsi_values'], mode='lines', name='RSI',
                                         line=dict(color='#f59e0b', width=2)), row=3, col=1)
            # Add Overbought/Oversold zones
            fig_pro.add_hrect(y0=70, y1=100, line_width=0, fillcolor='rgba(239, 68, 68, 0.2)', opacity=0.3, row=3,
                              col=1)
            fig_pro.add_hrect(y0=0, y1=30, line_width=0, fillcolor='rgba(16, 185, 129, 0.2)', opacity=0.3, row=3, col=1)

            # Layout
            fig_pro.update_layout(title_text=f"{chart_title} - Pro View (Candlestick, Volume, RSI)",
                                  xaxis_rangeslider_visible=False, height=800, template="plotly_dark",
                                  plot_bgcolor="#2c3847", paper_bgcolor="#2c3847", font=dict(color="#f1f1f1"),
                                  legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig_pro.update_yaxes(title_text="Price", row=1, col=1)
            fig_pro.update_yaxes(title_text="Volume", row=2, col=1)
            fig_pro.update_yaxes(title_text="RSI", row=3, col=1, range=[0, 100])  # Fix RSI scale
            fig_json_pro = pio.to_json(fig_pro, pretty=True)

            # --- FIG 2: Simple Chart (Line) ---
            fig_simple = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            line_color = 'rgba(16, 185, 129, 1)' if change >= 0 else 'rgba(239, 68, 68, 1)'
            fig_simple.add_trace(go.Scatter(x=chart_data.index, y=chart_data['Close'], mode='lines', name='Price',
                                            line=dict(color=line_color, width=2)), row=1, col=1)
            fig_simple.add_trace(
                go.Bar(x=chart_data.index, y=chart_data['Volume'], name='Volume', marker_color=volume_color), row=2,
                col=1)

            # Add annotation to simple chart too
            if pattern_name != "None":
                fig_simple.add_annotation(x=chart_data.index[-1], y=chart_data['Close'].iloc[-1],
                                          text=f"← {pattern_name}", showarrow=True, arrowhead=1, ax=60, ay=-20,
                                          font=dict(color="yellow", size=14), bgcolor="#2a3440")

            fig_simple.update_layout(title_text=f"{chart_title} - Simple View (Price Line)",
                                     xaxis_rangeslider_visible=False, height=600, template="plotly_dark",
                                     plot_bgcolor="#2c3847", paper_bgcolor="#2c3847", font=dict(color="#f1f1f1"),
                                     legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig_simple.update_yaxes(title_text="Price", row=1, col=1)
            fig_simple.update_yaxes(title_text="Volume", row=2, col=1)
            fig_json_simple = pio.to_json(fig_simple, pretty=True)

        return jsonify({
            'success': True,
            'analysis': response_analysis,
            'chart_json_pro': fig_json_pro,
            'chart_json_simple': fig_json_simple,
            'alarm_status': alarm_status
        })

    except Exception as e:
        traceback.print_exc()
        msg = str(e)
        if 'Too Many Requests' in msg or '429' in msg:
            msg = ("Yahoo Finance is rate-limiting requests right now. "
                   "Wait a minute and try again (avoid clicking Analyze repeatedly).")
        elif 'No chart data' in msg or 'no data' in msg.lower():
            msg = (f"No data found for '{symbol}' with that timeframe. "
                   "Check the symbol (Indian stocks need .NS, e.g. RELIANCE.NS) "
                   "or try a longer timeframe.")
        return jsonify({
            'success': False,
            'error_message': msg
        })


# --- Helper Functions ---
def get_recommendation_text(result, price):
    """(UPDATED) Returns an object with 'simple' and 'pro' recommendations."""
    buy_signals = 0
    sell_signals = 0

    # 1. EMA
    if "Bullish" in result.get("ema_signal_pro", ""):
        buy_signals += 1
    elif "Bearish" in result.get("ema_signal_pro", ""):
        sell_signals += 1

    # 2. RSI
    if "Oversold" in result.get("rsi_signal_pro", ""):
        buy_signals += 1
    elif "Overbought" in result.get("rsi_signal_pro", ""):
        sell_signals += 1

    # 3. Pattern
    pattern = result.get("pattern_signal_pro", "")
    if "Bullish" in pattern:
        buy_signals += 1
    elif "Bearish" in pattern:
        sell_signals += 1

    # 4. Prediction
    if result["predicted_price_text"] != "Prediction not available.":
        try:
            numeric_predicted_price = float(result["predicted_price_text"].replace('₹', ''))
            if numeric_predicted_price > price * 1.005:  # Require at least 0.5% up move
                buy_signals += 0.5
            elif numeric_predicted_price < price * 0.995:  # Require 0.5% down move
                sell_signals += 0.5
        except (ValueError, IndexError):
            pass

    # 5. Volume
    if 'higher than average' in result.get("volume_analysis_pro", "") and (buy_signals > 0 or sell_signals > 0):
        # High volume confirms the existing signals
        if buy_signals > sell_signals:
            buy_signals += 0.5
        else:
            sell_signals += 0.5

    # Recommendation Logic
    if buy_signals >= 3.0:
        return {
            "pro": "<strong>Strong Bullish (BUY).</strong> Multiple indicators (Trend, Momentum, Pattern) confirm a strong potential upward trend. Exercise risk management.",
            "simple": "👍 <strong>Looks Good (Potential Buy).</strong> Our analysis suggests this stock is in a strong upward trend. (This is not financial advice.)"
        }
    elif buy_signals > sell_signals and buy_signals >= 2.0:
        return {
            "pro": "<strong>Moderate Bullish (Monitor).</strong> The general sentiment is positive, but signals are mixed. Consider entering with a tight stop-loss.",
            "simple": "🙂 <strong>Looking Positive (Monitor).</strong> Signs are mostly good, but it's not a strong signal. It's best to watch this stock."
        }
    elif sell_signals >= 3.0:
        return {
            "pro": "<strong>Strong Bearish (SELL/AVOID).</strong> Multiple indicators suggest strong downward momentum. Avoid entry or consider a bearish strategy.",
            "simple": "👎 <strong>Looks Bad (Potential Sell/Avoid).</strong> Our analysis suggests this stock is in a strong downward trend. Be careful."
        }
    elif sell_signals > buy_signals and sell_signals >= 2.0:
        return {
            "pro": "<strong>Moderate Bearish (Caution).</strong> The general sentiment is negative. Avoid new entry until clearer bullish signals emerge.",
            "simple": "🤔 <strong>Use Caution (Monitor).</strong> Signs are mostly negative. It's best to wait for a positive change."
        }
    else:
        return {
            "pro": "<strong>Neutral (Hold/Wait).</strong> The signals are balanced or non-existent. It is best to wait for a clearer trend or momentum signal.",
            "simple": "😐 <strong>Neutral (Wait).</strong> The market seems undecided on this stock. It's best to wait for a clearer sign."
        }


def get_chart_title_part(timeframe_selection):
    # This function is unchanged
    mapping = {
        "1d_1m": "1 Day (1 Min candles)", "5d_5m": "5 Days (5 Min candles)", "1mo_30m": "1 Month (30 Min candles)",
        "6mo_1h": "6 Months (1 Hour candles)", "1y_1d": "1 Year (Daily candles)", "2y_1d": "2 Years (Daily candles)",
        "5y_1d": "5 Years (Daily candles)", "ytd_1d": "Year To Date (Daily candles)",
        "max_1d": "Max Available (Daily candles)",
        "7d_1d": "Last 7 Days (Daily candles)",
    }
    return mapping.get(timeframe_selection, timeframe_selection)


def get_bullish_stocks_live_data():
    # This function is unchanged
    symbols = ['TCS.NS', 'RELIANCE.NS', 'INFY.NS', 'HDFCBANK.NS']
    try:
        data = yf.download(symbols, period="3d", interval="1d", progress=False)
        if data.empty or 'Close' not in data.columns:
            return "<em>Could not fetch live stock suggestions. Data is empty.</em>"

        if isinstance(data['Close'], pd.DataFrame):
            latest_close = data['Close'].iloc[-1].fillna(data['Close'].iloc[-2])
            prev_close = data['Close'].iloc[-2].fillna(data['Close'].iloc[-3])
        else:
            return "<em>Data structure error in live feed.</em>"

        valid_prev_close = prev_close.replace(0, np.nan)
        daily_change = ((latest_close - prev_close) / valid_prev_close) * 100

        suggestions_df = pd.DataFrame({'Price': latest_close, 'Change': daily_change}).dropna()
        suggestions_df = suggestions_df.sort_values(by='Change', ascending=False).head(3)

        html_output = []
        for symbol, row in suggestions_df.iterrows():
            display_symbol = symbol.split('.')[0]
            change_text = f"{'+' if row['Change'] >= 0 else ''}{row['Change']:.2f}%"
            color_class = 'positive' if row['Change'] >= 0 else 'negative'
            html_output.append(
                f"- <strong>{display_symbol}</strong> (<span class='{color_class}'>{change_text}</span> @ ₹{row['Price']:.2f})"
            )
        if not html_output:
            return "<em>No live bullish stocks found today.</em>"

        html_output.append("<br><em>*Live data based on daily change of pre-selected symbols.</em>")
        return "<br>".join(html_output)

    except Exception as e:
        print(f"Error in get_bullish_stocks_live_data: {e}")
        return "<em>Could not fetch live stock suggestions. Check API access or symbols.</em>"


if __name__ == '__main__':
    print("\n  StockWise AI running -> open http://127.0.0.1:5000 in your browser\n")
    app.run(host='0.0.0.0', port=5000, debug=True)