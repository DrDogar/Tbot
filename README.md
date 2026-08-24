# TBOT — Multi-Bot Crypto Paper-Trading Arena

TBOT is a **paper-trading** (simulated money, real market data) crypto trading system built around one central experiment: instead of picking one strategy, run **8 independent bots**, each with its own $1,000, its own strategy, and its own risk rules, side by side on the same 5 coins — and let the results decide which approach actually works.

Everything runs locally. No paid APIs, no cloud costs. The two "AI" bots are neural networks and decision-tree ensembles written from scratch in NumPy and trained on a full year of historical data — not a hosted LLM.

> ⚠️ **Paper trading only.** No real orders are ever sent, no exchange API keys are required for trading. This is a research/learning project, not investment advice.

---

## What it actually does

1. Pulls live and historical OHLCV candles for `BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT` from Binance's public API (via `ccxt` — no account or API key needed).
2. Trains 8 bots on the last **full year** of hourly data per coin: the 5 rule-based bots get backtested to see which coins they historically made money on; the 3 AI bots get properly trained.
3. Runs continuously, evaluating all 8 bots against all 5 coins once a minute, simulating fills, fees, stop-losses and take-profits exactly as a real spot exchange would apply them.
4. Serves a live web dashboard so you can watch every bot's equity, trades, and reasoning in real time.
5. Is designed to survive the machine it runs on being unreliable — it checkpoints after every single action and self-heals if killed, the laptop sleeps, or the network drops.

---

## Quick start

```bash
pip install -r requirements.txt

python run_arena.py       # starts the 8-bot arena (resumable, runs forever until stopped)
python run_monitor.py     # starts the web dashboard
```

Then open **http://127.0.0.1:5000/arena** in a browser.

