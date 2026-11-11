# features.py — per-beat audio features for every track that has a Serato grid.
#
# For each beat (beat -> next beat) it stores:
#   bands  (n, 3)  low (<150 Hz) / mid (150-2000 Hz) / high (>2000 Hz) energy in dB
#   rms    (n, 1)  loudness in dB
#   chroma (n, 12) pitch-class profile
#   mfcc   (n, 13) timbre
#   onset  (n, 1)  onset strength
#   perc   (n, 1)  percussive share of energy (HPSS), 0-1
# plus `beats` (times) and `is_db` (True on downbeats), copied from the Serato grid.
#
# Needs: data/audio/<id>.*  and  data/beats_serato/<id>.beats      (ffmpeg on PATH)
# Writes: data/features/<id>.npz
#
#   pip install librosa numpy
#   python features.py              # skips finished tracks, safe to stop/restart
import glob, os, subprocess
import numpy as np, librosa
from concurrent.futures import ProcessPoolExecutor

SR, HOP, NFFT = 22050, 512, 2048
AUDIO, BEATS, OUT = "data/audio", "data/beats_serato", "data/features"
WORKERS = 8
os.makedirs(OUT, exist_ok=True)

def load(path):
    """Decode any format with ffmpeg -> mono float32 at SR (one decoder for every script)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)

def per_beat(M, frames):
    """Average each feature row over the frames between consecutive beats -> (n_beats, d)."""
    T = M.shape[1]
    return np.stack([M[:, a:b].mean(1) if b > a else M[:, min(a, T - 1)]
                     for a, b in zip(frames[:-1], frames[1:])]).astype(np.float32)

def process(path):
    tid = os.path.splitext(os.path.basename(path))[0]
    out, bp = f"{OUT}/{tid}.npz", f"{BEATS}/{tid}.beats"
    if os.path.exists(out) or not os.path.exists(bp):
        return None
    try:
        b = np.loadtxt(bp, ndmin=2)
        beats, is_db = b[:, 0], b[:, 1] == 1
        y = load(path)

        S = np.abs(librosa.stft(y, n_fft=NFFT, hop_length=HOP))
        P = S ** 2
        f = librosa.fft_frequencies(sr=SR, n_fft=NFFT)
        bands = librosa.power_to_db(np.stack([P[f < 150].sum(0),
                                              P[(f >= 150) & (f < 2000)].sum(0),
                                              P[f >= 2000].sum(0)]))
        mel = librosa.power_to_db(librosa.feature.melspectrogram(S=P, sr=SR))
        H, Pc = librosa.decompose.hpss(S)
        feats = dict(
            bands=bands,
            rms=librosa.amplitude_to_db(librosa.feature.rms(S=S, frame_length=NFFT)),
            chroma=librosa.feature.chroma_stft(S=P, sr=SR),
            mfcc=librosa.feature.mfcc(S=mel, n_mfcc=13),
            onset=librosa.onset.onset_strength(S=mel, sr=SR)[None],
            perc=((Pc ** 2).sum(0) / ((H ** 2).sum(0) + (Pc ** 2).sum(0) + 1e-9))[None],
        )

        edges = np.append(beats, beats[-1] + np.median(np.diff(beats)))
        frames = np.clip(librosa.time_to_frames(edges, sr=SR, hop_length=HOP), 0, S.shape[1])
        np.savez(out, beats=beats, is_db=is_db, **{k: per_beat(v, frames) for k, v in feats.items()})
        return None
    except Exception as e:                       # one bad file shouldn't stop the run
        return f"{tid}: {e}"

if __name__ == "__main__":
    paths = sorted(glob.glob(f"{AUDIO}/*"))
    failed = []
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        for i, err in enumerate(pool.map(process, paths), 1):
            if err:
                failed.append(err)
            if i % 200 == 0:
                print(f"{i}/{len(paths)}")
    print(f"done | {len(failed)} failed")
    for e in failed[:20]:
        print("  ", e)