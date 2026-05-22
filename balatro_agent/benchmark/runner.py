"""
Benchmark runner.
For each agent in the roster, launches RUNS_PER_AGENT games (or ingests
existing scripted-bot logs), with a hard wall-clock cap, then aggregates
per-run JSONs into a single benchmark result file.

Usage:
    cd balatro_agent
    python3 -m benchmark.runner                 # run full bench
    python3 -m benchmark.runner --agent gemini  # single agent only
    python3 -m benchmark.runner --dry-run       # show planned commands

Outputs:
    benchmark/results/<timestamp>/
        runs/<label>_<i>.json    (one per AI-agent run, copied from runs/)
        scripted/*.json          (linked from week1 logs)
        meta.json                (per-run status, timeouts, errors)
"""
from __future__ import annotations
import argparse
import datetime
import glob
import json
import os
import shutil
import subprocess
import sys
import time

from benchmark.agents import (
    AGENTS, LLM_STRATEGY, RUNS_PER_AGENT, RUN_TIMEOUT_SECONDS, AgentSpec,
)


REPO_ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_ROOT    = os.path.join(REPO_ROOT, "benchmark", "results")
LIVE_RUNS_DIR   = os.path.join(REPO_ROOT, "runs")


def _ts() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _find_newest_run_json(since: float) -> str | None:
    """Return path of the most recent runs/*.json created after `since` (epoch)."""
    candidates = []
    for p in glob.glob(os.path.join(LIVE_RUNS_DIR, "*.json")):
        try:
            mt = os.path.getmtime(p)
            if mt >= since - 1:
                candidates.append((mt, p))
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _run_llm_agent(agent: AgentSpec, run_idx: int, out_dir: str,
                   dry_run: bool) -> dict:
    """Spawn `python3 main.py ...` for one game, with a 15-min wall cap.
    Returns a dict with status + path to the resulting run JSON.
    """
    cmd = ["python3", "-u", "main.py", "--runs", "1"] + agent.main_args(LLM_STRATEGY)
    label = agent.label
    log_path = os.path.join(out_dir, f"{label}_{run_idx:02d}.log")

    if dry_run:
        print(f"  [dry] {label} run {run_idx}: {' '.join(cmd)}")
        return {"agent": label, "run": run_idx, "status": "dry"}

    print(f"\n──── {label} run {run_idx}/{RUNS_PER_AGENT} ────")
    print(f"  cmd: {' '.join(cmd)}")
    print(f"  log: {log_path}")

    start_ts = time.time()
    with open(log_path, "w") as logf:
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=REPO_ROOT,
                stdout=logf,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
                start_new_session=True,   # own process group → killpg works
            )
            try:
                proc.wait(timeout=RUN_TIMEOUT_SECONDS)
                status  = "ok" if proc.returncode == 0 else f"exit_{proc.returncode}"
                timeout = False
            except subprocess.TimeoutExpired:
                import signal, os as _os
                print(f"  ⏱  TIMEOUT after {RUN_TIMEOUT_SECONDS}s — sending SIGTERM (10s to save)...")
                try:
                    _os.killpg(_os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=10)   # give it 10s to save partial run
                except subprocess.TimeoutExpired:
                    _os.killpg(_os.getpgid(proc.pid), signal.SIGKILL)
                    proc.wait()
                except ProcessLookupError:
                    pass
                status  = "TIMEOUT"
                timeout = True
        except Exception as exc:
            status  = f"error: {exc}"
            timeout = False
    elapsed = time.time() - start_ts

    # Find the resulting run JSON (latest in runs/ created during this window)
    run_json = _find_newest_run_json(start_ts)
    copied = None
    if run_json:
        dest = os.path.join(out_dir, "runs", f"{label}_{run_idx:02d}.json")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(run_json, dest)
        copied = dest
        print(f"  → copied {os.path.basename(run_json)} → {dest}")
    else:
        print(f"  ⚠ no run JSON found (status={status})")

    return {
        "agent": label, "run": run_idx, "status": status,
        "timeout": timeout, "elapsed_sec": round(elapsed, 1),
        "run_json": copied,
        "log": log_path,
    }


def _ingest_scripted(agent: AgentSpec, out_dir: str) -> list[dict]:
    """Pull RUNS_PER_AGENT pre-existing scripted-bot JSONs into the bench dir."""
    src_dir = os.path.join(REPO_ROOT, agent.scripted_run_dir)
    src_dir = os.path.normpath(src_dir)
    pattern = os.path.join(src_dir, agent.scripted_run_glob)
    files = sorted(glob.glob(pattern))[:RUNS_PER_AGENT]
    if not files:
        print(f"  ⚠ no scripted runs found at {pattern}")
        return []

    dest_dir = os.path.join(out_dir, "runs")
    os.makedirs(dest_dir, exist_ok=True)
    out_meta = []
    for i, src in enumerate(files, start=1):
        dest = os.path.join(dest_dir, f"{agent.label}_{i:02d}.json")
        shutil.copy2(src, dest)
        out_meta.append({
            "agent": agent.label, "run": i, "status": "ok",
            "timeout": False, "elapsed_sec": 0.0,
            "run_json": dest,
            "log": None, "source_file": src,
        })
        print(f"  → ingested {os.path.basename(src)}")
    return out_meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent",   default=None,
                    help="Comma-separated agent labels to run (default: all)")
    ap.add_argument("--runs",    type=int, default=RUNS_PER_AGENT,
                    help=f"Runs per agent (default: {RUNS_PER_AGENT})")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Override roster runs count
    global RUNS_PER_AGENT_LOCAL
    runs_per_agent = args.runs

    roster = AGENTS
    if args.agent:
        labels = [l.strip() for l in args.agent.split(",")]
        roster = [a for a in AGENTS if a.label in labels]
        missing = [l for l in labels if l not in {a.label for a in roster}]
        if missing:
            print(f"Unknown agent(s): {missing}", file=sys.stderr)
            print(f"Available: {[a.label for a in AGENTS]}", file=sys.stderr)
            return 1

    stamp   = _ts()
    out_dir = os.path.join(RESULTS_ROOT, stamp)
    os.makedirs(out_dir, exist_ok=True)
    print(f"Benchmark output: {out_dir}")
    print(f"Roster: {[a.label for a in roster]}")
    print(f"Runs/agent: {runs_per_agent}  Timeout: {RUN_TIMEOUT_SECONDS}s")

    all_meta: list[dict] = []
    for agent in roster:
        print(f"\n════ {agent.label} ({agent.kind}) ════")
        if agent.kind == "scripted":
            all_meta += _ingest_scripted(agent, out_dir)
            continue

        for i in range(1, runs_per_agent + 1):
            meta = _run_llm_agent(agent, i, out_dir, dry_run=args.dry_run)
            all_meta.append(meta)

    # Save meta
    meta_path = os.path.join(out_dir, "meta.json")
    with open(meta_path, "w") as f:
        json.dump({
            "timestamp": stamp,
            "strategy":  LLM_STRATEGY,
            "timeout_sec": RUN_TIMEOUT_SECONDS,
            "runs_per_agent": runs_per_agent,
            "results": all_meta,
        }, f, indent=2)
    print(f"\nSaved meta → {meta_path}")
    print(f"\nNext step: python3 -m benchmark.report {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
