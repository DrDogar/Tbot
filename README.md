# TBOT — Multi-Bot Crypto Paper-Trading Arena

TBOT is a **paper-trading** (simulated money, real market data) crypto trading system built around one central experiment: instead of picking one strategy, run **independent bots**, each with its own $1,000, its own strategy, and its own risk rules, side by side on the same 5 coins — and let the results decide which approach actually works. Underperforming bots get retired and replaced rather than left running forever, so the roster changes over time as the experiment continues.

Everything runs locally. No paid APIs, no cloud costs. The 4 "AI" bots are neural networks and decision-tree ensembles written from scratch in NumPy and trained on historical data — not a hosted LLM.

> ⚠️ **Paper trading only.** No real orders are ever sent, no exchange API keys are required for trading. This is a research/learning project, not investment advice.

---

## What it actually does

1. Pulls live and historical OHLCV candles for `BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT` from Binance's public API (via `ccxt` — no account or API key needed).
2. Trains all bots on the last **full year** of hourly data per coin: the 1 rule-based bot gets backtested to see which coins it historically made money on; the 4 AI bots get properly trained.
3. Runs continuously, evaluating every bot against all 5 coins once a minute, simulating fills, fees, stop-losses and take-profits exactly as a real spot exchange would apply them.
4. Serves a live web dashboard so you can watch every bot's equity, trades, and reasoning in real time.
5. Is designed to survive the machine it runs on being unreliable — it checkpoints after every single action and self-heals if killed, the laptop sleeps, or the network drops.

---

## Quick start

```bash
pip install -r requirements.txt

python run_arena.py       # starts the 5-bot arena (resumable, runs forever until stopped)
python run_monitor.py     # starts the web dashboard
```

Then open **http://127.0.0.1:5000/arena** in a browser.

