"""Descriptive coverage/error curves from saved margins, without new fitting.

Only development margin magnitudes create the abstention-threshold grid.
The saved dummy assignment threshold and all upstream model outputs stay fixed.
Holdout answers are used only to report the resulting descriptive curves.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METHODS = ("B_frozen", "C_relation_quality")
SPLITS = ("development", "exploratory_holdout")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def decision(margin, threshold):
    if margin is None or not math.isfinite(float(margin)):
        return "failed"
    if abs(margin) + 1e-12 < threshold:
        return "pending"
    return "same" if margin > 0 else "different"


def metrics(rows, threshold):
    decided = []
    failed = pending = false_merges = missed_merges = 0
    for row in rows:
        answer = decision(row.get("margin"), threshold) if row["decision"] != "failed" else "failed"
        if answer == "failed":
            failed += 1
        elif answer == "pending":
            pending += 1
        else:
            decided.append(row)
            false_merges += answer == "same" and not row["same_object"]
            missed_merges += answer == "different" and row["same_object"]
    total, automatic = len(rows), len(decided)
    return {"pairs": total, "automatic_count": automatic, "automatic_fraction": automatic / total if total else None, "decided_errors": false_merges + missed_merges, "decided_error_rate": (false_merges + missed_merges) / automatic if automatic else None, "false_merges": false_merges, "missed_merges": missed_merges, "pending": pending, "failed": failed, "result_completeness": (total - failed) / total if total else None}


def make_curves(saved_rows, frozen):
    curves, grids, marked = [], [], []
    for method in METHODS:
        parameters = frozen["parameters"][method]
        frozen_threshold = float(parameters["abstention_margin"])
        development = [r for r in saved_rows if r["method"] == method and r["split"] == "development"]
        valid = [abs(float(r["margin"])) for r in development if r.get("margin") is not None and r["decision"] != "failed"]
        if not valid:
            raise ValueError(f"No development margins for {method}")
        # Endpoint is derived from the development maximum, never from test margins.
        thresholds = sorted({0.0, frozen_threshold, *valid, max(valid) + 1e-9})
        grids.append({"method": method, "dummy_threshold_unchanged": parameters["dummy_threshold"], "abstention_thresholds": thresholds, "source": "development absolute margins plus 0, saved frozen threshold and development max+1e-9", "development_pairs": len(development), "holdout_values_used_to_create_grid": False})
        for split in SPLITS:
            rows = [r for r in saved_rows if r["method"] == method and r["split"] == split]
            if not rows:
                raise ValueError(f"No saved rows for {method}/{split}")
            # An artifact mismatch must not silently produce a misleading new curve.
            for row in rows:
                expected = decision(row.get("margin"), frozen_threshold) if row["decision"] != "failed" else "failed"
                if expected != row["decision"]:
                    raise ValueError(f"Frozen operating point does not reproduce {row['pair_id']}/{method}")
            for threshold in thresholds:
                row = {"method": method, "split": split, "abstention_margin": threshold, "is_frozen_operating_point": threshold == frozen_threshold, "is_no_abstention_point": threshold == 0.0, "thresholds_from_development_only": True, "analysis_role": "posthoc_descriptive_no_parameter_selection", **metrics(rows, threshold)}
                curves.append(row)
                if row["is_frozen_operating_point"] or row["is_no_abstention_point"]:
                    marked.append(row)
    return curves, grids, marked


def plot_curves(curves, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
    chinese = font.exists()
    if chinese:
        font_manager.fontManager.addfont(str(font))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({"font.size": 11, "axes.unicode_minus": False, "savefig.dpi": 220})
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.3), sharey=True)
    styles = {"B_frozen": ("#2563eb", "-", "B 冻结特征" if chinese else "B frozen features"), "C_relation_quality": ("#d97706", "--", "C 关系与质量" if chinese else "C relation + quality")}
    titles = {"development": "开发数据 24 对" if chinese else "Development (24 pairs)", "exploratory_holdout": "探索性留出 24 对" if chinese else "Exploratory holdout (24 pairs)"}
    all_errors = [100 * r["decided_error_rate"] for r in curves if r["decided_error_rate"] is not None]
    ymax = max(10, min(100, math.ceil(max(all_errors, default=0) / 5) * 5 + 5))
    for ax, split in zip(axes, SPLITS):
        for method in METHODS:
            rows = [r for r in curves if r["method"] == method and r["split"] == split and r["decided_error_rate"] is not None]
            rows.sort(key=lambda r: (r["automatic_fraction"], r["abstention_margin"]))
            color, linestyle, label = styles[method]
            ax.plot([100*r["automatic_fraction"] for r in rows], [100*r["decided_error_rate"] for r in rows], color=color, linestyle=linestyle, marker=".", markersize=4, linewidth=1.8, label=label)
            for marker_key, marker, size in [("is_frozen_operating_point", "*", 190), ("is_no_abstention_point", "X", 100)]:
                selected = next(r for r in rows if r[marker_key])
                ax.scatter([100*selected["automatic_fraction"]], [100*selected["decided_error_rate"]], c=color, marker=marker, s=size, edgecolor="#111827", linewidth=.7, zorder=5)
        ax.set(title=titles[split], xlabel="自动判定比例（%）" if chinese else "Automatic decision coverage (%)", xlim=(-2, 103), ylim=(-.7, ymax))
        ax.grid(alpha=.2)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("已判定错误率（%）" if chinese else "Error rate among decided pairs (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    from matplotlib.lines import Line2D
    handles += [Line2D([0],[0],marker="*",color="none",markerfacecolor="#9ca3af",markeredgecolor="#111827",markersize=12), Line2D([0],[0],marker="X",color="none",markerfacecolor="#9ca3af",markeredgecolor="#111827",markersize=8)]
    labels += ["已冻结工作点" if chinese else "Frozen operating point", "取消待确认" if chinese else "No abstention"]
    fig.legend(handles, labels, loc="upper center", ncol=4, bbox_to_anchor=(.5,.98), frameon=False)
    fig.suptitle("方向一 覆盖率与已判定错误率" if chinese else "Direction 1 coverage versus decided error", y=1.035, fontsize=16)
    note = ("阈值列表仅来自开发 margin；留出曲线为事后描述，不重新选参。零覆盖率时错误率未定义。\n公开标注尚未独立人工复核，场地独立性未验证；本曲线不能证明 C 有额外收益。" if chinese else "Threshold grid uses development margins only; holdout curves are descriptive, with no retuning. Error is undefined at zero coverage.\nPublisher labels lack independent human review; site independence is unverified. These curves do not establish a benefit for C.")
    fig.text(.5, .015, note, ha="center", va="bottom", fontsize=9, color="#374151")
    fig.subplots_adjust(top=.86, bottom=.2, left=.085, right=.98, wspace=.12)
    fig.savefig(out / "覆盖率错误率.png", bbox_inches="tight")
    fig.savefig(out / "覆盖率错误率.pdf", bbox_inches="tight")
    plt.close(fig)
    return matplotlib.__version__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=ROOT / "runs/d1")
    args = parser.parse_args()
    run = args.run_dir.resolve()
    out = run / "coverage_analysis"
    out.mkdir(parents=True, exist_ok=True)
    rows_path, frozen_path = run / "per_pair_results.jsonl", run / "frozen_config.json"
    rows, frozen = read_jsonl(rows_path), json.loads(frozen_path.read_text())
    curves, grids, marked = make_curves(rows, frozen)
    for name, data in [("coverage_error_curve.csv", curves), ("marked_operating_points.csv", marked)]:
        with (out / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    (out / "development_thresholds.json").write_text(json.dumps(grids, ensure_ascii=False, indent=2) + "\n")
    version = plot_curves(curves, out)
    notes = {"analysis_kind": "posthoc_descriptive_analysis", "new_model_calls": 0, "new_inference_timing_claim": False, "upstream_parameters_changed": False, "threshold_grid_from_development_only": True, "holdout_used_for_parameter_selection": False, "frozen_decisions_reproduced_exactly": True, "curve_rows": len(curves), "saved_pairs_per_method": len([r for r in rows if r["method"] == METHODS[0]]), "matplotlib_version": version, "source_hashes": {str(rows_path.relative_to(ROOT)): sha256(rows_path), str(frozen_path.relative_to(ROOT)): sha256(frozen_path)}, "limitations": ["Cannot prove C has incremental benefit", "No new independent human review", "Strict site independence remains unverified", "Few pairs and discrete coverage; no interpolated or smoothed claim", "Test curve is descriptive, not a new test-tuned operating point"], "marked_points": marked}
    (out / "analysis.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n")
    explanation = "本分析只重读已保存的 B/C 决策 margin，不运行模型、不改变匹配阈值或原始结果。待确认阈值列表来自开发集绝对 margin，并加入已冻结阈值、取消待确认的零阈值和开发最大值以上的拒判端点。留出曲线是事后描述，不据此选新阈值。星形表示原冻结工作点，叉形表示取消待确认。所有失败继续计入总样本分母；没有自动判定时错误率为空。\n\n当前样本的公开标注没有独立人工复核，严格场地隔离也未确认。曲线用于观察低错误率是否来自降低自动判定比例，不能证明 C 有额外收益。\n"
    (out / "说明.txt").write_text(explanation)
    print(json.dumps({"output": str(out), "curve_rows": len(curves), "matplotlib": version, "marked_points": marked}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
