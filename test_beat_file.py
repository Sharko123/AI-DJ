import json, glob, os
import numpy as np, pandas as pd, mir_eval

BT_DIR  = "data/beats_bt"                       # Beat This! output
ANN_DIR = "data/raveform/structures"            # Raveform hand annotations

# map YouTube ID -> annotation key (e.g. "5WvMql1Ejzs" -> "0019.5WvMql1Ejzs")
segs = json.load(open(f"{ANN_DIR}/segments.json"))
segs = segs.values() if isinstance(segs, dict) else segs
key_of = {s["id"]: s["key"] for s in segs}
all_ids = {os.path.basename(p)[:-len(".beats")] for p in glob.glob(f"{BT_DIR}/*.beats")}
print(f"{len(all_ids)} beat files | {len(key_of)} annotated tracks | "
      f"{len(all_ids & key_of.keys())} overlap")
scores = []
for path in sorted(glob.glob(f"{BT_DIR}/*.beats")):
    tid = os.path.basename(path)[:-len(".beats")]
    if tid not in key_of:
        continue                                # not an annotated track

    bt = np.loadtxt(path, ndmin=2)
    ours, ours_db = bt[:, 0], bt[bt[:, 1] == 1, 0]             # Beat This! beats, downbeats

    ann = pd.read_csv(f"{ANN_DIR}/beats/{key_of[tid]}.beat.csv")
    ref, ref_db = ann["time"].values, ann.loc[ann["downbeat"] == 1, "time"].values

    # offset from all beats, then apply it to downbeats
    nearest = ours[np.abs(ours[:, None] - ref[None, :]).argmin(axis=0)]
    offset = np.median(nearest - ref)

    f_beat = mir_eval.beat.f_measure(ref + offset, ours)
    f_down = mir_eval.beat.f_measure(ref_db + offset, ours_db)  # ±70 ms

    scores.append(f_down)
    print(f"{tid}  offset={offset*1000:6.1f} ms  beat={f_beat:.2f}  downbeat={f_down:.2f}")

scores = np.array(scores)
print(f"\n{len(scores)} annotated tracks | mean downbeat F = {scores.mean():.3f} | "
      f">= 0.9: {(scores >= 0.9).mean():.0%}")