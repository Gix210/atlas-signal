"""Backtest of the /atlas level rules on intraday bars.

Replays the command's rules bar by bar: at the close of each bar it builds the
long and short setups from the 100 bars the command would have seen, then walks
forward through the rest of the session to see which level price reaches first.

Runs the original v1 rules and the v2 grid fixed in v2-plan.md, picks one v2
variant on the in-sample period, and reports it on the out-of-sample period.

Usage:
    python3 backtest.py spy_15m.json --symbol-class etf

Input is a JSON array of [unix_seconds, open, high, low, close, volume] bars,
as written by export_bars.js. Only the standard library is used.
"""

import argparse
import json
import random
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

BUFFER = {"etf": 0.0005, "stock": 0.0015, "crypto": 0.0025}
LOOKBACK = 100          # bars the command reads
SWING_WINDOW = 20       # bars used for recent high/low and swing points
ATR_LEN = 14
MIN_RR = 1.0            # v2 skips setups that risk more than they target
COST_PER_SHARE = 0.02   # round trip: spread plus slippage
SESSION_GAP = 3600      # a gap longer than this starts a new session
ET = ZoneInfo("America/New_York")

IN_SAMPLE = (date(2026, 1, 2), date(2026, 6, 30))
OUT_OF_SAMPLE = (date(2026, 7, 1), date(2026, 10, 14))
MIN_TRADES = 200        # filled in-sample trades a variant needs to be picked
DAILY_BAR = "10:15"     # bar (New York open time) for the one-signal-per-day sample

# The v2 grid, fixed in v2-plan.md before any variant was run.
GRID = [
    {"stop_atr": s, "rr": r, "confluence": c}
    for c in (False, True)
    for s in (1.0, 1.5)
    for r in (1.0, 1.5, 2.0)
]

# The variant the selection rule picked. The command's script must use the
# same values; check_parity.py fails if they differ.
SELECTED = {"stop_atr": 1.5, "rr": 2.0, "confluence": False}

REJECT_TEXT = {
    "no_tp1": "no TP1 beyond entry",
    "tp1_side": "TP1 on the wrong side of entry",
    "sl_side": "stop on the wrong side of entry",
    "rr": "reward:risk below 1",
    "vwap": "price on the wrong side of VWAP",
    "swing": "swing level between entry and TP1",
}


