#!/usr/bin/env python3
"""Extract A->B transition points from the RaveForm dataset.

For each pair of adjacent tracklist entries (A, B) that both have an alignment:
  - B starts at B's mixin_beat_track (time from B's beat file).
  - A's position at that moment is found by looking up B's mixin_beat_mix in
    A's warping path (wp is [track_beat, mix_beat] pairs), then converting that
    track beat to seconds with A's beat file.
  - Transition length is A's mixout_beat_mix minus B's mixin_beat_mix (beats).

Usage: python3 extract_transitions.py [--data data/raveform] [--out transitions.csv]
                                      [--min-match-rate 0.3] [--max-beatfile-err 0.05]
"""
import argparse
import csv
import json
from bisect import bisect_left
from collections import Counter
from pathlib import Path

GENRES = {"House", "Tech House", "Deep House", "Progressive House"}

FIELDS = [
    "mix_id", "mix_genres",
    "track_a_id", "track_b_id", "track_a_title", "track_b_title",
    "track_a_genre", "track_b_genre",
    "a_start_beat", "a_start_time", "b_start_beat", "b_start_time",
    "transition_beats", "transition_seconds",
    "a_match_rate", "b_match_rate",
    "wp_lookup", "a_beatfile_err", "b_beatfile_err",
]


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def beat_to_time(beats, beat):
    """Beat index (0-based, may be fractional) -> seconds, or None if out of range."""
    if beat < 0 or beat > len(beats) - 1:
        return None
    i = int(beat)
    if i == beat:
        return beats[i]
    return beats[i] + (beats[i + 1] - beats[i]) * (beat - i)


def track_beat_at(wp, mix_beat):
    """Look up a mix beat in a warping path -> (track_beat, 'exact'|'interp').

    Returns (None, reason) when the mix beat is outside the path. The path does
    not always contain every mix beat, so gaps are linearly interpolated.
    """
    path = sorted((m, t) for t, m in wp)
    mix = [m for m, _ in path]
    if mix_beat < mix[0]:
        return None, "b_starts_before_a"
    if mix_beat > mix[-1]:
        return None, "no_overlap"
    i = bisect_left(mix, mix_beat)
    if mix[i] == mix_beat:
        return path[i][1], "exact"
    (m0, t0), (m1, t1) = path[i - 1], path[i]
    return t0 + (t1 - t0) * (mix_beat - m0) / (m1 - m0), "interp"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=Path, default=Path(__file__).parent / "data" / "raveform")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "transitions.csv")
    ap.add_argument("--min-match-rate", type=float, default=0.3)
    ap.add_argument("--max-beatfile-err", type=float, default=0.05,
                    help="drop pairs whose beat file disagrees with the alignment's "
                         "own times by more than this many seconds")
    args = ap.parse_args()

    titles = {t["id"]: t["title"] for t in read_jsonl(args.data / "tracks.jsonl")}
    with open(args.data / "structures" / "segments.json") as f:
        track_genres = {s["id"]: s["genre"] for s in json.load(f)}

    beat_cache = {}

    def track_beats(track_id):
        if track_id not in beat_cache:
            path = args.data / "beats" / "tracks" / f"{track_id}.beat.json"
            beat_cache[track_id] = json.loads(path.read_text())["beats"] if path.exists() else None
        return beat_cache[track_id]

    def beatfile_err(row, beats):
        """Largest gap between the alignment's own times and the beat file's."""
        errs = []
        for which in ("mixin", "mixout"):
            t = beat_to_time(beats, row[f"{which}_beat_track"])
            if t is not None:
                errs.append(abs(t - row[f"{which}_time_track"]))
        return round(max(errs), 3) if errs else ""

    stats = Counter()
    rows = []
    for mix in read_jsonl(args.data / "mixes.jsonl"):
        stats["mixes"] += 1
        if not GENRES & set(mix["genres"]):
            continue
        stats["mixes_in_genre"] += 1
        align_path = args.data / "alignments" / f"{mix['id']}.align.jsonl"
        if not align_path.exists():
            stats["mixes_without_alignment"] += 1
            continue
        aligns = {a["track_id"]: a for a in read_jsonl(align_path)}

        tracklist = [t["id"] for t in mix["tracklist"]]
        for a_id, b_id in zip(tracklist, tracklist[1:]):
            if a_id not in aligns or b_id not in aligns or a_id == b_id:
                continue
            stats["pairs"] += 1
            a, b = aligns[a_id], aligns[b_id]
            if min(a["match_rate"], b["match_rate"]) < args.min_match_rate:
                stats["drop_low_match_rate"] += 1
                continue
            a_beats, b_beats = track_beats(a_id), track_beats(b_id)
            if a_beats is None or b_beats is None:
                stats["drop_missing_beat_file"] += 1
                continue

            a_beat, how = track_beat_at(a["wp"], b["mixin_beat_mix"])
            if a_beat is None:
                stats[f"drop_{how}"] += 1
                continue
            a_time = beat_to_time(a_beats, a_beat)
            b_time = beat_to_time(b_beats, b["mixin_beat_track"])
            a_out_time = beat_to_time(a_beats, a["mixout_beat_track"])
            if a_time is None or b_time is None:
                stats["drop_beat_out_of_range"] += 1
                continue

            a_err, b_err = beatfile_err(a, a_beats), beatfile_err(b, b_beats)
            if a_err == "" or b_err == "" or max(a_err, b_err) > args.max_beatfile_err:
                stats["drop_beatfile_mismatch"] += 1
                continue

            stats[f"kept_{how}"] += 1
            rows.append({
                "mix_id": mix["id"],
                "mix_genres": "|".join(mix["genres"]),
                "track_a_id": a_id,
                "track_b_id": b_id,
                "track_a_title": titles.get(a_id, ""),
                "track_b_title": titles.get(b_id, ""),
                "track_a_genre": track_genres.get(a_id, ""),
                "track_b_genre": track_genres.get(b_id, ""),
                "a_start_beat": round(a_beat, 2),
                "a_start_time": round(a_time, 3),
                "b_start_beat": b["mixin_beat_track"],
                "b_start_time": round(b_time, 3),
                "transition_beats": a["mixout_beat_mix"] - b["mixin_beat_mix"],
                "transition_seconds": "" if a_out_time is None else round(a_out_time - a_time, 3),
                "a_match_rate": round(a["match_rate"], 4),
                "b_match_rate": round(b["match_rate"], 4),
                "wp_lookup": how,
                "a_beatfile_err": a_err,
                "b_beatfile_err": b_err,
            })

    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    for key, n in stats.items():
        print(f"{key:28s} {n}")
    print(f"wrote {len(rows)} transitions to {args.out}")


if __name__ == "__main__":
    main()
