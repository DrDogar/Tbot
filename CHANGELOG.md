# Changelog

All notable changes to TBOT are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning
follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`):
- **MAJOR** — a fundamental architecture change.
- **MINOR** — a bot added/removed, or a new capability, in a backward-compatible way.
- **PATCH** — bug fixes, reliability fixes, docs/tooling.

The current running version is tracked in `config/settings.py` (`APP_VERSION`) and
shown in the arena/monitor dashboard headers and the arena's startup log line.
Released versions are tagged in git (`git tag -l`).

**Push policy**: commits happen locally as changes are made; nothing is pushed to
GitHub until explicitly requested. Everything under **[Unreleased]** exists only
on this machine.

---

## [Unreleased]

### Changed
- Watchdog check interval: 5 minutes → 30 minutes. Verified it still registers
  and runs successfully (`LastTaskResult=0`) at the new interval before leaving
  it there.

### Fixed
- Arena/monitor console windows, done properly this time: launched via
  `pythonw.exe` (the windowless build of the interpreter) as the task's direct
  action, instead of `python.exe` or the earlier `wscript.exe` wrapper that
  broke `Stop-ScheduledTask`. `pythonw.exe` never allocates a console at all —
  no wrapper needed, so Task Scheduler tracks it exactly like `python.exe` and
  kill semantics are identical (re-verified explicitly: `Stop-ScheduledTask` →
  0 processes, on both a throwaway test task and the live arena task). Also
  verified beforehand, since `sys.stdout`/`sys.stderr` are `None` under
  `pythonw.exe`: the logger's console handler no-ops safely instead of
  crashing, `print()` doesn't raise, and Flask's dev server starts and serves
  normally.

---

## [5.3.1] — 2026-08-25 — `a71b1dc`

### Added
- This changelog, in [Keep a Changelog](https://keepachangelog.com) format.
  (`89e9884`, `2cd97e7`, `4c612ba`)
- `APP_VERSION` in `config/settings.py` as the single source of truth for the
  running version; surfaced in the arena/monitor dashboard headers and the
  arena's startup log line. (`4c612ba`)
- Git tags for every past release, `v0.1.0` through `v5.3.0`. (`4c612ba`)

### Fixed
- Attempted to hide the arena/monitor console windows the same way as the
  watchdog (hidden `wscript.exe` wrapper, `0fea1ba`) — but this actually broke
  something worse: `Stop-ScheduledTask` only kills the wrapper's `wscript.exe`
  process, not the `python.exe` it spawns via `Shell.Run`, which survives as an
  orphan. A routine restart briefly ran two arenas against the same portfolio
  files at once (caught it live: duplicate cycle numbers in `session.log`; no
  data corruption resulted, but it was a real race). Reverted arena/monitor to
  direct `python.exe` launch — Task Scheduler tracks that process itself, so
  `Stop-ScheduledTask` reliably kills it. The console window is back for these
  two (watchdog's fix is unaffected and stays, since it's short-lived enough
  that an occasional orphan there is harmless). `scripts/run_hidden.vbs` removed
  as dead code. (`a71b1dc`)

---

## [5.3.0] — 2026-08-25 — `1a0cb5b`

### Removed
- Momentum Rider and Weekly Trend Follower, trimming the roster from 7 to 5 —
  cut by choice to focus the lineup, not for losing money (both were solidly
  profitable, +9.6% and +6.8%, at the time). Open positions liquidated at the
  live market price before removal.

---

## [5.2.0] — 2026-08-25 — `3866391`

### Added
- **Patient Trend AI**: a 4th from-scratch NumPy MLP bot, trained on a 2-day-
  ahead target (vs. a few hours for the other AI bots) plus an extra 30-day
  macro "regime" feature. No take-profit cap, 3% trailing stop instead of a
  tight one — built to sit out chop/down-drift and only commit on a real
  sustained trend. First attempt collapsed to always predicting HOLD (training
  accuracy exactly matched the majority-class baseline); fixed by tuning the
  label horizon/threshold and increasing model capacity, verified against real
  data across all 5 coins before going live.

### Removed
- Scalper and Aggressive Multi-Vote — the only two bots never clearly profitable
  after ~3 weeks live; fee-to-profit ratio never recovered even after the
  stop-loss widening in v5.0.0 helped every other bot. Positions liquidated
  first.

### Fixed
- The watchdog task's scheduled-task action wasn't set to run hidden, so its
  5-minute health check flashed a visible console window every time. Fixed by
  launching it through a hidden `wscript.exe` wrapper instead of PowerShell
  directly.

---

## [5.1.0] — 2026-08-24 — `0db533b`

### Added
- `README.md`: what the project is, quick start, every bot explained, the
  training pipeline, risk management, the reliability/self-healing design, the
  web dashboard, a file-by-file breakdown of every tracked file, and a results
  snapshot.

---

## [5.0.0] — 2026-08-24 — `a581496`

**"TBOT v5: multi-bot trading arena with ensemble ML strategies"** — the
architecture change from a single-strategy bot to a multi-bot arena.

### Added
- 8-bot arena (`bots/`): each bot gets its own $1,000, trades all 5 tracked
  coins, and is fully isolated from the others' errors.
  - 5 rule-based bots: Momentum Rider, Scalper, Breakout Hunter, Weekly Trend
    Follower, Aggressive Multi-Vote — each with distinct entry logic and
    stop-loss/take-profit/trailing-stop parameters.
  - Neural Net Trader: from-scratch NumPy MLP (2-layer, ReLU, softmax, manual
    backprop), trained locally, no paid API.
  - Random Forest Trader: from-scratch bagged ensemble of 25 decision trees.
  - Ensemble Meta-Trader: a second MLP "stacked" on what the Neural Net and
    Random Forest already predict.
- Full-year hourly training pipeline per coin; bar-by-bar backtest gating for
  rule-based bots; shared feature engineering for the AI models.
- Fee-aware paper trading (`risk/spot_guard.py`): real 0.1% Binance taker fee
  modeled on both entry and exit; exits always fully close a position
  regardless of entry chunk size.
- Confidence-scaled position sizing (`bots/position_sizing.py`): $100 chunks,
  1–4 chunks depending on signal confidence.
- Resumable, effectively-unlimited-duration sessions: checkpointed after every
  symbol evaluation; session duration set to 10 years instead of
  auto-finalizing on a fixed 24h window.
- Reliability: arena/monitor run as detached Windows Scheduled Tasks (survive
  terminal/IDE closing), self-restart in-process on crash, and a
  `TBOT-Watchdog` task checks every 5 minutes and relaunches either if it's
  not running.
- Live web dashboard (`dashboard/`): `/arena` leaderboard with live price
  ticker, per-bot detail, equity history, and activity log.

### Changed
- Stop-loss widened to 10% across all bots — originally 0.25–0.8% per bot,
  which meant ordinary volatility kept triggering exits before positions could
  recover. Widened uniformly so bots hold through drawdown instead of getting
  chopped by noise.

---

## [0.7.0] — 2026-06-28 — `f588fb0`

### Added
- Terminal market dashboard, RSI analysis, candlestick charts (`mplfinance`),
  and the initial modular project structure (config/exchange/data/indicators/
  strategies/risk/services/controllers).

---

## [0.1.0] — 2026-06-28 — `004766e`

### Added
- The very first version: fetch and print the live BTC/USDT price from Binance.
