---
description: Atlas-style trading signal — long/short levels + (optional) contracts + reason block, all driven from TradingView MCP
argument-hint: <symbol> <stock|option> <0dte|day|week|month | RAW_TV_RESOLUTION>
---

You are generating an Atlas Bot–style **Signal Alert** for the user.

**Raw arguments from the user:** `$ARGUMENTS`

## Parse arguments

- `symbol` = first arg, uppercase ticker (SPY, NVDA, TSLA, BTCUSD, etc.)
- `trade_type` = second arg, one of `stock` or `option`
- `tf_input` = third arg

If any are missing, ask the user to fill them in before continuing.

## Resolve the timeframe

Map `tf_input` to a TradingView resolution + an "expiry horizon" used for context and (if option) for picking an expiry:

| tf_input  | TV resolution | Horizon                |
|-----------|---------------|------------------------|
| `0dte`    | `5`           | today's close          |
| `day`     | `15`          | end of today           |
| `week`    | `60`          | this week's Fri expiry |
| `month`   | `D`           | next monthly expiry    |

If `tf_input` does NOT match a preset, treat it as a raw TV resolution string (`1`, `5`, `15`, `60`, `240`, `D`, `W`, `M`) and use a generic "intraday"/"swing" horizon label.

## Steps

1. **Set chart**
   - `mcp__tradingview__chart_set_symbol` → `symbol`
   - `mcp__tradingview__chart_set_timeframe` → resolved resolution

