# Backtest results: SPY, 15-minute bars

**Data:** 5,122 regular-hours bars, 197 sessions, 2026-01-02 to 2026-10-14, exported from TradingView Desktop. The raw data isn't in this repo because it's licensed. Run `export_bars.js` to make your own copy.

**Method:** the command's rules are replayed at the close of every bar, using only the 100 bars the command would have seen at that moment. Each setup is then walked forward to the end of that session. A trade exits at TP1, at its stop, or at the session close. Costs are $0.02 per share round trip (spread plus slippage).

**R** is the distance from entry to stop, so a trade that hits its stop loses 1 R and "−0.10 R per trade" means losing a tenth of the amount risked, on average.

## Summary

- **v1 has no edge.** After costs it averages −0.117 R per trade from January to June and −0.102 R from July to October. Under the most favourable assumption about prices inside a bar ([below](#sensitivity-order-of-prices-inside-a-bar)) it roughly breaks even. It's never clearly positive.
- **v2 doesn't find one either.** The variant picked from the [pre-registered grid](v2-plan.md) had a 1.5 ATR stop, a target at 2× the stop distance, and no confluence filter. It was the best of 12 from January to June at −0.019 R. From July to October it came in at −0.063 R, with a 95% interval of −0.148 to +0.031 R. By the success criterion fixed in advance, v2 doesn't work.
- **v2's setups are coherent and it loses less.** Every v2 setup has its target beyond the entry and 2:1 reward:risk, where 28–32% of v1's setups put the target or the stop on the wrong side of the entry. The intervals overlap, though, so the smaller loss isn't statistically established either.
- **v2's targets rarely come into play.** TP1 sits 3 ATR from the entry and is hit first on only 7–13% of trades, while 55–62% are still open at the close. In practice v2 is a breakout entry with a wide stop, held to the close.

## v1 vs v2

| Rule | Period | Filled trades | Before costs | After costs | 95% interval, after costs |
|---|---|---|---|---|---|
| v1 (published) | In-sample | 3,291 | −0.107 R | −0.117 R | −0.150 to −0.085 |
| v1 (published) | Out-of-sample | 1,746 | −0.083 R | −0.102 R | −0.142 to −0.060 |
| v1 + reject rule | In-sample | 298 | −0.525 R | −0.570 R | −0.685 to −0.443 |
| v1 + reject rule | Out-of-sample | 221 | −0.319 R | −0.414 R | −0.629 to −0.179 |
| stop 1.5 ATR, R:R 2.0, confluence off | In-sample | 4,215 | −0.009 R | −0.019 R | −0.090 to +0.055 |
| stop 1.5 ATR, R:R 2.0, confluence off | Out-of-sample | 2,370 | −0.050 R | −0.063 R | −0.148 to +0.031 |

Every bar is a signal, so consecutive signals overlap and share outcomes. The intervals come from a bootstrap that resamples whole sessions to account for that.

"v1 + reject rule" is v1 with v2's new filter, which drops setups whose reward:risk is below 1. It does far worse than v1. The v1 setups that pass have a median stop only 0.75 ATR from the entry, less than an average bar's range, so a single 15-minute bar often touches both the entry and the stop. That makes their result depend almost entirely on the assumption about prices inside a bar (see the sensitivity table).

### One signal per day (close of the 10:15 ET bar)

| Rule | Period | Filled trades | Before costs | After costs | 95% interval, after costs |
|---|---|---|---|---|---|
| v1 (published) | In-sample | 118 | −0.065 R | −0.075 R | −0.170 to +0.023 |
| v1 (published) | Out-of-sample | 71 | −0.085 R | −0.093 R | −0.220 to +0.035 |
| v1 + reject rule | In-sample | 12 | −0.613 R | −0.661 R | −1.068 to −0.072 |
| v1 + reject rule | Out-of-sample | 9 | −0.382 R | −0.401 R | −0.851 to +0.174 |
| stop 1.5 ATR, R:R 2.0, confluence off | In-sample | 173 | +0.011 R | +0.002 R | −0.160 to +0.178 |
| stop 1.5 ATR, R:R 2.0, confluence off | Out-of-sample | 107 | −0.012 R | −0.024 R | −0.239 to +0.208 |

With 70 to 175 trades per period, this sample is too small to tell v1 and v2 apart: all four of their intervals include zero.

## How v2 was picked

The variants, periods, costs and selection rule were written down and committed in [v2-plan.md](v2-plan.md) before any variant was run. The rule picks the highest in-sample expectancy after costs, pooling long and short trades, among variants with at least 200 filled trades.

| Rule | Setups kept | Filled trades | TP1 first | Stopped | Open at close | Before costs | After costs |
|---|---|---|---|---|---|---|---|
| v1 (published) | 71.5% | 3,291 | 42.7% | 19.0% | 38.3% | −0.107 R | −0.117 R |
| v1 + reject rule | 8.2% | 298 | 12.8% | 69.5% | 17.8% | −0.525 R | −0.570 R |
| stop 1.0 ATR, R:R 1.0, confluence off | 100.0% | 4,215 | 34.0% | 47.8% | 18.2% | −0.133 R | −0.148 R |
| stop 1.0 ATR, R:R 1.5, confluence off | 100.0% | 4,215 | 23.0% | 50.7% | 26.2% | −0.119 R | −0.134 R |
| stop 1.0 ATR, R:R 2.0, confluence off | 100.0% | 4,215 | 15.3% | 52.1% | 32.6% | −0.115 R | −0.130 R |
| stop 1.5 ATR, R:R 1.0, confluence off | 100.0% | 4,215 | 27.8% | 31.5% | 40.8% | −0.047 R | −0.057 R |
| stop 1.5 ATR, R:R 1.5, confluence off | 100.0% | 4,215 | 16.2% | 32.6% | 51.2% | −0.030 R | −0.040 R |
| stop 1.5 ATR, R:R 2.0, confluence off | 100.0% | 4,215 | 10.9% | 32.9% | 56.2% | −0.009 R | −0.019 R |
| stop 1.0 ATR, R:R 1.0, confluence on | 19.5% | 953 | 32.4% | 49.7% | 17.8% | −0.177 R | −0.192 R |
| stop 1.0 ATR, R:R 1.5, confluence on | 14.5% | 695 | 22.0% | 49.5% | 28.5% | −0.139 R | −0.155 R |
| stop 1.0 ATR, R:R 2.0, confluence on | 12.3% | 593 | 15.3% | 48.1% | 36.6% | −0.091 R | −0.108 R |
| stop 1.5 ATR, R:R 1.0, confluence on | 14.5% | 695 | 26.3% | 31.7% | 42.0% | −0.068 R | −0.079 R |
| stop 1.5 ATR, R:R 1.5, confluence on | 11.7% | 566 | 17.0% | 32.2% | 50.9% | −0.028 R | −0.039 R |
| stop 1.5 ATR, R:R 2.0, confluence on | 10.5% | 517 | 9.9% | 32.9% | 57.3% | −0.039 R | −0.051 R |

The 1.5 ATR stops beat the 1.0 ATR stops at every reward:risk setting, and the confluence filter didn't help on average.

### The picked variant, side by side

#### In-sample (Jan 2 – Jun 30)

| | Long | Short |
|---|---|---|
| Setups evaluated | 2,978 | 2,978 |
| Rejected (skipped) | 0 (0.0%) | 0 (0.0%) |
| Entry filled | 2,205 (74.0% of kept) | 2,010 (67.5% of kept) |
| TP1 hit first | 9.2% | 12.7% |
| Stopped out | 33.7% | 32.0% |
| Open at session close | 57.1% | 55.2% |
| TP2 reached before stop | 0.1% | 4.1% |
| Median reward:risk to TP1 | 2.00 | 2.00 |
| Expectancy before costs | −0.047 R | +0.032 R |
| Expectancy after costs | −0.057 R | +0.022 R |

#### Out-of-sample (Jul 1 – Oct 14)

| | Long | Short |
|---|---|---|
| Setups evaluated | 1,850 | 1,850 |
| Rejected (skipped) | 0 (0.0%) | 0 (0.0%) |
| Entry filled | 1,175 (63.5% of kept) | 1,195 (64.6% of kept) |
| TP1 hit first | 6.6% | 10.1% |
| Stopped out | 31.3% | 32.1% |
| Open at session close | 62.1% | 57.8% |
| TP2 reached before stop | 0.6% | 0.6% |
| Median reward:risk to TP1 | 2.00 | 2.00 |
| Expectancy before costs | −0.099 R | −0.003 R |
| Expectancy after costs | −0.111 R | −0.016 R |

## Sensitivity: order of prices inside a bar

A 15-minute bar records its high and low but not which came first. The simulator assumes the worst for the trade. On the bar that fills the entry, only the stop can be hit, and when a later bar touches both the stop and TP1, the stop counts first. This was fixed before testing. To see how much it matters, the table below re-runs everything with the opposite assumption (target first). That's an optimistic bound, not a better estimate. This check wasn't in the plan: I added it after the first run, and it plays no part in the selection.

| Rule | In-sample, stop first | In-sample, target first | Out-of-sample, stop first | Out-of-sample, target first |
|---|---|---|---|---|
| v1 (published) | −0.117 R | +0.019 R | −0.102 R | +0.002 R |
| v1 + reject rule | −0.570 R | +0.328 R | −0.414 R | +0.097 R |
| stop 1.0 ATR, R:R 1.0, confluence off | −0.148 R | −0.021 R | −0.135 R | +0.018 R |
| stop 1.0 ATR, R:R 1.5, confluence off | −0.134 R | −0.017 R | −0.104 R | +0.040 R |
| stop 1.0 ATR, R:R 2.0, confluence off | −0.130 R | −0.015 R | −0.117 R | +0.023 R |
| stop 1.5 ATR, R:R 1.0, confluence off | −0.057 R | −0.035 R | −0.024 R | +0.027 R |
| stop 1.5 ATR, R:R 1.5, confluence off | −0.040 R | −0.018 R | −0.046 R | +0.004 R |
| stop 1.5 ATR, R:R 2.0, confluence off | −0.019 R | +0.002 R | −0.063 R | −0.010 R |
| stop 1.0 ATR, R:R 1.0, confluence on | −0.192 R | −0.091 R | −0.129 R | −0.029 R |
| stop 1.0 ATR, R:R 1.5, confluence on | −0.155 R | −0.067 R | −0.080 R | −0.001 R |
| stop 1.0 ATR, R:R 2.0, confluence on | −0.108 R | −0.039 R | −0.039 R | +0.030 R |
| stop 1.5 ATR, R:R 1.0, confluence on | −0.079 R | −0.061 R | −0.058 R | −0.045 R |
| stop 1.5 ATR, R:R 1.5, confluence on | −0.039 R | −0.027 R | −0.019 R | −0.007 R |
| stop 1.5 ATR, R:R 2.0, confluence on | −0.051 R | −0.044 R | +0.049 R | +0.065 R |

- **v1 swings from clearly negative to break-even**, so "v1 loses money" holds only under the cautious assumption. Its structural problems hold either way: TP1 sits about 0.4 R from the entry, which needs roughly a 70% win rate to break even, and many setups put the target on the wrong side.
- **The picked v2 variant moves much less** (−0.063 R to −0.010 R out of sample) and stays negative. It's also the best of the 12 in-sample under either assumption, so the choice doesn't depend on it.
- **Tight stops can't be judged from 15-minute bars.** Settling them needs 1-minute data for the same months, which this export doesn't include.

## Appendix: every variant out of sample

For transparency only. This table played no part in the selection.

| Rule | Setups kept | Filled trades | TP1 first | Stopped | Open at close | Before costs | After costs |
|---|---|---|---|---|---|---|---|
| v1 (published) | 68.4% | 1,746 | 35.2% | 15.0% | 49.8% | −0.083 R | −0.102 R |
| v1 + reject rule | 11.5% | 221 | 10.4% | 43.9% | 45.7% | −0.319 R | −0.414 R |
| stop 1.0 ATR, R:R 1.0, confluence off | 100.0% | 2,370 | 34.7% | 45.5% | 19.8% | −0.116 R | −0.135 R |
| stop 1.0 ATR, R:R 1.5, confluence off | 100.0% | 2,370 | 23.7% | 47.7% | 28.6% | −0.085 R | −0.104 R |
| stop 1.0 ATR, R:R 2.0, confluence off | 100.0% | 2,370 | 15.7% | 49.4% | 34.9% | −0.098 R | −0.117 R |
| stop 1.5 ATR, R:R 1.0, confluence off | 100.0% | 2,370 | 29.2% | 29.2% | 41.6% | −0.012 R | −0.024 R |
| stop 1.5 ATR, R:R 1.5, confluence off | 100.0% | 2,370 | 15.7% | 31.2% | 53.2% | −0.033 R | −0.046 R |
| stop 1.5 ATR, R:R 2.0, confluence off | 100.0% | 2,370 | 8.4% | 31.7% | 60.0% | −0.050 R | −0.063 R |
| stop 1.0 ATR, R:R 1.0, confluence on | 22.6% | 627 | 36.5% | 46.7% | 16.7% | −0.109 R | −0.129 R |
| stop 1.0 ATR, R:R 1.5, confluence on | 17.2% | 470 | 26.8% | 50.0% | 23.2% | −0.060 R | −0.080 R |
| stop 1.0 ATR, R:R 2.0, confluence on | 14.8% | 410 | 20.7% | 50.5% | 28.8% | −0.020 R | −0.039 R |
| stop 1.5 ATR, R:R 1.0, confluence on | 17.2% | 470 | 31.1% | 33.8% | 35.1% | −0.045 R | −0.058 R |
| stop 1.5 ATR, R:R 1.5, confluence on | 13.8% | 388 | 20.6% | 33.8% | 45.6% | −0.006 R | −0.019 R |
| stop 1.5 ATR, R:R 2.0, confluence on | 12.2% | 355 | 14.6% | 32.1% | 53.2% | +0.062 R | +0.049 R |

The best row here (1.5 ATR stop, 2:1, confluence on, +0.049 R) was −0.051 R in-sample. Picking it now would mean choosing whatever happened to work on the test data.

## v1 on the full period

The original v1 backtest. Same numbers as the first version of this page, plus a row with costs.

### Every bar

| | Long | Short |
|---|---|---|
| Setups evaluated | 4,828 | 4,828 |
| Rejected (skipped) | 1,345 (27.9%) | 1,521 (31.5%) |
| Entry filled | 2,616 (75.1% of kept) | 2,421 (73.2% of kept) |
| TP1 hit first | 35.5% | 45.0% |
| Stopped out | 20.1% | 14.9% |
| Open at session close | 44.3% | 40.1% |
| TP2 reached before stop | 6.4% | 11.0% |
| Median reward:risk to TP1 | 0.41 | 0.40 |
| Expectancy before costs | −0.139 R | −0.054 R |
| Expectancy after costs | −0.154 R | −0.065 R |

- Long rejected: TP1 on the wrong side of entry: 1,125, stop on the wrong side of entry: 220
- Short rejected: TP1 on the wrong side of entry: 1,243, stop on the wrong side of entry: 278

### One signal per day (close of the 10:15 ET bar)

| | Long | Short |
|---|---|---|
| Setups evaluated | 193 | 193 |
| Rejected (skipped) | 76 (39.4%) | 88 (45.6%) |
| Entry filled | 99 (84.6% of kept) | 90 (85.7% of kept) |
| TP1 hit first | 49.5% | 52.2% |
| Stopped out | 22.2% | 22.2% |
| Open at session close | 28.3% | 25.6% |
| TP2 reached before stop | 12.1% | 16.7% |
| Median reward:risk to TP1 | 0.40 | 0.37 |
| Expectancy before costs | −0.066 R | −0.080 R |
| Expectancy after costs | −0.076 R | −0.087 R |

- Long rejected: TP1 on the wrong side of entry: 68, stop on the wrong side of entry: 8
- Short rejected: TP1 on the wrong side of entry: 81, stop on the wrong side of entry: 7

## What the backtest doesn't model

- **Fill prices.** Entries, stops and targets fill exactly at their level, even when a bar opens beyond it. Real spreads also widen at the open and in fast markets, beyond the flat $0.02.
- **Order of prices inside a bar.** Only bounded (see the sensitivity table), not resolved.
- **Overnight holds.** Every trade is closed at the session close.
- **Anything beyond this sample.** The test covers SPY only, January to October 2026 only, and only the `day` setting (15-minute bars). The command uses the same rules on other symbols and timeframes, untested.

## Reproduce

```bash
node backtest/export_bars.js backtest/spy_15m.json     # TradingView Desktop open on SPY, 15 min
python3 backtest/backtest.py backtest/spy_15m.json --symbol-class etf
python3 backtest/check_parity.py backtest/spy_15m.json
```

`backtest.py` uses only the Python standard library and also re-checks the v1 numbers above. `check_parity.py` runs the command's own script in Node against the same bars and confirms that every level matches the backtest to the cent. On this data the largest difference was 3.4 × 10⁻¹³.
