#!/usr/bin/env bash
# Record one demo take: phone screen (scrcpy) + laptop audio (your mic + what the speakers/earbuds play), merged to one mp4.
# Usage: scripts/record_demo.sh [take_name]   (Enter stops the recording). Output: demo/<take>.mp4 (gitignored).
# Run the agent in another terminal while this records. Plug in the wired earbuds BEFORE starting: the default sink is read once.
set -euo pipefail
cd "$(dirname "$0")/.."
take="${1:-take_$(date +%H%M%S)}"
mkdir -p demo && tmp="$(mktemp -d)"

sink="$(wpctl inspect @DEFAULT_SINK@ | sed -n 's/.*node.name = "\(.*\)"/\1/p' | head -1)"
src="$(wpctl inspect @DEFAULT_SOURCE@ | sed -n 's/.*node.name = "\(.*\)"/\1/p' | head -1)"
echo "speaker monitor: $sink"; echo "mic:             $src"
case "$src" in *bluez*|*bluetooth*) echo "WARNING: Bluetooth mic selected (drops audio quality); pick the laptop or wired mic first." ;; esac

scrcpy --no-audio --no-control --record "$tmp/video.mkv" </dev/null >/dev/null 2>&1 &   # --no-control: nothing on the mirror can tap the phone
sp=$!
ffmpeg -nostdin -loglevel error -f pulse -i "$sink.monitor" -f pulse -i "$src" \
  -filter_complex "amix=inputs=2:duration=longest:normalize=0" "$tmp/audio.wav" &
fp=$!
sleep 2; echo "● recording $take — speak, run the agent in another terminal. Enter to stop."
stop() { kill -INT "$fp" "$sp" 2>/dev/null || true; wait "$fp" "$sp" 2>/dev/null || true; }
trap 'stop; echo; echo "interrupted, merging what was recorded"' INT   # Ctrl+C stops both recorders, then falls through to the merge
read -r || true
stop; trap - INT

# ponytail: audio and video start ~0.2-1 s apart, not synced; trim with AUDIO_OFFSET=<seconds> (positive = delay audio) if a take drifts
ffmpeg -loglevel error -y -i "$tmp/video.mkv" -itsoffset "${AUDIO_OFFSET:-0}" -i "$tmp/audio.wav" \
  -map 0:v -map 1:a -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p -c:a aac -shortest "demo/$take.mp4"
rm -rf "$tmp"; echo "saved demo/$take.mp4"
