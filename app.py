# Streamlit app for manual backtesting with TQQQ/SQQQ
import streamlit as st
import pandas as pd
import numpy as np
import random
import time
import os
import yfinance as yf
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# Parameters
POSITION_SIZE = 2_000_000

# Load historical 1-minute data from yfinance (cache for faster dev)
@st.cache_data
def get_intraday_data(ticker, date):
    start = datetime.strptime(date, "%Y-%m-%d")
    end = start + timedelta(days=1)
    data = yf.download(ticker, start=start, end=end, interval="1m", progress=False)
    if data.empty:
        return None
    data = data.between_time("09:30", "16:00")
    data.reset_index(inplace=True)
    return data

# Randomly select 50 tradeable dates (2023–2024 for example)
@st.cache_data
def get_random_dates(n=50):
    base = datetime(2023, 1, 1)
    dates = [(base + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(365)]
    return random.sample(dates, n)

# Initialize session state
if 'trade_data' not in st.session_state:
    st.session_state.trade_data = []
    st.session_state.dates = get_random_dates()
    st.session_state.current_day = 0
    st.session_state.running = False
    st.session_state.entered = False
    st.session_state.ticker = None
    st.session_state.entry_price = None
    st.session_state.entry_time = None

# TP/SL sliders
st.sidebar.title("Settings")
TP_PCT = st.sidebar.slider("Take Profit %", min_value=0.5, max_value=5.0, value=1.5, step=0.1) / 100
SL_PCT = st.sidebar.slider("Stop Loss %", min_value=0.2, max_value=5.0, value=0.5, step=0.1) / 100

st.title("Manual Backtesting Simulator: TQQQ vs SQQQ")

# Start simulation
if st.button("Start Next Day"):
    if st.session_state.current_day < len(st.session_state.dates):
        st.session_state.running = True
        st.session_state.entered = False
        st.session_state.ticker = None
        st.session_state.entry_price = None
        st.session_state.entry_time = None
        st.session_state.data = None

# Simulation logic
if st.session_state.running and not st.session_state.entered:
    date = st.session_state.dates[st.session_state.current_day]
    tqqq_data = get_intraday_data("TQQQ", date)
    sqqq_data = get_intraday_data("SQQQ", date)

    if tqqq_data is None or sqqq_data is None:
        st.write(f"Skipping {date} due to missing data.")
        st.session_state.current_day += 1
        st.session_state.running = False
    else:
        st.write(f"### {date} - Market Open")
        for i in range(len(tqqq_data)):
            with st.empty():
                st.write(f"Time: {tqqq_data.loc[i, 'Datetime'].strftime('%H:%M')} | TQQQ Price: ${tqqq_data.loc[i, 'Open']:.2f} | SQQQ Price: ${sqqq_data.loc[i, 'Open']:.2f}")
                if not st.session_state.entered:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Enter TQQQ", key=f"t{i}"):
                            st.session_state.ticker = "TQQQ"
                            st.session_state.entry_price = tqqq_data.loc[i, 'Open']
                            st.session_state.entry_time = tqqq_data.loc[i, 'Datetime']
                            st.session_state.data = tqqq_data.iloc[i:].copy()
                            st.session_state.entered = True
                    with col2:
                        if st.button("Enter SQQQ", key=f"s{i}"):
                            st.session_state.ticker = "SQQQ"
                            st.session_state.entry_price = sqqq_data.loc[i, 'Open']
                            st.session_state.entry_time = sqqq_data.loc[i, 'Datetime']
                            st.session_state.data = sqqq_data.iloc[i:].copy()
                            st.session_state.entered = True
                time.sleep(5)
            if st.session_state.entered:
                break

# After trade is entered
if st.session_state.entered:
    tp = st.session_state.entry_price * (1 + TP_PCT)
    sl = st.session_state.entry_price * (1 - SL_PCT)
    result = None
    exit_price = None

    for idx, row in st.session_state.data.iterrows():
        if row['High'] >= tp:
            result = 'Win'
            exit_price = tp
            break
        elif row['Low'] <= sl:
            result = 'Loss'
            exit_price = sl
            break

    if not result:
        result = 'No TP/SL Hit'
        exit_price = st.session_state.data.iloc[-1]['Close']

    pnl = (exit_price - st.session_state.entry_price) * POSITION_SIZE / st.session_state.entry_price
    st.session_state.trade_data.append({
        "Date": st.session_state.dates[st.session_state.current_day],
        "Ticker": st.session_state.ticker,
        "Entry Time": st.session_state.entry_time,
        "Entry Price": st.session_state.entry_price,
        "Exit Price": exit_price,
        "Result": result,
        "PnL ($)": round(pnl, 2)
    })

    st.write(f"## Trade Result: {result} | PnL: ${pnl:,.2f}")

    # Plot chart with entry, TP, SL
    st.write("### Trade Visualization")
    chart_data = st.session_state.data.copy()
    chart_data.set_index("Datetime", inplace=True)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(chart_data['Close'], label='Price')
    ax.axhline(st.session_state.entry_price, color='blue', linestyle='--', label='Entry')
    ax.axhline(tp, color='green', linestyle='--', label='Take Profit')
    ax.axhline(sl, color='red', linestyle='--', label='Stop Loss')
    ax.set_title(f"{st.session_state.ticker} Trade on {st.session_state.dates[st.session_state.current_day]}")
    ax.legend()
    st.pyplot(fig)

    st.session_state.current_day += 1
    st.session_state.running = False
    st.session_state.entered = False

# Summary after all days
if st.session_state.current_day >= 50:
    st.write("# Simulation Complete - Final Results")
    results_df = pd.DataFrame(st.session_state.trade_data)
    st.dataframe(results_df)
    st.write(f"### Total PnL: ${results_df['PnL ($)'].sum():,.2f}")
    st.write(f"### Win Rate: {round((results_df['Result'] == 'Win').mean() * 100, 2)}%")

    st.write("### Equity Curve")
    results_df['Cumulative PnL'] = results_df['PnL ($)'].cumsum()
    fig2, ax2 = plt.subplots()
    ax2.plot(results_df['Cumulative PnL'], label='Equity Curve')
    ax2.set_title("Cumulative Profit Over Time")
    ax2.set_ylabel("Cumulative PnL ($)")
    ax2.set_xlabel("Trade Number")
    ax2.legend()
    st.pyplot(fig2)
