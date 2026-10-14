#!/usr/bin/env python3
"""Histogram of where in track B the transition starts, as a share of B's length.

Reads transitions.csv (b_start_time) and track durations from tracks.jsonl,
and writes a self-contained b_start.html.

Usage: python3 plot_b_start.py [--transitions transitions.csv]
                               [--data data/raveform] [--out b_start.html]
"""
import argparse
import csv
import json
import statistics
from pathlib import Path

from histogram import write_histogram

ROOT = Path(__file__).parent

BIN = 2  # percent of track length per bin


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--transitions", type=Path, default=ROOT / "transitions.csv")
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "raveform")
    ap.add_argument("--out", type=Path, default=ROOT / "b_start.html")
    args = ap.parse_args()

    with open(args.data / "tracks.jsonl") as f:
        durations = {t["id"]: t["duration"] for t in map(json.loads, f)}
    with open(args.transitions, newline="") as f:
        rows = list(csv.DictReader(f))

    seconds = [float(r["b_start_time"]) for r in rows]
    percents = [100 * s / durations[r["track_b_id"]] for s, r in zip(seconds, rows)]
    n = len(percents)

    counts = [0] * (100 // BIN)
    for p in percents:
        counts[min(int(p // BIN), len(counts) - 1)] += 1
    labels = [f"{i * BIN}–{i * BIN + BIN}% into track B" for i in range(len(counts))]

    median = statistics.median(percents)
    first_tenth = 100 * sum(p < 10 for p in percents) / n
    past_quarter = 100 * sum(p >= 25 for p in percents) / n
    write_histogram(
        args.out, counts, labels, [(p / BIN, f"{p}%") for p in range(0, 101, 10)],
        page_title="Track B start position",
        title=f"Where track B is when it enters the mix, across {n:,} house transitions",
        subtitle=f"Position of B's mix-in point as a share of B's full length. "
                 f"{first_tenth:.0f}% of transitions bring B in within its first tenth "
                 f"(median {statistics.median(seconds):.0f} s in); only {past_quarter:.0f}% "
                 f"start past the first quarter.",
        x_label=f"Position in track B at mix-in (% of track length, {BIN}-point bins)",
        column="Position",
        marker=(median / BIN, f"Median {median:.0f}%"))

    print(f"{n} transitions, median {median:.1f}% / {statistics.median(seconds):.1f} s into track B")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
