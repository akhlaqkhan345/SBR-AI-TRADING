import warnings
warnings.filterwarnings("ignore")

import os
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytz
import requests
import yfinance as yf


# ==========================================
# TELEGRAM CONFIGURATION
# ==========================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

if not CHAT_ID:
    raise RuntimeError("CHAT_ID is not set")


def send_telegram_message(message):
    try:
        url = (
            f"https://api.telegram.org/"
            f"bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        )

        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }

        response = requests.post(
            url,
            json=payload,
            timeout=15
        )

        data = response.json()

        if response.status_code != 200 or not data.get("ok"):
            print("Telegram Error:", data)
            return False

        print("📲 Telegram signal sent.")
        return True

    except Exception as e:
        print("Telegram Error:", e)
        return False


# ==========================================
# TIMEZONE
# ==========================================

LOCAL_TIMEZONE = pytz.timezone("Asia/Karachi")


# ==========================================
# SIGNAL ENGINE
# ==========================================

class SBR_ProfitableEngine:

    def __init__(self):
        self.signal_count = 0

    def get_real_data(self, asset="AUDUSD=X"):

        try:
            df = yf.download(
                asset,
                period="1d",
                interval="1m",
                progress=False,
                threads=False,
                auto_adjust=True
            )

            if df is not None and len(df) >= 20:
                return df

        except Exception as e:
            print(f"Data Error {asset}: {e}")

        return None

    def get_profitable_signal(self, asset="AUDUSD=X"):

        df = self.get_real_data(asset)

        if df is None or len(df) < 20:
            return {
                "signal": "WAIT",
                "direction": "wait",
                "confidence": 0
            }

        close = df["Close"].values.astype(float).ravel()
        high = df["High"].values.astype(float).ravel()
        low = df["Low"].values.astype(float).ravel()

        current_price = float(close[-1])

        # EMA
        ema_short = (
            pd.Series(close)
            .ewm(span=10, adjust=False)
            .mean()
            .iloc[-1]
        )

        ema_long = (
            pd.Series(close)
            .ewm(span=20, adjust=False)
            .mean()
            .iloc[-1]
        )

        # RSI
        deltas = np.diff(close[-15:])

        gains = [d for d in deltas if d > 0]
        losses = [abs(d) for d in deltas if d < 0]

        avg_gain = sum(gains) / 14 if gains else 0
        avg_loss = sum(losses) / 14 if losses else 0

        if avg_loss > 0:
            rsi = 100 - (
                100 / (1 + (avg_gain / avg_loss))
            )
        else:
            rsi = 50

        # Support / Resistance
        support = float(min(low[-20:]))
        resistance = float(max(high[-20:]))

        # Momentum
        momentum_up = (
            close[-1] > close[-2] > close[-3]
        )

        momentum_down = (
            close[-1] < close[-2] < close[-3]
        )

        buy_score = 0
        sell_score = 0

        # EMA
        if ema_short > ema_long * 1.002:
            buy_score += 2

        elif ema_short < ema_long * 0.998:
            sell_score += 2

        # RSI
        if rsi < 25:
            buy_score += 2

        elif rsi > 75:
            sell_score += 2

        elif rsi < 35:
            buy_score += 1

        elif rsi > 65:
            sell_score += 1

        # Support / Resistance
        if current_price <= support * 1.002:
            buy_score += 2

        elif current_price >= resistance * 0.998:
            sell_score += 2

        elif current_price <= support * 1.005:
            buy_score += 1

        elif current_price >= resistance * 0.995:
            sell_score += 1

        # Momentum
        if momentum_up:
            buy_score += 1

        elif momentum_down:
            sell_score += 1

        total_weight = 7

        confidence = (
            max(buy_score, sell_score)
            / total_weight
        ) * 100

        # SIGNAL RULES UNCHANGED
        if buy_score >= 4:

            return {
                "signal": "CALL / UP 🟢",
                "direction": "call",
                "confidence": confidence,
                "price": current_price,
                "rsi": rsi,
                "buy_score": buy_score,
                "sell_score": sell_score,
                "strength": (
                    "STRONG"
                    if confidence >= 80
                    else "NORMAL"
                )
            }

        elif sell_score >= 4:

            return {
                "signal": "PUT / DOWN 🔴",
                "direction": "put",
                "confidence": confidence,
                "price": current_price,
                "rsi": rsi,
                "buy_score": buy_score,
                "sell_score": sell_score,
                "strength": (
                    "STRONG"
                    if confidence >= 80
                    else "NORMAL"
                )
            }

        return {
            "signal": "WAIT",
            "direction": "wait",
            "confidence": confidence,
            "price": current_price,
            "rsi": rsi,
            "buy_score": buy_score,
            "sell_score": sell_score
        }


