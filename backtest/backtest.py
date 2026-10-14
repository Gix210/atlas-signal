"""Backtest of the /atlas level rules on intraday bars.

Replays the command's rules bar by bar: at the close of each bar it builds the
long and short setups from the 100 bars the command would have seen, then walks
forward through the rest of the session to see which level price reaches first.

Usage:
    python3 backtest.py spy_15m.json --symbol-class etf

Input is a JSON array of [unix_seconds, open, high, low, close, volume] bars,
as written by export_bars.js. Only the standard library is used.
"""

import argparse
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BUFFER = {"etf": 0.0005, "stock": 0.0015, "crypto": 0.0025}
LOOKBACK = 100      # bars the command reads
SWING_WINDOW = 20   # bars used for recent high/low and swing points
SESSION_GAP = 3600  # a gap longer than this starts a new session
ET = ZoneInfo("America/New_York")


def ema(values, length):
    k = 2 / (length + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def session_starts(bars):
    """Index of the first bar of the session each bar belongs to."""
    starts, cur = [], 0
    for i, b in enumerate(bars):
        if i > 0 and b[0] - bars[i - 1][0] > SESSION_GAP:
            cur = i
        starts.append(cur)
    return starts


def second_extreme(window, kind):
    """2nd-highest local high / 2nd-lowest local low, excluding the last 2 bars.

    A local high is a bar whose high is above both neighbours. Falls back to
    the single extreme when fewer than two swing points exist.
    """
    idx = 2 if kind == "high" else 3
    vals = [b[idx] for b in window[:-2]]
    pts = []
    for i in range(1, len(vals) - 1):
        if kind == "high" and vals[i] > vals[i - 1] and vals[i] > vals[i + 1]:
            pts.append(vals[i])
        if kind == "low" and vals[i] < vals[i - 1] and vals[i] < vals[i + 1]:
            pts.append(vals[i])
    if not pts:
        return max(vals) if kind == "high" else min(vals)
    pts.sort(reverse=(kind == "high"))
    return pts[1] if len(pts) > 1 else pts[0]


def levels(bars, i, sess_start, buf_pct):
    """Long and short setups exactly as the command defines them."""
    hist = bars[max(0, i - LOOKBACK + 1): i + 1]
    closes = [b[4] for b in hist]
    price = closes[-1]
    buf = price * buf_pct

    session = bars[sess_start: i + 1]
    pv = sum((b[2] + b[3] + b[4]) / 3 * b[5] for b in session)
    vv = sum(b[5] for b in session)
    vwap = pv / vv if vv else price
    e9, e20 = ema(closes, 9), ema(closes, 20)

    window = hist[-SWING_WINDOW:]
    recent_high = max(b[2] for b in window)
    recent_low = min(b[3] for b in window)
    prior_high = second_extreme(window, "high")
    prior_low = second_extreme(window, "low")

    # Long
    le = max(price, e9) + buf
    if price < vwap:
        ltp1 = vwap
    else:
        cands = [c for c in (prior_high, le * 1.003) if c > le]
        ltp1 = min(cands) if cands else None
    ltp2 = max(recent_high, le * 1.006)
    lsl = min(e20, prior_low) - buf

    # Short (mirror)
    se = min(price, e9) - buf
    if price > vwap:
        stp1 = vwap
    else:
        cands = [c for c in (prior_low, se * 0.997) if c < se]
        stp1 = max(cands) if cands else None
    stp2 = min(recent_low, se * 0.994)
    ssl = max(e20, prior_high) + buf

    return {
        "long": {"entry": le, "tp1": ltp1, "tp2": ltp2, "sl": lsl},
        "short": {"entry": se, "tp1": stp1, "tp2": stp2, "sl": ssl},
        "price": price, "vwap": vwap,
    }


def validity(side, lv):
    e, tp1, sl = lv["entry"], lv["tp1"], lv["sl"]
    if tp1 is None:
        return "no TP1 beyond entry"
    if side == "long":
        if tp1 <= e:
            return "TP1 at or below entry"
        if sl >= e:
            return "SL at or above entry"
    else:
        if tp1 >= e:
            return "TP1 at or above entry"
        if sl <= e:
            return "SL at or below entry"
    return None


def simulate(bars, i, sess_end, side, lv):
    """Walk forward to the session close.

    Entry is a stop order at `entry`. On the bar that fills it, only the stop
    can be hit (conservative: the bar's order of highs and lows is unknown).
    When TP and SL fall inside the same later bar, the stop is assumed first.
    Returns (outcome, R multiple, reached TP2 before SL).
    """
    e, tp1, tp2, sl = lv["entry"], lv["tp1"], lv["tp2"], lv["sl"]
    risk = abs(e - sl)
    filled = False
    for j in range(i + 1, sess_end + 1):
        h, l, c = bars[j][2], bars[j][3], bars[j][4]
        if not filled:
            if (side == "long" and h >= e) or (side == "short" and l <= e):
                filled = True
                if (side == "long" and l <= sl) or (side == "short" and h >= sl):
                    return "stop", -1.0, False
            continue
        stop = l <= sl if side == "long" else h >= sl
        t1 = h >= tp1 if side == "long" else l <= tp1
        t2 = h >= tp2 if side == "long" else l <= tp2
        if stop:
            return "stop", -1.0, False
        if t1:
            if t2:
                return "tp1", abs(tp1 - e) / risk, True
            # keep walking only to learn whether TP2 is reached before the stop
            for k in range(j + 1, sess_end + 1):
                hk, lk = bars[k][2], bars[k][3]
                if (side == "long" and lk <= sl) or (side == "short" and hk >= sl):
                    break
                if (side == "long" and hk >= tp2) or (side == "short" and lk <= tp2):
                    return "tp1", abs(tp1 - e) / risk, True
            return "tp1", abs(tp1 - e) / risk, False
    if not filled:
        return "no fill", 0.0, False
    close = bars[sess_end][4]
    r = (close - e) / risk if side == "long" else (e - close) / risk
    return "session close", r, False


def run(bars, buf_pct, only_time=None):
    starts = session_starts(bars)
    ends = {}
    for i, s in enumerate(starts):
        ends[s] = i
    results = {"long": [], "short": []}
    invalid = {"long": Counter(), "short": Counter()}
    for i in range(LOOKBACK, len(bars)):
        s = starts[i]
        e = ends[s]
        if i == e:
            continue  # no bars left in the session to trade
        if only_time:
            # bar timestamps are the bar's open time, in New York time here
            t = datetime.fromtimestamp(bars[i][0], tz=ET)
            if t.strftime("%H:%M") != only_time:
                continue
        lv = levels(bars, i, s, buf_pct)
        for side in ("long", "short"):
            bad = validity(side, lv[side])
            if bad:
                invalid[side][bad] += 1
                continue
            outcome, r, tp2 = simulate(bars, i, e, side, lv[side])
            reward = abs(lv[side]["tp1"] - lv[side]["entry"])
            risk = abs(lv[side]["entry"] - lv[side]["sl"])
            results[side].append({"outcome": outcome, "r": r, "tp2": tp2, "rr": reward / risk})
    return results, invalid


def report(results, invalid, label):
    lines = [f"### {label}", ""]
    lines.append("| | Long | Short |")
    lines.append("|---|---|---|")
    rows = {}
    for side in ("long", "short"):
        res = results[side]
        n_inv = sum(invalid[side].values())
        total = len(res) + n_inv
        filled = [x for x in res if x["outcome"] != "no fill"]
        wins = [x for x in filled if x["outcome"] == "tp1"]
        stops = [x for x in filled if x["outcome"] == "stop"]
        closes = [x for x in filled if x["outcome"] == "session close"]
        rr = [x["rr"] for x in res]
        exp = statistics.mean(x["r"] for x in filled) if filled else 0
        pct = lambda a, b: f"{100 * a / b:.1f}%" if b else "n/a"
        rows[side] = {
            "Signals evaluated": f"{total:,}",
            "Invalid geometry (skipped)": f"{n_inv:,} ({pct(n_inv, total)})",
            "Entry filled": f"{len(filled):,} ({pct(len(filled), len(res))} of valid)",
            "TP1 hit first": pct(len(wins), len(filled)),
            "Stopped out": pct(len(stops), len(filled)),
            "Open at session close": pct(len(closes), len(filled)),
            "TP2 reached before stop": pct(sum(x["tp2"] for x in filled), len(filled)),
            "Median reward:risk to TP1": f"{statistics.median(rr):.2f}" if rr else "n/a",
            "Expectancy per filled trade": f"{exp:+.3f} R",
        }
    for key in rows["long"]:
        lines.append(f"| {key} | {rows['long'][key]} | {rows['short'][key]} |")
    lines.append("")
    for side in ("long", "short"):
        if invalid[side]:
            reasons = ", ".join(f"{k}: {v:,}" for k, v in invalid[side].most_common())
            lines.append(f"- {side.title()} invalid setups: {reasons}")
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bars")
    ap.add_argument("--symbol-class", default="etf", choices=BUFFER)
    args = ap.parse_args()
    with open(args.bars) as f:
        bars = json.load(f)
    bars.sort(key=lambda b: b[0])
    first = datetime.fromtimestamp(bars[0][0], tz=ET).date()
    last = datetime.fromtimestamp(bars[-1][0], tz=ET).date()
    n_sessions = len(set(session_starts(bars)))
    print(f"{len(bars):,} bars, {n_sessions} sessions, {first} to {last}\n")
    buf = BUFFER[args.symbol_class]
    res, inv = run(bars, buf)
    print(report(res, inv, "Every bar (overlapping signals)"))
    res, inv = run(bars, buf, only_time="10:15")
    print(report(res, inv, "One signal per day (close of the 10:15 ET bar)"))


if __name__ == "__main__":
    main()
