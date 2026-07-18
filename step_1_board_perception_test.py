#!/usr/bin/env python3
"""
Step 1: Static board-reading kill test (self-playing).

The script plays the match-3 game BY ITSELF using the SDK's semantic RPC actions
(random valid swaps — same approach as the SDK's random_bot). Between moves, when
the board is settled, it captures a screenshot + the true board state. Then Gemini
reads each screenshot and we score per-cell accuracy against the truth.

Usage:
    1. Launch the game:
       cd /Users/t101/Documents/godot_games/match3-board && \
         /Users/t101/Downloads/Godot.app/Contents/MacOS/Godot --play
    2. Collect (auto-plays, no human needed):  python3 step_1_board_perception_test.py --collect
    3. Analyze with Gemini:                    python3 step_1_board_perception_test.py --analyze
    4. Results: step_1_results.json

Requires GEMINI_API_KEY in balatro_agent/.env (already present).
"""

import os
import json
import time
import random
import subprocess
import glob
import argparse
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

# SDK python client (ships with the game repo)
import sys
sys.path.insert(0, "/Users/t101/Documents/godot_games/match3-board/tools/python_client")
from economy_client import EconomyPlaytestClient

load_dotenv(Path(__file__).parent / "balatro_agent" / ".env")

GEMINI_MODEL = "gemini-2.5-flash"
CAPTURE_DIR = Path("step_1_captures")
RESULTS_FILE = "step_1_results.json"

_gemini_client = None


def gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set (expected in balatro_agent/.env)")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


# ── Screenshot capture (macOS) ────────────────────────────────────────────────

def capture_screenshot(filename: str) -> bool:
    try:
        result = subprocess.run(["screencapture", "-x", filename],
                                capture_output=True, timeout=5)
        return result.returncode == 0 and os.path.exists(filename)
    except Exception as e:
        print(f"  ✗ capture error: {e}")
        return False


# ── Collect: self-play + capture ──────────────────────────────────────────────

def wait_for_settle(client: EconomyPlaytestClient, tries: int = 60, delay: float = 0.1) -> dict:
    """Poll until the board is idle (waiting_input) or an overlay appears."""
    state = client.get_state()
    for _ in range(tries):
        if state.get("status") in ("waiting_input", "level_intro", "level_finished"):
            return state
        time.sleep(delay)
        state = client.get_state()
    return state


def collect_boards(target_boards: int = 50):
    """Auto-play the game with random valid swaps; capture screenshot + true
    board state each time the board settles."""
    CAPTURE_DIR.mkdir(exist_ok=True)
    client = EconomyPlaytestClient()

    print("ping:", client.ping())
    validation = client.validate_integration()
    if not validation.get("ok"):
        print("✗ integration checks failed:", validation)
        return
    print(f"\n[collect] auto-playing until {target_boards} settled boards are captured")
    print(f"[collect] saving to {CAPTURE_DIR}/  (keep the game window visible & unobstructed!)\n")

    captured = 0
    steps = 0
    while captured < target_boards and steps < target_boards * 4:
        steps += 1
        state = wait_for_settle(client)
        ui = state.get("ui", {})

        # Overlay (Start / Next Level / Play Again ...) -> advance past it
        if ui.get("overlay_visible"):
            if ui.get("primary_enabled"):
                print(f"  [overlay] advancing: {ui.get('primary_action')!r}")
                client.step({"type": "advance"})
                time.sleep(0.6)
                continue
            print("  [overlay] no enabled action; stopping.")
            break

        if state.get("status") != "waiting_input":
            time.sleep(0.3)
            continue

        # Board is settled -> capture screenshot + ground truth as a pair
        shot = CAPTURE_DIR / f"board_{captured:03d}.png"
        meta = CAPTURE_DIR / f"board_{captured:03d}.json"
        # Re-read state immediately around the screenshot to minimize skew
        truth = client.get_state()
        if not capture_screenshot(str(shot)):
            continue
        truth2 = client.get_state()
        if truth.get("board", {}).get("cells") != truth2.get("board", {}).get("cells"):
            # board changed while capturing (shouldn't happen when settled) — skip
            os.remove(shot)
            continue

        with open(meta, "w") as f:
            json.dump({"timestamp": datetime.now().isoformat(),
                       "board": truth.get("board", {}),
                       "level": truth.get("level", {})}, f, indent=2)
        captured += 1

        # Make a random valid move to change the board
        actions = client.get_valid_actions()
        lvl = truth.get("level", {})
        print(f"  ✓ {shot.name}  (score={lvl.get('score')} moves={lvl.get('moves_remaining')} "
              f"valid_swaps={len(actions)})")
        if actions:
            client.step(random.choice(actions))
            time.sleep(0.4)
        else:
            time.sleep(0.5)

    client.close()
    print(f"\n[collect] captured {captured} boards → {CAPTURE_DIR}/")


# ── Analyze: Gemini reads each board ─────────────────────────────────────────

# Board location measured from a sample screenshot, as FRACTIONS of full screen
# size (so it survives retina 2x capture). Assumes the game window is not moved
# between captures. Re-measure if the window position changes.
BOARD_CROP = (592 / 1920, 212 / 1080, 1322 / 1920, 612 / 1080)

