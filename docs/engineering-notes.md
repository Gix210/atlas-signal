# Engineering notes

Findings from building this command against TradingView Desktop and the TradingView MCP server. Kept here because each one changed how the command works.

## Adding indicators fails silently

`chart_manage_indicator` calls TradingView's `chart.createStudy()`, which returns a Promise. The MCP server evaluates it with `awaitPromise: false`, so when TradingView rejects the request (plan limit reached, unknown indicator name), the tool returns `success: false` with no error message.

The Basic plan also caps user indicators at two (Volume doesn't count).

**Resolution:** the command never adds indicators. It reads the chart's bar data directly and computes VWAP and both EMAs in one `ui_evaluate` call.

## `ui_evaluate` can't await either

The same `awaitPromise: false` setting applies to `ui_evaluate`. The injected function has to be a synchronous IIFE that returns plain values.

## Options chains can't be read from the chart (verified 2026-05-30)

- TradingView's options API hosts (`options-charting.tradingview.com` and related) reject requests from the chart page because of CORS.
- The chart page has no options widget in its DOM.
- The Electron app blocks navigation to `/symbols/{symbol}/options/`.
- `tab_new` opens chart tabs, not browser tabs, and takes no URL.

**Resolution:** when `option` is requested, the command states that chain data isn't available and lists sources that would supply it. It never makes up strikes or premiums.

## Session detection for VWAP

VWAP resets each session. The bar series doesn't flag session boundaries, so the command treats the most recent gap of more than one hour between consecutive bars as the session open. This works for regular-hours equities and ETFs. Crypto and other 24-hour markets have no such gap. An earlier version then treated only the latest bar as the session, which made VWAP equal to that bar's typical price. The command now falls back to anchoring VWAP at the most recent 00:00 UTC.

## Testing the in-page script outside TradingView

The levels come from a JavaScript function that runs inside the TradingView page, so the backtest (Python) and the command could silently drift apart. `backtest/check_parity.py` closes that gap. It pulls the script out of the command file and runs it in Node against a stand-in for the four calls the script makes to TradingView's chart API: `activeChart()`, `_chartWidget.model().mainSeries()`, `bars()` and `valueAt(i)`. For each bar, the stand-in serves the 300 bars a freshly opened chart would have loaded. The check then compares every value with the Python backtest.

Both sides perform the same floating-point operations in the same order, so they agree to within 10⁻¹² rather than merely to the cent. Running the script in TradingView itself on the live SPY chart also matched the backtest exactly.
