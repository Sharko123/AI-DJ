# serato_batch.py
# Usage (works from any folder):
#   python beat_grids/serato_batch.py extract            # save grids from analyzed FLACs
#   python beat_grids/serato_batch.py extract --delete   # ...and delete FLACs whose grid was saved
#   python beat_grids/serato_batch.py prepare 500        # convert the next 500 tracks to FLAC
from os import path
import argparse, base64, glob, json, os, struct, subprocess
import numpy as np
from mutagen.flac import FLAC
from concurrent.futures import ThreadPoolExecutor, as_completed


ROOT      = path.dirname(path.dirname(path.abspath(__file__)))   # project root
AUDIO_DIR = path.join(ROOT, "data/audio")                # original downloads (opus/m4a/webm)
WORK_DIR  = path.join(ROOT, "data/rekordbox_input")      # folder Serato analyzes
OUT_DIR   = path.join(ROOT, "data/beats_serato")         # extracted grids (.beats files)
ANN_DIR   = path.join(ROOT, "data/raveform/structures")
os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

def tid_of(path):
    return os.path.splitext(os.path.basename(path))[0]

def serato_beats(path):
    f = FLAC(path)
    raw = (f.tags or {}).get("SERATO_BEATGRID")
    if not raw:
        return None
    b64 = raw[0].replace("\n", "")
    data = base64.b64decode(b64 + "=" * (-len(b64) % 4))
    tag = b"Serato BeatGrid\x00"
    if tag in data:
        data = data[data.index(tag) + len(tag):]
    n = struct.unpack(">I", data[2:6])[0]
    markers, off = [], 6
    for k in range(n):
        pos = struct.unpack(">f", data[off:off + 4])[0]
        if k < n - 1:
            markers.append((pos, struct.unpack(">I", data[off + 4:off + 8])[0], None))
        else:
            markers.append((pos, None, struct.unpack(">f", data[off + 4:off + 8])[0]))
        off += 8
    beats = []
    for k, (pos, nbeats, bpm) in enumerate(markers):
        if nbeats is not None:
            beats += list(np.linspace(pos, markers[k + 1][0], nbeats, endpoint=False))
        else:
            beats += list(np.arange(pos, f.info.length, 60.0 / bpm))
    return np.array(beats)

def extract(delete):
    saved, missing = 0, []
    for path in sorted(glob.glob(f"{WORK_DIR}/*.flac")):
        tid = tid_of(path)
        beats = serato_beats(path)
        if beats is None or len(beats) < 16:
            missing.append(tid)                       # not analyzed yet -> keep the file
            continue
        pos = (np.arange(len(beats)) % 4) + 1         # 1 = downbeat
        np.savetxt(f"{OUT_DIR}/{tid}.beats", np.column_stack([beats, pos]),
                   fmt=["%.4f", "%d"], delimiter="\t")
        saved += 1
        if delete:
            os.remove(path)
    print(f"saved {saved} grids to {OUT_DIR}" + (" (and deleted their FLACs)" if delete else ""))
    if missing:
        print(f"{len(missing)} FLACs have no grid yet (kept): {missing[:10]}")

def prepare(n):
    done    = {tid_of(p) for p in glob.glob(f"{OUT_DIR}/*.beats")}
    pending = {tid_of(p) for p in glob.glob(f"{WORK_DIR}/*.flac")}
    segs = json.load(open(f"{ANN_DIR}/segments.json"))
    segs = segs.values() if isinstance(segs, dict) else segs
    annotated = {s["id"] for s in segs}

    todo = [p for p in sorted(glob.glob(f"{AUDIO_DIR}/*"))
            if tid_of(p) not in done and tid_of(p) not in pending]
    todo.sort(key=lambda p: tid_of(p) not in annotated)   # annotated tracks first
    todo = todo[:n]

    def convert(path):
        out = f"{WORK_DIR}/{tid_of(path)}.flac"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-ar", "44100",
                            "-compression_level", "0", out])          # fastest FLAC setting
        return tid_of(path), r.returncode

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
        futures = [pool.submit(convert, p) for p in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            tid, code = fut.result()
            if code != 0:
                print(f"  failed to convert {tid}")
            if i % 50 == 0:
                print(f"  converted {i}/{len(todo)}")
    
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract"); e.add_argument("--delete", action="store_true")
    p = sub.add_parser("prepare"); p.add_argument("n", type=int)
    a = ap.parse_args()
    extract(a.delete) if a.cmd == "extract" else prepare(a.n)