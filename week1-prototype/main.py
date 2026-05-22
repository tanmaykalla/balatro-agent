import time

from metrics import MetricsLogger, RunMetrics, HandRecord
from perception import BalatrobotPerception, run_strategy
from strategy import ALL_STRATEGIES, Strategy
from report_generator import generate_report
from run_logger import RunLogger, format_state_prompt, _derive_reasoning

NUM_RUNS          = 15   # runs per strategy
WIN_ANTE          = 8    # beat ante 8 = win; stop immediately
ACTION_DELAY      = 0.1  # seconds between most actions
BLIND_SKIP_DELAY  = 2.0  # longer pause after blind skip (tag reward animation)


def run_single_game(
    perception: BalatrobotPerception,
    logger: MetricsLogger,
    strategy: Strategy,
    run_num: int,
) -> RunMetrics:
    logger.reset_run()
    perception.start_game()
    ended_early = False
    action_logger = RunLogger(strategy_name=strategy.name, source="strategy",
                              log_dir="finetune_logs/")

    while not perception.is_game_over():
        state = perception.get_state()

        if state.ante_num > WIN_ANTE:
            ended_early = True
            break

        logger.record_money(state.money)
        chips_before = state.chips
        prompt = format_state_prompt(state)         # capture before action
        action = run_strategy(state, strategy)
        reasoning = _derive_reasoning(state, action, strategy)

        new_state = perception.take_action(action)
        action_logger.log(state, action, reasoning, prompt)

        # Record per-hand data immediately after every play action
        if action.action_type == "play" and new_state is not None:
            chips_delta = max(0, new_state.chips - chips_before)
            logger.record_hand(HandRecord(
                run_num      = run_num,
                ante         = action.meta.get("ante", state.ante_num),
                blind        = action.meta.get("blind", state.current_blind),
                hand_type    = action.meta.get("hand_type", "?"),
                chips_scored = chips_delta,
                joker_keys   = action.meta.get("joker_keys", []),
            ))

        if action.action_type == "skip_blind":
            time.sleep(BLIND_SKIP_DELAY)
        else:
            time.sleep(ACTION_DELAY)

    action_logger.save(run_num=run_num)

    if ended_early:
        return RunMetrics(
            strategy_name             = strategy.name,
            run_num                   = run_num,
            ante_reached_at_game_end  = WIN_ANTE,
            won                       = True,
            total_dollars_earned      = logger._dollars_this_run,
        )

    result = perception.get_game_over_result()
    return RunMetrics(
        strategy_name             = strategy.name,
        run_num                   = run_num,
        ante_reached_at_game_end  = result["ante_reached_at_game_end"],
        won                       = result["won"],
        total_dollars_earned      = logger._dollars_this_run,
    )


def print_strategy_summary(strategy_name: str, runs: list) -> None:
    wins        = sum(1 for r in runs if r.won)
    avg_ante    = sum(r.ante_reached_at_game_end for r in runs) / len(runs)
    avg_dollars = sum(r.total_dollars_earned for r in runs) / len(runs)
    width       = 60

    print(f"\n{'─' * width}")
    print(f"  {strategy_name}")
    print(f"{'─' * width}")
    print(f"  {'Run':>4}  {'Ante':>4}  {'Won':>5}  {'Dollars':>8}  {'Hands':>5}")
    print(f"  {'----':>4}  {'----':>4}  {'-----':>5}  {'--------':>8}  {'-----':>5}")
    for r in runs:
        print(
            f"  {r.run_num:>4}  "
            f"{r.ante_reached_at_game_end:>4}  "
            f"{'yes' if r.won else 'no':>5}  "
            f"${r.total_dollars_earned:>7}  "
            f"{len(r.hands):>5}",
        )
    print(f"{'─' * width}")
    print(
        f"  Wins: {wins}/{len(runs)}  |  "
        f"Avg ante: {avg_ante:.1f}  |  "
        f"Avg $: ${avg_dollars:.0f}"
    )


def main() -> None:
    perception = BalatrobotPerception()
    logger     = MetricsLogger("week1_results.csv", reports_dir="reports")

    print(f"Benchmark: {len(ALL_STRATEGIES)} strategies × {NUM_RUNS} runs each")
    print(f"Results   : week1_results.csv  +  reports/<strategy>.html")

    all_runs: list[RunMetrics] = []

    for strategy in ALL_STRATEGIES:
        strategy_runs: list[RunMetrics] = []

        for run_num in range(1, NUM_RUNS + 1):
            print(
                f"  [{strategy.name}]  run {run_num}/{NUM_RUNS} ...",
                end=" ", flush=True,
            )
            metrics = run_single_game(perception, logger, strategy, run_num)
            logger.log_run(metrics)
            strategy_runs.append(metrics)
            all_runs.append(metrics)

            hands_played = len(metrics.hands)
            status = "WON ✓" if metrics.won else f"ante {metrics.ante_reached_at_game_end}"
            print(f"{status}  ${metrics.total_dollars_earned}  ({hands_played} hands)", flush=True)

        print_strategy_summary(strategy.name, strategy_runs)
        report_path = generate_report(strategy.name, strategy_runs, reports_dir="reports")
        print(f"  Report → {report_path}")

    total_wins = sum(1 for r in all_runs if r.won)
    print(f"\n{'═' * 56}")
    print(f"  All done.  {total_wins}/{len(all_runs)} total wins across all strategies.")
    print(f"  Combined results → week1_results.csv")
    print(f"{'═' * 56}")


if __name__ == "__main__":
    main()
