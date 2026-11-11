# structure.py — section boundaries + drop points per track, as DOWNBEAT indices.
#
# Annotated tracks (Raveform structures/) -> human sections; drops = starts of "drop" sections.
# Everything else -> spectral clustering on bar-level features (McFee & Ellis 2014, as in the
# Spotify paper) for sections, and a low-end energy-jump detector for drops.
#
# Needs: data/beats_serato/<id>.beats, data/features/<id>.npz (from features.py)
# Writes: data/structure/<id>.json  ->  {"sections": [...], "drops": [...], "source": "annotated"|"auto"}
#
#   python pipeline/structure.py      (works from any folder)
import glob, json, os
import numpy as np
import scipy.linalg, scipy.ndimage
from scipy.sparse.csgraph import laplacian
from sklearn.cluster import KMeans
import librosa
from concurrent.futures import ProcessPoolExecutor

ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # project root
FEAT_DIR = os.path.join(ROOT, "data/features")
OUT_DIR  = os.path.join(ROOT, "data/structure")
ANN_DIR  = os.path.join(ROOT, "data/raveform/structures")
OFFSET   = -0.0079          # our_time = raveform_time + OFFSET (measured earlier)
K_SEGMENTS = 6              # clusters for spectral clustering
DROP_JUMP_DB = 6.0          # low-end rise (dB) that counts as a drop
os.makedirs(OUT_DIR, exist_ok=True)

def load_annotations():
    p = f"{ANN_DIR}/segments.json"
    if not os.path.exists(p):
        return {}
    segs = json.load(open(p))
    segs = segs.values() if isinstance(segs, dict) else segs
    return {s["id"]: s["sections"] for s in segs}

def bar_features(F):
    """Average per-beat features over each bar (downbeat to next downbeat)."""
    db = np.where(F["is_db"])[0]
    edges = np.append(db, len(F["beats"]))
    def per_bar(M):
        return np.stack([M[a:b].mean(0) for a, b in zip(edges[:-1], edges[1:])])
    return db, per_bar

def nearest_downbeat(F, db, t):
    return int(np.abs(F["beats"][db] - t).argmin())

def spectral_sections(X, k=K_SEGMENTS):
    """Laplacian segmentation (McFee & Ellis 2014) on bar-level features X (n_bars, d).
    Returns boundary bar indices (always includes 0)."""
    n = len(X)
    if n < 2 * k:
        return [0]
    X = (X - X.mean(0)) / (X.std(0) + 1e-9)
    R = librosa.segment.recurrence_matrix(X.T, width=3, mode="affinity", sym=True)
    path_dist = np.sum(np.diff(X, axis=0) ** 2, axis=1)
    sigma = np.median(path_dist) + 1e-9
    path_sim = np.exp(-path_dist / sigma)
    R_path = np.diag(path_sim, 1) + np.diag(path_sim, -1)
    deg_path, deg_rec = R_path.sum(1), R.sum(1)
    mu = deg_path.dot(deg_path + deg_rec) / (np.sum((deg_path + deg_rec) ** 2) + 1e-9)
    A = mu * R + (1 - mu) * R_path
    L = laplacian(A, normed=True)
    _, evecs = scipy.linalg.eigh(L)
    evecs = scipy.ndimage.median_filter(evecs, size=(5, 1))
    norm = np.cumsum(evecs ** 2, axis=1) ** 0.5
    Xk = evecs[:, :k] / (norm[:, k - 1:k] + 1e-9)
    labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(Xk)
    return [0] + (1 + np.flatnonzero(labels[:-1] != labels[1:])).tolist()

def energy_drops(low_bar, min_gap=16):
    """Bars where low-end energy jumps up after a quieter stretch (breakdown -> drop)."""
    n = len(low_bar)
    jump = np.full(n, -np.inf)
    for b in range(8, n - 4):
        jump[b] = low_bar[b:b + 4].mean() - low_bar[b - 8:b].mean()
    drops = []
    for b in np.argsort(-jump):
        if jump[b] < DROP_JUMP_DB:
            break
        if all(abs(b - d) >= min_gap for d in drops):
            drops.append(int(b))
    return sorted(drops)

ANN = None
def process(path):
    global ANN
    if ANN is None:
        ANN = load_annotations()
    tid = os.path.splitext(os.path.basename(path))[0]
    out = f"{OUT_DIR}/{tid}.json"
    if os.path.exists(out):
        return
    F = dict(np.load(path))
    db, per_bar = bar_features(F)
    if len(db) < 16:
        return

    if tid in ANN:                                   # human annotations
        secs = ANN[tid]
        sections = sorted({nearest_downbeat(F, db, s["start"] + OFFSET) for s in secs})
        drops = sorted({nearest_downbeat(F, db, s["start"] + OFFSET)
                        for s in secs if s["name"].lower().startswith("drop")})
        source = "annotated"
    else:                                            # automatic
        X = np.hstack([per_bar(F["mfcc"]), per_bar(F["chroma"]), per_bar(F["bands"])])
        sections = spectral_sections(X)
        drops = energy_drops(per_bar(F["bands"])[:, 0])
        source = "auto"

    json.dump({"sections": [int(x) for x in sections], "drops": [int(x) for x in drops],
               "source": source, "n_bars": int(len(db))}, open(out, "w"))

if __name__ == "__main__":
    paths = sorted(glob.glob(f"{FEAT_DIR}/*.npz"))
    if not paths:
        raise SystemExit(f"no feature files in {FEAT_DIR} -- run features.py first")
    print(f"{len(paths)} feature files")
    with ProcessPoolExecutor(max_workers=8) as pool:
        for i, _ in enumerate(pool.map(process, paths), 1):
            if i % 500 == 0:
                print(f"{i}/{len(paths)}")
    print("done")