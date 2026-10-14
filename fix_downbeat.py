import json, glob, os
import numpy as np, pandas as pd, mir_eval

BT_DIR  = "data/beats_bt"
ANN_DIR = "data/raveform/structures"

segs = json.load(open(f"{ANN_DIR}/segments.json"))
segs = segs.values() if isinstance(segs, dict) else segs
key_of = {s["id"]: s["key"] for s in segs}



def local_phase_downbeats(beats, pos, window_bars=4, min_run_bars=4):
    idx = np.arange(len(beats))
    db_idx = idx[pos == 1]                        # beat indices Beat This! called downbeats
    if len(db_idx) == 0:
        return beats[0::4]
    phases = db_idx % 4

    # majority phase among nearby downbeats (±window_bars), for each Beat This! downbeat
    local = np.array([np.bincount(phases[max(0, k - window_bars): k + window_bars + 1],
                                  minlength=4).argmax() for k in range(len(phases))])

    # ignore short runs (< min_run_bars) as noise: keep the previous phase
    smoothed = local.copy()
    k = 0
    while k < len(local):
        j = k
        while j < len(local) and local[j] == local[k]:
            j += 1
        if j - k < min_run_bars and k > 0:
            smoothed[k:j] = smoothed[k - 1]
        k = j

    # each beat takes the phase of the nearest Beat This! downbeat; keep beats on that phase
    nearest = np.clip(np.searchsorted(db_idx, idx), 0, len(db_idx) - 1)
    return beats[(idx % 4) == smoothed[nearest]]

before, after, rows = [], [], []
for path in sorted(glob.glob(f"{BT_DIR}/*.beats")):
    tid = os.path.basename(path)[:-len(".beats")]
    if tid not in key_of:
        continue

    bt = np.loadtxt(path, ndmin=2)
    beats, pos = bt[:, 0], bt[:, 1]
    raw_db = beats[pos == 1]

    # vote: which of the 4 positions (beat index mod 4) do Beat This!'s downbeats fall on?
    idx = np.arange(len(beats))
    votes = np.bincount(idx[pos == 1] % 4, minlength=4)
    phase = votes.argmax()
    confidence = votes.max() / max(votes.sum(), 1)       # share of downbeats agreeing
    fixed_db = local_phase_downbeats(beats, pos)                       # every 4th beat from that phase

    ann = pd.read_csv(f"{ANN_DIR}/beats/{key_of[tid]}.beat.csv")
    ref, ref_db = ann["time"].values, ann.loc[ann["downbeat"] == 1, "time"].values
    offset = np.median(beats[np.abs(beats[:, None] - ref[None, :]).argmin(axis=0)] - ref)

    f_before = mir_eval.beat.f_measure(ref_db + offset, raw_db)
    f_after  = mir_eval.beat.f_measure(ref_db + offset, fixed_db)
    before.append(f_before); after.append(f_after)
    print(f"{tid}  conf={confidence:.2f}  downbeat before={f_before:.2f}  after={f_after:.2f}")

before, after = np.array(before), np.array(after)
print(f"\n{len(after)} tracks")
print(f"before: mean {before.mean():.3f} | >=0.9: {(before >= 0.9).mean():.0%}")
print(f"after:  mean {after.mean():.3f} | >=0.9: {(after >= 0.9).mean():.0%}")
