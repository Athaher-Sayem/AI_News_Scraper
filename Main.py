import argparse

from pipeline import flow


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scrape, deduplicate, and process news.")
    parser.add_argument("--input", type=str, default=flow.UNIQUE_CSV_PATH)
    parser.add_argument("--output", type=str, default=flow.PROCESSED_CSV_PATH)
    parser.add_argument("--scrape", action="store_true", help="Collect all sources, then deduplicate before processing")
    parser.add_argument("--deduplicate", action="store_true", help="Deduplicate data/news_data.csv into --input before processing")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--limit", type=int, default=1, help="Number of articles to process (default: 1)")
    selection.add_argument("--all", action="store_true", help="Process every input article")
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be positive")

    try:
        results = flow.run_flow(
            input_csv=args.input,
            output_csv=args.output,
            limit=None if args.all else args.limit,
            scrape=args.scrape,
            deduplicate=args.deduplicate,
        )
    except (OSError, ValueError) as error:
        parser.exit(1, f"Pipeline failed: {error}\n")

    # Rejection is a valid editorial outcome; service failures are run failures.
    if results["status"].str.endswith("_FAILED").any():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
