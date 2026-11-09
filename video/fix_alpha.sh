#!/bin/sh
# Chrome saves fully opaque frames (title, arch explainer, paper dips) as RGB PNG, the rest as RGBA.
# ffmpeg re-inits the composite filtergraph at every RGB<->RGBA switch and emits black / overlay-less
# frames there. Run after render.js, before the ffmpeg composite: rewrites every non-RGBA frame as RGBA.
cd "$(dirname "$0")/out" || exit 1
python3 -c "
import glob
print('\n'.join(f for f in sorted(glob.glob('f*.png')) if open(f, 'rb').read(26)[25] != 6))
" | xargs -r -P 16 -I{} sh -c 'ffmpeg -loglevel error -y -i {} -pix_fmt rgba tmp_{} && mv tmp_{} {}'
python3 -c "
import glob
bad = [f for f in glob.glob('f*.png') if open(f, 'rb').read(26)[25] != 6]
print('non-RGBA frames left:', len(bad))
"
