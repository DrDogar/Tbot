# TBOT — Multi-Bot Crypto Paper-Trading Arena

TBOT is a **paper-trading** (simulated money, real market data) crypto trading system built around one central experiment: instead of picking one strategy, run **independent bots**, each with its own $1,000, its own strategy, and its own risk rules, side by side on the same 5 coins — and let the results decide which approach actually works. Underperforming bots get retired and replaced rather than left running forever, so the roster changes over time as the experiment continues.

Everything runs locally. No paid APIs, no cloud costs. The 4 "AI" bots are neural networks and decision-tree ensembles written from scratch in NumPy and trained on historical data — not a hosted LLM.

> ⚠️ **Paper trading only.** No real orders are ever sent, no exchange API keys are required for trading. This is a research/learning project, not investment advice.

---

## What it actually does

1. Pulls live and historical OHLCV candles for `BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT` from Binance's public API (via `ccxt` — no account or API key needed).
2. Trains all bots on the last **full year** of hourly data per coin: the 3 rule-based bots get backtested to see which coins they historically made money on; the 4 AI bots get properly trained.
3. Runs continuously, evaluating every bot against all 5 coins once a minute, simulating fills, fees, stop-losses and take-profits exactly as a real spot exchange would apply them.
4. Serves a live web dashboard so you can watch every bot's equity, trades, and reasoning in real time.
5. Is designed to survive the machine it runs on being unreliable — it checkpoints after every single action and self-heals if killed, the laptop sleeps, or the network drops.

---

## Quick start

```bash
pip install -r requirements.txt

python run_arena.py       # starts the 7-bot arena (resumable, runs forever until stopped)
python run_monitor.py     # starts the web dashboard
```

Then open **http://127.0.0.1:5000/arena** in a browser.