For hands-off, reboot-proof operation on Windows, use `scripts/start_detached.ps1` (see [Reliability](#reliability--staying-alive) below) instead of running the two commands directly in a terminal.

`main.py` also offers an interactive menu covering everything (single-symbol tools, the older single-strategy session, and the arena) — run `python main.py`.

---

## Versioning

The running version is tracked in one place — `APP_VERSION` in `config/settings.py`
— and shown in the arena's startup log line and as a small badge in both dashboard
headers. It follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`):
MAJOR for architecture changes, MINOR for a bot added/removed or a new capability,
PATCH for bug fixes/reliability work/tooling.

`CHANGELOG.md` documents every version in [Keep a Changelog](https://keepachangelog.com)
format — what was Added/Changed/Fixed/Removed, with the git commit hash for each
entry so you can `git show <hash>` for the full diff. Every released version is
also tagged in git (`git tag -l`).

Commits happen locally as changes are made; nothing reaches GitHub until
explicitly pushed — check `CHANGELOG.md`'s `[Unreleased]` section for what's
sitting locally versus what's actually live on the remote.

---

## The bots

Every bot gets a fresh **$1,000**, trades across all 5 coins, and is fully isolated from the others (one bot's error never affects another's — see `bots/engine.py`). What differs between them is **when they enter a trade** and **how tightly they manage the exit**.

| Bot | How it decides to enter | Stop-loss | Take-profit | Trailing stop |
|---|---|---|---|---|
| **Breakout Hunter** | Price breaks a 20-candle high on 1.2×+ volume | 10% | 1.0% | — |
| **Neural Net Trader** 🤖 | A from-scratch NumPy MLP (2-layer, ReLU, softmax, manual backprop) trained on a year of data per coin, predicting the next few hours | 10% | 0.8% | — |
| **Random Forest Trader** 🤖 | A from-scratch bagged ensemble of 25 decision trees (Gini splits, feature-sampled), same short-horizon target as the neural net | 10% | 0.8% | — |
| **Ensemble Meta-Trader** 🤖🤖 | A second NumPy MLP, "stacked" on top of the other two — trained on what the Neural Net *and* Random Forest already predicted, learning when to trust which one | 10% | 0.8% | — |
| **Patient Trend AI** 🤖🤖🤖 | A third, separately-tuned NumPy MLP trained to predict 2-day-ahead moves (not a few hours), using an extra 30-day macro "regime" feature the others don't see. Deliberately selective — sits in cash through chop/down-drift, only acts on a real trend | 10% | — (rides winners) | 3% off peak |

The three original AI bots share the same 6 engineered input features (RSI, EMA trend, volume, volatility, price action, weekly trend — see `strategies/market_models.py`) and predict SELL/HOLD/BUY with a confidence score. Patient Trend AI uses those same 6 plus a 7th (30-day regime) and a longer, harder-to-hit label, which needed more model capacity (12 hidden units, 1,200 training epochs vs. the others' 6/400) to actually learn instead of collapsing to always predicting HOLD — verified empirically before it went live (see `bots/trend_ai_model.py`). Breakout Hunter uses hand-written logic (`bots/entry_strategies.py`).

**Retired**: 4 of the original 9 bots have been pulled from the roster so far. Each time, any open position was liquidated at the live market price before removal, and the historical portfolio/trade data stays on disk (`state/bots/portfolio_<key>.json`) for the record — they just no longer trade.
- **Scalper** and **Aggressive Multi-Vote** — removed after both proved to be net losers over ~3 weeks of live trading; their fee-to-profit ratio never recovered even after the stop-loss widening below helped every other bot.
- **Momentum Rider** and **Weekly Trend Follower** — removed to trim the roster to 5, not for losing money (both were solidly profitable, +9.6% and +6.8%, at the time). Weekly Trend Follower was the weakest performer among the active traders; Momentum Rider was cut by choice rather than by results.

**Position sizing** is confidence-scaled: every entry is sized in **$100 chunks**, 1–4 chunks depending on how confident the signal is (`bots/position_sizing.py`), so a 90%-confidence AI prediction risks more than a 30%-confidence one.

**Why every stop-loss is 10%**: the bots originally ran with tight per-bot stops (0.25%–0.8%). In a choppy/declining market this meant they got stopped out of positions by ordinary noise before the position had a chance to recover, repeatedly paying the round-trip fee for nothing. All bots were widened to a uniform 10% stop-loss so they hold through normal volatility instead of panic-selling on small dips — see [Results](#results-to-date) for how that changed things.

---

## How training works

Every time the arena (re)starts, and any time a new bot joins mid-run:

1. For each of the 5 coins, fetch the **last 365 days of 1-hour candles** (`data/collector.py`).
2. For the 1 rule-based bot (Breakout Hunter), replay that whole year bar-by-bar through its own entry/exit logic (`bots/trainer.py`) to see how it would have performed — this decides whether it's allowed to trade a given coin live (a coin it lost money on in the backtest is blocked, unless it has zero trade history).
3. Build one shared feature/label dataset from that year of data (`bots/neural_model.py: build_training_dataset`) — reused by the Neural Net, Random Forest, and Ensemble so the expensive feature engineering only happens once per coin.
4. Train the Neural Net (gradient descent) and Random Forest (bagged trees) on that dataset.
5. Train the Ensemble Meta-Trader on a *second* dataset built from what the Neural Net and Random Forest already predicted at each historical point (`bots/ensemble_model.py`), so it learns when to trust which one.
6. Train Patient Trend AI on a *third*, differently-shaped dataset (`bots/trend_ai_model.py: build_long_training_dataset`) — a 2-day-ahead label instead of a few hours, plus a 30-day regime feature, built from the same year_df but sliced differently.

A full retrain (~4 minutes) only happens on a fresh start, when a brand-new bot joins an in-progress arena, or if a network blip corrupted the last attempt (auto-retried with backoff — see `bots/runner.py: _run_training_with_retry`).

---

## Risk management

- **Fee-aware fills**: every trade models Binance's real 0.1% spot taker fee. A BUY receives fewer coins than the raw dollar amount would suggest; a SELL nets less cash back (`risk/spot_guard.py`).
- **No shorting, spot-only**: a SELL is blocked if the bot doesn't hold the coin.
- **Exits always fully close a position**, however many $100 chunks it was built from — only entries are capped at `MAX_TRADE_QUOTE_AMOUNT` ($500); an exit is never artificially clamped, because a stop-loss that can't fully close a position isn't really a stop-loss.
- **Three independent exit triggers**, checked every cycle (`bots/position_manager.py`):
  - **Stop-loss** — hard exit if the position is down more than the bot's `stop_loss_pct` from entry.
  - **Trailing stop** — (Patient Trend AI only) locks in gains by exiting if price falls more than 3% off its peak *while still in profit*.
  - **Take-profit** — locks in gains once the position is up `take_profit_pct`.

---

## Reliability — staying alive

This started as a laptop that "turns off on its own," so a lot of the engineering here is about the system surviving that rather than assuming a stable always-on server.

- **Resumable by design**: state is checkpointed to `state/` after every single symbol evaluation, not just every cycle. Killing the process at any point loses at most a few seconds of work.
- **Detached from the terminal**: the arena and monitor run as **Windows Scheduled Tasks** (`scripts/start_detached.ps1`), not as child processes of a terminal/IDE session — so closing VS Code, a terminal, or a Claude Code session doesn't kill them. (Both tasks also explicitly ignore battery-power restrictions, since this runs on a laptop.)
- **No console windows**: both tasks launch via `pythonw.exe` (the windowless build of the Python interpreter) rather than `python.exe`, so nothing pops up on screen when they (re)start. This runs the actual script directly as the task's own action — no wrapper process involved — so Task Scheduler tracks and can kill it exactly like a normal console process.
- **Self-healing at the process level**: `run_arena.py` and `run_monitor.py` each wrap their main loop in a crash-and-restart loop — an uncaught exception logs, waits 5 seconds, and restarts in-process rather than taking the whole task down.
- **Self-healing at the OS level**: a third task, `TBOT-Watchdog` (`scripts/watchdog.ps1`), runs every 30 minutes and relaunches either task if it isn't in the `Running` state — the safety net for the case where the laptop's own sleep/hibernate killed both the process-level retry loop *and* Task Scheduler's built-in restart-on-failure at the same time (observed happening after long sleeps). It runs via a hidden `wscript.exe` wrapper (`scripts/watchdog_silent.vbs`) rather than invoking PowerShell directly, so the check never flashes a visible console window.
- **Network-resilient training**: a failed retrain (e.g. a DNS blip fetching Binance data) is retried 3× with backoff; if it still fails, a resumed arena falls back to whatever training/weights already exist instead of crashing a session that has hours of progress.
- **Unbounded run**: `SESSION_DURATION_HOURS` is set to 10 years (`config/settings.py`) — the arena runs continuously until manually stopped rather than auto-finalizing on a fixed schedule.
- **Known limitation**: both tasks are registered with `LogonType: Interactive`, meaning they depend on an active Windows logon session. They survive closing any app/terminal (including this one), computer sleep, and crashes — but not an actual sign-out or a reboot nobody logs back into. Fixing that requires switching to a logon type that doesn't need an active session (e.g. storing credentials), which needs an elevated one-time setup step outside of what this project automates.

---

## Web dashboard

`dashboard/web_server.py` is a small Flask app with two views:

- **`/arena`** — the live 5-bot leaderboard: equity, P&L%, trade count, fees paid, live price ticker, per-coin positions and reasoning, and a recent-activity log. This is the main view.
- **`/`** — a single-strategy monitor for the older `run_session.py` engine (see below).

Both poll `state/*.json` and `state/*.csv` on an interval (`WEB_MONITOR_REFRESH_SECONDS`, default 5s) — the dashboard is a pure read-only viewer over the same state files the arena writes, so it never affects trading.

---

## Project structure

### Entry points

| File | Purpose |
|---|---|
| `main.py` | Interactive menu covering every feature (single-symbol tools, the old single-strategy session, and the arena). |
| `run_arena.py` | Starts/resumes the 5-bot arena, unattended. Self-restarts on crash. |
| `run_monitor.py` | Starts the Flask web dashboard. Self-restarts on crash. |
| `run_session.py` | Starts/resumes the older single-portfolio, single-strategy 24h session (see [Two systems](#two-systems-in-this-repo)). |

### `bots/` — the arena (the current system)

| File | Purpose |
|---|---|
| `bot_configs.py` | Declares every bot: name, entry function, stop-loss/take-profit/trailing-stop, which AI model (if any) it uses. |
| `engine.py` | Evaluates one coin against every bot for one cycle: checks exits first, then entries; fully isolates each bot's errors from the others. |
| `entry_strategies.py` | Breakout Hunter's entry logic (the one active rule-based bot), plus the retired Momentum Rider/Weekly Trend Follower/Scalper/Aggressive Multi-Vote logic (unused but kept for the record). |
| `position_manager.py` | Stop-loss / trailing-stop / take-profit exit logic, shared by every bot. |
| `position_sizing.py` | Confidence → $100-chunk position size (1–4 chunks). |
| `trainer.py` | Bar-by-bar backtester used to train and gate the rule-based bot(s) on a year of data. |
| `neural_model.py` | The from-scratch NumPy MLP: feature engineering, dataset building, training (manual backprop), inference, JSON (de)serialization. Shared feature code is reused by the Random Forest and Ensemble bots too. |
| `forest_model.py` | The from-scratch Random Forest: Gini-impurity tree building, bagging, feature subsampling, quantile-based split search (kept fast enough to train on a year of hourly data), JSON (de)serialization. |
| `ensemble_model.py` | The stacking Ensemble Meta-Trader: builds a training set from the Neural Net's and Random Forest's own predictions, then trains a third MLP (reusing `neural_model`'s trainer) on top of them. |
| `trend_ai_model.py` | Patient Trend AI: a 7-feature (6 shared + a 30-day regime feature), 2-day-ahead-label dataset builder, trained with more capacity/epochs than the other AI bots (needed to avoid collapsing to always-HOLD — a longer, higher-threshold target is a harder learning problem). Reuses `neural_model`'s MLP trainer/predictor as-is. |
| `runner.py` | The main arena loop: fresh-start vs. resume logic, per-symbol training, the resumable cycle loop, crash-retry around retraining, config resync (interval/duration) on resume. |

### `config/`

| File | Purpose |
|---|---|
| `settings.py` | Every tunable constant in the system: tracked symbols, timeframes, indicator periods, risk limits, fee assumptions, position sizing, session duration, dashboard port, etc. |

### `data/` & `exchange/`

| File | Purpose |
|---|---|
| `exchange/binance.py` | The shared `ccxt` Binance client (public endpoints only) and `get_live_price`. |
| `data/collector.py` | Candle fetching: a single recent window (`get_market_data`), and paginated historical pulls for the last 24h/week/30-day-regime/year (`get_historical_market_data` and its `get_last_*`/`get_regime_market_data` wrappers). |

### `indicators/` & `strategies/`

| File | Purpose |
|---|---|
| `indicators/rsi.py` | RSI calculation (via the `ta` library). |
| `strategies/market_models.py` | 5 independent "model votes" (RSI, EMA trend, volume, volatility, price action) plus a weekly-trend vote — the building blocks both the AI feature vector and the rule-based bots are built from. |
| `strategies/rsi_scalper.py` | Combines the model votes into one weighted mood score and BUY/SELL/HOLD signal — used by the *older* single-strategy engine and by `aggressive_voter_entry`. |
| `strategies/weekly_context.py` | Summarizes a window of candles into open/close/high/low/% change stats, used as the "weekly trend" feature everywhere. |

### `risk/` & `portfolio/`

| File | Purpose |
|---|---|
| `risk/spot_guard.py` | Turns a signal into an actual fee-aware `TradePlan`: caps entries, guarantees exits can always fully close a position, blocks shorting. |
| `portfolio/portfolio_state.py` | The `PortfolioState`/`Position`/`TradeRecord` data model and `apply_fill` (the only place cash/coins/realized P&L actually change). |
| `portfolio/persistence.py` | Save/load a portfolio to/from JSON. |
| `portfolio/valuation.py` | Marks open positions to the current live price to compute equity and P&L%. |

### `engine/` — the older single-strategy session

| File | Purpose |
|---|---|
| `runner.py` | The resumable loop for the single-portfolio session (mirrors `bots/runner.py` but for one strategy/one portfolio instead of a whole roster). |
| `trading_engine.py` | Evaluates one coin for the single-strategy engine; can route the decision through either the internal model or the Claude API (`DECISION_ENGINE` setting). |
| `session_state.py` | The `RunState` model: run id, start time, duration, cycle count, `is_expired`/`remaining_seconds`. |
| `equity_history.py` | Append-only CSV equity snapshots, used to draw the dashboard's equity chart. |
| `last_cycle.py` | Persists the most recent per-symbol decision/result for the dashboard to display. |

### `reporting/`

| File | Purpose |
|---|---|
| `arena_report.py` | Generates a text leaderboard report across every bot, sorted by P&L%. |
| `session_report.py` | Generates a text report for the single-strategy session. |

### `dashboard/`

| File | Purpose |
|---|---|
| `web_server.py` | The Flask app: `/api/status` and `/api/arena-status` JSON endpoints, `/` and `/arena` pages, live price fetching for the ticker. |
| `templates/arena.html` | The 5-bot arena dashboard: leaderboard, live price ticker, per-bot detail cards, activity log. |
| `templates/monitor.html` | The single-strategy dashboard. |
| `market_dashboard.py` | A terminal (non-web) snapshot dashboard for one symbol, used by the `main.py` menu. |

### `ai/` — optional, unused by default

| File | Purpose |
|---|---|
| `claude_client.py` | Lazily builds an `anthropic.Anthropic` client from `ANTHROPIC_API_KEY`. |
| `claude_advisor.py` | Sends the weekly context + current signal to Claude and asks it to call a `record_trade_decision` tool. Only used if `DECISION_ENGINE = "claude"` in `config/settings.py` — the arena itself never uses this; the AI bots are all local. Requires a **funded** Anthropic API key. |

### `controllers/` & `ui/`

| File | Purpose |
|---|---|
| `ui/menu.py` | The `main.py` terminal menu text. |
| `controllers/market_controller.py` | Handlers for the single-symbol menu items (live price, chart, RSI, dashboard, trade preview, market model analysis, the 1-second scalping smoke test). |
| `controllers/session_controller.py` | Handlers for the single-strategy session + web monitor menu items. |
| `controllers/arena_controller.py` | Handlers for the arena + arena report menu items. |

### `backtesting/` & `charts/`

| File | Purpose |
|---|---|
| `backtesting/scalping_smoke_test.py` | Replays 24h of 1-second candles through the RSI-scalper model to measure how often it would have captured a real short-term move vs. missed it or false-signaled. |
| `charts/plotter.py` | Renders a candlestick chart for one symbol via `mplfinance`. |

### `scripts/` — process management (Windows)

| File | Purpose |
|---|---|
| `start_detached.ps1` | Registers/starts the arena and monitor as Windows Scheduled Tasks (via `pythonw.exe`, so no console window), detached from any terminal, immune to battery-power restrictions; also (re)registers the watchdog task by calling `register_watchdog_task.ps1`. Safe to re-run any time (all three resume/reattach cleanly). |
| `register_watchdog_task.ps1` | Registers the `TBOT-Watchdog` task on its own (silent, hidden-window) definition — the single source of truth for it, so `start_detached.ps1` doesn't carry its own separate/divergent copy. |
| `watchdog.ps1` | The actual check: every 30 minutes, relaunches the arena/monitor tasks if either isn't `Running` — the safety net for extended sleep/hibernate. |
| `watchdog_silent.vbs` | Launches `watchdog.ps1` with a fully hidden window (`wscript.exe`, style 0) instead of the console flash a direct PowerShell scheduled-task action gives. |
| `register_autostart_task.ps1` | An older, simpler "run at logon" task for the single-strategy session (`run_session.py`). Superseded by `start_detached.ps1` for the arena. |

### `utils/`

| File | Purpose |
|---|---|
| `logger.py` | One shared logger, writing to both the console and `state/session.log`. |

---

## Two systems in this repo

TBOT grew from a single-strategy bot into a 5-bot arena, and both still work:

- **The arena** (`bots/`, `run_arena.py`, `/arena`) — the current system, described above. Independently-risked bots, $1,000 each.
- **The single-strategy session** (`engine/`, `run_session.py`, `/`) — the original design: one portfolio, one strategy (the same RSI/EMA/volume/volatility/price-action vote used by `aggressive_voter_entry`), optionally decided by the Claude API instead of the local model. Kept for comparison and because `main.py`'s menu still exposes it.

---

## Results to date

**As of 2026-08-31** — the overall session has been running continuously (with a handful of brief, self-healed interruptions) since **2026-08-02**, roughly **29 days**, cycle **7,336**. The current 5-bot lineup has been in place since **2026-08-25**. $1,000 starting balance per bot, all figures paper-trading only.

| Rank | Bot | Equity | P&L | Trades | Fees paid | Realized P&L |
|---|---|---|---|---|---|---|
| 1 | 🤖 Random Forest Trader | $1,175.01 | **+17.50%** | 335 | $65.04 | $235.49 |
| 2 | 🤖 Neural Net Trader | $1,169.50 | **+16.95%** | 336 | $67.24 | $239.37 |
| 3 | Breakout Hunter | $1,144.00 | **+14.40%** | 124 | $33.77 | $172.33 |
| 4 | 🤖🤖 Ensemble Meta-Trader | $1,106.15 | **+10.61%** | 159 | $29.76 | $155.82 |
| 5 | 🤖🤖🤖 Patient Trend AI | $1,000.00 | 0.00% | 0 | $0.00 | $0.00 |

Market context: BTC ran from ~$63,000 to ~$79,000 over the period (+~25%), with a rough patch in the first week (down to ~$62,700) before the broader rally. ETH, SOL, BNB, and XRP all moved similarly.

**What the data shows so far:**

- **The stop-loss change mattered.** In the first week, with tight per-bot stops (0.25–0.8%), every single bot was in the red — small, ordinary volatility kept triggering stop-losses before positions could recover, and round-trip fees compounded the damage. After widening every bot's stop-loss to a uniform 10% (holding through drawdown instead of cutting fast), the surviving bots are now all solidly positive, riding the market's actual trend instead of getting shaken out of it.
- **Both original from-scratch AI models are winning.** Neural Net Trader and Random Forest Trader — the two models trained on a full year of data — are the top two performers, and by a clear margin. They also trade the most (335–336 trades), which under the old tight-stop regime was a liability (more trades = more chances to get chopped) but under the wide-stop regime turned into an advantage (more chances to catch a real move).
- **The selective ensemble bet is paying off differently than expected.** Ensemble Meta-Trader was designed to be more selective — and it is (159 trades vs. 335–336 for the two models it's built on) — but that selectivity has so far cost it upside in a strongly trending market, landing it 4th rather than 1st. It's still clearly profitable and pays the least in fees per dollar earned of the three original AI bots, which may matter more in a choppier market than this one has mostly been.
- **The roster has been trimmed twice (both 2026-08-25).** First, Scalper and Aggressive Multi-Vote were retired — the only two bots never clearly profitable, both high-frequency/tight-take-profit designs that kept exiting winners early even after the stop-loss widening helped everyone else. Then Momentum Rider and Weekly Trend Follower were cut too, this time by choice rather than results (both were solidly profitable, +9.6% and +6.8%), to bring the arena down to a focused 5-bot lineup. All open positions were liquidated at the live price before each removal; full history stays on disk.
- **Patient Trend AI still hasn't traded, 6+ days in.** It's the most deliberately selective bot by design: trained on a 2-day-ahead target (vs. a few hours for the other AI bots) plus an extra 30-day macro regime feature, specifically so it can sit out chop/down-drift and only commit to a real, sustained trend. Getting that target to actually learn (rather than collapsing to always-HOLD) took real tuning — more model capacity and a carefully chosen horizon/threshold, verified against real data before going live. It's been consistently predicting HOLD or SELL across all 5 coins despite the broad uptrend — a legitimate outcome of combining the macro regime with near-term technicals rather than blindly following the trend, but a full week of total silence is long enough to start asking whether the bar it requires is simply too high to ever clear in practice, versus correctly disciplined patience. Still watching.
- **Reliability held up, with real gaps found and fixed along the way.** The watchdog has repeatedly caught and self-healed silent outages (the arena/monitor tasks going dead after extended laptop sleep). Two real bugs surfaced and got fixed: the watchdog's own scheduled-task action wasn't set to run hidden, flashing a visible console every check; and a first attempt to hide the arena/monitor windows the same way (a `wscript.exe` wrapper) broke `Stop-ScheduledTask`'s ability to actually kill the process, briefly running two arenas against the same portfolio files at once during a restart (caught immediately, no data corruption, but a real race). Both are now fixed properly: watchdog runs hidden via a verified-safe wrapper, and arena/monitor run via `pythonw.exe` directly (no wrapper needed, so kill semantics stay intact) — full story in `CHANGELOG.md`.

This snapshot will go stale — it's a point-in-time read of a system that's still running. Check `/arena` for the live numbers, or ask for a fresh summary.
