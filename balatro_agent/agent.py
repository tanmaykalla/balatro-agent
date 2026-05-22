from __future__ import annotations
import time
import uuid

from strategies import Strategy
from agent_memory import RunMemory
from balatrobot_client import BalatrobotClient
from llm_clients import GeminiFlashLiteClient, OllamaLocalClient, ClaudeSonnetClient
from phase_prompts import PromptBuilder
from phase_handlers import (
    SelectingHandHandler, ShopHandler, BlindSelectHandler, BoosterPackHandler,
)
from run_logger import RunLogger


# Approximate $/Mtoken (input / output)
GEMINI_FLASH_LITE_COST = (0.10, 0.40)
CLAUDE_SONNET_COST = (3.00, 15.00)


class BalatroAgent:
    def __init__(self, strategy: Strategy,
                 gemini: GeminiFlashLiteClient | OllamaLocalClient,
                 sonnet: ClaudeSonnetClient | None, logger: RunLogger):
        self.strategy = strategy
        self.gemini = gemini  # holds whichever LLM client is active
        self.sonnet = sonnet
        self.logger = logger
        self.prompts = PromptBuilder()
        self.bot = BalatrobotClient()
        self.last_memory: RunMemory | None = None   # updated live; used by SIGTERM handler

        booster = BoosterPackHandler()
        self.handlers = {
            "SELECTING_HAND": SelectingHandHandler(),
            "SHOP": ShopHandler(booster),
            "BLIND_SELECT": BlindSelectHandler(),
            "SMODS_BOOSTER_OPENED": booster,
        }

    def _populate_agent_stats(self, memory: RunMemory) -> None:
        memory.agent_stats = {
            "input_chars":    getattr(self.gemini, "input_chars", 0),
            "output_chars":   getattr(self.gemini, "output_chars", 0),
            "call_latencies": list(getattr(self.gemini, "call_latencies", [])),
            "api_errors":     getattr(self.gemini, "api_errors", 0),
            "nudge_retries":  getattr(self.gemini, "nudge_retries", 0),
            "model":          getattr(self.gemini, "model", None)
                               or getattr(self.gemini, "model_name", None),
            "think":          getattr(self.gemini, "think", None),
        }

    def run(self, deck: str = "RED", stake: str = "WHITE",
            seed: str | None = None, generate_report: bool = True) -> RunMemory:
        source = "ollama" if isinstance(self.gemini, OllamaLocalClient) else "gemini"
        memory = RunMemory(run_id=uuid.uuid4().hex[:12],
                           strategy_name=self.strategy.name,
                           source=source)
        self.last_memory = memory   # expose for SIGTERM partial save
        system_prompt = self.prompts.build_system_prompt(self.strategy)
        memory.system_prompt = system_prompt

        log_path = self.logger.open_live_log(memory.run_id)
        print(f"[agent] logging to {log_path}")

        try:
            self.bot.start(deck, stake, seed)
            G = self.bot.get_gamestate()
            # Wait for state to leave MENU
            for _ in range(20):
                if G.get("state") and G.get("state") != "MENU":
                    break
                time.sleep(0.5)
                G = self.bot.get_gamestate()

            _last_state = None
            while True:
                state = G.get("state")
                memory.ante_num = G.get("ante_num", memory.ante_num)
                memory.round_num = G.get("round_num", memory.round_num)

                # Print header on state transitions
                if state != _last_state:
                    ante  = G.get("ante_num", "?")
                    rnd   = G.get("round_num", "?")
                    money = G.get("money", "?")
                    print(f"\n── {state}  Ante {ante}  Round {rnd}  ${money} ──")
                    _last_state = state

                if G.get("won") or state == "GAME_OVER":
                    memory.won = bool(G.get("won"))
                    memory.final_ante = G.get("ante_num", memory.ante_num)
                    result = "WON 🎉" if memory.won else f"LOST at ante {memory.final_ante}"
                    print(f"\n{result}")
                    break

                if state == "ROUND_EVAL":
                    print("  → cash_out (auto)")
                    G = self.bot.cash_out()
                    continue

                handler = self.handlers.get(state)
                if not handler:
                    time.sleep(0.5)
                    G = self.bot.get_gamestate()
                    continue

                G = handler.handle(G, self.strategy, memory,
                                   self.gemini, self.prompts, system_prompt, self.bot)
                time.sleep(0.15)  # small pause between actions so game can animate

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[agent] run aborted: {e}")
            memory.action_log.append({"error": f"run aborted: {e}"})
            memory.final_ante = memory.ante_num

        # Persist per-call telemetry into memory before saving
        self._populate_agent_stats(memory)

        self.logger.close_live_log()
        self.logger.save_run(memory)
        real_actions = [e for e in memory.action_log if "error" not in e]
        if generate_report and self.sonnet is not None and real_actions:
            try:
                report = self.sonnet.generate_report(memory, self.strategy)
                self.logger.save_report(memory.run_id, report)
            except Exception as e:
                print(f"[report] generation failed: {e}")
        elif generate_report and not real_actions:
            print("[report] skipped — no game actions recorded")

        self._print_cost(memory)
        return memory

    def _print_cost(self, memory: RunMemory) -> None:
        is_ollama = isinstance(self.gemini, OllamaLocalClient)
        llm_in = self.gemini.input_chars / 4 / 1_000_000
        llm_out = self.gemini.output_chars / 4 / 1_000_000
        llm_cost = 0.0 if is_ollama else (
            llm_in * GEMINI_FLASH_LITE_COST[0] + llm_out * GEMINI_FLASH_LITE_COST[1]
        )
        s_cost = 0.0
        if self.sonnet is not None:
            s_in = self.sonnet.input_chars / 4 / 1_000_000
            s_out = self.sonnet.output_chars / 4 / 1_000_000
            s_cost = s_in * CLAUDE_SONNET_COST[0] + s_out * CLAUDE_SONNET_COST[1]
        total = llm_cost + s_cost
        label = "ollama (free)" if is_ollama else "gemini"
        cost_str = "free" if is_ollama and self.sonnet is None else f"~${total:.4f}"
        print(f"  ~tokens: {label} {int(self.gemini.input_chars/4)}/"
              f"{int(self.gemini.output_chars/4)}  cost {cost_str}")
