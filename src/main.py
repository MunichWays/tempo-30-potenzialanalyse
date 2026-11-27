import argparse

from PotentialCalculationPipeline import run_potential_calculation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tempo-30-Potenzial und Unfallstatistik berechnen")
    parser.add_argument("region", nargs="?", default="München", help="Region aus data/regions")
    parser.add_argument(
        "--crash-years",
        type=int,
        default=3,
        help="Anzahl der neuesten Unfallatlas-Jahre (Standard: 3)",
    )
    parser.add_argument(
        "--no-crashes",
        action="store_true",
        help="Unfallstatistik nicht erzeugen",
    )
    args = parser.parse_args()

    run_potential_calculation(
        args.region,
        include_crashes=not args.no_crashes,
        crash_years=args.crash_years,
    )
