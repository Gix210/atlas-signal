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

2. **DO NOT add indicators.** TradingView Basic plan caps at 2 user indicators, and `chart_manage_indicator` silently fails (server bug: doesn't await the createStudy Promise). Instead, compute VWAP / 9 EMA / 20 EMA yourself from the OHLCV data via `mcp__tradingview__ui_evaluate` in step 4. Use whatever RSI is already on the chart via `data_get_study_values`; if missing, mark RSI as `n/a` in the output.

3. **Read state in parallel**
   - `mcp__tradingview__quote_get`
   - `mcp__tradingview__data_get_study_values` → grab RSI if present (skip if not)
   - `mcp__tradingview__data_get_ohlcv` count=100 summary=false → for indicator math + swing levels
   - `mcp__tradingview__capture_screenshot` region=chart filename=`atlas_{symbol}_{tf_input}`

3b. **Compute indicators in-page** via `mcp__tradingview__ui_evaluate` (one round-trip, exact math). Use this template:

```javascript
(function() {
  var chart = window.TradingViewApi.activeChart();
  var bars = chart._chartWidget.model().mainSeries().bars();
  var first = bars.firstIndex(), last = bars.lastIndex();
  var all = [];
  for (var i = first; i <= last; i++) {
    var v = bars.valueAt(i);
    if (v) all.push({ t: v[0], o: v[1], h: v[2], l: v[3], c: v[4], v: v[5] });
  }
  // Last gap > 1 hour marks the start of the current session.
  // 24h markets (crypto) have no gap: anchor to the latest 00:00 UTC instead.
  var sessionStart = -1;
  for (var j = all.length - 1; j > 0; j--) {
    if (all[j].t - all[j-1].t > 3600) { sessionStart = j; break; }
  }
  if (sessionStart < 0) {
    var dayStart = Math.floor(all[all.length-1].t / 86400) * 86400;
    sessionStart = 0;
    while (sessionStart < all.length - 1 && all[sessionStart].t < dayStart) sessionStart++;
  }
  var session = all.slice(sessionStart);
  var pv = 0, vv = 0;
  for (var k = 0; k < session.length; k++) {
    var b = session[k];
    pv += ((b.h + b.l + b.c) / 3) * b.v;
    vv += b.v;
  }
  function ema(closes, len) {
    var kk = 2 / (len + 1), e = closes[0];
    for (var i = 1; i < closes.length; i++) e = closes[i] * kk + e * (1 - kk);
    return e;
  }
  var closes = all.map(function(b){ return b.c; });
  var last20 = all.slice(-20);
  return {
    last_price: all[all.length-1].c,
    vwap: Number((pv/vv).toFixed(2)),
    ema9: Number(ema(closes, 9).toFixed(2)),
    ema20: Number(ema(closes, 20).toFixed(2)),
    recent_high: Math.max.apply(null, last20.map(function(b){return b.h;})),
    recent_low:  Math.min.apply(null, last20.map(function(b){return b.l;})),
    session_high: Math.max.apply(null, session.map(function(b){return b.h;})),
    session_low:  Math.min.apply(null, session.map(function(b){return b.l;})),
    session_bars: session.length,
  };
})()
```

4. **Derive levels** from those bars + indicators:
   - `recent_high` = max high of last 20 bars
   - `recent_low`  = min low of last 20 bars
   - `prior_high` = 2nd-highest local high (exclude last 2 bars)
   - `prior_low`  = 2nd-lowest local low (exclude last 2 bars)
   - For index ETFs (SPY/QQQ/IWM) use ~0.05% buffer; individual stocks ~0.15%; crypto ~0.25%

5. **Build Long setup**
   - **Entry**: `max(last_price, 9_EMA) + buffer` (breakout-style); if price is sitting well above 9 EMA, use `last_price + small buffer` for a continuation
   - **TP1**: VWAP if price is below VWAP, otherwise `prior_high` or `entry × (1 + 0.3%)` whichever is closer
   - **TP2**: `recent_high` or `entry × (1 + 0.6%)` whichever is further
   - **SL**:  `min(20_EMA, prior_low) − buffer`

6. **Build Short setup** (mirror everything)

7. **If `trade_type == option`** — DO NOT try to scrape TradingView. Verified 2026-05-30 to be impossible:
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

8. **Build Reason block**
   - **Price Action**: describe position vs VWAP, 9 EMA, 20 EMA (e.g. "above VWAP 751.28, above 9 EMA 752.10, above 20 EMA 751.53")
   - **Key Levels**: recent_high, recent_low, VWAP — call out which is closest as immediate support/resistance
   - **News and Metrics**: we don't have a news feed wired up — write `Manual check recommended (no news source connected)`
   - **Impact**: `hold {long_entry} and {long_TP1} is next; lose {short_entry} and {short_TP1} is next`

9. **Render output in this exact format** (mimics Atlas Bot's Discord message):

```
**Signal Alert**

- Current Price: {price}
- Timeframe: {horizon} ({tv_resolution})

**Long**
- Entry: {long_entry}
- TP1: {long_tp1}
- TP2: {long_tp2}
- SL: {long_sl}

**Short**
- Entry: {short_entry}
- TP1: {short_tp1}
- TP2: {short_tp2}
- SL: {short_sl}

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

> ⚠ Levels are derived from technicals only (VWAP, EMAs, recent swings). No Greek/GEX data — Atlas Bot's GEX walls come from an options-flow provider that's not wired up here. Not financial advice.

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
