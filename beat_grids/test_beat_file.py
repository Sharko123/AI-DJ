import json, glob, os
import numpy as np, pandas as pd, mir_eval

ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # project root
BEATS_DIR = os.path.join(ROOT, "data/beats_serato")        # grids saved by serato_batch.py extract
ANN_DIR   = os.path.join(ROOT, "data/raveform/structures") # Raveform hand annotations

def serato_beats(path):
    """Read a saved Serato grid (time<TAB>beat position, 1 = downbeat) -> (beats, downbeats)."""
    grid = np.loadtxt(path, ndmin=2)
    beats, pos = grid[:, 0], grid[:, 1]
    return beats, beats[pos == 1]

# map YouTube ID -> annotation key (e.g. "5WvMql1Ejzs" -> "0019.5WvMql1Ejzs")
segs = json.load(open(f"{ANN_DIR}/segments.json"))
segs = segs.values() if isinstance(segs, dict) else segs
key_of = {s["id"]: s["key"] for s in segs}

# ---- pass 1: load everything and measure each track's own offset ----
tracks = []
for path in sorted(glob.glob(f"{BEATS_DIR}/*.beats")):
    tid = os.path.splitext(os.path.basename(path))[0]
    if tid not in key_of:
        continue
    ours, ours_db = serato_beats(path)
    ann = pd.read_csv(f"{ANN_DIR}/beats/{key_of[tid]}.beat.csv")
    ref, ref_db = ann["time"].values, ann.loc[ann["downbeat"] == 1, "time"].values
    nearest = ours[np.abs(ours[:, None] - ref[None, :]).argmin(axis=0)]
    own_offset = np.median(nearest - ref)
    tracks.append((tid, ours, ours_db, ref, ref_db, own_offset))

global_offset = np.median([t[5] for t in tracks])
print(f"global offset = {global_offset*1000:.1f} ms\n")

# ---- pass 2: score every track with the SAME offset ----
own_scores, global_scores = [], []
for tid, ours, ours_db, ref, ref_db, own_offset in tracks:
    f_down_own    = mir_eval.beat.f_measure(ref_db + own_offset, ours_db)
    f_beat_global = mir_eval.beat.f_measure(ref + global_offset, ours)
    f_down_global = mir_eval.beat.f_measure(ref_db + global_offset, ours_db)
    own_scores.append(f_down_own)
    global_scores.append(f_down_global)

    flag = "  <-- shifted grid" if f_down_own >= 0.9 and f_down_global < 0.9 else ""
    print(f"{tid}  own_offset={own_offset*1000:7.1f} ms  "
          f"downbeat own={f_down_own:.2f}  global={f_down_global:.2f}  beat global={f_beat_global:.2f}{flag}")

own_scores, global_scores = np.array(own_scores), np.array(global_scores)
print(f"\n{len(tracks)} tracks")
print(f"per-track offset: mean downbeat F {own_scores.mean():.3f} | >= 0.9: {(own_scores >= 0.9).mean():.0%}")
print(f"global offset:    mean downbeat F {global_scores.mean():.3f} | >= 0.9: {(global_scores >= 0.9).mean():.0%}")