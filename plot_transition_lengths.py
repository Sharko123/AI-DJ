#!/usr/bin/env python3
"""Histogram of transition lengths (A's mixout_beat_mix - B's mixin_beat_mix).

Reads transitions.csv and writes a self-contained transition_lengths.html.

Usage: python3 plot_transition_lengths.py [--transitions transitions.csv]
                                          [--out transition_lengths.html]
"""
import argparse
import csv
import statistics
from pathlib import Path

from histogram import write_histogram

ROOT = Path(__file__).parent

BIN = 4          # beats per bin (one bar of 4/4)
CAP = 320        # everything at or above this goes in one overflow bin


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--transitions", type=Path, default=ROOT / "transitions.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "transition_lengths.html")
    args = ap.parse_args()

    with open(args.transitions, newline="") as f:
        lengths = [int(r["transition_beats"]) for r in csv.DictReader(f)]
    n = len(lengths)
    median = statistics.median(lengths)

    counts = [0] * (CAP // BIN + 1)
    for v in lengths:
        counts[min(v, CAP) // BIN] += 1
    labels = [f"{i * BIN}–{i * BIN + BIN - 1} beats" for i in range(CAP // BIN)]
    labels.append(f"{CAP}+ beats (longest: {max(lengths)})")

    write_histogram(
        args.out, counts, labels, [(b / BIN, b) for b in range(0, CAP, 32)],
        page_title="Transition lengths",
        title=f"Transition lengths across {n:,} house transitions",
        subtitle=f"Length is A's mix-out beat minus B's mix-in beat, on the mix timeline. "
                 f"Median {median:g} beats; {counts[-1]} transitions of {CAP} beats or more "
                 f"are grouped in the last bar.",
        x_label=f"Transition length (beats, {BIN}-beat bins)", column="Length",
        marker=(median / BIN, f"Median {median:g} beats"), overflow=f"{CAP}+")
    print(f"{n} transitions, median {median:g} beats, {counts[-1]} at {CAP}+ beats")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