TILE_LEGEND = """Tile appearance guide (color id -> what the tile looks like):
- blue   = a blue TRIANGLE
- green  = a green DIAMOND (rhombus gem)
- red    = a red TEARDROP / droplet
- yellow = a yellow-orange TEARDROP / droplet
- purple = a purple CRYSTAL / polygonal gem
- special-blue-triangle and special-blue-triangle-5 = larger / glowing special blue triangles (rare)"""


def _raw_crop(image_path: str):
    """Crop the full-screen capture to the board region (PIL Image, RGB)."""
    from PIL import Image
    img = Image.open(image_path)
    w, h = img.size
    box = (int(BOARD_CROP[0] * w), int(BOARD_CROP[1] * h),
           int(BOARD_CROP[2] * w), int(BOARD_CROP[3] * h))
    return img.crop(box).convert("RGB")


def pixel_read(crop, grid_w: int, grid_h: int) -> list:
    """Classify each cell's dominant color straight from pixels (no AI).
    Used as a frame-validity check: if this disagrees wildly with ground truth,
    the game window was covered or moved when the screenshot was taken."""
    cw, ch = crop.width / grid_w, crop.height / grid_h
    grid = []
    for r in range(grid_h):
        row = []
        for c in range(grid_w):
            votes = {}
            for dx in (-0.15, 0.0, 0.15):
                for dy in (-0.15, 0.0, 0.15):
                    px, py = int((c + 0.5 + dx) * cw), int((r + 0.5 + dy) * ch)
                    rr, gg, bb = crop.getpixel((px, py))
                    if rr > 130 and gg < 110 and bb < 110: name = "red"
                    elif rr > 150 and gg > 110 and bb < 100: name = "yellow"
                    elif gg > 110 and rr < 110 and bb < 130: name = "green"
                    elif bb > 120 and rr < 110: name = "blue"
                    elif rr > 90 and bb > 120 and gg < 90: name = "purple"
                    else: name = "?"
                    votes[name] = votes.get(name, 0) + 1
            row.append(max(votes, key=votes.get))
        grid.append(row)
    return grid


def frame_validity(crop, gt_cells: list, grid_w: int, grid_h: int) -> float:
    """% of cells where the pixel classifier agrees with ground truth (base color)."""
    pix = pixel_read(crop, grid_w, grid_h)
    ok = tot = 0
    for r in range(grid_h):
        for c in range(grid_w):
            tot += 1
            gt = str(gt_cells[r][c])
            base = "blue" if "blue" in gt else gt
            if pix[r][c] == base:
                ok += 1
    return ok / tot * 100 if tot else 0.0


def crop_board_png(image_path: str, grid_w: int = 15, grid_h: int = 8) -> bytes:
    """Crop the full-screen capture down to just the board, draw gridlines +
    row/column labels (so the VLM doesn't have to count cells), return PNG bytes.
    Also saves the annotated crop for visual debugging."""
    from PIL import Image, ImageDraw
    from io import BytesIO

    img = Image.open(image_path)
    w, h = img.size
    box = (int(BOARD_CROP[0] * w), int(BOARD_CROP[1] * h),
           int(BOARD_CROP[2] * w), int(BOARD_CROP[3] * h))
    crop = img.crop(box).convert("RGB")
    if crop.width < 1100:
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)

    # Draw bright gridlines at cell boundaries
    draw = ImageDraw.Draw(crop)
    cw, ch = crop.width / grid_w, crop.height / grid_h
    for c in range(1, grid_w):
        draw.line([(c * cw, 0), (c * cw, crop.height)], fill=(0, 255, 0), width=2)
    for r in range(1, grid_h):
        draw.line([(0, r * ch), (crop.width, r * ch)], fill=(0, 255, 0), width=2)

    # Add a margin with column letters (A..) and row numbers (1..)
    margin = 40
    labeled = Image.new("RGB", (crop.width + margin, crop.height + margin), (20, 20, 20))
    labeled.paste(crop, (margin, margin))
    ldraw = ImageDraw.Draw(labeled)
    for c in range(grid_w):
        ldraw.text((margin + c * cw + cw / 2 - 5, 12), chr(ord("A") + c),
                   fill=(255, 255, 0))
    for r in range(grid_h):
        ldraw.text((14, margin + r * ch + ch / 2 - 6), str(r + 1),
                   fill=(255, 255, 0))

    debug_dir = CAPTURE_DIR / "cropped"
    debug_dir.mkdir(exist_ok=True)
    labeled.save(debug_dir / Path(image_path).name)

    buf = BytesIO()
    labeled.save(buf, format="PNG")
    return buf.getvalue()


def piece_vocabulary(boards: list) -> list:
    """Collect the distinct piece ids present across all ground-truth boards."""
    vocab = set()
    for board_file in boards:
        with open(board_file) as f:
            cells = json.load(f)["board"].get("cells", [])
        for row in cells:
            for piece in row:
                if piece is not None:
                    vocab.add(str(piece))
    return sorted(vocab)


