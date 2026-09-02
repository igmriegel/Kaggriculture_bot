import json
import re
from pathlib import Path


def main():
    candidates = [
        Path("reports/kaggle/best_optuna_params.json"),
        Path("agent/engines/leader_v10_best.json"),
        Path("reports/kaggle/best_result.json"),
        Path("reports/kaggle/leader_v10_best.json"),
    ]
    best_json_path = None
    for p in candidates:
        if p.exists():
            best_json_path = p
            break

    if best_json_path is None:
        # Fallback to any json in reports/kaggle
        kaggle_dir = Path("reports/kaggle")
        if kaggle_dir.exists():
            jsons = list(kaggle_dir.glob("*.json"))
            if jsons:
                best_json_path = jsons[0]

    if best_json_path is None:
        print("Error: Could not find any parameter JSON file in agent/engines/ or reports/kaggle/.")
        return 1

    v10_py_path = Path("agent/engines/leader_v10.py")

    with open(best_json_path) as f:
        best_params = json.load(f)

    content = v10_py_path.read_text(encoding="utf-8")

    updated_content = content
    for key, value in best_params.items():
        # Match pattern: key: type = value
        # Matches e.g. "closing_day: int = 26" or "melon_roi_multiplier: float = 1.5"
        pattern = rf"({re.escape(key)}:\s*[\w\.]+\s*=\s*)[^\n#]+"
        updated_content = re.sub(
            pattern, lambda m, val=value: m.group(1) + str(val), updated_content
        )

    v10_py_path.write_text(updated_content, encoding="utf-8")
    print(f"Successfully integrated optimized parameters from {best_json_path} into {v10_py_path}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
