import argparse
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def plot_strategy_curves(strategy_dir, out_path):
    if not os.path.isdir(strategy_dir):
        print(f"strategy_dir not found: {strategy_dir}")
        return
    files = [f for f in os.listdir(strategy_dir) if f.endswith(".json")]
    if not files:
        print(f"No strategy json found in {strategy_dir}")
        return

    runs = []
    for name in files:
        path = os.path.join(strategy_dir, name)
        try:
            data = load_json(path)
        except Exception as e:
            print(f"Skip {name}: {e}")
            continue
        history = data.get("history") or []
        if not history:
            continue
        epochs = [h["epoch"] for h in history]
        loss_train = [h["loss_train"] for h in history]
        loss_val = [h["loss_val"] for h in history]
        acc_train = [h["acc_train"] for h in history]
        acc_val = [h["acc_val"] for h in history]
        eer_vals = [h["eer"] for h in history]
        runs.append(
            {
                "name": data.get("run_name", os.path.splitext(name)[0]),
                "epochs": epochs,
                "loss_train": loss_train,
                "loss_val": loss_val,
                "acc_train": acc_train,
                "acc_val": acc_val,
                "eer": eer_vals,
            }
        )

    if not runs:
        print(f"No valid runs in {strategy_dir}")
        return

    fig, axes = plt.subplots(3, 1, figsize=(8, 10), sharex=True)

    for run in runs:
        x = run["epochs"]
        axes[0].plot(x, run["loss_train"], label=f"{run['name']}-train")
        axes[0].plot(x, run["loss_val"], linestyle="--", label=f"{run['name']}-val")
        axes[1].plot(x, run["acc_train"], label=f"{run['name']}-train")
        axes[1].plot(x, run["acc_val"], linestyle="--", label=f"{run['name']}-val")
        eer_vals = [v for v in run["eer"] if v is not None]
        if eer_vals:
            x_eer = [e for e, v in zip(x, run["eer"]) if v is not None]
            y_eer = [float(v) for v in run["eer"] if v is not None]
            axes[2].plot(x_eer, y_eer, marker="o", label=run["name"])

    axes[0].set_ylabel("Loss")
    axes[1].set_ylabel("Accuracy")
    axes[2].set_ylabel("EER")
    axes[2].set_xlabel("Epoch")
    axes[0].legend()
    axes[1].legend()
    if axes[2].lines:
        axes[2].legend()
    axes[0].set_title("Training Strategy Comparison")
    plt.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, dpi=160)
    plt.close(fig)
    print(f"Saved strategy curves to {out_path}")


def summarize_score_norm(score_norm_dir, out_path):
    if not os.path.isdir(score_norm_dir):
        print(f"score_norm_dir not found: {score_norm_dir}")
        return
    files = [f for f in os.listdir(score_norm_dir) if f.endswith(".json")]
    if not files:
        print(f"No score_norm json found in {score_norm_dir}")
        return

    summary = {}
    for name in files:
        path = os.path.join(score_norm_dir, name)
        try:
            data = load_json(path)
        except Exception as e:
            print(f"Skip {name}: {e}")
            continue
        method = data.get("method") or os.path.splitext(name)[0]
        summary[method] = {
            "eer": data.get("eer"),
            "mindcf": data.get("mindcf_res", {}).get("min_dcf") if isinstance(data.get("mindcf_res"), dict) else data.get("mindcf"),
            "threshold": data.get("threshold"),
        }

    if not summary:
        print(f"No valid score_norm entries in {score_norm_dir}")
        return

    print("ScoreNorm Summary (method, EER, minDCF, threshold):")
    for method, vals in summary.items():
        print(f"- {method}: EER={vals['eer']}, minDCF={vals['mindcf']}, thr={vals['threshold']}")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Saved score_norm summary to {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy_dir", default=os.path.join("reports", "strategy"))
    parser.add_argument("--score_norm_dir", default=os.path.join("reports", "score_norm"))
    parser.add_argument("--out_dir", default="reports")
    args = parser.parse_args()

    strategy_png = os.path.join(args.out_dir, "strategy", "strategy_curves.png")
    plot_strategy_curves(args.strategy_dir, strategy_png)

    score_norm_summary = os.path.join(args.out_dir, "score_norm", "summary.json")
    summarize_score_norm(args.score_norm_dir, score_norm_summary)


if __name__ == "__main__":
    main()

