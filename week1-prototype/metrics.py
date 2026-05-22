import csv
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class HandRecord:
    run_num: int
    ante: int
    blind: str          # "small" | "big" | "boss" | ""
    hand_type: str      # e.g. "Full House", "Two Pair"
    chips_scored: int   # chips added to round total by this single hand
    joker_keys: List[str] = field(default_factory=list)


@dataclass
class RunMetrics:
    strategy_name: str
    run_num: int
    ante_reached_at_game_end: int
    won: bool
    total_dollars_earned: int
    hands: List[HandRecord] = field(default_factory=list)


class MetricsLogger:
    COMBINED_FIELDS = ["strategy", "run", "ante_reached_at_game_end", "won", "total_dollars_earned"]

    def __init__(self, filepath: str = "week1_results.csv", reports_dir: str = "reports"):
        self.filepath    = filepath
        self.reports_dir = reports_dir
        self._dollars_this_run: int = 0
        self._last_money: int       = 0
        self._hands_this_run: List[HandRecord] = []

    def reset_run(self, starting_money: int = 0) -> None:
        self._dollars_this_run  = 0
        self._last_money        = starting_money
        self._hands_this_run    = []

    def record_money(self, current_money: int) -> None:
        delta = current_money - self._last_money
        if delta > 0:
            self._dollars_this_run += delta
        self._last_money = current_money

    def record_hand(self, record: HandRecord) -> None:
        self._hands_this_run.append(record)

    def log_run(self, metrics: RunMetrics) -> None:
        """Attach accumulated hands then append to the combined summary CSV."""
        metrics.hands = list(self._hands_this_run)

        row = {
            "strategy":                 metrics.strategy_name,
            "run":                      metrics.run_num,
            "ante_reached_at_game_end": metrics.ante_reached_at_game_end,
            "won":                      str(metrics.won).lower(),
            "total_dollars_earned":     metrics.total_dollars_earned,
        }
        file_exists = os.path.exists(self.filepath)
        with open(self.filepath, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.COMBINED_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