For hands-off, reboot-proof operation on Windows, use `scripts/start_detached.ps1` (see [Reliability](#reliability--staying-alive) below) instead of running the two commands directly in a terminal.

`main.py` also offers an interactive menu covering everything (single-symbol tools, the older single-strategy session, and the arena) — run `python main.py`.

---

## The bots

Every bot gets a fresh **$1,000**, trades across all 5 coins, and is fully isolated from the others (one bot's error never affects another's — see `bots/engine.py`). What differs between them is **when they enter a trade** and **how tightly they manage the exit**.

| Bot | How it decides to enter | Stop-loss | Take-profit | Trailing stop |
|---|---|---|---|---|
| **Momentum Rider** | EMA(20) crosses above EMA(50) with a strong bullish candle | 10% | — (rides winners) | 0.4% off peak |
| **Breakout Hunter** | Price breaks a 20-candle high on 1.2×+ volume | 10% | 1.0% | — |
| **Weekly Trend Follower** | Only trades with the 7-day trend (+1.5% or more), entering on RSI pullbacks | 10% | 1.6% | — |
| **Neural Net Trader** 🤖 | A from-scratch NumPy MLP (2-layer, ReLU, softmax, manual backprop) trained on a year of data per coin, predicting the next few hours | 10% | 0.8% | — |
| **Random Forest Trader** 🤖 | A from-scratch bagged ensemble of 25 decision trees (Gini splits, feature-sampled), same short-horizon target as the neural net | 10% | 0.8% | — |
| **Ensemble Meta-Trader** 🤖🤖 | A second NumPy MLP, "stacked" on top of the other two — trained on what the Neural Net *and* Random Forest already predicted, learning when to trust which one | 10% | 0.8% | — |
| **Patient Trend AI** 🤖🤖🤖 | A third, separately-tuned NumPy MLP trained to predict 2-day-ahead moves (not a few hours), using an extra 30-day macro "regime" feature the others don't see. Deliberately selective — sits in cash through chop/down-drift, only acts on a real trend | 10% | — (rides winners) | 3% off peak |

The first three AI bots share the same 6 engineered input features (RSI, EMA trend, volume, volatility, price action, weekly trend — see `strategies/market_models.py`) and predict SELL/HOLD/BUY with a confidence score. Patient Trend AI uses those same 6 plus a 7th (30-day regime) and a longer, harder-to-hit label, which needed more model capacity (12 hidden units, 1,200 training epochs vs. the others' 6/400) to actually learn instead of collapsing to always predicting HOLD — verified empirically before it went live (see `bots/trend_ai_model.py`). The rule-based bots use hand-written logic (`bots/entry_strategies.py`).

**Retired**: Scalper (tiny 0.35% take-profit, high frequency) and Aggressive Multi-Vote were removed after both proved to be net losers over ~3 weeks of live trading — their fee-to-profit ratio never recovered even after the stop-loss widening below helped every other bot. Any open position was liquidated at the live market price before removal; their historical portfolio/trade data is still on disk (`state/bots/portfolio_scalper.json`, `portfolio_aggressive_voter.json`) for the record, they just no longer trade.

**Position sizing** is confidence-scaled: every entry is sized in **$100 chunks**, 1–4 chunks depending on how confident the signal is (`bots/position_sizing.py`), so a 90%-confidence AI prediction risks more than a 30%-confidence one.

**Why every stop-loss is 10%**: the bots originally ran with tight per-bot stops (0.25%–0.8%). In a choppy/declining market this meant they got stopped out of positions by ordinary noise before the position had a chance to recover, repeatedly paying the round-trip fee for nothing. All bots were widened to a uniform 10% stop-loss so they hold through normal volatility instead of panic-selling on small dips — see [Results](#results-to-date) for how that changed things.

---

## How training works

Every time the arena (re)starts, and any time a new bot joins mid-run:

1. For each of the 5 coins, fetch the **last 365 days of 1-hour candles** (`data/collector.py`).
2. For each of the 3 rule-based bots, replay that whole year bar-by-bar through the bot's own entry/exit logic (`bots/trainer.py`) to see how it would have performed — this decides whether that bot is allowed to trade that coin live (a coin it lost money on in the backtest is blocked, unless it has zero trade history).
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
  - **Trailing stop** — (Momentum Rider only) locks in gains by exiting if price falls more than 0.4% off its peak *while still in profit*.
  - **Take-profit** — locks in gains once the position is up `take_profit_pct`.

---

## Reliability — staying alive

This started as a laptop that "turns off on its own," so a lot of the engineering here is about the system surviving that rather than assuming a stable always-on server.

- **Resumable by design**: state is checkpointed to `state/` after every single symbol evaluation, not just every cycle. Killing the process at any point loses at most a few seconds of work.
- **Detached from the terminal**: the arena and monitor run as **Windows Scheduled Tasks** (`scripts/start_detached.ps1`), not as child processes of a terminal/IDE session — so closing VS Code, a terminal, or a Claude Code session doesn't kill them. (Both tasks also explicitly ignore battery-power restrictions, since this runs on a laptop.)
- **Self-healing at the process level**: `run_arena.py` and `run_monitor.py` each wrap their main loop in a crash-and-restart loop — an uncaught exception logs, waits 5 seconds, and restarts in-process rather than taking the whole task down.
- **Self-healing at the OS level**: a third task, `TBOT-Watchdog` (`scripts/watchdog.ps1`), runs every 5 minutes and relaunches either task if it isn't in the `Running` state — the safety net for the case where the laptop's own sleep/hibernate killed both the process-level retry loop *and* Task Scheduler's built-in restart-on-failure at the same time (observed happening after long sleeps). It runs via a hidden `wscript.exe` wrapper (`scripts/watchdog_silent.vbs`) rather than invoking PowerShell directly, so the 5-minute check never flashes a visible console window.
- **Network-resilient training**: a failed retrain (e.g. a DNS blip fetching Binance data) is retried 3× with backoff; if it still fails, a resumed arena falls back to whatever training/weights already exist instead of crashing a session that has hours of progress.
- **Unbounded run**: `SESSION_DURATION_HOURS` is set to 10 years (`config/settings.py`) — the arena runs continuously until manually stopped rather than auto-finalizing on a fixed schedule.

---

## Web dashboard

`dashboard/web_server.py` is a small Flask app with two views:

- **`/arena`** — the live 7-bot leaderboard: equity, P&L%, trade count, fees paid, live price ticker, per-coin positions and reasoning, and a recent-activity log. This is the main view.
- **`/`** — a single-strategy monitor for the older `run_session.py` engine (see below).

Both poll `state/*.json` and `state/*.csv` on an interval (`WEB_MONITOR_REFRESH_SECONDS`, default 5s) — the dashboard is a pure read-only viewer over the same state files the arena writes, so it never affects trading.

---

## Project structure

### Entry points

| File | Purpose |
|---|---|
| `main.py` | Interactive menu covering every feature (single-symbol tools, the old single-strategy session, and the arena). |
| `run_arena.py` | Starts/resumes the 7-bot arena, unattended. Self-restarts on crash. |
| `run_monitor.py` | Starts the Flask web dashboard. Self-restarts on crash. |
| `run_session.py` | Starts/resumes the older single-portfolio, single-strategy 24h session (see [Two systems](#two-systems-in-this-repo)). |

### `bots/` — the arena (the current system)

| File | Purpose |
|---|---|
| `bot_configs.py` | Declares every bot: name, entry function, stop-loss/take-profit/trailing-stop, which AI model (if any) it uses. |
| `engine.py` | Evaluates one coin against every bot for one cycle: checks exits first, then entries; fully isolates each bot's errors from the others. |
| `entry_strategies.py` | The 3 active rule-based bots' entry logic (Momentum Rider, Breakout Hunter, Weekly Trend Follower), plus the retired Scalper/Aggressive Multi-Vote logic (unused but kept for the record). |
| `position_manager.py` | Stop-loss / trailing-stop / take-profit exit logic, shared by every bot. |
| `position_sizing.py` | Confidence → $100-chunk position size (1–4 chunks). |
| `trainer.py` | Bar-by-bar backtester used to train and gate the 3 rule-based bots on a year of data. |
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
| `templates/arena.html` | The 7-bot arena dashboard: leaderboard, live price ticker, per-bot detail cards, activity log. |
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
| `start_detached.ps1` | Registers/starts the arena and monitor as Windows Scheduled Tasks, detached from any terminal, immune to battery-power restrictions; also (re)registers the watchdog task by calling `register_watchdog_task.ps1`. Safe to re-run any time (all three resume/reattach cleanly). |
| `register_watchdog_task.ps1` | Registers the `TBOT-Watchdog` task on its own (silent, hidden-window) definition — the single source of truth for it, so `start_detached.ps1` doesn't carry its own separate/divergent copy. |
| `watchdog.ps1` | The actual check: every 5 minutes, relaunches the arena/monitor tasks if either isn't `Running` — the safety net for extended sleep/hibernate. |
| `watchdog_silent.vbs` | Launches `watchdog.ps1` with a fully hidden window (`wscript.exe`, style 0) instead of the console flash a direct PowerShell scheduled-task action gives. |
| `register_autostart_task.ps1` | An older, simpler "run at logon" task for the single-strategy session (`run_session.py`). Superseded by `start_detached.ps1` for the arena. |

### `utils/`

| File | Purpose |
|---|---|
| `logger.py` | One shared logger, writing to both the console and `state/session.log`. |

---

## Two systems in this repo

TBOT grew from a single-strategy bot into an 7-bot arena, and both still work:

- **The arena** (`bots/`, `run_arena.py`, `/arena`) — the current system, described above. Independently-risked bots, $1,000 each.
- **The single-strategy session** (`engine/`, `run_session.py`, `/`) — the original design: one portfolio, one strategy (the same RSI/EMA/volume/volatility/price-action vote used by `aggressive_voter_entry`), optionally decided by the Claude API instead of the local model. Kept for comparison and because `main.py`'s menu still exposes it.

---

## Results to date

**As of 2026-08-25** — the arena has been running continuously (with a couple of brief, self-healed interruptions) since **2026-08-02**, roughly **22 days**, cycle **5,299**. $1,000 starting balance per bot, all figures paper-trading only.

| Rank | Bot | Equity | P&L | Trades | Fees paid | Realized P&L |
|---|---|---|---|---|---|---|
| 1 | 🤖 Random Forest Trader | $1,178.12 | **+17.81%** | 285 | $55.01 | $211.68 |
| 2 | 🤖 Neural Net Trader | $1,173.22 | **+17.32%** | 292 | $58.42 | $220.23 |
| 3 | Breakout Hunter | $1,141.50 | **+14.15%** | 123 | $33.37 | $168.01 |
| 4 | 🤖🤖 Ensemble Meta-Trader | $1,119.12 | **+11.91%** | 115 | $20.94 | $135.70 |
| 5 | Momentum Rider | $1,096.08 | **+9.61%** | 76 | $18.92 | $118.47 |
| 6 | Weekly Trend Follower | $1,067.48 | **+6.75%** | 25 | $7.87 | $74.68 |
| 7 | 🤖🤖🤖 Patient Trend AI | $1,000.00 | 0.00% | 0 | $0.00 | $0.00 |

Market context: BTC ran from ~$63,000 to ~$79,000 over the period (+~25%), with a rough patch in the first week (down to ~$62,700) before the broader rally. ETH, SOL, BNB, and XRP all moved similarly.

**What the data shows so far:**

- **The stop-loss change mattered.** In the first week, with tight per-bot stops (0.25–0.8%), every single bot was in the red — small, ordinary volatility kept triggering stop-losses before positions could recover, and round-trip fees compounded the damage. After widening every bot's stop-loss to a uniform 10% (holding through drawdown instead of cutting fast), the surviving bots are now all solidly positive, riding the market's actual trend instead of getting shaken out of it.
- **Both original from-scratch AI models are winning.** Neural Net Trader and Random Forest Trader — the two models trained on a full year of data — are the top two performers, and by a clear margin. They also trade the most (285–292 trades), which under the old tight-stop regime was a liability (more trades = more chances to get chopped) but under the wide-stop regime turned into an advantage (more chances to catch a real move).
- **The selective ensemble bet is paying off differently than expected.** Ensemble Meta-Trader was designed to be more selective — and it is (115 trades vs. 285–292 for the two models it's built on) — but that selectivity has so far cost it upside in a strongly trending market, landing it 4th rather than 1st. It's still clearly profitable and pays the least in fees per dollar earned of the three original AI bots, which may matter more in a choppier market than this one has mostly been.
- **Scalper and Aggressive Multi-Vote were retired (2026-08-25).** Both were the only two bots never clearly profitable — high-frequency, tight-take-profit designs that kept exiting winners early even after the stop-loss widening helped everyone else. Their open positions were liquidated and they were pulled from the active roster; their history is preserved on disk.
- **Patient Trend AI just joined (2026-08-25) — no track record yet.** It's the most deliberately selective bot by design: trained on a 2-day-ahead target (vs. a few hours for the other AI bots) plus an extra 30-day macro regime feature, specifically so it can sit out chop/down-drift and only commit to a real, sustained trend. Getting that target to actually learn (rather than collapsing to always-HOLD) took real tuning — more model capacity and a carefully chosen horizon/threshold, verified against real data before going live. Its first live prediction across the 5 coins was mixed (HOLD on some, SELL on others) despite the broad uptrend, which is the intended behavior: it isn't a blind trend-follower, it combines the macro regime with near-term technicals before committing capital.
- **Reliability held up, with one real gap found and fixed.** Across 22 days the watchdog has caught and self-healed multiple silent outages (the arena/monitor tasks going dead after extended laptop sleep). One genuine bug did surface: the watchdog's scheduled-task action wasn't set to run hidden, so every 5-minute check flashed a visible console window — fixed by launching it through a hidden `wscript.exe` wrapper instead of PowerShell directly, with no loss of the safety net.

This snapshot will go stale — it's a point-in-time read of a system that's still running. Check `/arena` for the live numbers, or ask for a fresh summary.
