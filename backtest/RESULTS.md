# Backtest results: SPY, 15-minute bars

**Data:** 5,122 regular-hours bars, 197 sessions, 2026-01-02 to 2026-10-14, exported from TradingView Desktop. The raw data isn't in this repo because it's licensed. Run `export_bars.js` to make your own copy.

**Setup:** the `/atlas SPY stock day` rules, replayed at the close of every bar using only the 100 bars the command would have seen at that moment. Each setup is then walked forward to the end of that session.

## Results

### Every bar (overlapping signals)

| | Long | Short |
|---|---|---|
| Signals evaluated | 4,828 | 4,828 |
| Invalid geometry (skipped) | 1,345 (27.9%) | 1,521 (31.5%) |
| Entry filled | 2,616 (75.1% of valid) | 2,421 (73.2% of valid) |
| TP1 hit first | 35.5% | 45.0% |
| Stopped out | 20.1% | 14.9% |
| Open at session close | 44.3% | 40.1% |
| TP2 reached before stop | 6.4% | 11.0% |
| Median reward:risk to TP1 | 0.41 | 0.40 |
| Expectancy per filled trade | −0.139 R | −0.054 R |

### One signal per day (close of the 10:15 ET bar)

Consecutive bars produce nearly identical setups, so the table above counts many of the same trades more than once. Taking a single signal per day removes that overlap.

| | Long | Short |
|---|---|---|
| Signals evaluated | 193 | 193 |
| Invalid geometry (skipped) | 76 (39.4%) | 88 (45.6%) |
| Entry filled | 99 (84.6% of valid) | 90 (85.7% of valid) |
| TP1 hit first | 49.5% | 52.2% |
| Stopped out | 22.2% | 22.2% |
| Open at session close | 28.3% | 25.6% |
| TP2 reached before stop | 12.1% | 16.7% |
| Median reward:risk to TP1 | 0.40 | 0.37 |
| Expectancy per filled trade | −0.066 R | −0.080 R |

*R = the distance from entry to stop. A trade that hits its stop loses 1 R.*

## What this says about the rules

1. **The rules lose money before costs.** Expectancy is negative on both sides in both samples. TP1 is hit about twice as often as the stop, but TP1 sits only about 0.4 R from entry. A strategy with that payoff needs to win roughly 70% of the time to break even.
2. **Stops are too wide for the targets.** The stop sits beyond the 20 EMA *and* the prior swing low, while TP1 is often the nearest level (VWAP or a 0.3% move). Reward:risk is under 1 for most setups.
3. **About a third of setups make no sense.** When price is below VWAP, the long target is VWAP. But the long entry is placed above the 9 EMA, which can already be above VWAP, and then the target sits below the entry. The command prints these setups anyway.
4. **Many trades never resolve.** 25–45% of filled trades hit neither level by the close. The "day" horizon is too short for the distance to TP2.

## What the backtest doesn't model

- Commissions, slippage, and the bid/ask spread. All of them would make the results worse.
- Order of prices inside a bar. When a single bar touches both the stop and the target, the stop is assumed to come first, and a bar that fills the entry can only stop out on that bar. Both choices make the results look worse than reality, never better.
- Overnight holds. Every trade is closed at the session close.
- Any year other than 2026, any symbol other than SPY, and the `0dte`, `week` and `month` timeframes.

## Reproduce

```bash
node backtest/export_bars.js backtest/spy_15m.json   # TradingView Desktop open on SPY 15m
python3 backtest/backtest.py backtest/spy_15m.json --symbol-class etf
```

The script uses only the Python standard library. It also reproduces the live levels from the README's sample run to the cent.
