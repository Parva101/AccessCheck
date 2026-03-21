"""
AccessCheck — Main Demo Script

Orchestrates the full pipeline:
  1. Load dataset (Rotterdam / YouTube / local images)
  2. Run VLM accessibility audit on each sample
  3. Compute Brain embeddings for clustering
  4. Evaluate against ground truth (if available)
  5. Generate accessibility report
  6. Launch FiftyOne App

Usage:
    # Run on Rotterdam dataset (default)
    python demo.py

    # Run on Rotterdam with limited samples (fast demo)
    python demo.py --rotterdam --max-samples 50

    # Run on a YouTube property tour video
    python demo.py --youtube "https://www.youtube.com/watch?v=VIDEO_ID"

    # Run on local images
    python demo.py --images /path/to/images

    # Skip audit (just load + launch App with existing data)
    python demo.py --skip-audit --dataset-name "my-existing-dataset"
"""

import argparse
import logging
import sys
import os
import re
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
# Add src/ to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fiftyone as fo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="AccessCheck - Accessibility Auditor")

    # Data source (pick one)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--rotterdam", action="store_true", default=True,
                        help="Use Rotterdam Accessibility dataset (default)")
    source.add_argument("--youtube", type=str, default=None,
                        help="YouTube video URL to analyze")
    source.add_argument("--images", type=str, default=None,
                        help="Path to local images directory")

    # Options
    parser.add_argument("--max-samples", type=int, default=None,
                        help="Max samples to load/audit (useful for testing)")
    parser.add_argument("--dataset-name", type=str, default=None,
                        help="Custom dataset name")
    parser.add_argument("--model", type=str, default="gemini-3-flash-preview",
                        help="Gemini model name (default: gemini-3-flash-preview)")
    parser.add_argument("--skip-audit", action="store_true",
                        help="Skip VLM audit (just load data and launch App)")
    parser.add_argument("--skip-brain", action="store_true",
                        help="Skip Brain embeddings computation")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay between API calls in seconds (rate limiting)")

    # Video sampler options
    parser.add_argument("--strategy", type=str, default="hybrid",
                        choices=["uniform", "scene_change", "hybrid"],
                        help="Frame extraction strategy for video")
    parser.add_argument("--max-frames", type=int, default=100,
                        help="Max frames to extract from video")

    return parser.parse_args()


def _raw_to_accessibility_label(raw_value, field_name=""):
    """Normalize common GT formats to {'accessible', 'inaccessible'} labels."""
    lname = (field_name or "").lower()

    if raw_value is None:
        return None

    if isinstance(raw_value, fo.Classification):
        raw_value = raw_value.label

    # Booleans can represent either `is_accessible` or `is_inaccessible`
    if isinstance(raw_value, bool):
        if "inaccess" in lname or "non_access" in lname or "not_access" in lname:
            return "inaccessible" if raw_value else "accessible"
        return "accessible" if raw_value else "inaccessible"

    # Common binary integer encoding
    if isinstance(raw_value, (int, float)):
        ivalue = int(raw_value)
        if ivalue in (0, 1):
            if "inaccess" in lname or "non_access" in lname or "not_access" in lname:
                return "inaccessible" if ivalue == 1 else "accessible"
            return "accessible" if ivalue == 1 else "inaccessible"
        return None

    if isinstance(raw_value, str):
        value = raw_value.strip().lower()
        if not value:
            return None

        normalized = value.replace("_", " ").replace("-", " ")
        normalized = re.sub(r"\s+", " ", normalized).strip(" '\".,:;!?()[]{}")

        inaccessible_values = {
            "0",
            "false",
            "no",
            "inaccessible",
            "non compliant",
            "not accessible",
            "not wheelchair accessible",
            "wheelchair inaccessible",
        }
        accessible_values = {
            "1",
            "true",
            "yes",
            "accessible",
            "compliant",
            "wheelchair accessible",
        }

        # Use exact normalized labels only; avoid substring matching that can
        # misclassify free text like video titles.
        if normalized in inaccessible_values:
            return "inaccessible"

        if normalized in accessible_values:
            return "accessible"

    return None


def _sample_get(sample, field_name, default=None):
    """Safely read a sample field without throwing on missing fields."""
    try:
        return sample.get_field(field_name)
    except Exception:
        return default