def ask_gemini_read_board(image_path: str, width: int, height: int, vocab: list) -> str:
    image_data = crop_board_png(image_path)

    prompt = f"""This image shows a match-3 puzzle board of exactly {width} columns x {height} rows.
GREEN gridlines mark the cell boundaries. Column letters (A-{chr(ord('A') + width - 1)}) run along the top
and row numbers (1-{height}) down the left side. A thin line of HUD text may overlap the top edge — ignore it.

{TILE_LEGEND}

Valid ids: {', '.join(vocab)}, or "empty" for an empty cell.

Read one row at a time, using the gridlines and labels to stay aligned: for row 1, read the tile
in column A, then B, then C... classifying each by its SHAPE first, then color.

Output ONLY the grid: {height} lines, each with exactly {width} ids separated by single spaces,
row 1 first, column A first. No other text, no markdown."""

    response = gemini_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=[genai_types.Part.from_bytes(data=image_data, mime_type="image/png"),
                  prompt],
    )
    return (response.text or "").strip()


def parse_vlm_grid(vlm_output: str, width: int, height: int) -> list:
    lines = [ln.strip() for ln in vlm_output.replace("`", "").split("\n") if ln.strip()]
    if len(lines) != height:
        return []
    cells = []
    for line in lines:
        row = line.split()
        if len(row) != width:
            return []
        cells.append(row)
    return cells


def analyze_boards(limit: int = 0):
    boards = sorted(glob.glob(str(CAPTURE_DIR / "board_*.json")))
    if not boards:
        print("✗ no boards captured — run --collect first")
        return
    if limit > 0:
        boards = boards[:limit]

    vocab = piece_vocabulary(boards)
    print(f"[analyze] {len(boards)} boards, piece vocabulary: {vocab}\n")

    results = {"timestamp": datetime.now().isoformat(), "model": GEMINI_MODEL,
               "piece_vocabulary": vocab, "boards": []}
    total_cells = correct_cells = parse_failures = 0

    for board_file in boards:
        with open(board_file) as f:
            data = json.load(f)
        board = data["board"]
        gt_cells = board.get("cells", [])
        width, height = board.get("width", 0), board.get("height", 0)
        shot = board_file.replace(".json", ".png")
        name = Path(board_file).stem

        if not gt_cells or not os.path.exists(shot):
            print(f"  ✗ {name}: missing data")
            continue

        # Frame validity: was the board actually visible in this screenshot?
        validity = frame_validity(_raw_crop(shot), gt_cells, width, height)
        if validity < 50:
            print(f"  ✗ {name}: skipped — board not visible in screenshot "
                  f"(pixel check {validity:.0f}%)")
            results["boards"].append({"board_id": name, "skipped_invalid_frame": True,
                                      "pixel_validity_percent": validity})
            continue

        print(f"  • {name}: ", end="", flush=True)
        try:
            raw = ask_gemini_read_board(shot, width, height, vocab)
        except Exception as e:
            print(f"gemini error: {e}")
            continue

        vlm_cells = parse_vlm_grid(raw, width, height)
        if not vlm_cells:
            parse_failures += 1
            print(f"unparseable output ({len(raw)} chars)")
            results["boards"].append({"board_id": name, "parse_failure": True, "raw": raw})
            continue

        ok = tot = 0
        for r in range(height):
            for c in range(width):
                tot += 1
                gt = str(gt_cells[r][c]) if gt_cells[r][c] is not None else "empty"
                if gt == vlm_cells[r][c]:
                    ok += 1
        total_cells += tot
        correct_cells += ok
        acc = ok / tot * 100
        print(f"{acc:.1f}%  ({ok}/{tot})")
        results["boards"].append({"board_id": name, "accuracy_percent": acc,
                                  "correct": ok, "total": tot,
                                  "ground_truth": gt_cells, "vlm_reading": vlm_cells})

    overall = correct_cells / total_cells * 100 if total_cells else 0.0
    results.update({"overall_accuracy_percent": overall, "total_cells": total_cells,
                    "correct_cells": correct_cells, "parse_failures": parse_failures})
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[analyze] OVERALL per-cell accuracy: {overall:.1f}%  "
          f"({correct_cells}/{total_cells}, {parse_failures} unparseable)")
    print(f"[analyze] results → {RESULTS_FILE}")
    print("[analyze] green light for step 2 is ≥95%")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Step 1: match-3 board perception test")
    parser.add_argument("--collect", action="store_true", help="auto-play + capture boards")
    parser.add_argument("--boards", type=int, default=50, help="boards to capture (default 50)")
    parser.add_argument("--analyze", action="store_true", help="score Gemini reads vs truth")
    parser.add_argument("--limit", type=int, default=0, help="analyze only the first N boards")
    parser.add_argument("--model", default=None, help="Gemini model override (e.g. gemini-2.5-flash-lite)")
    args = parser.parse_args()

    if args.model:
        global GEMINI_MODEL
        GEMINI_MODEL = args.model

    if not args.collect and not args.analyze:
        parser.print_help()
        return
    if args.collect:
        collect_boards(target_boards=args.boards)
    if args.analyze:
        analyze_boards(limit=args.limit)


if __name__ == "__main__":
    main()
