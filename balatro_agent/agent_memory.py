from dataclasses import dataclass, field, asdict


@dataclass
class RunMemory:
    run_id: str
    strategy_name: str
    source: str = "gemini"          # "gemini" | "ollama" — set by agent.py
    system_prompt: str = ""         # full system prompt used this run (for self-contained training)
    ante_num: int = 1
    round_num: int = 1
    wallet_history: list[dict] = field(default_factory=list)
    hand_history: list[dict] = field(default_factory=list)
    joker_history: list[dict] = field(default_factory=list)
    blind_history: list[dict] = field(default_factory=list)
    action_log: list[dict] = field(default_factory=list)
    final_ante: int = 0
    won: bool = False
    # Per-call LLM telemetry — populated at end of run from llm_client
    agent_stats: dict = field(default_factory=dict)

    def to_summary_prompt(self) -> str:
        lines = [f"## Run Memory ({self.strategy_name})"]
        lines.append(f"Current: ante {self.ante_num}, round {self.round_num}")
        if self.wallet_history:
            recent = self.wallet_history[-4:]
            lines.append("Recent wallet: " + ", ".join(
                f"A{w['ante']}R{w['round']}=${w['money']}" for w in recent
            ))
        if self.hand_history:
            recent = self.hand_history[-4:]
            lines.append("Recent hands:")
            for h in recent:
                lines.append(
                    f"  - A{h['ante']}R{h['round']}: {h['hand_type']} "
                    f"scored {h['score']} (hands_used={h['hands_used']}, "
                    f"discards_used={h['discards_used']})"
                )
        if self.blind_history:
            recent = self.blind_history[-3:]
            lines.append("Recent blinds:")
            for b in recent:
                tag = "SKIPPED" if b.get("skipped") else f"{b.get('achieved_score', 0)}/{b.get('target_score', 0)}"
                lines.append(f"  - A{b['ante']} {b['blind_type']}: {tag}")
        if self.joker_history:
            recent = self.joker_history[-5:]
            lines.append("Recent joker moves: " + ", ".join(
                f"{j['action']} {j['joker_key']} (${j.get('cost', 0)})" for j in recent
            ))
        return "\n".join(lines)

    def to_json(self) -> dict:
        return asdict(self)
