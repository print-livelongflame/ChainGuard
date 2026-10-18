"""Optional report figure: python -m evaluation.plot path/to/results (requires matplotlib)."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = [json.loads(line) for line in (args.directory / "trials.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((args.directory / "manifest.json").read_text(encoding="utf-8"))
    strategies = ("zero_shot", "chain_of_thought", "few_shot")
    figure, axes = plt.subplots(1, 2, figsize=(10, 5))
    for axis, agent, label in zip(axes, ("scam_checker", "business_analyser"), ("Scam Checker", "Business Analyser")):
        trials = [[row for row in rows if row["agent"] == agent and row["strategy"] == strategy] for strategy in strategies]
        correct = [sum(row["valid"] and all(row["checks"].values()) for row in group) for group in trials]
        wrong = [sum(row["valid"] and not all(row["checks"].values()) for row in group) for group in trials]
        failed = [sum(not row["valid"] for row in group) for group in trials]
        axis.bar(range(3), correct, label="Pass", color="#29836e")
        axis.bar(range(3), wrong, bottom=correct, label="Wrong decision", color="#d69b32")
        axis.bar(range(3), failed, bottom=[a+b for a,b in zip(correct, wrong)], label="Invalid / failed", color="#c55b58")
        for index, count in enumerate(correct):
            axis.text(index, count / 2, f"{count}/{len(trials[index])}", ha="center", va="center", color="white", fontweight="bold")
        axis.set_xticks(range(3), ["Zero-shot", "Chain-of-thought", "Few-shot"], rotation=10)
        axis.set_title(label)
        axis.set_ylabel("Trials (case × repetition)")
        axis.set_ylim(0, max(map(len, trials), default=1) + 2)
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=8)
    figure.suptitle(f"Synthetic pilot benchmark · {manifest['model']} · temperature {manifest['temperature']}")
    figure.text(0.5, 0.02, "Objective checks only; repeated cases are not independent. FI explanation quality requires blind review.", ha="center", fontsize=9)
    figure.tight_layout(rect=(0, 0.08, 1, 0.94))
    figure.savefig(args.directory / "objective-results.png", dpi=180, bbox_inches="tight")
    figure.savefig(args.directory / "objective-results.svg", bbox_inches="tight")
    plt.close(figure)


if __name__ == "__main__":
    main()
