# Changelog

## v2.0 (2026-10-14)

The rules were rebuilt after the v1 backtest. Full results: [backtest/RESULTS.md](backtest/RESULTS.md).

### Changed

- Stops and targets are now sized in ATR(14): the stop is 1.5 ATR from the entry, TP1 is at 2× the stop distance and TP2 at 4×. These settings were picked from 12 variants on January–June 2026 data, using a [plan](backtest/v2-plan.md) committed before any variant was run.
- The in-page script computes every level. Claude formats the output and no longer works out levels from written rules.
- The honesty footer now states the backtest result.

### Added

- Reject rule: a side prints `No valid long/short setup: {reason}` when its TP1 or stop is on the wrong side of the entry, or when reward:risk is below 1.
- An `R:R to TP1` line for each side.
- Optional confluence filter, off by default: longs only above VWAP and with no swing high before TP1 (shorts mirrored).
- `backtest/check_parity.py`, which runs the command's script in Node and confirms it matches the backtest to the cent on every bar.
- Backtest additions: in-sample and out-of-sample periods, $0.02-per-share costs, session-bootstrap confidence intervals, and a check of how much the order of prices inside a bar matters.

### Result

No variant showed an edge out of sample. The picked variant averaged −0.063 R per trade after costs from July to October 2026 (95% interval −0.148 to +0.031), against −0.102 R for v1.

## v1.0 (2026-10-13)

- First release. Long and short levels from VWAP, the 9 and 20 EMAs and recent swing levels:
  - Entry: max(price, 9 EMA) + buffer.
  - TP1: VWAP when price is below it, otherwise the closer of the prior swing high and entry + 0.3%.
  - TP2: the further of the 20-bar high and entry + 0.6%.
  - Stop: min(20 EMA, prior swing low) − buffer.
  - Shorts mirror all four.
- Backtest on SPY 15-minute bars, January–October 2026.
