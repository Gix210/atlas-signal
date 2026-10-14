# v2 test plan

Written and committed before any v2 variant was run, so the results can't influence the choices below. The commit history shows the order.

## Data and periods

- SPY 15-minute regular-hours bars, 2026-01-02 to 2026-10-14. This is the same export as the v1 backtest.
- **In-sample:** signals dated 2026-01-02 to 2026-06-30. Used only to pick one variant.
- **Out-of-sample:** signals dated 2026-07-01 to 2026-10-14. Used once, to report the variant that was picked. Nothing changes after these results are seen.

Disclosure: I had already seen v1's results on the full period, which is why v2 exists. No v2 variant had been run on either period when this plan was written.

## Rules shared by every variant

- **Entry** is unchanged from v1. Long: max(price, 9 EMA) + buffer. Short: min(price, 9 EMA) − buffer. Filled as a stop order.
- **ATR(14)** uses Wilder smoothing and the same 100 bars the command reads.
- **Stop** = entry ∓ s × ATR. **TP1** = entry ± r × stop distance. **TP2** = entry ± 2r × stop distance.
- **Reject rule:** skip a setup when TP1 or the stop is on the wrong side of the entry, or when reward:risk to TP1 is below 1.0.
- **Exits:** TP1, the stop, or the session close, whichever comes first. Same simulator as v1, with the same assumptions that favour the stop when a bar's order of prices is unknown.

## The grid (12 variants)

| Setting | Values |
|---|---|
| Stop distance s | 1.0 ATR, 1.5 ATR |
| Reward:risk r | 1.0, 1.5, 2.0 |
| Confluence filter | off, on |

With the confluence filter on, a long is taken only when price is above session VWAP and neither the 20-bar high nor the prior swing high sits between the entry and TP1. Shorts mirror this. VWAP and the swing levels become filters, where v1 used them as targets.

Two reference rows are reported but can't be picked: v1 as published, and v1 with the new reject rule.

## Costs

$0.02 per share round trip (spread plus slippage), charged on every filled trade. In R terms: cost = 0.02 / stop distance.

## Selection rule

Pick the variant with the highest in-sample expectancy per filled trade after costs. Long and short trades are pooled, signals come from every bar, and a variant needs at least 200 filled in-sample trades to qualify. On a tie, the variant with more filled trades wins.

## What gets reported

- In-sample results for all 12 variants and both reference rows.
- The picked variant and v1 on both periods, before and after costs. Each comes with a 95% confidence interval from a bootstrap that resamples whole sessions (2,000 resamples), since signals within a session overlap.
- The same comparison for the one-signal-per-day sample (close of the 10:15 ET bar).
- Out-of-sample results for every variant in an appendix. These are for transparency and play no part in the selection.

## Success criterion

v2 counts as working if the picked variant's out-of-sample expectancy after costs is above zero. If the 95% interval includes zero, the write-up says the edge isn't established.