For hands-off, reboot-proof operation on Windows, use `scripts/start_detached.ps1` (see [Reliability](#reliability--staying-alive) below) instead of running the two commands directly in a terminal.

`main.py` also offers an interactive menu covering everything (single-symbol tools, the older single-strategy session, and the arena) — run `python main.py`.

---

## The 8 bots

Every bot gets a fresh **$1,000**, trades across all 5 coins, and is fully isolated from the others (one bot's error never affects another's — see `bots/engine.py`). What differs between them is **when they enter a trade** and **how tightly they manage the exit**.

| Bot | How it decides to enter | Stop-loss | Take-profit | Trailing stop |
|---|---|---|---|---|
| **Momentum Rider** | EMA(20) crosses above EMA(50) with a strong bullish candle | 10% | — (rides winners) | 0.4% off peak |
| **Scalper** | RSI dips below 45 with a bullish reversal candle | 10% | 0.35% | — |
| **Breakout Hunter** | Price breaks a 20-candle high on 1.2×+ volume | 10% | 1.0% | — |
| **Weekly Trend Follower** | Only trades with the 7-day trend (+1.5% or more), entering on RSI pullbacks | 10% | 1.6% | — |
| **Aggressive Multi-Vote** | A weighted vote across RSI/EMA/Volume/Volatility/Price-Action/Weekly-Trend models | 10% | 0.8% | — |
| **Neural Net Trader** 🤖 | A from-scratch NumPy MLP (2-layer, ReLU, softmax, manual backprop) trained on a year of data per coin | 10% | 0.8% | — |
| **Random Forest Trader** 🤖 | A from-scratch bagged ensemble of 25 decision trees (Gini splits, feature-sampled) | 10% | 0.8% | — |
| **Ensemble Meta-Trader** 🤖🤖 | A second NumPy MLP, "stacked" on top of the other two — trained on what the Neural Net *and* Random Forest already predicted, learning when to trust which one | 10% | 0.8% | — |

All 3 AI bots share the same 6 engineered input features (RSI, EMA trend, volume, volatility, price action, weekly trend — see `strategies/market_models.py`) and predict SELL/HOLD/BUY with a confidence score. The rule-based bots use hand-written logic (`bots/entry_strategies.py`).

**Position sizing** is confidence-scaled: every entry is sized in **$100 chunks**, 1–4 chunks depending on how confident the signal is (`bots/position_sizing.py`), so a 90%-confidence AI prediction risks more than a 30%-confidence one.

**Why every stop-loss is 10%**: the bots originally ran with tight per-bot stops (0.25%–0.8%). In a choppy/declining market this meant they got stopped out of positions by ordinary noise before the position had a chance to recover, repeatedly paying the round-trip fee for nothing. All 8 bots were widened to a uniform 10% stop-loss so they hold through normal volatility instead of panic-selling on small dips — see [Results](#results-to-date) for how that changed things.

---

## How training works

Every time the arena (re)starts, and any time a new bot joins mid-run:

1. For each of the 5 coins, fetch the **last 365 days of 1-hour candles** (`data/collector.py`).
2. For each of the 5 rule-based bots, replay that whole year bar-by-bar through the bot's own entry/exit logic (`bots/trainer.py`) to see how it would have performed — this decides whether that bot is allowed to trade that coin live (a coin it lost money on in the backtest is blocked, unless it has zero trade history).
3. Build one shared feature/label dataset from that year of data (`bots/neural_model.py: build_training_dataset`) — reused by all 3 AI models so the expensive feature engineering only happens once per coin.
4. Train the Neural Net (gradient descent) and Random Forest (bagged trees) on that dataset.
5. Train the Ensemble Meta-Trader on a *second* dataset built from what the Neural Net and Random Forest already predicted at each historical point (`bots/ensemble_model.py`), so it learns when to trust which one.

A full retrain (~4 minutes) only happens on a fresh start, when a brand-new bot joins an in-progress arena, or if a network blip corrupted the last attempt (auto-retried with backoff — see `bots/runner.py: _run_training_with_retry`).

---

## Risk management

- **Fee-aware fills**: every trade models Binance's real 0.1% spot taker fee. A BUY receives fewer coins than the raw dollar amount would suggest; a SELL nets less cash back (`risk/spot_guard.py`).
- **No shorting, spot-only**: a SELL is blocked if the bot doesn't hold the coin.
- **Exits always fully close a position**, however many $100 chunks it was built from — only entries are capped at `MAX_TRADE_QUOTE_AMOUNT` ($500); an exit is never artificially clamped, because a stop-loss that can't fully close a position isn't really a stop-loss.
- **Three independent exit triggers**, checked every cycle (`bots/position_manager.py`):
  - **Stop-loss** — hard exit if the position is down more than the bot's `stop_loss_pct` from entry.
  - **Trailing stop** — (Momentum Rider only) locks in gains by exiting if price falls more than 0.4% off its peak *while still in profit*.
  - **Take-profit** — locks in gains once the position is up `take_profit_pct`.

---

## Reliability — staying alive

This started as a laptop that "turns off on its own," so a lot of the engineering here is about the system surviving that rather than assuming a stable always-on server.

- **Resumable by design**: state is checkpointed to `state/` after every single symbol evaluation, not just every cycle. Killing the process at any point loses at most a few seconds of work.
- **Detached from the terminal**: the arena and monitor run as **Windows Scheduled Tasks** (`scripts/start_detached.ps1`), not as child processes of a terminal/IDE session — so closing VS Code, a terminal, or a Claude Code session doesn't kill them. (Both tasks also explicitly ignore battery-power restrictions, since this runs on a laptop.)
- **Self-healing at the process level**: `run_arena.py` and `run_monitor.py` each wrap their main loop in a crash-and-restart loop — an uncaught exception logs, waits 5 seconds, and restarts in-process rather than taking the whole task down.
- **Self-healing at the OS level**: a third task, `TBOT-Watchdog` (`scripts/watchdog.ps1`), runs every 5 minutes and relaunches either task if it isn't in the `Running` state — the safety net for the case where the laptop's own sleep/hibernate killed both the process-level retry loop *and* Task Scheduler's built-in restart-on-failure at the same time (observed happening after long sleeps).
- **Network-resilient training**: a failed retrain (e.g. a DNS blip fetching Binance data) is retried 3× with backoff; if it still fails, a resumed arena falls back to whatever training/weights already exist instead of crashing a session that has hours of progress.
- **Unbounded run**: `SESSION_DURATION_HOURS` is set to 10 years (`config/settings.py`) — the arena runs continuously until manually stopped rather than auto-finalizing on a fixed schedule.

---

## Web dashboard

`dashboard/web_server.py` is a small Flask app with two views:

- **`/arena`** — the live 8-bot leaderboard: equity, P&L%, trade count, fees paid, live price ticker, per-coin positions and reasoning, and a recent-activity log. This is the main view.
- **`/`** — a single-strategy monitor for the older `run_session.py` engine (see below).

Both poll `state/*.json` and `state/*.csv` on an interval (`WEB_MONITOR_REFRESH_SECONDS`, default 5s) — the dashboard is a pure read-only viewer over the same state files the arena writes, so it never affects trading.

---

## Project structure

### Entry points

| File | Purpose |
|---|---|
| `main.py` | Interactive menu covering every feature (single-symbol tools, the old single-strategy session, and the arena). |
| `run_arena.py` | Starts/resumes the 8-bot arena, unattended. Self-restarts on crash. |
| `run_monitor.py` | Starts the Flask web dashboard. Self-restarts on crash. |
| `run_session.py` | Starts/resumes the older single-portfolio, single-strategy 24h session (see [Two systems](#two-systems-in-this-repo)). |

### `bots/` — the arena (the current system)

| File | Purpose |
|---|---|
| `bot_configs.py` | Declares all 8 bots: name, entry function, stop-loss/take-profit/trailing-stop, which AI model (if any) it uses. |
| `engine.py` | Evaluates one coin against all 8 bots for one cycle: checks exits first, then entries; fully isolates each bot's errors from the others. |
| `entry_strategies.py` | The 5 rule-based bots' entry logic (Momentum Rider, Scalper, Breakout Hunter, Weekly Trend Follower, Aggressive Multi-Vote). |
| `position_manager.py` | Stop-loss / trailing-stop / take-profit exit logic, shared by every bot. |
| `position_sizing.py` | Confidence → $100-chunk position size (1–4 chunks). |
| `trainer.py` | Bar-by-bar backtester used to train and gate the 5 rule-based bots on a year of data. |
| `neural_model.py` | The from-scratch NumPy MLP: feature engineering, dataset building, training (manual backprop), inference, JSON (de)serialization. Shared feature code is reused by the Random Forest and Ensemble bots too. |
| `forest_model.py` | The from-scratch Random Forest: Gini-impurity tree building, bagging, feature subsampling, quantile-based split search (kept fast enough to train on a year of hourly data), JSON (de)serialization. |
| `ensemble_model.py` | The stacking Ensemble Meta-Trader: builds a training set from the Neural Net's and Random Forest's own predictions, then trains a third MLP (reusing `neural_model`'s trainer) on top of them. |
| `runner.py` | The main arena loop: fresh-start vs. resume logic, per-symbol training, the resumable cycle loop, crash-retry around retraining, config resync (interval/duration) on resume. |

### `config/`

| File | Purpose |
|---|---|
| `settings.py` | Every tunable constant in the system: tracked symbols, timeframes, indicator periods, risk limits, fee assumptions, position sizing, session duration, dashboard port, etc. |

### `data/` & `exchange/`

| File | Purpose |
|---|---|
| `exchange/binance.py` | The shared `ccxt` Binance client (public endpoints only) and `get_live_price`. |
| `data/collector.py` | Candle fetching: a single recent window (`get_market_data`), and paginated historical pulls for the last 24h/week/year (`get_historical_market_data` and its `get_last_*` wrappers). |

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
| `runner.py` | The resumable loop for the single-portfolio session (mirrors `bots/runner.py` but for one strategy/one portfolio instead of 8). |
| `trading_engine.py` | Evaluates one coin for the single-strategy engine; can route the decision through either the internal model or the Claude API (`DECISION_ENGINE` setting). |
| `session_state.py` | The `RunState` model: run id, start time, duration, cycle count, `is_expired`/`remaining_seconds`. |
| `equity_history.py` | Append-only CSV equity snapshots, used to draw the dashboard's equity chart. |
| `last_cycle.py` | Persists the most recent per-symbol decision/result for the dashboard to display. |

### `reporting/`

| File | Purpose |
|---|---|
| `arena_report.py` | Generates a text leaderboard report across all 8 bots, sorted by P&L%. |
| `session_report.py` | Generates a text report for the single-strategy session. |

### `dashboard/`

| File | Purpose |
|---|---|
| `web_server.py` | The Flask app: `/api/status` and `/api/arena-status` JSON endpoints, `/` and `/arena` pages, live price fetching for the ticker. |
| `templates/arena.html` | The 8-bot arena dashboard: leaderboard, live price ticker, per-bot detail cards, activity log. |
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
| `start_detached.ps1` | Registers/starts the arena and monitor as Windows Scheduled Tasks, detached from any terminal, immune to battery-power restrictions. Safe to re-run any time (both scripts resume from checkpoints). |
| `watchdog.ps1` | Checks every 5 minutes (via the `TBOT-Watchdog` task) whether the arena/monitor tasks are running, and relaunches them if not — the safety net for extended sleep/hibernate. |
| `register_autostart_task.ps1` | An older, simpler "run at logon" task for the single-strategy session (`run_session.py`). Superseded by `start_detached.ps1` + `watchdog.ps1` for the arena. |

### `utils/`

| File | Purpose |
|---|---|
| `logger.py` | One shared logger, writing to both the console and `state/session.log`. |

---

## Two systems in this repo

TBOT grew from a single-strategy bot into an 8-bot arena, and both still work:

- **The arena** (`bots/`, `run_arena.py`, `/arena`) — the current system, described above. 8 independently-risked bots, $1,000 each.
- **The single-strategy session** (`engine/`, `run_session.py`, `/`) — the original design: one portfolio, one strategy (the same RSI/EMA/volume/volatility/price-action vote used by `aggressive_voter_entry`), optionally decided by the Claude API instead of the local model. Kept for comparison and because `main.py`'s menu still exposes it.

---

## Results to date

**As of 2026-08-24** — the arena has been running continuously (with a couple of brief, self-healed interruptions) since **2026-08-02**, roughly **22 days**, cycle **5,150**. $1,000 starting balance per bot, all figures paper-trading only.

| Rank | Bot | Equity | P&L | Trades | Fees paid | Realized P&L |
|---|---|---|---|---|---|---|
| 1 | 🤖 Neural Net Trader | $1,185.02 | **+18.50%** | 292 | $58.42 | $220.23 |
| 2 | 🤖 Random Forest Trader | $1,181.17 | **+18.12%** | 279 | $53.81 | $208.53 |
| 3 | Breakout Hunter | $1,148.57 | **+14.86%** | 123 | $33.37 | $168.01 |
| 4 | 🤖🤖 Ensemble Meta-Trader | $1,124.53 | **+12.45%** | 113 | $20.54 | $135.70 |
| 5 | Momentum Rider | $1,102.93 | **+10.29%** | 76 | $18.92 | $118.47 |
| 6 | Weekly Trend Follower | $1,071.53 | **+7.15%** | 25 | $7.87 | $74.68 |
| 7 | Aggressive Multi-Vote | $997.76 | -0.22% | 40 | $4.50 | $0.01 |
| 8 | Scalper | $983.61 | -1.64% | 234 | $47.51 | $7.60 |

Market context: BTC ran from ~$63,000 to ~$79,700 over the period (+~26%), with a rough patch in the first week (down to ~$62,700) before the broader rally. ETH, SOL, BNB, and XRP all moved similarly.

**What the data shows so far:**

- **The stop-loss change mattered.** In the first week, with tight per-bot stops (0.25–0.8%), every single bot was in the red — small, ordinary volatility kept triggering stop-losses before positions could recover, and round-trip fees compounded the damage. After widening every bot's stop-loss to a uniform 10% (holding through drawdown instead of cutting fast), 6 of 8 bots are now solidly positive, riding the market's actual trend instead of getting shaken out of it.
- **Both from-scratch AI models are winning.** Neural Net Trader and Random Forest Trader — the two models trained on a full year of data — are the top two performers, and by a clear margin. They also trade the most (279–292 trades), which under the old tight-stop regime was a liability (more trades = more chances to get chopped) but under the wide-stop regime turned into an advantage (more chances to catch a real move).
- **The "smarter" ensemble bet is paying off differently than expected.** Ensemble Meta-Trader was designed to be more selective — and it is (113 trades vs. 279–292 for the two models it's built on) — but that selectivity has so far cost it upside in a strongly trending market, landing it 4th rather than 1st. It's still clearly profitable and pays the least in fees per dollar earned of the three AI bots, which may matter more in a choppier market than this one has mostly been.
- **High-frequency + tight take-profit is still the weak combination.** Scalper (0.35% take-profit, 234 trades) and Aggressive Multi-Vote (0.8% take-profit) are the only two bots not clearly profitable — both exit winners quickly by design, which works against them once a position is left free to run further on a wide stop-loss. Their fee-to-realized-profit ratio is the worst in the arena.
- **Reliability held up.** Across 22 days the watchdog has caught and self-healed multiple silent outages (the arena/monitor tasks going dead after extended laptop sleep) without losing any state or requiring manual intervention beyond the periodic status checks.

This snapshot will go stale — it's a point-in-time read of a system that's still running. Check `/arena` for the live numbers, or ask for a fresh summary.
