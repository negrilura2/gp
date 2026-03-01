# scripts/train.py
import argparse
import yaml
import os
import sys

# Ensure project root in path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voice_engine.core.trainer import Trainer
from voice_engine.config import MODELS_DIR

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="Train voice recognition model from config")
    parser.add_argument("--config", "-c", required=True, help="Path to config yaml file")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--early_stop", action="store_true")
    parser.add_argument("--no_early_stop", action="store_true")
    parser.add_argument("--patience", type=int, default=None)
    parser.add_argument("--save_dir", type=str, default=None, help="Override save directory")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)

    print(f"Loading config from {args.config}")
    cfg = load_config(args.config)
    training_cfg = cfg.setdefault("training", {})
    paths_cfg = cfg.setdefault("paths", {})

    if args.epochs is not None:
        training_cfg["epochs"] = args.epochs
    if args.patience is not None:
        training_cfg["patience"] = args.patience
    if args.early_stop:
        training_cfg["early_stop"] = True
    if args.no_early_stop:
        training_cfg["early_stop"] = False
    
    # Allow overriding save_dir via CLI or default to config constant
    if args.save_dir:
        paths_cfg["save_dir"] = args.save_dir
    elif not paths_cfg.get("save_dir"):
        paths_cfg["save_dir"] = str(MODELS_DIR)

    trainer = Trainer(cfg)
    trainer.fit()

if __name__ == "__main__":
    main()
