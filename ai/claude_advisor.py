import json
from dataclasses import dataclass

from ai.claude_client import get_client
from config.settings import CLAUDE_MAX_TOKENS, CLAUDE_MODEL

_TOOL_NAME = "record_trade_decision"

_DECISION_TOOL = {
    "name": _TOOL_NAME,
    "description": "Record the final BUY/SELL/HOLD trading decision for this coin.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "string"},
        },
        "required": ["action", "confidence", "reasoning"],
    },
}


@dataclass(frozen=True)
class TradeDecision:
    action: str
    confidence: float
    reasoning: str


def ask_trade_decision(symbol, weekly_summary, current_signal, position, round_trip_fee_pct):
    client = get_client()

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=_build_system_prompt(),
        tools=[_DECISION_TOOL],
        tool_choice={"type": "tool", "name": _TOOL_NAME},
        messages=[
            {
                "role": "user",
                "content": _build_user_prompt(
                    symbol, weekly_summary, current_signal, position, round_trip_fee_pct
                ),
            }
        ],
    )

    return _parse_decision(response)


def _build_system_prompt():
    return (
        "You are a disciplined crypto spot trading strategist running a 24-hour paper-trading "
        "session across multiple coins. You only trade spot, long-only, no shorting. For each "
        "request you are given the last 7 days of market context and the current technical "
        "signal for one coin, plus the round-trip trading fee percentage (paid once on entry "
        "and once on exit). Only recommend BUY or SELL when the expected move clearly outweighs "
        "the round-trip fee cost and the weekly trend and current signal agree; otherwise "
        "recommend HOLD. Never recommend SELL when current_position.holding is false. Respond "
        "only by calling the record_trade_decision tool."
    )


def _build_user_prompt(symbol, weekly_summary, current_signal, position, round_trip_fee_pct):
    payload = {
        "symbol": symbol,
        "round_trip_fee_pct": round(round_trip_fee_pct * 100, 4),
        "weekly_context": weekly_summary,
        "current_signal": current_signal,
        "current_position": position,
    }

    return "Evaluate this coin and decide BUY, SELL, or HOLD.\n\n" + json.dumps(payload, indent=2, default=str)


def _parse_decision(response):
    for block in response.content:
        if block.type == "tool_use" and block.name == _TOOL_NAME:
            data = block.input
            return TradeDecision(
                action=data["action"],
                confidence=float(data["confidence"]),
                reasoning=data["reasoning"],
            )

    return TradeDecision(action="HOLD", confidence=0.0, reasoning="Claude did not return a decision.")
