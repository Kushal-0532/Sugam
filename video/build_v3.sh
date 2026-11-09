#!/bin/sh
# v3 = v2 + 4.5 s problem-line card after the title. Usage: sh build_v3.sh render|av|all
#   render: timeline -> layout check -> 8 parallel render.js workers -> fix_alpha
#   av:     phone track + audio mix + final composite -> ../demo/sugam_demo_v3.mp4
# ponytail: phone/voice tracks are v2's (work/phone.mp4, work/voice.wav) shifted by PITCH s, not rebuilt from takes.
set -e
cd "$(dirname "$0")"
PITCH=4.5
step=${1:-all}

if [ "$step" = render ] || [ "$step" = all ]; then
  python3 build_timeline.py
  node check_layout.js
  N=$(python3 -c "import re;print(int(float(re.search(r'\"dur\": ([\d.]+)',open('timeline.js').read())[1])*24))")
  C=$(( (N + 7) / 8 ))
  for i in 0 1 2 3 4 5 6 7; do
    a=$((i * C)); b=$((a + C - 1)); [ $b -ge $N ] && b=$((N - 1))
    node render.js $a $b 1 > work/rv3_$i.log 2>&1 &
  done
  wait
  sh fix_alpha.sh
fi

if [ "$step" = av ] || [ "$step" = all ]; then
  TOT=$(python3 -c "import re;print(re.search(r'\"dur\": ([\d.]+)',open('timeline.js').read())[1])")
  FR=$(python3 -c "print(round($PITCH*24) - 1)")  # loop=N gives N+1 copies of the still
  # phone: hold v2's first frame (frozen first YouTube frame) PITCH s longer
  ffmpeg -v error -y -i work/phone.mp4 -filter_complex \
    "[0]split[a][b];[a]trim=end_frame=1,loop=$FR:1:0,setpts=N/24/TB[h];[b]setpts=PTS-STARTPTS[r];[h][r]concat=n=2:v=1[v]" \
    -map "[v]" -r 24 -c:v libx264 -crf 16 -pix_fmt yuv420p work/phone_v3.mp4
  # voice: v2 voice track delayed PITCH s; music: same splice as v2 (108 s, repeat from 84.1 s), ducked under voice
  ffmpeg -v error -y -i music/geoffharvey-country-craft.mp3 -i work/voice.wav -filter_complex "
    [0]aresample=48000,aformat=channel_layouts=stereo,asplit[m1][m2];
    [m1]atrim=0:108,asetpts=N/SR/TB[x];[m2]atrim=start=84.1,asetpts=N/SR/TB[y];
    [x][y]acrossfade=d=2,atrim=0:$TOT,afade=t=out:st=$(python3 -c "print($TOT-4)"):d=4,volume=0.42[mv];
    [1]adelay=$(python3 -c "print(int($PITCH*1000))"),apad,atrim=0:$TOT,aformat=channel_layouts=stereo,asplit[v1][v2];
    [mv][v1]sidechaincompress=threshold=0.014:ratio=8:attack=30:release=800[duck];
    [duck][v2]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5,aresample=48000[out]" \
    -map "[out]" work/mix_v3.wav
  ffmpeg -v error -y -f lavfi -i "color=black:s=1080x1350:r=24:d=$TOT" -i work/phone_v3.mp4 -framerate 24 -i out/f%05d.png -i work/mix_v3.wav \
    -filter_complex "[0][1]overlay=30:230:eof_action=repeat[b];[b][2]overlay=0:0[v]" -map "[v]" -map 3 -t $TOT \
    -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart ../demo/sugam_demo_v3.mp4
  ffprobe -v error -show_entries format=duration,size -of compact ../demo/sugam_demo_v3.mp4
fi
