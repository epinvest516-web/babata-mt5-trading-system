import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import sys
import os
import traceback
from datetime import datetime
import pytz

import config


def now_utc():
    return datetime.now(tz=pytz.UTC).strftime("%Y-%m-%d %H:%M:%S%z")


def log(msg: str):
    line = f"[{now_utc()}] {msg}"
    print(line, flush=True)


def log_err(msg: str):
    line = f"[{now_utc()}] {msg}"
    try:
        with open(config.ERROR_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def round_volume(v: float) -> float:
    step = config.VOLUME_STEP
    v = max(config.MIN_VOLUME, v)
    return round(round(v / step) * step, 2)


def weights_to_volumes(max_total: float):
    w = config.ENTRY_WEIGHTS
    vols = [round_volume(max_total * w[0]), round_volume(max_total * w[1]), round_volume(max_total * w[2])]
    # adjust to not exceed max_total due to rounding
    while sum(vols) > max_total + 1e-9:
        # reduce the last leg first
        if vols[2] > config.MIN_VOLUME:
            vols[2] = round_volume(vols[2] - config.VOLUME_STEP)
        elif vols[1] > config.MIN_VOLUME:
            vols[1] = round_volume(vols[1] - config.VOLUME_STEP)
        else:
            vols[0] = round_volume(vols[0] - config.VOLUME_STEP)
    return vols


def ema(series: pd.Series, period: int):
    return series.ewm(span=period, adjust=False).mean()


def atr(df: pd.DataFrame, period: int):
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calculate_rsi(close: pd.Series, period: int):
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calculate_bbands(close: pd.Series, period: int, std_dev: float):
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, lower


def now_local_dt():
    tz = pytz.timezone(config.LOCAL_TZ)
    return datetime.now(tz=tz)


def in_flat_window():
    dt = now_local_dt()
    flat_h, flat_m = map(int, config.DAILY_FLAT_HHMM.split(':'))
    flat_dt = dt.replace(hour=flat_h, minute=flat_m, second=0, microsecond=0)
    delta_min = (dt - flat_dt).total_seconds() / 60.0
    return 0 <= delta_min < config.NO_TRADE_MINUTES_AFTER_FLAT


class BabataTrader:
    def __init__(self):
        self.equity_start_of_day = None
        self.last_closed_bar_time = {}
        self.entry_plan = weights_to_volumes(config.MAX_VOLUME_PER_SYMBOL)
        self.last_entry_price = {}  # symbol -> last add price

    def connect(self):
        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        acc = mt5.account_info()
        if acc is None:
            raise RuntimeError("account_info() is None")
        self.equity_start_of_day = float(acc.equity)
        log(f"[INFO] Connected login={acc.login} balance={acc.balance} equity={acc.equity}")

        for s in config.SYMBOLS:
            info = mt5.symbol_info(s)
            if info is None:
                raise RuntimeError(f"symbol_info({s}) is None")
            if not info.visible:
                mt5.symbol_select(s, True)

        log(f"[PLAN] entry volumes per symbol={self.entry_plan} max_total={config.MAX_VOLUME_PER_SYMBOL}")

    def check_daily_dd(self):
        acc = mt5.account_info()
        if acc is None or self.equity_start_of_day is None:
            return True
        dd = (self.equity_start_of_day - float(acc.equity)) / self.equity_start_of_day
        if dd >= config.MAX_DAILY_DD_PCT:
            log_err(f"[ALERT] Daily DD hit {dd*100:.2f}% >= {config.MAX_DAILY_DD_PCT*100:.2f}%. Flat & stop.")
            self.close_all_positions()
            return False
        return True

    def close_all_positions(self):
        positions = mt5.positions_get()
        if not positions:
            return
        for pos in positions:
            tick = mt5.symbol_info_tick(pos.symbol)
            if tick is None:
                continue
            close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "price": price,
                "deviation": config.DEVIATION,
                "magic": config.MAGIC_NUMBER,
                "comment": "Babata Flat",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": config.FILLING_MODE,
            }
            mt5.order_send(req)

    def get_positions(self, symbol: str):
        pos = mt5.positions_get(symbol=symbol)
        return list(pos) if pos else []

    def total_volume(self, symbol: str):
        return sum(p.volume for p in self.get_positions(symbol))

    def get_data(self, symbol: str):
        rates = mt5.copy_rates_from_pos(symbol, config.TIMEFRAME, 0, 300)
        if rates is None:
            return None
        df = pd.DataFrame(rates)
        if df.empty:
            return None
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df["RSI"] = calculate_rsi(df["close"], config.RSI_PERIOD)
        df["BBU"], df["BBL"] = calculate_bbands(df["close"], config.BB_PERIOD, config.BB_DEV)
        df["ATR"] = atr(df, config.ATR_PERIOD)
        return df

    def send_order(self, symbol: str, order_type, volume: float, sl: float, tp: float, comment: str):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": config.DEVIATION,
            "magic": config.MAGIC_NUMBER,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": config.FILLING_MODE,
        }
        return mt5.order_send(req)

    def close_position(self, pos):
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "price": price,
            "deviation": config.DEVIATION,
            "magic": config.MAGIC_NUMBER,
            "comment": "Babata TP",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": config.FILLING_MODE,
        }
        mt5.order_send(req)

    def apply_trade_management(self, symbol: str, df: pd.DataFrame):
        """Handle TP1/TP2 and runner trailing using last closed candle."""
        positions = self.get_positions(symbol)
        if not positions:
            return

        info = mt5.symbol_info(symbol)
        if info is None:
            return
        point = info.point
        R = config.SL_POINTS * point

        last_closed = df.iloc[-2]
        trail_low = float(last_closed["low"])
        trail_high = float(last_closed["high"])

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return
        current = tick.bid  # use bid as conservative mark

        # Determine direction by first position
        direction = positions[0].type  # 0 buy, 1 sell
        # Average entry price
        avg_entry = sum(p.price_open * p.volume for p in positions) / sum(p.volume for p in positions)

        # profit in price units
        pnl = (current - avg_entry) if direction == mt5.ORDER_TYPE_BUY else (avg_entry - current)

        # TP1: >= 1R
        if pnl >= config.TP1_R * R and len(positions) >= 1:
            # close smallest ticket (or first) as TP1
            p = sorted(positions, key=lambda x: x.volume)[0]
            log(f"[TP1] closing 1st leg ticket={p.ticket} vol={p.volume}")
            self.close_position(p)

            # move remaining SL to breakeven for all positions
            remaining = self.get_positions(symbol)
            for rp in remaining:
                new_sl = avg_entry
                # update SL
                req = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": rp.ticket,
                    "sl": new_sl,
                    "tp": rp.tp,
                    "magic": config.MAGIC_NUMBER,
                    "comment": "Babata BE",
                }
                mt5.order_send(req)

        # TP2: >= 2R (close another leg if >1 position left)
        positions2 = self.get_positions(symbol)
        if pnl >= config.TP2_R * R and len(positions2) >= 2:
            p = sorted(positions2, key=lambda x: x.volume)[0]
            log(f"[TP2] closing 2nd leg ticket={p.ticket} vol={p.volume}")
            self.close_position(p)

        # Runner trailing: for last remaining position, trail SL to last closed candle low/high
        remaining = self.get_positions(symbol)
        if len(remaining) == 1:
            rp = remaining[0]
            if direction == mt5.ORDER_TYPE_BUY:
                new_sl = trail_low
                if rp.sl is None or rp.sl < new_sl:
                    req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": rp.ticket,
                        "sl": new_sl,
                        "tp": rp.tp,
                        "magic": config.MAGIC_NUMBER,
                        "comment": "Babata Trail",
                    }
                    mt5.order_send(req)
            else:
                new_sl = trail_high
                if rp.sl is None or rp.sl > new_sl:
                    req = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": rp.ticket,
                        "sl": new_sl,
                        "tp": rp.tp,
                        "magic": config.MAGIC_NUMBER,
                        "comment": "Babata Trail",
                    }
                    mt5.order_send(req)

    def maybe_enter_or_add(self, symbol: str, df: pd.DataFrame):
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            return
        point = info.point

        last = df.iloc[-2]  # closed bar
        rsi = float(last["RSI"])
        close = float(last["close"])
        bbu = float(last["BBU"])
        bbl = float(last["BBL"])
        atr_val = float(last["ATR"]) if not pd.isna(last["ATR"]) else None
        if atr_val is None:
            return

        buf = config.BAND_BUFFER_POINTS * point

        base_signal = None
        if rsi < config.RSI_LOWER and close <= (bbl + buf):
            base_signal = "BUY"
        elif rsi > config.RSI_UPPER and close >= (bbu - buf):
            base_signal = "SELL"

        # manage entries
        positions = self.get_positions(symbol)
        total_vol = sum(p.volume for p in positions) if positions else 0.0

        # Determine next planned volume based on how many legs already open
        legs_open = len(positions)
        if legs_open >= 3:
            return

        # If no position: require base signal
        if legs_open == 0:
            if not base_signal:
                log(f"[CHECK] {symbol} time={last['time']} no-signal rsi={rsi:.2f}")
                return

            # place leg1
            vol = self.entry_plan[0]
            sl = (tick.ask - config.SL_POINTS * point) if base_signal == "BUY" else (tick.bid + config.SL_POINTS * point)
            tp = (tick.ask + config.TP1_R * config.SL_POINTS * point) if base_signal == "BUY" else (tick.bid - config.TP1_R * config.SL_POINTS * point)
            order_type = mt5.ORDER_TYPE_BUY if base_signal == "BUY" else mt5.ORDER_TYPE_SELL
            res = self.send_order(symbol, order_type, vol, sl, tp, "Babata L1")
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                self.last_entry_price[symbol] = res.price
                log(f"[OK] ENTER L1 {base_signal} {symbol} vol={vol} price={res.price}")
            else:
                log_err(f"[ERROR] ENTER L1 failed {symbol} ret={getattr(res,'retcode',None)} comment={getattr(res,'comment',None)}")
            return

        # If have positions: only add if in profit by X = 0.6*ATR from last_entry_price
        direction = positions[0].type
        last_price = self.last_entry_price.get(symbol, positions[-1].price_open)
        X = config.PYRAMID_ATR_MULT * atr_val

        if direction == mt5.ORDER_TYPE_BUY:
            current = tick.bid
            if current < last_price + X:
                return
            add_type = mt5.ORDER_TYPE_BUY
            sl = current - config.SL_POINTS * point
            tp = current + config.TP2_R * config.SL_POINTS * point
        else:
            current = tick.ask
            if current > last_price - X:
                return
            add_type = mt5.ORDER_TYPE_SELL
            sl = current + config.SL_POINTS * point
            tp = current - config.TP2_R * config.SL_POINTS * point

        # respect volume cap
        next_vol = self.entry_plan[legs_open]
        if total_vol + next_vol > config.MAX_VOLUME_PER_SYMBOL + 1e-9:
            return

        res = self.send_order(symbol, add_type, next_vol, sl, tp, f"Babata L{legs_open+1}")
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            self.last_entry_price[symbol] = res.price
            log(f"[OK] ADD L{legs_open+1} {symbol} vol={next_vol} price={res.price} X={X:.5f}")
        else:
            log_err(f"[ERROR] ADD L{legs_open+1} failed {symbol} ret={getattr(res,'retcode',None)} comment={getattr(res,'comment',None)}")

    def run(self):
        self.connect()
        log(f"[SYSTEM] Started v2 TF=M30 fill=FOK maxVol/sym={config.MAX_VOLUME_PER_SYMBOL} weights={config.ENTRY_WEIGHTS} ATRmult={config.PYRAMID_ATR_MULT} DD={config.MAX_DAILY_DD_PCT*100:.1f}%")

        while True:
            if in_flat_window():
                log(f"[FLAT] {config.LOCAL_TZ} {config.DAILY_FLAT_HHMM} closing all positions and blocking entries")
                self.close_all_positions()
                time.sleep(30)
                continue

            if not self.check_daily_dd():
                time.sleep(60)
                continue

            for symbol in config.SYMBOLS:
                rates3 = mt5.copy_rates_from_pos(symbol, config.TIMEFRAME, 0, 3)
                if rates3 is None or len(rates3) < 3:
                    continue
                closed_bar_time = int(rates3[-2]["time"])
                if self.last_closed_bar_time.get(symbol) == closed_bar_time:
                    continue
                self.last_closed_bar_time[symbol] = closed_bar_time

                df = self.get_data(symbol)
                if df is None:
                    continue

                # 1) Manage existing positions
                self.apply_trade_management(symbol, df)
                # 2) Enter or pyramid-add
                self.maybe_enter_or_add(symbol, df)

            time.sleep(config.POLL_SECONDS)


def main():
    try:
        os.makedirs(os.path.dirname(config.LOG_PATH), exist_ok=True)
        BabataTrader().run()
    except KeyboardInterrupt:
        log("[SYSTEM] Stopped by user")
    except Exception as e:
        log_err(f"[FATAL] {e}")
        log_err(traceback.format_exc())
        raise
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
