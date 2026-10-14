#!/bin/sh
# Download every track in data/urls.txt as Opus into data/audio/.
# YouTube's Opus stream is kept as-is (no re-encode); decode to 44.1 kHz stereo
# at load time, e.g. ffmpeg -i x.opus -ar 44100 -ac 2 ...
# Resumable: finished tracks are recorded in data/audio/done.txt and skipped.
# Failed tracks are not recorded, so rerunning retries them. YouTube answers
# "Video unavailable" for videos that exist once it starts throttling, which is
# why the sleeps are long; pass further yt-dlp options to override them.
# Run build_track_manifest.py first (for urls.txt) and again afterwards
# (to refresh the manifest's `downloaded` column).
set -eu
cd "$(dirname "$0")"

# deno lets yt-dlp solve YouTube's JavaScript challenges (curl -fsSL https://deno.land/install.sh | sh).
DENO="${DENO:-$HOME/.deno/bin/deno}"

yt-dlp -a data/urls.txt \
  --js-runtimes "deno:$DENO" \
  -f "bestaudio[acodec=opus]/bestaudio" -x --audio-format opus \
  -o "data/audio/%(id)s.%(ext)s" \
  --download-archive data/audio/done.txt \
  -i --sleep-interval 5 --max-sleep-interval 15 --sleep-requests 1 \
  "$@"
