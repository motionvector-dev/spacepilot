#!/usr/bin/env bash
# Overnight BGM batch: brings up the local MiniMax server, generates the
# missing studio cues plus the full-length contemplative-ambient regen,
# then shuts the server down again. Safe to re-run; finished cues are skipped.
set -euo pipefail
cd "$(dirname "$0")/.."

/opt/homebrew/bin/mlx-serve serve --host 127.0.0.1 --port 11234 --skip-mem-preflight &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

until curl -s -m 2 http://127.0.0.1:11234/health | grep -q ok; do sleep 2; done

# caffeinate -i keeps the Mac from idle-sleeping mid-batch.
caffeinate -i python3 src/generate_music_templates.py
caffeinate -i python3 src/generate_music_templates.py --only contemplative-ambient --force

echo "overnight batch complete: $(ls outputs/music/*.wav | grep -cv raw) cues"
