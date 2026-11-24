import sys

from PotentialCalculationPipeline import run_potential_calculation


if __name__ == "__main__":
    selected_region = sys.argv[1] if len(sys.argv) > 1 else "München"
    run_potential_calculation(selected_region)
