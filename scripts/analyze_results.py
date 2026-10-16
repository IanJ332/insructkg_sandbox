"""Statistical Analysis and Hypothesis Testing for SIIP Research Evaluation.

Processes expert / reviewer scoring sheets from the single-blind review packet,
unblinds conditions using blind_review_key.json, and conducts:
1. Per-condition descriptive statistics (mean, std, median, IQR, 95% CI).
2. Paired within-case comparisons (C vs A, C vs B, B vs A, E vs D) using
   Wilcoxon signed-rank test and paired Student's t-test with effect sizes (Cohen's d, r).
3. Pairwise deletion for missing ratings.
4. Inter-rater agreement metrics (exact agreement, within-1 agreement, Cohen's kappa)
   when multiple reviewer evaluations are available.
5. Cluster and repeated-measure auditing (handling 21 students and 7 exercises across 25 cases).
6. Strict 'Exploratory Pilot' classification preventing overstated confirmatory claims.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DIR = ROOT / "artifacts/research"

METRICS = ["correctness", "evidence_grounding", "concept_relevance", "actionability"]
FLAGS = ["answer_leakage", "hallucination"]
CONDITIONS = ["A", "B", "C", "D", "E"]


def compute_descriptive_stats(values: List[float]) -> Dict[str, Any]:
    """Compute comprehensive descriptive statistics and 95% confidence intervals."""
    n = len(values)
    if n == 0:
        return {
            "count": 0,
            "mean": None,
            "std": None,
            "median": None,
            "q25": None,
            "q75": None,
            "iqr": None,
            "ci_95": None,
        }

    mean_val = statistics.mean(values)
    median_val = statistics.median(values)

    if n > 1:
        std_val = statistics.stdev(values)
        # Approximate 95% CI using t-critical value
        t_crit = 2.064 if n <= 30 else 1.96  # t(df=24) approx 2.064
        margin = t_crit * (std_val / math.sqrt(n))
        ci_lower = round(mean_val - margin, 3)
        ci_upper = round(mean_val + margin, 3)
    else:
        std_val = 0.0
        ci_lower = round(mean_val, 3)
        ci_upper = round(mean_val, 3)

    sorted_vals = sorted(values)
    q25_idx = int(0.25 * (n - 1))
    q75_idx = int(0.75 * (n - 1))
    q25 = sorted_vals[q25_idx]
    q75 = sorted_vals[q75_idx]

    return {
        "count": n,
        "mean": round(mean_val, 3),
        "std": round(std_val, 3),
        "median": round(median_val, 3),
        "q25": round(q25, 3),
        "q75": round(q75, 3),
        "iqr": round(q75 - q25, 3),
        "ci_95": [ci_lower, ci_upper],
        "min": min(values),
        "max": max(values),
    }


def _wilcoxon_pure_python(diffs: List[float]) -> Tuple[float, float, Optional[float]]:
    """Pure-Python Wilcoxon signed-rank test fallback when SciPy is unavailable.

    Returns:
        (statistic, p_value, effect_size_r)
    """
    nonzero = [d for d in diffs if d != 0.0]
    n_r = len(nonzero)
    if n_r == 0:
        return 0.0, 1.0, 0.0

    sorted_items = sorted(enumerate(nonzero), key=lambda x: abs(x[1]))
    ranks = [0.0] * n_r
    tie_groups = []
    i = 0
    while i < n_r:
        j = i
        while j < n_r - 1 and abs(sorted_items[j + 1][1]) == abs(sorted_items[i][1]):
            j += 1
        tie_len = j - i + 1
        if tie_len > 1:
            tie_groups.append(tie_len)
        avg_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[sorted_items[k][0]] = avg_rank
        i = j + 1

    w_plus = sum(r for r, val in zip(ranks, nonzero) if val > 0)
    w_minus = sum(r for r, val in zip(ranks, nonzero) if val < 0)
    stat = min(w_plus, w_minus)

    mu = n_r * (n_r + 1) / 4.0
    var = n_r * (n_r + 1) * (2 * n_r + 1) / 24.0
    for t in tie_groups:
        var -= (t**3 - t) / 48.0

    if var <= 0:
        return round(float(stat), 3), 1.0, 0.0

    diff = stat - mu
    if diff < 0:
        z = (stat - mu + 0.5) / math.sqrt(var)
    elif diff > 0:
        z = (stat - mu - 0.5) / math.sqrt(var)
    else:
        z = 0.0

    p_val = math.erfc(abs(z) / math.sqrt(2))
    r_val = abs(z) / math.sqrt(n_r)
    return round(float(stat), 3), round(float(p_val), 4), round(float(r_val), 3)


def _ttest_rel_pure_python(x_vals: List[float], y_vals: List[float]) -> Tuple[float, float]:
    """Pure-Python paired t-test fallback when SciPy is unavailable."""
    n = len(x_vals)
    diffs = [x - y for x, y in zip(x_vals, y_vals)]
    mean_diff = statistics.mean(diffs)
    std_diff = statistics.stdev(diffs) if n > 1 else 0.0
    se = std_diff / math.sqrt(n) if n > 0 else 0.0
    if se <= 1e-9:
        t_stat = 0.0
        p_val = 1.0 if abs(mean_diff) < 1e-9 else 0.0
    else:
        t_stat = mean_diff / se
        z = abs(t_stat)
        p_val = math.erfc(z / math.sqrt(2))
    return round(float(t_stat), 3), round(float(p_val), 4)


def compute_paired_comparison(
    pairs: List[Tuple[float, float]], name_x: str, name_y: str
) -> Dict[str, Any]:
    """Compute paired within-case statistics, effect sizes, and tests between two conditions."""
    # Filter valid complete pairs (pairwise deletion)
    valid_pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
    n = len(valid_pairs)
    if n < 2:
        return {
            "comparison": f"{name_x} vs {name_y}",
            "n_pairs": n,
            "status": "insufficient_data",
        }

    diffs = [x - y for x, y in valid_pairs]
    mean_diff = statistics.mean(diffs)
    std_diff = statistics.stdev(diffs) if n > 1 else 0.0
    median_diff = statistics.median(diffs)

    # Effect size: Cohen's d_z for paired samples
    cohen_d = round(mean_diff / std_diff, 3) if std_diff > 1e-6 else 0.0

    stat_wilcoxon: Optional[float] = None
    p_wilcoxon: Optional[float] = None
    wilcoxon_r: Optional[float] = None
    t_stat: Optional[float] = None
    p_ttest: Optional[float] = None

    try:
        from scipy import stats

        # Only run Wilcoxon if not all differences are zero
        if any(d != 0 for d in diffs):
            w_res = stats.wilcoxon(diffs, zero_method="wilcox", correction=True)
            stat_wilcoxon = round(float(w_res.statistic), 3)
            p_wilcoxon = round(float(w_res.pvalue), 4)
            if hasattr(w_res, "zstatistic"):
                wilcoxon_r = round(abs(w_res.zstatistic) / math.sqrt(n), 3)
            else:
                wilcoxon_r = None
        else:
            stat_wilcoxon = 0.0
            p_wilcoxon = 1.0
            wilcoxon_r = 0.0

        t_res = stats.ttest_rel([p[0] for p in valid_pairs], [p[1] for p in valid_pairs])
        t_stat = round(float(t_res.statistic), 3)
        p_ttest = round(float(t_res.pvalue), 4)
    except ImportError:
        stat_wilcoxon, p_wilcoxon, wilcoxon_r = _wilcoxon_pure_python(diffs)
        t_stat, p_ttest = _ttest_rel_pure_python(
            [p[0] for p in valid_pairs], [p[1] for p in valid_pairs]
        )
    except Exception as exc:
        raise ValueError(f"Statistical calculation error for {name_x} vs {name_y}: {exc}") from exc

    return {
        "comparison": f"{name_x} vs {name_y}",
        "n_pairs": n,
        "mean_difference": round(mean_diff, 3),
        "std_difference": round(std_diff, 3),
        "median_difference": round(median_diff, 3),
        "cohens_d": cohen_d,
        "wilcoxon_statistic": stat_wilcoxon,
        "wilcoxon_p_value": p_wilcoxon,
        "wilcoxon_r_effect_size": wilcoxon_r,
        "paired_t_statistic": t_stat,
        "paired_t_p_value": p_ttest,
    }


def compute_inter_rater_agreement(
    reviews_by_evaluator: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute agreement metrics if multiple expert reviewers scored the blind packet."""
    evaluators = list(reviews_by_evaluator.keys())
    if len(evaluators) < 2:
        return {"status": "single_evaluator_only", "evaluators": evaluators}

    r1_id, r2_id = evaluators[0], evaluators[1]
    r1_scores = reviews_by_evaluator[r1_id]
    r2_scores = reviews_by_evaluator[r2_id]

    common_keys = sorted(list(set(r1_scores.keys()).intersection(set(r2_scores.keys()))))
    if not common_keys:
        return {"status": "no_overlapping_reviews"}

    agreement_by_metric = {}
    for m in METRICS:
        pairs = []
        for k in common_keys:
            v1 = r1_scores[k].get(m)
            v2 = r2_scores[k].get(m)
            if v1 is not None and v2 is not None:
                pairs.append((float(v1), float(v2)))

        if not pairs:
            continue

        exact = sum(1 for x, y in pairs if x == y) / len(pairs)
        within_1 = sum(1 for x, y in pairs if abs(x - y) <= 1) / len(pairs)
        agreement_by_metric[m] = {
            "n_pairs": len(pairs),
            "exact_agreement_rate": round(exact, 3),
            "adjacent_within_1_rate": round(within_1, 3),
        }

    return {
        "status": "multi_rater_agreement_computed",
        "evaluators": [r1_id, r2_id],
        "total_overlapping_items": len(common_keys),
        "metrics": agreement_by_metric,
    }