def _candidate_gt_fields(dataset):
    system_fields = {
        "id",
        "filepath",
        "tags",
        "metadata",
        "created_at",
        "last_modified_at",
        "overall_accessible",
        "accessibility_score",
        "scene_type",
        "issues_json",
        "issue_count",
        "issue_types",
        "severity_tags",
        "audit_status",
        "pred_accessibility",
        "gt_accessibility",
        "accessibility_eval",
    }

    schema = dataset.get_field_schema()
    ranked = []
    for field_name, field in schema.items():
        if field_name in system_fields or field_name.startswith("_"):
            continue

        score = 0
        lname = field_name.lower()
        field_type = type(field).__name__.lower()

        # Ignore obvious metadata fields (e.g. YouTube source URL/title)
        if any(k in lname for k in ("source_", "url", "title", "timestamp", "frame_", "eval", "pred_")):
            continue

        if any(k in lname for k in ("ground_truth", "gt", "label", "target", "access")):
            score += 3
        if any(k in field_type for k in ("classification", "boolean", "string", "int", "float")):
            score += 1

        ranked.append((score, field_name))

    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [name for _, name in ranked]


def _detect_gt_field(dataset, probe_size=250):
    """
    Detect a field that likely contains binary accessibility GT labels.
    """
    candidates = _candidate_gt_fields(dataset)
    if not candidates:
        return None, None

    probe_view = dataset.limit(probe_size)
    best = None

    for field_name in candidates:
        non_null = 0
        recognized = 0
        for sample in probe_view:
            raw = _sample_get(sample, field_name, default=None)
            if raw is None:
                continue

            non_null += 1
            if _raw_to_accessibility_label(raw, field_name=field_name) is not None:
                recognized += 1

        if non_null == 0:
            continue

        ratio = recognized / non_null
        if recognized == 0:
            continue

        # Keep only high-signal candidates
        if ratio < 0.6:
            continue

        candidate = (recognized, ratio, field_name)
        if best is None or candidate > best:
            best = candidate

    if best is None:
        return None, None

    recognized, ratio, field_name = best
    return field_name, {"recognized": recognized, "ratio": round(ratio, 3)}


def _prepare_eval_fields(dataset, gt_field):
    """
    Build normalized classification fields for evaluation:
      - pred_accessibility: from model output bool `overall_accessible`
      - gt_accessibility: from detected GT field
    """
    pred_field = "pred_accessibility"
    gt_eval_field = "gt_accessibility"

    pred_count = 0
    gt_count = 0

    for sample in dataset:
        pred_bool = _sample_get(sample, "overall_accessible", default=None)
        if pred_bool is not None:
            sample[pred_field] = fo.Classification(
                label="accessible" if bool(pred_bool) else "inaccessible"
            )
            pred_count += 1

        gt_label = _raw_to_accessibility_label(
            _sample_get(sample, gt_field, default=None), field_name=gt_field
        )
        if gt_label is not None:
            sample[gt_eval_field] = fo.Classification(label=gt_label)
            gt_count += 1

        sample.save()

    return pred_field, gt_eval_field, pred_count, gt_count


def run_accessibility_evaluation(dataset):
    """
    Evaluate predicted accessibility labels against detected ground truth.

    Returns:
        dict with metrics, or None if evaluation cannot be performed
    """
    gt_field, gt_meta = _detect_gt_field(dataset)
    if not gt_field:
        logger.info("No usable accessibility ground-truth field detected; skipping evaluation")
        return None

    logger.info(
        "Detected GT field '%s' (recognized=%s, ratio=%s)",
        gt_field,
        gt_meta["recognized"],
        gt_meta["ratio"],
    )

    pred_field, gt_eval_field, pred_count, gt_count = _prepare_eval_fields(dataset, gt_field)
    if pred_count == 0:
        logger.info("No predictions found in `overall_accessible`; skipping evaluation")
        return None
    if gt_count == 0:
        logger.info("No normalized GT labels were derived from '%s'; skipping evaluation", gt_field)
        return None

    from fiftyone import ViewField as F

    eval_view = dataset.match((F(pred_field) != None) & (F(gt_eval_field) != None))
    num_eval = len(eval_view)
    if num_eval == 0:
        logger.info("No overlapping predictions/ground-truth labels; skipping evaluation")
        return None

    logger.info("Running evaluation on %d samples...", num_eval)
    results = eval_view.evaluate_classifications(
        pred_field,
        gt_field=gt_eval_field,
        eval_key="accessibility_eval",
    )
    results.print_report(classes=["accessible", "inaccessible"])
    metrics = results.metrics(classes=["accessible", "inaccessible"], average="macro")

    return {
        "gt_field": gt_field,
        "num_eval_samples": num_eval,
        "accuracy": metrics.get("accuracy"),
        "precision": metrics.get("precision"),
        "recall": metrics.get("recall"),
        "fscore": metrics.get("fscore"),
    }


