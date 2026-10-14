#!/bin/sh
# Live progress for download_audio.sh. Ctrl-C to quit (does not stop the download).
cd "$(dirname "$0")"

total=$(grep -c . data/urls.txt)
while :; do
  ok=$(grep -c . data/audio/done.txt 2>/dev/null)
  # Tracks whose latest attempt failed: errored in the log and not downloaded since.
  failed=$(grep '^ERROR: \[youtube\]' data/download.log 2>/dev/null |
    sed -E 's/^ERROR: \[youtube\] ([^:]+):.*/youtube \1/' | sort -u |
    grep -vxFf data/audio/done.txt | grep -c .)
  processed=$((ok + failed))
  pct=$(awk "BEGIN { printf \"%.2f\", 100 * $processed / $total }")
  if pgrep -f 'yt-dlp -a data/urls.txt' > /dev/null; then state=running; else state=stopped; fi
  printf '\r%s%%  %d/%d processed  (%d downloaded, %d failed)  [%s]   ' \
    "$pct" "$processed" "$total" "$ok" "$failed" "$state"
  sleep 5
done
