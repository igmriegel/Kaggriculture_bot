#!/usr/bin/env python3
"""Parse a Kaggle replay JSON and generate a compact, token-efficient Markdown summary."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ECONOMIC_ORDERS = {"BUY_ANIMAL", "BUY_LAND", "BUY_PRODUCT", "BUY_SEED", "HIRE", "SELL"}
WORK_OPS = {"CARE", "COLLECT_FERTILIZER", "FEED", "FERTILIZE", "HARVEST", "PLANT", "WATER", "DIG"}


def parse_replay(replay_path: Path) -> dict[str, Any]:
    with open(replay_path, encoding="utf-8") as f:
        replay = json.load(f)

    # Determine players
    agents = replay.get("info", {}).get("Agents", [])
    names = [
        entry.get("Name", f"Player_{i}") if isinstance(entry, dict) else f"Player_{i}"
        for i, entry in enumerate(agents)
    ]
    if len(names) < 1:
        names = ["Player_0", "Player_1"]

    # We assume player 0 is the primary agent (us) and player 1 is the opponent
    p0_name = names[0]
    p1_name = names[1] if len(names) > 1 else "Opponent"

    rewards = replay.get("rewards", [0, 0])
    steps = replay.get("steps", [])

    # Keep track of metrics for both players
    stats = {
        0: {
            "name": p0_name,
            "planted": Counter(),
            "actions": Counter(),
            "idle_turns": 0,
            "weeds_spawned": 0,
            "market": Counter(),
            "milestones": {},
            "grid_prev": {},
        },
        1: {
            "name": p1_name,
            "planted": Counter(),
            "actions": Counter(),
            "idle_turns": 0,
            "weeds_spawned": 0,
            "market": Counter(),
            "milestones": {},
            "grid_prev": {},
        },
    }

    for step_idx, step in enumerate(steps):
        if not isinstance(step, list):
            continue

        for p_idx in [0, 1]:
            if p_idx >= len(step) or not isinstance(step[p_idx], dict):
                continue

            record = step[p_idx]
            observation = record.get("observation", {})
            if not isinstance(observation, dict):
                continue

            day = int(observation.get("day", 0))
            farms = observation.get("farms", [])
            farm = farms[p_idx] if isinstance(farms, list) and p_idx < len(farms) else {}
            if not isinstance(farm, dict):
                farm = {}

            # Record milestone snapshots
            if day not in stats[p_idx]["milestones"]:
                tiles = [
                    tile for row in farm.get("tiles", []) if isinstance(row, list) for tile in row
                ]
                animals = sum(1 for tile in tiles if isinstance(tile, dict) and tile.get("animal"))
                crops = sum(
                    1 for tile in tiles if isinstance(tile, dict) and tile.get("kind") == "PLANT"
                )
                hands = len(farm.get("hands", [])) if isinstance(farm.get("hands"), list) else 0
                stats[p_idx]["milestones"][day] = {
                    "cash": int(farm.get("money", 0)),
                    "workers": 1 + hands,
                    "crops": crops,
                    "animals": animals,
                }

            # Grid analysis to count plants turning into weeds
            tiles_flat = {}
            for y, row in enumerate(farm.get("tiles", [])):
                if not isinstance(row, list):
                    continue
                for x, tile in enumerate(row):
                    if isinstance(tile, dict):
                        tiles_flat[(x, y)] = {"kind": tile.get("kind"), "crop": tile.get("crop")}

            grid_prev = stats[p_idx]["grid_prev"]
            if grid_prev:
                for pos, tile in tiles_flat.items():
                    prev_tile = grid_prev.get(pos)
                    if (
                        prev_tile
                        and prev_tile.get("kind") == "PLANT"
                        and tile.get("kind") == "WEED"
                    ):
                        stats[p_idx]["weeds_spawned"] += 1
            stats[p_idx]["grid_prev"] = tiles_flat

            # Actions and behavior parsing
            action = record.get("action")
            if isinstance(action, dict):
                # Farmer & Hired hands
                commands = []
                farmer_cmd = action.get("farmer")
                if farmer_cmd:
                    commands.append(farmer_cmd)
                for hand_cmd in action.get("hands", []):
                    if hand_cmd:
                        commands.append(hand_cmd)

                for cmd in commands:
                    if isinstance(cmd, list) and len(cmd) > 0:
                        op = cmd[0]
                        if op == "PASS":
                            stats[p_idx]["idle_turns"] += 1
                        elif op in WORK_OPS:
                            stats[p_idx]["actions"][op] += 1
                            if op == "PLANT" and len(cmd) > 1:
                                stats[p_idx]["planted"][cmd[1]] += 1

                # Market orders
                for order in action.get("market", []):
                    if isinstance(order, list) and len(order) > 0:
                        op = order[0]
                        if op in ECONOMIC_ORDERS:
                            stats[p_idx]["actions"][op] += 1
                            qty = int(order[2]) if len(order) > 2 else 1
                            item = order[1] if len(order) > 1 else "UNKNOWN"
                            stats[p_idx]["market"][f"{op}:{item}"] += qty

    # Include final state (Day 30)
    for p_idx in [0, 1]:
        if 30 not in stats[p_idx]["milestones"] and steps:
            # Get last observation farm
            last_record = steps[-1][p_idx] if p_idx < len(steps[-1]) else {}
            last_obs = last_record.get("observation", {}) if isinstance(last_record, dict) else {}
            last_farms = last_obs.get("farms", []) if isinstance(last_obs, dict) else []
            last_farm = (
                last_farms[p_idx]
                if isinstance(last_farms, list) and p_idx < len(last_farms)
                else {}
            )
            if isinstance(last_farm, dict):
                tiles = [
                    tile
                    for row in last_farm.get("tiles", [])
                    if isinstance(row, list)
                    for tile in row
                ]
                animals = sum(1 for tile in tiles if isinstance(tile, dict) and tile.get("animal"))
                crops = sum(
                    1 for tile in tiles if isinstance(tile, dict) and tile.get("kind") == "PLANT"
                )
                hands = (
                    len(last_farm.get("hands", []))
                    if isinstance(last_farm.get("hands"), list)
                    else 0
                )
                stats[p_idx]["milestones"][30] = {
                    "cash": int(last_farm.get("money", 0)),
                    "workers": 1 + hands,
                    "crops": crops,
                    "animals": animals,
                }

    return {
        "episode_id": replay.get("info", {}).get("EpisodeId", "unknown"),
        "seed": replay.get("info", {}).get("seed", "unknown"),
        "p0_score": rewards[0] if len(rewards) > 0 else 0,
        "p1_score": rewards[1] if len(rewards) > 1 else 0,
        "stats": stats,
    }


def generate_markdown(data: dict[str, Any]) -> str:
    stats = data["stats"]
    p0 = stats[0]
    p1 = stats[1]

    md = []
    md.append(f"# Replay Summary (Episode: {data['episode_id']} | Seed: {data['seed']})")

    winner = (
        p0["name"]
        if data["p0_score"] > data["p1_score"]
        else (p1["name"] if data["p1_score"] > data["p0_score"] else "Tie")
    )
    md.append(
        f"**Winner:** {winner} (Scores: {p0['name']} = ${data['p0_score']:,} vs {p1['name']} = ${data['p1_score']:,})\n"
    )

    md.append("## Game Milestones (Day | Cash / Workers / Crops / Animals)")
    md.append(
        "| Day | " + f"{p0['name']} (Cash/W/C/A)" + " | " + f"{p1['name']} (Cash/W/C/A)" + " |"
    )
    md.append("|---|---|---|")

    milestone_days = [0, 5, 10, 15, 20, 25, 30]
    for d in milestone_days:
        p0_m = p0["milestones"].get(d, {"cash": 0, "workers": 0, "crops": 0, "animals": 0})
        p1_m = p1["milestones"].get(d, {"cash": 0, "workers": 0, "crops": 0, "animals": 0})

        p0_str = f"${p0_m['cash']:,} / {p0_m['workers']} / {p0_m['crops']} / {p0_m['animals']}"
        p1_str = f"${p1_m['cash']:,} / {p1_m['workers']} / {p1_m['crops']} / {p1_m['animals']}"

        md.append(f"| Day {d:<2} | {p0_str} | {p1_str} |")
    md.append("")

    md.append("## Crop Portfolio (Planted seeds)")
    p0_planted = ", ".join(f"{c}: {n}" for c, n in sorted(p0["planted"].items())) or "None"
    p1_planted = ", ".join(f"{c}: {n}" for c, n in sorted(p1["planted"].items())) or "None"
    md.append(f"- **{p0['name']}:** {p0_planted}")
    md.append(f"- **{p1['name']}:** {p1_planted}\n")

    md.append("## Action Performance")
    md.append("| Metric | " + p0["name"] + " | " + p1["name"] + " |")
    md.append("|---|---|---|")

    actions_to_show = [
        ("Watering Actions", "WATER"),
        ("Harvesting Actions", "HARVEST"),
        ("Digging (Weeding) Actions", "DIG"),
        ("Feeding Actions", "FEED"),
        ("Animal Care Actions", "CARE"),
        ("Collect Fertilizer", "COLLECT_FERTILIZER"),
        ("Planting Actions", "PLANT"),
        ("Total Hires", "HIRE"),
        ("Land Unlocks", "BUY_LAND"),
    ]
    for label, op in actions_to_show:
        md.append(f"| {label} | {p0['actions'].get(op, 0)} | {p1['actions'].get(op, 0)} |")

    md.append(f"| Idle (PASS) Turns | {p0['idle_turns']} | {p1['idle_turns']} |")
    md.append("")

    md.append("## Failure Indicators")
    md.append(
        f"- **Crops dried/decayed into Weeds:** {p0['weeds_spawned']} times ({p0['name']}) vs {p1['weeds_spawned']} times ({p1['name']})"
    )

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="Generate ultra-compact replay summaries.")
    parser.add_argument(
        "target",
        type=str,
        help="Path to Kaggle replay JSON file, directory, or submission ID (e.g. 55680358)",
    )
    args = parser.parse_args()

    target_path = Path(args.target)
    is_sub_id = False
    sub_id = args.target

    # Check if target is a submission ID
    if not target_path.exists():
        # Check canonical HTML reports submissions folder first
        sub_dir = Path("reports/submissions") / args.target
        if sub_dir.is_dir():
            target_path = sub_dir
            is_sub_id = True
        else:
            kaggle_dir = Path("reports/kaggle") / f"submission-{args.target}"
            if kaggle_dir.is_dir():
                target_path = kaggle_dir
                is_sub_id = True
            else:
                print(
                    f"Error: {args.target} does not exist and was not found under reports/submissions/ or reports/kaggle/submission-"
                )
                sys.exit(1)
    else:
        # Check if the path itself is inside reports/submissions/<sub_id>
        parts = target_path.resolve().parts
        if "submissions" in parts:
            idx = parts.index("submissions")
            if idx + 1 < len(parts):
                sub_id = parts[idx + 1]
                is_sub_id = True

    # Gather files
    files = []
    if target_path.is_file():
        files.append(target_path)
    elif target_path.is_dir():
        # Find all json replays recursively
        for path in target_path.rglob("*.json"):
            if "replay" in path.name or "episode-" in path.name:
                # Exclude existing summary json if any
                if "_summary" not in path.name and "audit" not in path.name:
                    files.append(path)
        if not files:
            files = [
                p
                for p in target_path.rglob("*.json")
                if "_summary" not in p.name and "audit" not in p.name
            ]

    if not files:
        print(f"Error: No replay files found for target {args.target}")
        sys.exit(1)

    print(f"Found {len(files)} replay file(s) to summarize...")

    # Determine output directory aligned with HTML reports structure
    if is_sub_id:
        output_dir = Path("reports/submissions") / sub_id / "summaries"
    else:
        output_dir = Path("reports/summaries")
        if target_path.is_dir():
            output_dir = output_dir / target_path.name

    output_dir.mkdir(parents=True, exist_ok=True)

    for i, file_path in enumerate(files, 1):
        print(f"\nProcessing [{i}/{len(files)}]: {file_path}")
        try:
            data = parse_replay(file_path)
            markdown_content = generate_markdown(data)

            output_name = file_path.stem + "_summary.md"
            output_path = output_dir / output_name
            output_path.write_text(markdown_content, encoding="utf-8")

            if len(files) == 1:
                print(markdown_content)
            else:
                print(f"  Saved summary to: {output_path}")
        except Exception as e:
            print(f"  Error parsing {file_path}: {e}")


if __name__ == "__main__":
    main()
