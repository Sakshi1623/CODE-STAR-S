"""DriftShield evaluation entry point.

Runs the reproducible evaluation comparing Baseline vs. DriftShield across 6 key scenarios.

Usage:
    python evaluate.py
    python evaluate.py --live
    python evaluate.py --output-json results/evaluation_results.json
"""

from eval.deterministic_eval import main

if __name__ == "__main__":
    main()
