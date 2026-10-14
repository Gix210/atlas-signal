# atlas-signal

A Claude Code slash command that turns a live TradingView chart into a structured trade signal: long and short entries, two take-profit targets, a stop-loss, and a written rationale. It reads price data from TradingView Desktop through the [TradingView MCP server](https://github.com/LewisWJackson/tradingview-mcp-jackson), computes the indicators itself, and formats the result like a Discord signal alert.

```
/atlas SPY option 0dte
/atlas NVDA stock week
/atlas BTCUSD stock 60
```

## What it produces

A real run of `/atlas SPY stock day`, made after the close on October 14, 2026:

```
Signal Alert

- Current Price: 769.62
- Timeframe: end of day (15), based on the Oct 14 close; levels for the next session

Long
- Entry: 770.00
- TP1: 770.31
- TP2: 774.62
- SL: 766.70

Short
- Entry: 768.40
- TP1: 767.08
- TP2: 763.79
- SL: 770.90

Reason:
- Price Action: below VWAP 770.31, above 9 EMA 768.78, below 20 EMA 769.76
- Key Levels: recent high 772.60, recent low 766.70, VWAP 770.31 (closest, immediate resistance)
- News and Metrics: Manual check recommended (no news source connected)
- Impact: hold 770.00 and 770.31 is next; lose 768.40 and 767.08 is next
```

![SPY 15-minute chart analyzed by the run above](docs/atlas_SPY_day.png)

The long side of this run shows the main weakness the [backtest](#backtest) found: TP1 is $0.31 above the entry while the stop is $3.30 below it.

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

## Backtest

I replayed the rules on every 15-minute bar of SPY from January 2 to October 14, 2026 (197 sessions), using only the data the command would have seen at each moment. Full method and tables: [backtest/RESULTS.md](backtest/RESULTS.md).

| One signal per day (10:15 ET bar) | Long | Short |
|---|---|---|
| TP1 hit before stop | 49.5% | 52.2% |
| Stopped out | 22.2% | 22.2% |
| Still open at the close | 28.3% | 25.6% |
| Median reward:risk to TP1 | 0.40 | 0.37 |
| Expectancy per trade | −0.066 R | −0.080 R |

TP1 gets hit more than twice as often as the stop, yet the rules still lose money: TP1 sits about 0.4 R from entry, so they would need to win about 70% of the time to break even. Roughly a third of setups also have a target on the wrong side of the entry. These results set the next version's priorities: tie targets and stops to volatility (ATR), reject setups with reward:risk below 1, and test again.

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
- The rules are fixed heuristics, and the [backtest](#backtest) shows they lose money in their current form.

## Disclaimer

This is a personal project for learning and research. It is not financial advice, and nothing it outputs is a recommendation to buy or sell any security. The output format is modeled on the "Atlas Bot" Discord signal style. This project is not affiliated with Atlas Bot or TradingView.

---

Built with Claude Code.
