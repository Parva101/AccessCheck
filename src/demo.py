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
    parser.add_argument("--model", type=str, default="gemini-2.5-flash",
                        help="Gemini model name (default: gemini-2.5-flash)")
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
            fob.compute_similarity(
                dataset,
                brain_key="accessibility_sim",
                model="clip-vit-base32-torch",
            )
            logger.info("Similarity index computed")

            # 2D visualization
            fob.compute_visualization(
                dataset,
                brain_key="accessibility_viz",
                model="clip-vit-base32-torch",
            )
            logger.info("2D visualization computed")

        except Exception as e:
            logger.warning(f"Brain computation failed (non-fatal): {e}")
            logger.info("You can still view results in the App without embeddings")
    else:
        logger.info("STEP 3: Skipped (--skip-brain)")

    # =========================================================================
    # STEP 4: Evaluate (Rotterdam dataset only)
    # =========================================================================
    # TODO: Implement evaluation against Rotterdam ground truth labels
    # The Rotterdam dataset has binary accessible/inaccessible labels.
    # Compare our overall_accessible predictions against their labels.
    #
    # Example:
    # results = dataset.evaluate_classifications(
    #     "predicted_accessible",
    #     gt_field="label",  # check actual field name in dataset
    #     eval_key="accessibility_eval"
    # )
    # results.print_report()
    logger.info("STEP 4: Evaluation — TODO (implement once field names are confirmed)")

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
