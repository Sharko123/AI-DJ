#!/usr/bin/env python3
"""Histogram of where in track B the transition starts, in bars into B.

Reads outputs/transitions.csv (b_start_beat, B's beat index at mix-in; 4 beats
to a bar) and writes a self-contained outputs/b_start.html.

Usage: python3 plots/plot_b_start.py [--transitions outputs/transitions.csv]
                                     [--out outputs/b_start.html]
"""
import argparse
import csv
import statistics
from pathlib import Path

from histogram import write_histogram

ROOT = Path(__file__).resolve().parent.parent

BEATS_PER_BAR = 4
CAP = 96  # bars; later starts are grouped in one overflow bin


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--transitions", type=Path, default=ROOT / "outputs" / "transitions.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "outputs" / "b_start.html")
    args = ap.parse_args()

    with open(args.transitions, newline="") as f:
        bars = [int(r["b_start_beat"]) / BEATS_PER_BAR for r in csv.DictReader(f)]
    n = len(bars)

    counts = [0] * (CAP + 1)
    for b in bars:
        counts[min(int(b), CAP)] += 1
    labels = [f"bar {i}–{i + 1} of track B" for i in range(CAP)]
    labels.append(f"{CAP}+ bars in (latest: {max(bars):g})")

    median = statistics.median(bars)
    first_bar = 100 * counts[0] / n
    write_histogram(
        args.out, counts, labels, [(b, b) for b in range(0, CAP, 8)],
        page_title="Track B start position",
        title=f"How many bars into track B the mix-in starts, across {n:,} house transitions",
        subtitle=f"B's beat at the mix-in point, divided by 4. {first_bar:.0f}% start in B's "
                 f"first bar; the other peaks sit on phrase boundaries around 8, 16, 24, 32, 48 and 64 bars. "
                 f"{counts[-1]} transitions starting {CAP} or more bars in are grouped in the last bar.",
        x_label="Bars into track B at mix-in (1-bar bins)",
        column="Position",
        marker=(median, f"Median {median:g} bars"), overflow=f"{CAP}+")

    print(f"{n} transitions, median {median:g} bars into track B, {counts[-1]} at {CAP}+ bars")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
