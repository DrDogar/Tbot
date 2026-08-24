import json
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class RunState:
    run_id: str
    symbols: list
    started_at: str
    duration_hours: float
    interval_seconds: int
    cycle_count: int = 0
    completed: bool = False
    last_cycle_at: str = ""


def new_run_state(symbols, duration_hours, interval_seconds, now):
    return RunState(
        run_id=now.strftime("%Y%m%d_%H%M%S"),
        symbols=list(symbols),
        started_at=now.isoformat(),
        duration_hours=duration_hours,
        interval_seconds=interval_seconds,
    )


def save_run_state(state, path):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        json.dump(asdict(state), file, indent=2)


def load_run_state(path):
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    return RunState(**payload)


def is_expired(state, now):
    started_at = datetime.fromisoformat(state.started_at)
    elapsed_hours = (now - started_at).total_seconds() / 3600

    return elapsed_hours >= state.duration_hours


def remaining_seconds(state, now):
    started_at = datetime.fromisoformat(state.started_at)
    elapsed = (now - started_at).total_seconds()
    total = state.duration_hours * 3600

    return max(total - elapsed, 0.0)
