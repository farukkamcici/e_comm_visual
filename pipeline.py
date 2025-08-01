import argparse
import json
from pathlib import Path
from datetime import datetime
import logging

from src.data.clean_data import clean_data
from src.features.build_features import run_feature_building
from src.analysis.analyze_insights import (
    load_feature_data,
    generate_insights,
    load_summary,
)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_cleaning():
    project_root = Path(__file__).parents[0]
    cleaned_path = project_root / "data" / "cleaned" / "cleaned_data.csv"

    df_clean = clean_data()
    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(cleaned_path, index=False)
    logger.info(f"Cleaned events saved to: {cleaned_path}")


def run_features():
    logger.info("Running feature build...")
    run_feature_building()
    logger.info("Feature build complete.")


def save_summary(payload: dict, output_dir: Path, tag: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"summary_{tag}.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    logger.info(f"Summary saved to {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Pipeline: clean, build features, analyze, export summary.")
    parser.add_argument('--skip-clean', action='store_true')
    parser.add_argument('--skip-features', action='store_true')
    parser.add_argument('--baseline', '-b', help='Previous summary JSON for comparison', default=None)
    parser.add_argument('--tag', '-t', required=True, help='Run tag')
    parser.add_argument('--output', '-o', default='outputs', help='Output directory')
    parser.add_argument('--base-path', help='Override project base path', default=None)
    args = parser.parse_args()

    if not args.skip_clean:
        run_cleaning()
    if not args.skip_features:
        run_features()

    session_df, user_df, brand_df, category_df = load_feature_data(args.base_path)
    baseline = load_summary(args.baseline) if args.baseline else None

    summary = generate_insights(session_df, user_df, brand_df, category_df, baseline=baseline)
    payload = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'tag': args.tag,
        'summary': summary
    }

    save_summary(payload, Path(args.output), args.tag)


if __name__ == '__main__':
    main()