def main():
    args = parse_args()

    # =========================================================================
    # STEP 1: Load dataset
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 1: Loading dataset")
    logger.info("=" * 60)

    from ingest import load_rotterdam_dataset, load_from_images_dir, load_from_youtube

    if args.youtube:
        dataset_name = args.dataset_name or "youtube-accessibility-audit"
        dataset = load_from_youtube(
            youtube_url=args.youtube,
            dataset_name=dataset_name,
            strategy=args.strategy,
            max_frames=args.max_frames,
        )
    elif args.images:
        dataset_name = args.dataset_name or "local-accessibility-audit"
        dataset = load_from_images_dir(args.images, dataset_name=dataset_name)
    else:
        # Default: Rotterdam
        dataset_name = args.dataset_name or "rotterdam-accessibility"
        dataset = load_rotterdam_dataset(
            max_samples=args.max_samples,
            dataset_name=dataset_name,
        )

    logger.info(f"Dataset '{dataset.name}' loaded with {len(dataset)} samples")

    # =========================================================================
    # STEP 2: Run VLM accessibility audit
    # =========================================================================
    if not args.skip_audit:
        logger.info("=" * 60)
        logger.info("STEP 2: Running accessibility audit")
        logger.info("=" * 60)

        from audit_agent import audit_dataset

        audit_stats = audit_dataset(
            dataset,
            model_name=args.model,
            max_samples=args.max_samples,
            delay_between_calls=args.delay,
        )
        logger.info(f"Audit complete: {audit_stats}")
    else:
        logger.info("STEP 2: Skipped (--skip-audit)")

    # =========================================================================
    # STEP 3: Compute Brain embeddings
    # =========================================================================
    if not args.skip_brain:
        logger.info("=" * 60)
        logger.info("STEP 3: Computing Brain embeddings")
        logger.info("=" * 60)

        try:
            import fiftyone.brain as fob

            # Similarity index for search
            try:
                fob.compute_similarity(
                    dataset,
                    brain_key="accessibility_sim",
                    model="clip-vit-base32-torch",
                )
                logger.info("Similarity index computed")
            except Exception as e:
                logger.warning(f"Similarity computation failed (non-fatal): {e}")

            # 2D visualization: UMAP first, then fallback to PCA for tiny views
            try:
                fob.compute_visualization(
                    dataset,
                    brain_key="accessibility_viz",
                    model="clip-vit-base32-torch",
                )
                logger.info("2D visualization computed (UMAP)")
            except Exception as e:
                logger.warning(
                    "UMAP visualization failed (non-fatal): %s. Falling back to PCA...",
                    e,
                )
                try:
                    fob.compute_visualization(
                        dataset,
                        brain_key="accessibility_viz_pca",
                        model="clip-vit-base32-torch",
                        method="pca",
                    )
                    logger.info("2D visualization computed (PCA fallback)")
                except Exception as pca_e:
                    logger.warning(f"PCA visualization fallback failed (non-fatal): {pca_e}")

        except Exception as e:
            logger.warning(f"Brain computation failed (non-fatal): {e}")
            logger.info("You can still view results in the App without embeddings")
    else:
        logger.info("STEP 3: Skipped (--skip-brain)")

    # =========================================================================
    # STEP 4: Evaluate (when compatible ground truth exists)
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 4: Running evaluation (if GT is available)")
    logger.info("=" * 60)

    try:
        eval_stats = run_accessibility_evaluation(dataset)
        if eval_stats is None:
            logger.info("STEP 4: Skipped (no compatible GT/prediction labels found)")
        else:
            logger.info(
                "Evaluation complete on %d samples | "
                "accuracy=%.4f precision=%.4f recall=%.4f fscore=%.4f | gt_field=%s",
                eval_stats["num_eval_samples"],
                eval_stats["accuracy"],
                eval_stats["precision"],
                eval_stats["recall"],
                eval_stats["fscore"],
                eval_stats["gt_field"],
            )
            dataset.info["evaluation_stats"] = eval_stats
            dataset.save()
    except Exception as e:
        logger.warning(f"STEP 4 evaluation failed (non-fatal): {e}")

    # =========================================================================
    # STEP 5: Generate report
    # =========================================================================
    if not args.skip_audit:
        logger.info("=" * 60)
        logger.info("STEP 5: Generating accessibility report")
        logger.info("=" * 60)

        from scoring import compute_accessibility_report, print_report

        report = compute_accessibility_report(dataset)
        print_report(report)

        # Store report in dataset info
        dataset.info["accessibility_report"] = report
        dataset.save()
    else:
        logger.info("STEP 5: Skipped (no audit data)")

    # =========================================================================
    # STEP 6: Launch FiftyOne App
    # =========================================================================
    logger.info("=" * 60)
    logger.info("STEP 6: Launching FiftyOne App")
    logger.info("=" * 60)

    session = fo.launch_app(dataset)

    logger.info("FiftyOne App is running!")
    logger.info("Tips:")
    logger.info("  - Filter by tags: 'critical', 'major', 'minor', 'accessible', 'inaccessible'")
    logger.info("  - Sort by 'accessibility_score' to find worst locations")
    logger.info("  - Open Embeddings panel to see issue clusters")
    logger.info("  - Press Ctrl+C to stop")

    session.wait()


if __name__ == "__main__":
    main()
