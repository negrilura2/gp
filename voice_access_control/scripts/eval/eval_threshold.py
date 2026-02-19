# scripts/eval/eval_threshold.py
"""
Usage:
python -m scripts.eval.eval_threshold --model models/ecapa_best.pth --feature_dir data/features --out_dir reports --max_pairs 20000

Outputs:
reports/roc.png
reports/eer_threshold.json  ({"eer":..., "threshold":...})
"""
import os
import sys
import json
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import FEATURES_DIR, MODELS_DIR, REPORTS_DIR

from voice_engine.ecapa_tdnn import LightECAPA
from voice_engine.dataset import SpeakerDataset, pad_collate
from torch.utils.data import DataLoader
from voice_engine.evaluation import extract_all_embeddings
from voice_engine.metrics import compute_pairs_scores, eer_from_roc, compute_mindcf, recommend_threshold, compute_score_hist, compute_calibration

def main():

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--feature_dir", default=str(FEATURES_DIR))
    parser.add_argument("--out_dir", default=str(REPORTS_DIR))
    parser.add_argument("--max_pairs", type=int, default=20000)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    backend_dir = os.path.join(args.out_dir, "archive", "backend_responses")
    roc_dir = os.path.join(args.out_dir, "archive", "plots", "roc")
    os.makedirs(backend_dir, exist_ok=True)
    os.makedirs(roc_dir, exist_ok=True)
    
    device = "cuda" if torch.cuda.is_available() else "cpu"

    ds_tmp = SpeakerDataset(args.feature_dir)
    if len(ds_tmp) == 0:
        raise ValueError("feature_dir 内没有可用特征文件")
    sample_feat, _ = ds_tmp[0]
    feat_dim_data = int(sample_feat.shape[0])

    print("加载模型...")
    state = torch.load(args.model, map_location=device)
    ckpt_feat_dim = None
    w = state.get("layer1.conv.weight")
    if w is not None:
        ckpt_feat_dim = int(w.shape[1])
    if ckpt_feat_dim is not None and ckpt_feat_dim != feat_dim_data:
        raise RuntimeError(
            f"模型参数的特征维度为 {ckpt_feat_dim}，但当前特征目录 {args.feature_dir} 的维度为 {feat_dim_data}，请检查是否使用了对应的特征目录或模型文件"
        )
    feat_dim = ckpt_feat_dim or feat_dim_data
    model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=None).to(device)
    model.load_state_dict(state, strict=False)

    print("正在提取所有utterance embedding（可能较慢）...")
    embs, labels, spk2idx = extract_all_embeddings(model, device, args.feature_dir)

    print("计算成对得分（抽样）...")
    y, scores, same_scores, diff_scores = compute_pairs_scores(embs, labels, max_pairs=args.max_pairs)

    print("计算 ROC 与 EER ...")
    unique_labels = np.unique(y)
    if len(unique_labels) < 2 or len(scores) == 0:
        print("评估数据不足，无法计算 ROC/EER，已输出空指标")
        out_json = os.path.join(backend_dir, "eer_threshold.json")
        with open(out_json, "w") as f:
            json.dump({"auc": None, "eer": None, "threshold": None}, f, indent=2)
        roc_points_json = os.path.join(backend_dir, "roc_points.json")
        with open(roc_points_json, "w") as f:
            json.dump({"fpr": [], "tpr": [], "thresholds": []}, f, indent=2)
        det_points_json = os.path.join(backend_dir, "det_points.json")
        with open(det_points_json, "w") as f:
            json.dump({"fpr": [], "fnr": []}, f, indent=2)
        mindcf_json = os.path.join(backend_dir, "mindcf.json")
        with open(mindcf_json, "w") as f:
            json.dump({"threshold": None, "min_dcf": None, "dcf": [], "thresholds": []}, f, indent=2)
        score_dist_json = os.path.join(backend_dir, "score_dist.json")
        with open(score_dist_json, "w") as f:
            json.dump({"bins": [], "same": [], "diff": []}, f, indent=2)
        calib_json = os.path.join(backend_dir, "calibration.json")
        with open(calib_json, "w") as f:
            json.dump({"bins": [], "accuracy": [], "confidence": [], "count": [], "ece": None}, f, indent=2)
        sys.exit(0)
    try:
        fpr, tpr, thresholds = roc_curve(y, scores)
        roc_auc = auc(fpr, tpr)
        eer, eer_thr = eer_from_roc(fpr, tpr, thresholds)
        mindcf = compute_mindcf(fpr, tpr, thresholds)
        rec_thr, rec_youden = recommend_threshold(fpr, tpr, thresholds)
    except ValueError as exc:
        print(f"ROC 计算失败：{exc}")
        out_json = os.path.join(backend_dir, "eer_threshold.json")
        with open(out_json, "w") as f:
            json.dump({"auc": None, "eer": None, "threshold": None}, f, indent=2)
        roc_points_json = os.path.join(backend_dir, "roc_points.json")
        with open(roc_points_json, "w") as f:
            json.dump({"fpr": [], "tpr": [], "thresholds": []}, f, indent=2)
        det_points_json = os.path.join(backend_dir, "det_points.json")
        with open(det_points_json, "w") as f:
            json.dump({"fpr": [], "fnr": []}, f, indent=2)
        mindcf_json = os.path.join(backend_dir, "mindcf.json")
        with open(mindcf_json, "w") as f:
            json.dump({"threshold": None, "min_dcf": None, "dcf": [], "thresholds": []}, f, indent=2)
        score_dist_json = os.path.join(backend_dir, "score_dist.json")
        with open(score_dist_json, "w") as f:
            json.dump({"bins": [], "same": [], "diff": []}, f, indent=2)
        calib_json = os.path.join(backend_dir, "calibration.json")
        with open(calib_json, "w") as f:
            json.dump({"bins": [], "accuracy": [], "confidence": [], "count": [], "ece": None}, f, indent=2)
        sys.exit(0)
    if rec_thr is not None:
        print(f"AUC={roc_auc:.4f}  EER={eer:.4f}, suggested threshold={rec_thr:.4f}")
    else:
        print(f"AUC={roc_auc:.4f}  EER={eer:.4f}, suggested threshold={mindcf['threshold']:.4f}")

    # 保存 ROC 图
    plt.figure(figsize=(6,5))
    plt.plot(fpr, tpr, label=f"AUC={roc_auc:.4f}")
    plt.plot([0,1],[0,1],'k--', alpha=0.3)
    plt.xlabel("FPR")
    plt.ylabel("TPR")
    plt.title("ROC")
    plt.legend()
    plt.grid(True)
    out_png = os.path.join(roc_dir, "roc.png")
    plt.savefig(out_png)
    plt.close()
    print("Saved ROC to", out_png)

    out_json = os.path.join(backend_dir, "eer_threshold.json")
    with open(out_json, "w") as f:
        json.dump(
            {
                "auc": float(roc_auc),
                "eer": float(eer),
                "threshold_eer": float(eer_thr),
                "threshold_mindcf": float(mindcf["threshold"]),
                "mindcf": float(mindcf["min_dcf"]),
                "threshold_youden": float(rec_thr) if rec_thr is not None else None,
                "youden": float(rec_youden) if rec_youden is not None else None,
                "threshold": float(rec_thr) if rec_thr is not None else float(mindcf["threshold"]),
                "p_target": float(mindcf["p_target"]),
                "c_miss": float(mindcf["c_miss"]),
                "c_fa": float(mindcf["c_fa"]),
            },
            f,
            indent=2,
        )
    print("Saved metrics to", out_json)

    roc_points_json = os.path.join(backend_dir, "roc_points.json")
    with open(roc_points_json, "w") as f:
        json.dump(
            {
                "fpr": [float(v) for v in fpr],
                "tpr": [float(v) for v in tpr],
                "thresholds": [float(v) for v in thresholds],
            },
            f,
            indent=2,
        )
    print("Saved ROC points to", roc_points_json)

    det_points_json = os.path.join(backend_dir, "det_points.json")
    with open(det_points_json, "w") as f:
        json.dump(
            {
                "fpr": [float(v) for v in fpr],
                "fnr": [float(1 - v) for v in tpr],
            },
            f,
            indent=2,
        )
    print("Saved DET points to", det_points_json)

    mindcf_json = os.path.join(backend_dir, "mindcf.json")
    with open(mindcf_json, "w") as f:
        json.dump(mindcf, f, indent=2)
    print("Saved minDCF to", mindcf_json)

    score_dist_json = os.path.join(backend_dir, "score_dist.json")
    with open(score_dist_json, "w") as f:
        json.dump(compute_score_hist(same_scores, diff_scores), f, indent=2)
    print("Saved score distribution to", score_dist_json)

    calib_json = os.path.join(backend_dir, "calibration.json")
    with open(calib_json, "w") as f:
        json.dump(compute_calibration(scores, y), f, indent=2)
    print("Saved calibration to", calib_json)

if __name__ == "__main__":
    main()