def ema(values, length):
    k = 2 / (length + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def atr(hist, length=ATR_LEN):
    """Average true range with Wilder smoothing, seeded by a simple average."""
    trs = [hist[0][2] - hist[0][3]]
    for k in range(1, len(hist)):
        h, l, pc = hist[k][2], hist[k][3], hist[k - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(trs[:length]) / length
    for tr in trs[length:]:
        a = (a * (length - 1) + tr) / length
    return a


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


def indicators(bars, i, sess_start):
    """Everything the command reads from the chart at the close of bar i."""
    hist = bars[max(0, i - LOOKBACK + 1): i + 1]
    closes = [b[4] for b in hist]
    price = closes[-1]

    session = bars[sess_start: i + 1]
    pv = sum((b[2] + b[3] + b[4]) / 3 * b[5] for b in session)
    vv = sum(b[5] for b in session)

    window = hist[-SWING_WINDOW:]
    return {
        "price": price,
        "vwap": pv / vv if vv else price,
        "ema9": ema(closes, 9),
        "ema20": ema(closes, 20),
        "atr": atr(hist),
        "recent_high": max(b[2] for b in window),
        "recent_low": min(b[3] for b in window),
        "prior_high": second_extreme(window, "high"),
        "prior_low": second_extreme(window, "low"),
    }


def levels_v1(ind, buf_pct):
    """Long and short setups as v1 of the command defined them."""
    price, vwap, e9, e20 = ind["price"], ind["vwap"], ind["ema9"], ind["ema20"]
    buf = price * buf_pct

    le = max(price, e9) + buf
    if price < vwap:
        ltp1 = vwap
    else:
        cands = [c for c in (ind["prior_high"], le * 1.003) if c > le]
        ltp1 = min(cands) if cands else None
    ltp2 = max(ind["recent_high"], le * 1.006)
    lsl = min(e20, ind["prior_low"]) - buf

    se = min(price, e9) - buf
    if price > vwap:
        stp1 = vwap
    else:
        cands = [c for c in (ind["prior_low"], se * 0.997) if c < se]
        stp1 = max(cands) if cands else None
    stp2 = min(ind["recent_low"], se * 0.994)
    ssl = max(e20, ind["prior_high"]) + buf

    return {
        "long": {"entry": le, "tp1": ltp1, "tp2": ltp2, "sl": lsl},
        "short": {"entry": se, "tp1": stp1, "tp2": stp2, "sl": ssl},
    }


def levels_v2(ind, buf_pct, stop_atr, rr):
    """v2 setups: v1's entry, stop and targets sized in ATR."""
    price, e9 = ind["price"], ind["ema9"]
    buf = price * buf_pct
    risk = stop_atr * ind["atr"]
    le = max(price, e9) + buf
    se = min(price, e9) - buf
    return {
        "long": {"entry": le, "tp1": le + rr * risk, "tp2": le + 2 * rr * risk, "sl": le - risk},
        "short": {"entry": se, "tp1": se - rr * risk, "tp2": se - 2 * rr * risk, "sl": se + risk},
    }


def reward_risk(lv):
    return abs(lv["tp1"] - lv["entry"]) / abs(lv["entry"] - lv["sl"])


def geometry(side, lv):
    """Why a setup can't be traded at all, or None. v1's only check."""
    e, tp1, sl = lv["entry"], lv["tp1"], lv["sl"]
    if tp1 is None:
        return "no_tp1"
    if (side == "long" and tp1 <= e) or (side == "short" and tp1 >= e):
        return "tp1_side"
    if (side == "long" and sl >= e) or (side == "short" and sl <= e):
        return "sl_side"
    return None


def reject(side, lv, ind, confluence):
    """v2's reject rule: why a setup is skipped, or None to trade it."""
    bad = geometry(side, lv)
    if bad:
        return bad
    if reward_risk(lv) < MIN_RR - 1e-9:
        return "rr"
    if confluence:
        if side == "long":
            if ind["price"] <= ind["vwap"]:
                return "vwap"
            if any(lv["entry"] < x < lv["tp1"] for x in (ind["recent_high"], ind["prior_high"])):
                return "swing"
        else:
            if ind["price"] >= ind["vwap"]:
                return "vwap"
            if any(lv["tp1"] < x < lv["entry"] for x in (ind["recent_low"], ind["prior_low"])):
                return "swing"
    return None


def simulate(bars, i, sess_end, side, lv, optimistic=False):
    """Walk forward to the session close.

    Entry is a stop order at `entry`. A 15-minute bar doesn't say whether its
    high or its low came first, so by default the stop gets the benefit of the
    doubt: on the bar that fills the entry only the stop can be hit, and when
    TP1 and the stop fall inside the same later bar, the stop is assumed first.
    `optimistic=True` flips both assumptions; it's only used to bound how much
    they matter.
    Returns (outcome, R multiple, reached TP2 before SL).
    """
    e, tp1, tp2, sl = lv["entry"], lv["tp1"], lv["tp2"], lv["sl"]
    risk = abs(e - sl)
    filled = False
    for j in range(i + 1, sess_end + 1):
        h, l, c = bars[j][2], bars[j][3], bars[j][4]
        if not filled:
            if not ((side == "long" and h >= e) or (side == "short" and l <= e)):
                continue
            filled = True
            if not optimistic:
                if (side == "long" and l <= sl) or (side == "short" and h >= sl):
                    return "stop", -1.0, False
                continue
            stop = False  # optimistic: the move against the trade came before the fill
        else:
            stop = l <= sl if side == "long" else h >= sl
        t1 = h >= tp1 if side == "long" else l <= tp1
        t2 = h >= tp2 if side == "long" else l <= tp2
        if stop and not (optimistic and t1):
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


def prepare(bars):
    """Session boundaries and indicator values, computed once for every rule."""
    starts = session_starts(bars)
    end_of = {}
    for i, s in enumerate(starts):
        end_of[s] = i
    ctx = {
        "start": starts,
        "end": [end_of[s] for s in starts],
        "time": [datetime.fromtimestamp(b[0], tz=ET) for b in bars],
        "ind": {},
    }
    for i in range(LOOKBACK, len(bars)):
        if i != ctx["end"][i]:  # the session's last bar leaves nothing to trade
            ctx["ind"][i] = indicators(bars, i, starts[i])
    return ctx


def run(bars, ctx, rule, buf_pct, period, only_bar=None, optimistic=False):
    """Replay one rule. `rule` is "v1", "v1-reject" or a GRID entry."""
    trades = {"long": [], "short": []}
    rejected = {"long": Counter(), "short": Counter()}
    for i, ind in ctx["ind"].items():
        t = ctx["time"][i]
        if not period[0] <= t.date() <= period[1]:
            continue
        if only_bar and t.strftime("%H:%M") != only_bar:
            continue
        if isinstance(rule, str):
            lv = levels_v1(ind, buf_pct)
        else:
            lv = levels_v2(ind, buf_pct, rule["stop_atr"], rule["rr"])
        for side in ("long", "short"):
            if rule == "v1":
                bad = geometry(side, lv[side])
            elif rule == "v1-reject":
                bad = reject(side, lv[side], ind, confluence=False)
            else:
                bad = reject(side, lv[side], ind, rule["confluence"])
            if bad:
                rejected[side][bad] += 1
                continue
            outcome, r, tp2 = simulate(bars, i, ctx["end"][i], side, lv[side], optimistic)
            risk = abs(lv[side]["entry"] - lv[side]["sl"])
            filled = outcome != "no fill"
            trades[side].append({
                "session": ctx["start"][i],
                "outcome": outcome,
                "r": r,
                "r_net": r - COST_PER_SHARE / risk if filled else 0.0,
                "tp2": tp2,
                "rr": reward_risk(lv[side]),
            })
    return trades, rejected


def stats(trades, rejected, sides=("long", "short")):
    kept = [x for s in sides for x in trades[s]]
    n_rej = sum(sum(rejected[s].values()) for s in sides)
    filled = [x for x in kept if x["outcome"] != "no fill"]
    n = len(filled)

    def share(test):
        return sum(1 for x in filled if test(x)) / n if n else None

    return {
        "evaluated": len(kept) + n_rej,
        "rejected": n_rej,
        "kept": len(kept),
        "filled": n,
        "tp1": share(lambda x: x["outcome"] == "tp1"),
        "stop": share(lambda x: x["outcome"] == "stop"),
        "close": share(lambda x: x["outcome"] == "session close"),
        "tp2": share(lambda x: x["tp2"]),
        "rr": statistics.median(x["rr"] for x in kept) if kept else None,
        "exp": statistics.mean(x["r"] for x in filled) if n else None,
        "exp_net": statistics.mean(x["r_net"] for x in filled) if n else None,
    }


def bootstrap(trades, key, reps=2000, seed=7):
    """95% interval for pooled expectancy, resampling whole sessions.

    Signals within a session overlap, so sessions are the independent unit.
    """
    sums, counts = defaultdict(float), defaultdict(int)
    for side in trades:
        for x in trades[side]:
            if x["outcome"] != "no fill":
                sums[x["session"]] += x[key]
                counts[x["session"]] += 1
    ids = list(sums)
    if len(ids) < 2:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        pick = [rng.choice(ids) for _ in ids]
        means.append(sum(sums[p] for p in pick) / sum(counts[p] for p in pick))
    means.sort()
    return means[int(reps * 0.025)], means[int(reps * 0.975) - 1]


def label(rule):
    if rule == "v1":
        return "v1 (published)"
    if rule == "v1-reject":
        return "v1 + reject rule"
    return (f"stop {rule['stop_atr']:.1f} ATR, R:R {rule['rr']:.1f}, "
            f"confluence {'on' if rule['confluence'] else 'off'}")


def pct(x):
    return f"{100 * x:.1f}%" if x is not None else "n/a"


def r_fmt(x):
    return f"{x:+.3f} R".replace("-", "−") if x is not None else "n/a"


def ci_fmt(ci):
    if ci is None:
        return "n/a"
    return f"{ci[0]:+.3f} to {ci[1]:+.3f}".replace("-", "−")


def side_table(trades, rejected, title):
    lines = [f"#### {title}", "", "| | Long | Short |", "|---|---|---|"]
    st = {s: stats(trades, rejected, (s,)) for s in ("long", "short")}
    rows = [
        ("Setups evaluated", lambda s: f"{s['evaluated']:,}"),
        ("Rejected (skipped)", lambda s: f"{s['rejected']:,} ({pct(s['rejected'] / s['evaluated'] if s['evaluated'] else None)})"),
        ("Entry filled", lambda s: f"{s['filled']:,} ({pct(s['filled'] / s['kept'] if s['kept'] else None)} of kept)"),
        ("TP1 hit first", lambda s: pct(s["tp1"])),
        ("Stopped out", lambda s: pct(s["stop"])),
        ("Open at session close", lambda s: pct(s["close"])),
        ("TP2 reached before stop", lambda s: pct(s["tp2"])),
        ("Median reward:risk to TP1", lambda s: f"{s['rr']:.2f}" if s["rr"] is not None else "n/a"),
        ("Expectancy before costs", lambda s: r_fmt(s["exp"])),
        ("Expectancy after costs", lambda s: r_fmt(s["exp_net"])),
    ]
    for name, f in rows:
        lines.append(f"| {name} | {f(st['long'])} | {f(st['short'])} |")
    lines.append("")
    for side in ("long", "short"):
        if rejected[side]:
            reasons = ", ".join(f"{REJECT_TEXT[k]}: {v:,}" for k, v in rejected[side].most_common())
            lines.append(f"- {side.title()} rejected: {reasons}")
    lines.append("")
    return "\n".join(lines)


def grid_table(results, title):
    lines = [f"### {title}", "",
             "| Rule | Setups kept | Filled trades | TP1 first | Stopped | Open at close | Before costs | After costs |",
             "|---|---|---|---|---|---|---|---|"]
    for rule, st in results:
        lines.append(
            f"| {label(rule)} | {pct(st['kept'] / st['evaluated'])} | {st['filled']:,} | {pct(st['tp1'])} | "
            f"{pct(st['stop'])} | {pct(st['close'])} | {r_fmt(st['exp'])} | {r_fmt(st['exp_net'])} |")
    lines.append("")
    return "\n".join(lines)


def compare_table(rows, title):
    lines = [f"### {title}", "",
             "| Rule | Period | Filled trades | Before costs | After costs | 95% interval, after costs |",
             "|---|---|---|---|---|---|"]
    for rule, period_name, trades, rejected in rows:
        st = stats(trades, rejected)
        lines.append(
            f"| {label(rule)} | {period_name} | {st['filled']:,} | {r_fmt(st['exp'])} | "
            f"{r_fmt(st['exp_net'])} | {ci_fmt(bootstrap(trades, 'r_net'))} |")
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
    buf = BUFFER[args.symbol_class]
    ctx = prepare(bars)
    full = (ctx["time"][0].date(), ctx["time"][-1].date())
    n_sessions = len(set(ctx["start"]))
    print(f"{len(bars):,} bars, {n_sessions} sessions, {full[0]} to {full[1]}\n")

    print("## v1 on the full period (should match the published tables)\n")
    print(side_table(*run(bars, ctx, "v1", buf, full), "Every bar"))
    print(side_table(*run(bars, ctx, "v1", buf, full, DAILY_BAR), "One signal per day"))

    rules = ["v1", "v1-reject"] + GRID
    ins = [(rule, stats(*run(bars, ctx, rule, buf, IN_SAMPLE))) for rule in rules]
    print(grid_table(ins, "In-sample (every bar, long and short pooled)"))

    eligible = [(r, st) for r, st in ins if isinstance(r, dict) and st["filled"] >= MIN_TRADES]
    picked = max(eligible, key=lambda x: (x[1]["exp_net"], x[1]["filled"]))[0]
    print(f"**Picked by the selection rule:** {label(picked)}\n")
    if SELECTED is not None and SELECTED != picked:
        print(f"WARNING: SELECTED in this file is {label(SELECTED)}\n")

    rows, daily = [], []
    for rule in ("v1", "v1-reject", picked):
        for name, period in (("In-sample", IN_SAMPLE), ("Out-of-sample", OUT_OF_SAMPLE)):
            rows.append((rule, name, *run(bars, ctx, rule, buf, period)))
            daily.append((rule, name, *run(bars, ctx, rule, buf, period, DAILY_BAR)))
    print(compare_table(rows, "v1 vs v2, every bar (long and short pooled)"))
    print(compare_table(daily, "v1 vs v2, one signal per day (long and short pooled)"))

    print(f"## Picked variant per side: {label(picked)}\n")
    print(side_table(*run(bars, ctx, picked, buf, IN_SAMPLE), "In-sample, every bar"))
    print(side_table(*run(bars, ctx, picked, buf, OUT_OF_SAMPLE), "Out-of-sample, every bar"))

    oos = [(rule, stats(*run(bars, ctx, rule, buf, OUT_OF_SAMPLE))) for rule in rules]
    print(grid_table(oos, "Appendix: out-of-sample, every variant (not used for selection)"))

    print("### Sensitivity: order of prices inside a bar (after costs, every bar, pooled)\n")
    print("| Rule | In-sample, stop first | In-sample, target first | Out-of-sample, stop first | Out-of-sample, target first |")
    print("|---|---|---|---|---|")
    for rule in rules:
        cells = [r_fmt(stats(*run(bars, ctx, rule, buf, period, optimistic=opt))["exp_net"])
                 for period in (IN_SAMPLE, OUT_OF_SAMPLE) for opt in (False, True)]
        print(f"| {label(rule)} | " + " | ".join(cells) + " |")
    print()


if __name__ == "__main__":
    main()