2. **DO NOT add indicators.** TradingView Basic plan caps at 2 user indicators, and `chart_manage_indicator` silently fails (server bug: doesn't await the createStudy Promise). The script in step 4 computes VWAP, the EMAs and ATR from the chart's own bars instead. Use whatever RSI is already on the chart via `data_get_study_values`; if missing, mark RSI as `n/a` in the output.

3. **Read state in parallel**
   - `mcp__tradingview__data_get_study_values` → grab RSI if present (skip if not)
   - `mcp__tradingview__capture_screenshot` region=chart filename=`atlas_{symbol}_{tf_input}`

4. **Compute every level in-page** via `mcp__tradingview__ui_evaluate` (one round-trip, exact math). Before running it, set `BUFFER_PCT` for the symbol: `0.0005` for index ETFs (SPY/QQQ/IWM), `0.0015` for single stocks, `0.0025` for crypto. Change nothing else: the other constants are the variant `backtest/backtest.py` picked, and `backtest/check_parity.py` fails if this script and the backtest stop giving the same levels.

```javascript
(function () {
  // atlas v2 rules. backtest/backtest.py implements the same rules and
  // backtest/check_parity.py checks that both give the same levels.
  var BUFFER_PCT = 0.0005;  // 0.0005 index ETFs, 0.0015 single stocks, 0.0025 crypto
  var STOP_ATR = 1.5;       // stop distance, in ATR(14)
  var RR = 2.0;             // TP1 distance, as a multiple of the stop distance
  var CONFLUENCE = false;   // true: long only above VWAP with no swing high before TP1 (short mirrored)
  var LOOKBACK = 100, SWING = 20, ATR_LEN = 14, MIN_RR = 1.0;

  var bars = window.TradingViewApi.activeChart()._chartWidget.model().mainSeries().bars();
  var all = [];
  for (var i = bars.firstIndex(); i <= bars.lastIndex(); i++) {
    var v = bars.valueAt(i);
    if (v) all.push({ t: v[0], o: v[1], h: v[2], l: v[3], c: v[4], v: v[5] });
  }

  // Last gap > 1 hour marks the start of the current session.
  // 24h markets (crypto) have no gap: anchor to the latest 00:00 UTC instead.
  var sessionStart = -1;
  for (var j = all.length - 1; j > 0; j--) {
    if (all[j].t - all[j - 1].t > 3600) { sessionStart = j; break; }
  }
  if (sessionStart < 0) {
    var dayStart = Math.floor(all[all.length - 1].t / 86400) * 86400;
    sessionStart = 0;
    while (sessionStart < all.length - 1 && all[sessionStart].t < dayStart) sessionStart++;
  }
  var pv = 0, vv = 0;
  for (var k = sessionStart; k < all.length; k++) {
    pv += (all[k].h + all[k].l + all[k].c) / 3 * all[k].v;
    vv += all[k].v;
  }

  var hist = all.slice(-LOOKBACK);
  var closes = hist.map(function (b) { return b.c; });
  var price = closes[closes.length - 1];
  var vwap = vv ? pv / vv : price;

  function ema(xs, len) {
    var kk = 2 / (len + 1), e = xs[0];
    for (var n = 1; n < xs.length; n++) e = xs[n] * kk + e * (1 - kk);
    return e;
  }
  var ema9 = ema(closes, 9), ema20 = ema(closes, 20);

  // ATR(14): Wilder smoothing, seeded with a simple average
  var trs = [hist[0].h - hist[0].l];
  for (var m = 1; m < hist.length; m++) {
    var pc = hist[m - 1].c;
    trs.push(Math.max(hist[m].h - hist[m].l, Math.abs(hist[m].h - pc), Math.abs(hist[m].l - pc)));
  }
  var atr = 0;
  for (var p = 0; p < ATR_LEN; p++) atr += trs[p];
  atr = atr / ATR_LEN;
  for (var q = ATR_LEN; q < trs.length; q++) atr = (atr * (ATR_LEN - 1) + trs[q]) / ATR_LEN;

  // Swing levels from the last 20 bars. "Prior" = 2nd-highest local high /
  // 2nd-lowest local low, excluding the last 2 bars.
  var win = hist.slice(-SWING);
  function secondExtreme(isHigh) {
    var vals = win.slice(0, -2).map(function (b) { return isHigh ? b.h : b.l; });
    var pts = [];
    for (var r = 1; r < vals.length - 1; r++) {
      if (isHigh && vals[r] > vals[r - 1] && vals[r] > vals[r + 1]) pts.push(vals[r]);
      if (!isHigh && vals[r] < vals[r - 1] && vals[r] < vals[r + 1]) pts.push(vals[r]);
    }
    if (!pts.length) return isHigh ? Math.max.apply(null, vals) : Math.min.apply(null, vals);
    pts.sort(function (a, b) { return isHigh ? b - a : a - b; });
    return pts.length > 1 ? pts[1] : pts[0];
  }
  var recentHigh = Math.max.apply(null, win.map(function (b) { return b.h; }));
  var recentLow = Math.min.apply(null, win.map(function (b) { return b.l; }));
  var priorHigh = secondExtreme(true), priorLow = secondExtreme(false);

  var buf = price * BUFFER_PCT;
  var risk = STOP_ATR * atr;
  function setup(isLong) {
    var entry = isLong ? Math.max(price, ema9) + buf : Math.min(price, ema9) - buf;
    var s = {
      valid: true, code: null, reason: null, rr: null, entry: entry,
      tp1: isLong ? entry + RR * risk : entry - RR * risk,
      tp2: isLong ? entry + 2 * RR * risk : entry - 2 * RR * risk,
      sl: isLong ? entry - risk : entry + risk
    };
    function reject(code, reason) { s.valid = false; s.code = code; s.reason = reason; return s; }
    if (isLong ? s.tp1 <= entry : s.tp1 >= entry) return reject('tp1_side', 'TP1 is not beyond the entry');
    if (isLong ? s.sl >= entry : s.sl <= entry) return reject('sl_side', 'stop is not behind the entry');
    s.rr = Math.abs(s.tp1 - entry) / Math.abs(entry - s.sl);
    if (s.rr < MIN_RR - 1e-9) return reject('rr', 'reward:risk ' + s.rr.toFixed(2) + ' is below ' + MIN_RR.toFixed(2));
    if (CONFLUENCE) {
      if (isLong ? price <= vwap : price >= vwap) {
        return reject('vwap', 'price ' + price.toFixed(2) + (isLong ? ' is not above' : ' is not below') + ' VWAP ' + vwap.toFixed(2));
      }
      var swings = isLong ? [recentHigh, priorHigh] : [recentLow, priorLow];
      for (var w = 0; w < swings.length; w++) {
        var x = swings[w];
        if (isLong ? (x > entry && x < s.tp1) : (x < entry && x > s.tp1)) {
          return reject('swing', 'swing ' + (isLong ? 'high ' : 'low ') + x.toFixed(2) + ' sits between entry and TP1');
        }
      }
    }
    return s;
  }

  return {
    price: price, vwap: vwap, ema9: ema9, ema20: ema20, atr: atr,
    recent_high: recentHigh, recent_low: recentLow, prior_high: priorHigh, prior_low: priorLow,
    long: setup(true), short: setup(false),
    rules: { buffer_pct: BUFFER_PCT, stop_atr: STOP_ATR, rr: RR, confluence: CONFLUENCE }
  };
})()
```

5. **Use the script's levels exactly as returned.** Don't recompute, adjust or "sanity-fix" any of them; round to 2 decimals for display only. Current Price is the script's `price`. For each side:
   - `valid: true` → print Entry, TP1, TP2, SL and `R:R to TP1` (the side's `rr`).
   - `valid: false` → print `No valid long setup: {reason}` (or short) in place of that side's levels.

6. **If `trade_type == option`** — DO NOT try to scrape TradingView. Verified 2026-05-30 to be impossible:
   - TV's option API hosts (`options-charting.tradingview.com` et al) reject fetches from the chart page (CORS).
   - The chart page DOM has no options widget.
   - The Electron app blocks navigation to `/symbols/{symbol}/options/`.
   - `tab_new` creates TV chart tabs, not browser tabs — no URL parameter exists.

   Instead, emit this block in the output (don't fabricate strikes):

   ```
   **Best Call / Put Contracts:** options-chain data unavailable from the TradingView MCP. To enable contract picks, connect one of:
   - Unusual Whales API (gives GEX walls + full chain + Greeks — closest match to Atlas Bot)
   - Polygon.io options endpoint (chain + Greeks, no GEX)
   - Chrome MCP scraping `tradingview.com/symbols/{symbol}/options/` (free, but bid/ask only)
   - Paste a chain snapshot manually
   ```

   Continue with the technicals-only signal so the user still gets long/short levels.

7. **Build Reason block** from the script's values
   - **Price Action**: describe position vs VWAP, 9 EMA, 20 EMA (e.g. "above VWAP 751.28, above 9 EMA 752.10, above 20 EMA 751.53")
   - **Key Levels**: recent_high, recent_low, VWAP — call out which is closest as immediate support/resistance
   - **News and Metrics**: we don't have a news feed wired up — write `Manual check recommended (no news source connected)`
   - **Impact**: `hold {long_entry} and {long_TP1} is next; lose {short_entry} and {short_TP1} is next`. If one side was rejected, keep only the other half. If both were, write `No trade: both setups were rejected`.

8. **Render output in this exact format** (mimics Atlas Bot's Discord message):

```
**Signal Alert**

- Current Price: {price}
- Timeframe: {horizon} ({tv_resolution})

**Long**
- Entry: {long_entry}
- TP1: {long_tp1}
- TP2: {long_tp2}
- SL: {long_sl}
- R:R to TP1: {long_rr}

**Short**
- Entry: {short_entry}
- TP1: {short_tp1}
- TP2: {short_tp2}
- SL: {short_sl}
- R:R to TP1: {short_rr}

[a rejected side replaces its five lines with:]
- No valid long setup: {long_reason}

[if trade_type == option:]
**Best Call Contract:**
- {strike}c {expiry_date} — ${premium}/contract

**Best Put Contract:**
- {strike}p {expiry_date} — ${premium}/contract

**Reason:**
- Price Action: {description}
- Key Levels: {description}
- News and Metrics: Manual check recommended (no news source connected)
- Impact: hold {x} and {y} is next; lose {a} and {b} is next
```

Then attach the chart screenshot.

## Honesty footer (always include)

> ⚠ Levels are derived from technicals only (VWAP, EMAs, ATR, recent swings). No Greek/GEX data — Atlas Bot's GEX walls come from an options-flow provider that's not wired up here. Backtested on SPY 15-minute bars (Jan–Oct 2026), these rules showed no edge after costs. Not financial advice.

## When to ask the user

- Symbol/trade_type/timeframe missing → ask once, then proceed.
- `trade_type == option` but TV's option chain didn't render → tell them, suggest connecting an options-flow data source. Don't fabricate strike data.
- Symbol unknown to TradingView (`chart_set_symbol` returns an error) → ask for clarification.

## Notes about market state

- If the most recent bar is from a Friday/holiday and "today" is non-trading, frame the signal as **next session 0DTE** (e.g. "based on Fri close, levels for Mon's open"). State this clearly so the user doesn't assume the levels are intra-session.
- If the screenshot comes back covered by a TradingView upgrade/promo modal (the indicator-limit popup, etc.), tell the user to dismiss it and continue with the textual signal anyway.

## Memory notes for the developer

- The MCP server's `chart_manage_indicator` has a bug: `chart.createStudy` returns a Promise that the server doesn't await (`evaluate()` defaults to `awaitPromise: false`). When TV rejects (e.g. plan limit, unknown name), the tool returns `success: false` with no error string. Compute indicators yourself instead.
- `ui_evaluate` has the same `awaitPromise: false` issue — don't try to `await` Promises in the returned IIFE; return synchronous values.
- TradingView Basic plan = 2 user indicators (Volume is free). Don't try to add more.
- The rules live in the step 4 script, not in this prose. To change them, change `backtest/backtest.py` to match (including `SELECTED`), re-run the backtest, and run `backtest/check_parity.py` before committing.