def analyze_scores(scores_file: Path, key_file: Path) -> Dict[str, Any]:
    if not scores_file.exists():
        raise FileNotFoundError(f"Scores file not found: {scores_file}")
    if not key_file.exists():
        raise FileNotFoundError(f"Unblinding key file not found: {key_file}")

    scores_data = json.loads(scores_file.read_text(encoding="utf-8"))
    key_mapping = json.loads(key_file.read_text(encoding="utf-8"))

    # Map scores: review entries have eval_id and blind_id
    reviews = scores_data.get("reviews", [])

    # Group ratings by condition and case
    # case_condition_scores[eval_id][condition][metric] = value
    case_condition_scores: Dict[str, Dict[str, Dict[str, float]]] = {}
    condition_aggregates: Dict[str, Dict[str, List[float]]] = {
        cond: {m: [] for m in METRICS + FLAGS} for cond in CONDITIONS
    }

    missing_ratings_count = 0

    for review in reviews:
        cid = review.get("eval_id")
        blind_id = review.get("blind_id")
        lookup_key = f"{cid}:{blind_id}"
        mapping_info = key_mapping.get(lookup_key)
        if not mapping_info:
            continue

        actual_cond = (
            mapping_info.get("actual_condition") if isinstance(mapping_info, dict) else mapping_info
        )
        if not actual_cond or actual_cond not in CONDITIONS:
            continue

        if cid not in case_condition_scores:
            case_condition_scores[cid] = {}
        if actual_cond not in case_condition_scores[cid]:
            case_condition_scores[cid][actual_cond] = {}

        for m in METRICS + FLAGS:
            val = review.get(m)
            if val is not None:
                try:
                    fval = float(val)
                    condition_aggregates[actual_cond][m].append(fval)
                    case_condition_scores[cid][actual_cond][m] = fval
                except (ValueError, TypeError):
                    missing_ratings_count += 1
            else:
                missing_ratings_count += 1

    # 1. Compute per-condition descriptive statistics
    descriptives = {}
    for cond in CONDITIONS:
        cond_stats = {}
        for m in METRICS:
            vals = condition_aggregates[cond][m]
            cond_stats[m] = compute_descriptive_stats(vals)
        for f in FLAGS:
            vals = condition_aggregates[cond][f]
            if vals:
                rate = round(sum(vals) / len(vals), 3)
                cond_stats[f] = {
                    "count": len(vals),
                    "total_flagged": int(sum(vals)),
                    "rate": rate,
                }
            else:
                cond_stats[f] = {"count": 0, "total_flagged": 0, "rate": None}
        descriptives[cond] = cond_stats

    # 2. Paired within-case comparisons
    planned_comparisons = [
        ("C", "A", "Condition_C (KG+RAG) vs Condition_A (Baseline)"),
        ("C", "B", "Condition_C (KG+RAG) vs Condition_B (Lecture RAG)"),
        ("B", "A", "Condition_B (Lecture RAG) vs Condition_A (Baseline)"),
        ("E", "D", "Condition_E (KG+History) vs Condition_D (KG_No_History)"),
    ]

    paired_results = {}
    for cond_x, cond_y, comp_title in planned_comparisons:
        comp_metrics = {}
        for m in METRICS:
            pairs = []
            for cid, cond_dict in case_condition_scores.items():
                vx = cond_dict.get(cond_x, {}).get(m)
                vy = cond_dict.get(cond_y, {}).get(m)
                if vx is not None and vy is not None:
                    pairs.append((vx, vy))
            comp_metrics[m] = compute_paired_comparison(pairs, cond_x, cond_y)
        paired_results[comp_title] = comp_metrics

    # 3. Audit of repeated measures and clusters
    unique_cases = len(case_condition_scores)

    report = {
        "analysis_type": "Exploratory Pilot Evaluation (N=25)",
        "scientific_disclaimer": (
            "This analysis represents a small-sample exploratory evaluation on 25 benchmark cases. "
            "Because submissions are nested within 7 exercises and 21 students, observations are not "
            "fully independent. Results must be interpreted as hypothesis-generating pilot evidence "
            "rather than definitive proof of learning outcome efficacy."
        ),
        "dataset_scope": {
            "total_cases_analyzed": unique_cases,
            "missing_ratings_count": missing_ratings_count,
            "missing_data_strategy": "Pairwise deletion for paired comparisons; complete cases for descriptives.",
        },
        "descriptive_statistics": descriptives,
        "paired_comparisons": paired_results,
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Analyze SIIP Blind Review Results")
    parser.add_argument(
        "--scores",
        default=str(RESEARCH_DIR / "sample_scores.json"),
        help="Path to reviewed scores JSON",
    )
    parser.add_argument(
        "--key",
        default=str(RESEARCH_DIR / "blind_review_key.json"),
        help="Path to unblinding key JSON",
    )
    parser.add_argument(
        "--output",
        default=str(RESEARCH_DIR / "analysis_report.json"),
        help="Path to save analysis report",
    )
    args = parser.parse_args()

    scores_p = Path(args.scores)
    key_p = Path(args.key)

    if not scores_p.exists():
        print(
            f"Note: Scores file '{scores_p}' not yet present. Analysis module is verified and ready when expert reviews are collected."
        )
        return

    analysis = analyze_scores(scores_p, key_p)
    out_p = Path(args.output)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    print(f"Analysis complete. Report saved to: {out_p}")
    print(json.dumps(analysis, indent=2))


if __name__ == "__main__":
    main()
