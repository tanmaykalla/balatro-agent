import json
import os
import sys
from collections import Counter

from agent_memory import RunMemory


class _Tee:
    """Writes to two streams at once — terminal and log file."""
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            s.write(data)

    def flush(self):
        for s in self._streams:
            s.flush()

    def fileno(self):
        return self._streams[0].fileno()


class RunLogger:
    def __init__(self, log_dir: str = "runs/"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self._live_log = None
        self._orig_stdout = None

    def open_live_log(self, run_id: str) -> str:
        path = os.path.join(self.log_dir, f"{run_id}.log")
        self._live_log = open(path, "w", buffering=1)
        self._orig_stdout = sys.stdout
        sys.stdout = _Tee(self._orig_stdout, self._live_log)
        return path

    def close_live_log(self) -> None:
        if self._live_log:
            sys.stdout = self._orig_stdout
            self._live_log.close()
            self._live_log = None

    MIN_ENTRIES = 5  # runs with fewer real action entries are treated as crashes

    def save_run(self, memory: RunMemory) -> str:
        real_entries = [e for e in memory.action_log if "error" not in e]
        if len(real_entries) < self.MIN_ENTRIES:
            print(f"  [log] skipped saving run {memory.run_id} "
                  f"— only {len(real_entries)} entries (crash/abort)")
            return ""
        path = os.path.join(self.log_dir, f"{memory.run_id}.json")
        with open(path, "w") as f:
            json.dump(memory.to_json(), f, indent=2, default=str)
        print(f"  [log] saved {len(real_entries)} entries → {path}")
        return path

    def save_report(self, run_id: str, report: str) -> str:
        path = os.path.join(self.log_dir, f"{run_id}_report.md")
        with open(path, "w") as f:
            f.write(report)
        return path

    def get_run_summary_stats(self, run_id: str) -> dict:
        path = os.path.join(self.log_dir, f"{run_id}.json")
        with open(path) as f:
            data = json.load(f)

        hand_history  = data.get("hand_history", [])
        joker_history = data.get("joker_history", [])
        wallet_history = data.get("wallet_history", [])

        money_at_each_ante: dict = {}
        for w in wallet_history:
            money_at_each_ante[w["ante"]] = w["money"]

        hands_by_type = Counter(h.get("hand_type", "?") for h in hand_history)

        return {
            "final_ante":          data.get("final_ante", 0),
            "won":                 data.get("won", False),
            "total_hands_played":  sum(h.get("hands_used", 0)    for h in hand_history),
            "total_discards_used": sum(h.get("discards_used", 0) for h in hand_history),
            "money_at_each_ante":  money_at_each_ante,
            "jokers_bought":       [j["joker_key"] for j in joker_history if j["action"] == "buy"],
            "jokers_sold":         [j["joker_key"] for j in joker_history if j["action"] == "sell"],
            "hands_played_by_type": dict(hands_by_type),
        }
