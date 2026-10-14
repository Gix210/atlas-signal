# atlas-signal

A Claude Code slash command that turns a live TradingView chart into a structured trade signal: long and short entries, two take-profit targets, a stop-loss, and a written rationale. It reads price data from TradingView Desktop through the [TradingView MCP server](https://github.com/LewisWJackson/tradingview-mcp-jackson), computes the indicators itself, and formats the result like a Discord signal alert.

```
/atlas SPY option 0dte
/atlas NVDA stock week
/atlas BTCUSD stock 60
```

## What it produces

```
Signal Alert

- Current Price: 751.84
- Timeframe: today's close (5)

Long
- Entry: 752.22
- TP1: 754.10
- TP2: 756.40
- SL: 750.95

Short
- Entry: 751.46
- TP1: 749.90
- TP2: 748.05
- SL: 752.80

Reason:
- Price Action: above VWAP 751.28, above 9 EMA 751.70, above 20 EMA 751.53
- Key Levels: recent high 756.40, recent low 748.05, VWAP 751.28 (closest, immediate support)
- News and Metrics: Manual check recommended (no news source connected)
- Impact: hold 752.22 and 754.10 is next; lose 751.46 and 749.90 is next
```

*Illustrative numbers. Each run also attaches a screenshot of the chart it analyzed.*

## Methodology

### Timeframe mapping

| Input   | Chart resolution | Horizon                  |
|---------|------------------|--------------------------|
| `0dte`  | 5 min            | today's close            |
| `day`   | 15 min           | end of today             |
| `week`  | 1 hour           | this week's Friday expiry |
| `month` | Daily            | next monthly expiry      |

Any raw TradingView resolution (`1`, `5`, `15`, `60`, `240`, `D`, `W`, `M`) also works.

### Indicators (computed from the last 100 bars)

- **VWAP**, session-anchored: Σ(typical price × volume) / Σ(volume), where typical price = (H + L + C) / 3. The session start is detected as the last gap of more than one hour between bars.
- **9 EMA and 20 EMA**: standard exponential moving averages, smoothing factor k = 2 / (n + 1).
- **Swing levels**: highest high and lowest low of the last 20 bars, plus the second-highest and second-lowest local extremes (excluding the two most recent bars).
- **RSI**: read from the chart if it's already there, otherwise reported as `n/a`.

### Level construction

A price buffer is scaled to the instrument's typical volatility: 0.05% for index ETFs (SPY, QQQ, IWM), 0.15% for single stocks, 0.25% for crypto.

| Level | Long rule |
|-------|-----------|
| Entry | max(last price, 9 EMA) + buffer (breakout); last price + buffer if already extended above the 9 EMA |
| TP1   | VWAP if price is below it; otherwise the closer of the prior swing high or entry + 0.3% |
| TP2   | the further of the 20-bar high or entry + 0.6% |
| SL    | min(20 EMA, prior swing low) − buffer |

The short side mirrors these rules.

### Options contracts

When `option` is passed, the command does not invent strikes. TradingView's options data can't be reached from the chart (see [engineering notes](docs/engineering-notes.md)), so the output names the data sources that would make contract selection possible (Unusual Whales, Polygon.io, or a pasted chain) and delivers the technical levels on their own.

## Design decisions

- **Compute indicators in-page instead of adding studies.** TradingView's Basic plan caps user indicators at two, and the MCP's add-indicator tool fails silently. Running the math in a single JavaScript call against the chart's own bar data is exact and costs one round-trip.
- **No fabricated data.** Missing RSI shows as `n/a`, missing options data is stated, and the news section asks for a manual check. Every signal ends with a disclaimer that the levels are technical-only.
- **Market-state awareness.** On weekends or holidays, the signal is framed as levels for the next session's open.

## Requirements

- [Claude Code](https://claude.com/claude-code)
- TradingView Desktop, running
- [tradingview-mcp-jackson](https://github.com/LewisWJackson/tradingview-mcp-jackson) connected to Claude Code

## Install

Copy the command into your Claude Code commands folder:

```bash
cp .claude/commands/atlas.md ~/.claude/commands/
```

Or clone this repo and run Claude Code from inside it. The command is picked up from `.claude/commands/` automatically.

## Limitations

- Technical levels only. No order flow, gamma exposure (GEX), or options Greeks.
- No news feed. Earnings dates, macro releases and headlines have to be checked by hand.
- The rules are fixed heuristics. They have not been backtested, and nothing here measures their hit rate.

## Disclaimer

This is a personal project for learning and research. It is not financial advice, and nothing it outputs is a recommendation to buy or sell any security. The output format is modeled on the "Atlas Bot" Discord signal style. This project is not affiliated with Atlas Bot or TradingView.

---

Built with Claude Code.
