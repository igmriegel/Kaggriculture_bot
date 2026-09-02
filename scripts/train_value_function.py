"""Train State Value Function model on collected replay data (V11 Phase 4)."""

import argparse
import os

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Value Function Regressor")
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        default="data/replays/v11_replays.npz",
        help="Input replay data path",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="agent/engines/value_function.joblib",
        help="Output model path",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Dataset {args.input} not found. Collecting sample replay data first...")
        from scripts.collect_replay_data import main as collect_main

        collect_main()

    data = np.load(args.input)
    X = data["X"]
    y = data["y"]

    print(f"=== TRAINING VALUE FUNCTION REGRESSOR (Dataset: {X.shape[0]} samples) ===")

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = HistGradientBoostingRegressor(
        max_iter=100,
        max_depth=5,
        learning_rate=0.05,
        random_state=42,
    )

    model.fit(X_train, y_train)

    preds = model.predict(X_val)
    r2 = r2_score(y_val, preds)
    mae = mean_absolute_error(y_val, preds)

    print(f"Validation R2 Score: {r2:.4f}")
    print(f"Validation MAE: ${mae:,.2f}")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    joblib.dump(model, args.output)

    file_size_kb = os.path.getsize(args.output) / 1024.0
    print(f"Trained Value Function model saved to: {args.output} ({file_size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
