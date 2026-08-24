"""
TBOT Configuration
"""

from pathlib import Path

# ==========================================
# CURRENT MARKET
# ==========================================

CURRENT_SYMBOL = "BTC/USDT"

SPOT_ONLY = True

# ==========================================
# DEFAULT SETTINGS
# ==========================================

DEFAULT_TIMEFRAME = "5m"

DEFAULT_LIMIT = 100

TRADE_MODE = "paper"

# ==========================================
# 1S DATA / SMOKE TEST
# ==========================================

BACKTEST_TIMEFRAME = "1s"

BACKTEST_LOOKBACK_HOURS = 24

BACKTEST_SIGNAL_STEP_SECONDS = 5

BACKTEST_MODEL_WINDOW = 100

SCALP_LOOKAHEAD_SECONDS = 60

SCALP_TARGET_PCT = 0.08

SCALP_MAX_ADVERSE_PCT = 0.12

# ==========================================
# INDICATORS
# ==========================================

RSI_PERIOD = 14

RSI_OVERSOLD = 30

RSI_OVERBOUGHT = 70

EMA_FAST = 20

EMA_SLOW = 50

# ==========================================
# MARKET MODELS
# ==========================================

VOLUME_LOOKBACK = 20

MIN_VOLUME_RATIO = 0.85

VOLATILITY_LOOKBACK = 20

MIN_SCALP_VOLATILITY_PCT = 0.05

MAX_SCALP_VOLATILITY_PCT = 1.25

MARKET_MOOD_BUY_THRESHOLD = 0.12

MARKET_MOOD_SELL_THRESHOLD = -0.12

MIN_SCALP_CONFIDENCE = 0.15

# ==========================================
# RISK CONTROLS
# ==========================================

SCALP_TRADE_QUOTE_AMOUNT = 25.0

MAX_TRADE_QUOTE_AMOUNT = 500.0

PAPER_BASE_BALANCE = 0.0

PAPER_QUOTE_BALANCE = 1000.0

MIN_QUOTE_BALANCE_BUFFER = 10.0

# ==========================================
# ARENA POSITION SIZING (chunk-based, scales with confidence)
# ==========================================

CHUNK_SIZE_USD = 100.0

MIN_POSITION_CHUNKS = 1

MAX_POSITION_CHUNKS = 4

# ==========================================
# CHART
# ==========================================

CHART_STYLE = "yahoo"

# ==========================================
# MULTI-COIN CLAUDE-ADVISED SESSION
# ==========================================

TRACKED_SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
]

WEEKLY_TIMEFRAME = "1h"

WEEKLY_LOOKBACK_DAYS = 7

NEURAL_TRAINING_TIMEFRAME = "1h"

NEURAL_TRAINING_LOOKBACK_DAYS = 365

# Effectively unlimited -- runs continuously until manually stopped rather than
# auto-finalizing after a fixed window (10 years, to avoid float('inf') JSON edge cases).
SESSION_DURATION_HOURS = 24.0 * 365 * 10

SESSION_INTERVAL_SECONDS = 60

SESSION_STARTING_QUOTE_BALANCE = 1000.0

SESSION_TRADE_QUOTE_AMOUNT = 150.0

STATE_DIR = Path("state")

# ==========================================
# WEB MONITOR
# ==========================================

WEB_MONITOR_HOST = "127.0.0.1"

WEB_MONITOR_PORT = 5000

WEB_MONITOR_REFRESH_SECONDS = 5

# ==========================================
# EXCHANGE FEES
# ==========================================

TAKER_FEE_PCT = 0.001  # Binance default spot taker fee (0.1%)

MAKER_FEE_PCT = 0.001

# ==========================================
# DECISION ENGINE
# ==========================================

# "internal_model" = free, uses the built-in RSI/EMA/volume/volatility/price-action
#                    voting model (strategies/market_models.py). No API cost.
# "claude"         = consults the Claude API for each decision. Requires a funded
#                    ANTHROPIC_API_KEY.
DECISION_ENGINE = "internal_model"

CLAUDE_MODEL = "claude-sonnet-5"

CLAUDE_MAX_TOKENS = 600
