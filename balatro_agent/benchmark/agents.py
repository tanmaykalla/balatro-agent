"""
Benchmark agent roster.
Each entry describes how to invoke one agent under test.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class AgentSpec:
    label: str                     # short tag used in tables / dirs
    kind: str                      # "llm" or "scripted"
    llm: str = "gemini"            # for kind=llm: "gemini", "ollama", "claude", or "openai"
    ollama_model: str | None = None
    ollama_think: bool = False
    claude_model: str = "haiku"    # "haiku" or "sonnet"
    openai_model: str = "gpt-4o-mini"
    strategy: str | None = None    # overrides LLM_STRATEGY if set
    # For scripted: path to a directory of pre-existing run JSONs to ingest
    scripted_run_dir: str | None = None
    scripted_run_glob: str = "*.json"

    def main_args(self, default_strategy: str) -> list[str]:
        """CLI args for main.py to launch this agent (kind=llm only)."""
        strategy = self.strategy or default_strategy
        args = ["--strategy", strategy, "--no-report", "--llm", self.llm]
        if self.llm == "ollama":
            args += ["--ollama-model", self.ollama_model or "qwen3-base"]
            if self.ollama_think:
                args.append("--ollama-think")
        elif self.llm == "claude":
            args += ["--claude-model", self.claude_model]
        elif self.llm == "openai":
            args += ["--openai-model", self.openai_model]
        return args


# ── Roster ─────────────────────────────────────────────────────────────────────
AGENTS: list[AgentSpec] = [
    AgentSpec(label="gemma4-noThink",      kind="llm", llm="ollama",
              ollama_model="gemma4:26b",         ollama_think=False,
              strategy="FH_TWOPAIR_ECONOMIC"),
    AgentSpec(label="balatro-v1",          kind="llm", llm="ollama",
              ollama_model="balatro-qwen3",      ollama_think=False,
              strategy="FH_DISCARD"),
    AgentSpec(label="balatro-v2",          kind="llm", llm="ollama",
              ollama_model="balatro-qwen3-v2",   ollama_think=False,
              strategy="FLUSH_FAST"),
    AgentSpec(label="gemini",              kind="llm", llm="gemini",
              strategy="FLUSH_JOKER_SPECIALIST"),
    AgentSpec(label="scripted-flush",      kind="scripted",
              scripted_run_dir="../week1-prototype/finetune_logs/",
              scripted_run_glob="Flush_Joker_Specialist_*.json"),
    # ── OpenAI agents ─────────────────────────────────────────────────────
    AgentSpec(label="gpt4o-mini",          kind="llm", llm="openai",
              openai_model="gpt-4o-mini",  strategy="OPTIMAL_CHASER"),
    AgentSpec(label="gpt4o",               kind="llm", llm="openai",
              openai_model="gpt-4o",       strategy="OPTIMAL_CHASER"),
    AgentSpec(label="gpt41",               kind="llm", llm="openai",
              openai_model="gpt-4.1",      strategy="OPTIMAL_CHASER"),
    AgentSpec(label="gpt41-mini",          kind="llm", llm="openai",
              openai_model="gpt-4.1-mini", strategy="OPTIMAL_CHASER"),
    AgentSpec(label="gpt5-mini",           kind="llm", llm="openai",
              openai_model="gpt-5-mini",   strategy="OPTIMAL_CHASER"),
    AgentSpec(label="o4-mini",             kind="llm", llm="openai",
              openai_model="o4-mini",      strategy="OPTIMAL_CHASER"),
    # ── Claude agents ─────────────────────────────────────────────────────
    AgentSpec(label="claude-haiku",        kind="llm", llm="claude",
              claude_model="haiku",        strategy="OPTIMAL_CHASER"),
    AgentSpec(label="claude-haiku-free",   kind="llm", llm="claude",
              claude_model="haiku",        strategy="FREE_AGENT"),
    AgentSpec(label="claude-sonnet",       kind="llm", llm="claude",
              claude_model="sonnet",       strategy="OPTIMAL_CHASER"),
    # ── OPTIMAL_CHASER — 1 run per agent ──────────────────────────────────
    AgentSpec(label="gemma4-opt",          kind="llm", llm="ollama",
              ollama_model="gemma4:26b",         ollama_think=False,
              strategy="OPTIMAL_CHASER"),
    AgentSpec(label="balatro-v1-opt",      kind="llm", llm="ollama",
              ollama_model="balatro-qwen3",      ollama_think=False,
              strategy="OPTIMAL_CHASER"),
    AgentSpec(label="balatro-v2-opt",      kind="llm", llm="ollama",
              ollama_model="balatro-qwen3-v2",   ollama_think=False,
              strategy="OPTIMAL_CHASER"),
    AgentSpec(label="gemini-opt",          kind="llm", llm="gemini",
              strategy="OPTIMAL_CHASER"),
]


# Default strategy for LLM agents (overrideable per-agent via AgentSpec.strategy)
LLM_STRATEGY = "FREE_AGENT"

# Wall-clock cap per run
RUN_TIMEOUT_SECONDS = 15 * 60   # 15 minutes

# Number of runs per agent
RUNS_PER_AGENT = 3
