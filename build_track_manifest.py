#!/usr/bin/env python3
"""Build the track manifest for every track referenced in transitions.csv.

Writes:
  data/urls.txt            one YouTube URL per track, input for download_audio.sh
  data/track_manifest.csv  track_id, url, title, duration, audio_path, downloaded

Run it before downloading to produce urls.txt, and again afterwards to refresh
the `downloaded` column.

Usage: python3 build_track_manifest.py [--transitions transitions.csv]
                                       [--data data/raveform] [--out-dir data]
"""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).parent
FIELDS = ["track_id", "url", "title", "duration", "audio_path", "downloaded"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--transitions", type=Path, default=ROOT / "transitions.csv")
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "raveform")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "data")
    args = ap.parse_args()

    with open(args.transitions, newline="") as f:
        track_ids = sorted({row[k] for row in csv.DictReader(f)
                            for k in ("track_a_id", "track_b_id")})

    with open(args.data / "tracks.jsonl") as f:
        tracks = {t["id"]: t for t in map(json.loads, f)}

    audio_dir = args.out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # yt-dlp records a track here only once it is fully downloaded and converted,
    # so a half-written .opus doesn't count as downloaded.
    archive = audio_dir / "done.txt"
    finished = {line.split()[-1] for line in archive.read_text().splitlines() if line.strip()} \
        if archive.exists() else None

    rows = []
    for track_id in track_ids:
        meta = tracks.get(track_id, {})
        audio_path = audio_dir / f"{track_id}.opus"
        rows.append({
            "track_id": track_id,
            # Full URLs, not bare IDs: some IDs start with "-".
            "url": f"https://www.youtube.com/watch?v={track_id}",
            "title": meta.get("title", ""),
            "duration": meta.get("duration", ""),
            "audio_path": audio_path.relative_to(ROOT) if audio_path.is_relative_to(ROOT) else audio_path,
            "downloaded": audio_path.exists() and (finished is None or track_id in finished),
        })

    (args.out_dir / "urls.txt").write_text("".join(r["url"] + "\n" for r in rows))
    manifest = args.out_dir / "track_manifest.csv"
    with open(manifest, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    done = sum(r["downloaded"] for r in rows)
    hours = sum(float(r["duration"] or 0) for r in rows) / 3600
    print(f"{len(rows)} tracks ({hours:.0f} h of audio), {done} downloaded")
    print(f"wrote {manifest} and {args.out_dir / 'urls.txt'}")


if __name__ == "__main__":
    main()
