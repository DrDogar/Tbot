# Changelog

All notable changes to TBOT, in order. Each entry maps to a git commit (hash noted)
so you can `git show <hash>` for the full diff.

**Push policy**: changes are committed locally as they're made, but NOT pushed to
GitHub until explicitly requested. Entries under **[Unreleased]** exist locally only.

---

## [Unreleased]

Nothing pending — the last commit below is the current `HEAD`, not yet pushed
further work will land here first.

---

## v5.3 — 2026-08-25 — `1a0cb5b`
**Trim arena to 5 bots**
- Retired Momentum Rider (+9.6%) and Weekly Trend Follower (+6.8%) — cut by choice
  to focus the roster, not for losing money.
- Liquidated both bots' open positions at live market price before removal.
- Updated README to match (roster, results table, retired-bots note).

## v5.2 — 2026-08-25 — `3866391`
**Retire losers, add Patient Trend AI, fix watchdog popup**
- Retired Scalper and Aggressive Multi-Vote — the only two bots never clearly
  profitable after ~3 weeks live. Positions liquidated first.
- Added **Patient Trend AI**: a 4th from-scratch NumPy MLP bot, trained on a
  2-day-ahead target (vs. a few hours for the other AI bots) plus an extra 30-day
  macro "regime" feature. No take-profit cap, 3% trailing stop instead of a tight
  one — built to sit out chop/down-drift and only commit on a real sustained trend.
  First attempt collapsed to always predicting HOLD (training accuracy exactly
  matched the majority-class baseline); fixed by tuning the label horizon/threshold
  and increasing model capacity, verified against real data across all 5 coins
  before going live.
- Fixed the watchdog task flashing a visible console window every 5 minutes — it
  now runs via a hidden `wscript.exe` wrapper. Consolidated its registration into
  one script (`register_watchdog_task.ps1`) so `start_detached.ps1` couldn't
  clobber the fix with its own stale copy again (it briefly did, mid-session).
- Updated README to match.

## v5.1 — 2026-08-24 — `0db533b`
**Add README**
- Full documentation: what the project is, quick start, every bot explained,
  the training pipeline, risk management, the reliability/self-healing design,
  the web dashboard, a file-by-file breakdown of every tracked file, and a
  results snapshot (8-bot roster at the time).

## v5.0 — 2026-08-24 — `a581496`
**"TBOT v5: multi-bot trading arena with ensemble ML strategies"**

The big one — everything from a single-strategy bot to an 8-bot arena, built up
over an extended session:
- **8-bot arena** (`bots/`): each bot gets its own $1,000, trades all 5 coins,
  fully isolated from the others' errors.
  - 5 rule-based bots: Momentum Rider, Scalper, Breakout Hunter, Weekly Trend
    Follower, Aggressive Multi-Vote — each with distinct entry logic and
    stop-loss/take-profit/trailing-stop parameters.
  - Neural Net Trader: from-scratch NumPy MLP (2-layer, ReLU, softmax, manual
    backprop), trained locally, no API/cost.
  - Random Forest Trader: from-scratch bagged ensemble of 25 decision trees.
  - Ensemble Meta-Trader: a second MLP "stacked" on what the Neural Net and
    Random Forest already predict.
- **Training pipeline**: full year of hourly data per coin, bar-by-bar backtest
  gating for rule-based bots, shared feature engineering for the AI models.
- **Fee-aware paper trading** (`risk/spot_guard.py`): real 0.1% Binance taker
  fee modeled on both entry and exit; exits always fully close a position
  regardless of entry chunk size.
- **Confidence-scaled position sizing** (`bots/position_sizing.py`): $100
  chunks, 1–4 chunks depending on signal confidence.
- **Resumable, unlimited-duration sessions**: checkpointed after every symbol
  evaluation; `SESSION_DURATION_HOURS` set effectively unlimited (10 years)
  instead of auto-finalizing on a fixed 24h window.
- **Reliability**: arena/monitor run as detached Windows Scheduled Tasks
  (survive terminal/IDE closing), self-restart in-process on crash, and a
  `TBOT-Watchdog` task checks every 5 minutes and relaunches either if it's
  not running (the safety net for extended laptop sleep/hibernate).
- **Live web dashboard** (`dashboard/`): `/arena` leaderboard with live price
  ticker, per-bot detail, equity history, and activity log.
- **Stop-loss widened to 10% across all bots**: originally 0.25–0.8% per bot,
  which meant ordinary volatility kept triggering exits before positions could
  recover. Widened uniformly so bots hold through drawdown instead of getting
  chopped by noise.
- Also retained the original single-strategy engine (`engine/`, `run_session.py`)
  for comparison, optionally Claude-API-advised (`ai/`) though unused by default.

## v0.7 — 2026-06-28 — `f588fb0`
**"Added dashboard, RSI, charts and project architecture"**
- Terminal market dashboard, RSI analysis, candlestick charts (`mplfinance`),
  and the initial modular project structure (config/exchange/data/indicators/
  strategies/risk/services/controllers).

## v0.1 — 2026-06-28 — `004766e`
**"Version 0.1 - Live BTC Price"**
- The very first version: fetch and print the live BTC/USDT price from Binance.
