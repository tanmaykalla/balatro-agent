import argparse
import os
import signal
import sys

from dotenv import load_dotenv

from strategies import STRATEGIES
from llm_clients import GeminiFlashLiteClient, OllamaLocalClient, ClaudeSonnetClient, ClaudeGameClient, OpenAIGameClient, OpenAIReportClient
from run_logger import RunLogger
from agent import BalatroAgent


# Graceful shutdown: save partial run on SIGTERM (sent by benchmark runner before SIGKILL)
_current_agent: "BalatroAgent | None" = None
_logger: "RunLogger | None" = None

def _sigterm_handler(signum, frame):
    print("\n[main] SIGTERM received — saving partial run...")
    if _current_agent and _logger:
        mem = _current_agent.last_memory
        if mem:
            try:
                _current_agent._populate_agent_stats(mem)
            except Exception:
                pass
            try:
                _logger.save_run(mem)
            except Exception as e:
                print(f"[main] partial save failed: {e}")
    sys.exit(0)

signal.signal(signal.SIGTERM, _sigterm_handler)


def main() -> int:
    global _current_agent, _logger
    load_dotenv()

    parser = argparse.ArgumentParser(description="Balatro LLM Agent")
    parser.add_argument("--strategy", help="Strategy name (see --list-strategies)")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--deck", default="RED")
    parser.add_argument("--stake", default="WHITE")
    parser.add_argument("--seed", default=None)
    parser.add_argument("--no-report", action="store_true")
    parser.add_argument("--list-strategies", action="store_true")
    parser.add_argument("--llm", default="gemini",
                        choices=["gemini", "ollama", "claude", "openai"],
                        help="LLM backend: gemini (default), ollama (local), claude, or openai")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434",
                        help="Ollama base URL (default: http://127.0.0.1:11434)")
    parser.add_argument("--ollama-model", default="qwen3-8b-q4-local",
                        help="Ollama model name")
    parser.add_argument("--ollama-think", action="store_true",
                        help="Enable hidden chain-of-thought for Ollama models")
    parser.add_argument("--claude-model", default="haiku",
                        choices=["haiku", "sonnet"],
                        help="Claude model variant (default: haiku)")
    parser.add_argument("--openai-model", default="gpt-4o-mini",
                        help="OpenAI model name (default: gpt-4o-mini)")
    args = parser.parse_args()

    if args.list_strategies:
        print("Available strategies:")
        for key, strat in STRATEGIES.items():
            print(f"  {key:30s} → {strat.name}")
        return 0

    if not args.strategy:
        parser.error("--strategy is required (or use --list-strategies)")

    if args.strategy not in STRATEGIES:
        print(f"Unknown strategy: {args.strategy}", file=sys.stderr)
        print(f"Available: {', '.join(STRATEGIES.keys())}", file=sys.stderr)
        return 1

    strategy = STRATEGIES[args.strategy]

    if args.llm == "ollama":
        llm_client = OllamaLocalClient(base_url=args.ollama_url,
                                       model=args.ollama_model,
                                       think=args.ollama_think)
        print(f"LLM: ollama ({args.ollama_model} @ {args.ollama_url}, think={args.ollama_think})")
    elif args.llm == "claude":
        llm_client = ClaudeGameClient(model=args.claude_model)
        print(f"LLM: claude ({llm_client.model})")
    elif args.llm == "openai":
        llm_client = OpenAIGameClient(model=args.openai_model)
        print(f"LLM: openai ({llm_client.model})")
    else:
        llm_client = GeminiFlashLiteClient()
        print(f"LLM: gemini ({GeminiFlashLiteClient.model_name})")

    if args.no_report:
        sonnet = None
    elif os.environ.get("OPENAI_API_KEY"):
        sonnet = OpenAIReportClient()
    else:
        sonnet = ClaudeSonnetClient()
    logger = RunLogger()

    for i in range(1, args.runs + 1):
        agent = BalatroAgent(strategy, llm_client, sonnet, logger)
        _current_agent = agent
        _logger = logger
        memory = agent.run(deck=args.deck, stake=args.stake, seed=args.seed,
                           generate_report=not args.no_report)
        outcome = "WON" if memory.won else f"LOST ante {memory.final_ante}"
        print(f"Run {i}/{args.runs} | Strategy: {strategy.name} | Result: {outcome}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
