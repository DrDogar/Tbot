import json
from dataclasses import asdict

from engine.trading_engine import CycleRecord


def save_last_cycle(records, path):
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {symbol: asdict(record) for symbol, record in records.items()}

    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def load_last_cycle(path):
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    return {symbol: CycleRecord(**data) for symbol, data in payload.items()}