# ==========================================
# MONITOR
# ==========================================

def start_monitor():

    engine = SBR_ProfitableEngine()

    all_pairs = [
        "EURUSD=X",
        "GBPUSD=X",
        "USDJPY=X",
        "AUDUSD=X",
        "USDCAD=X",
        "USDCHF=X",
        "NZDUSD=X",
        "EURJPY=X",
        "GBPJPY=X",
        "EURGBP=X"
    ]

    print("=" * 55)
    print("🔥 SBR AI BINARY MONITOR")
    print("⏰ Target: 5 seconds before new candle")
    print("🕐 Timezone: Pakistan Standard Time")
    print("=" * 55)

    last_scan_minute = None
    last_signal_time = None

    while True:

        now_local = datetime.now(LOCAL_TIMEZONE)

        # Target: :55 of every minute
        if now_local.second == 55:

            current_minute = (
                now_local.strftime("%Y-%m-%d %H:%M")
            )

            if current_minute == last_scan_minute:
                time.sleep(0.2)
                continue

            last_scan_minute = current_minute

            print(
                f"\n🔎 Scan: "
                f"{now_local.strftime('%I:%M:%S %p')} PKT"
            )

            best_signal = None
            best_confidence = -1
            best_asset = None

            for asset in all_pairs:

                # Minimum gap between signals
                if last_signal_time is not None:

                    time_diff = (
                        now_local - last_signal_time
                    ).total_seconds()

                    if time_diff < 110:
                        continue

                signal = engine.get_profitable_signal(asset)

                print(
                    f"{asset.replace('=X', ''):<10} | "
                    f"{signal['signal']:<15} | "
                    f"Confidence: "
                    f"{signal['confidence']:.1f}%"
                )

                if (
                    signal["direction"] != "wait"
                    and signal["confidence"] >= 40
                ):

                    if (
                        signal["confidence"]
                        > best_confidence
                    ):

                        best_confidence = (
                            signal["confidence"]
                        )

                        best_signal = signal
                        best_asset = asset

            # ======================================
            # SEND BEST SIGNAL
            # ======================================

            if best_signal is not None:

                last_signal_time = now_local
                engine.signal_count += 1

                pair_name = best_asset.replace("=X", "")

                signal_time = now_local.strftime(
                    "%I:%M:%S %p"
                )

                entry_dt = (
                    now_local
                    + timedelta(seconds=5)
                )

                expiry_dt = (
                    entry_dt
                    + timedelta(minutes=1)
                )

                entry_time = entry_dt.strftime(
                    "%I:%M:%S %p"
                )

                expiry_time = expiry_dt.strftime(
                    "%I:%M:%S %p"
                )

                telegram_msg = (
                    f"🔥 *SBR AI SIGNAL* 🔥\n"
                    f"-----------------------------\n"
                    f"🕐 *Signal*: {signal_time}\n"
                    f"📊 *Asset*: {pair_name}\n"
                    f"🚀 *Direction*: "
                    f"{best_signal['signal']}\n"
                    f"📈 *Confidence*: "
                    f"{best_signal['confidence']:.0f}%\n"
                    f"⚡ *Strength*: "
                    f"{best_signal['strength']}\n"
                    f"⏰ *Entry*: {entry_time}\n"
                    f"⏳ *Expiry*: {expiry_time}\n"
                    f"💵 *Price*: "
                    f"${best_signal['price']:.5f}\n"
                    f"🔢 *Scores*: "
                    f"Buy {best_signal['buy_score']}/7 | "
                    f"Sell {best_signal['sell_score']}/7"
                )

                print("\n🔥 SIGNAL FOUND")
                print(telegram_msg)

                send_telegram_message(
                    telegram_msg
                )

            else:

                print(
                    "⏳ No eligible signal this candle."
                )

        time.sleep(0.15)


# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    start_monitor()
