#!/usr/bin/env python3
"""게시 폴더의 카드 이미지로 9:16 릴스 영상(reel.mp4)을 만든다. ffmpeg 필요.
Usage: python3 make_reel.py posts/YYYY-MM-DD
구성: story.jpg(있으면) → 카드 1~N장(세로 화면 가운데 배치), 장면 전환은 짧은 페이드. 무음 오디오 트랙 포함.
"""
import json, os, subprocess, sys

d = sys.argv[1]
man = json.load(open(f"{d}/manifest.json", encoding="utf-8"))
imgs = ([man["story"]] if man.get("story") and os.path.exists(f"{d}/{man['story']}") else []) + man["images"]
FIRST, EACH, FADE, BG = 2.5, 3.2, 0.4, "0x0b1220"

args = ["ffmpeg", "-y", "-loglevel", "error"]
durs = []
for k, im in enumerate(imgs):
    t = (FIRST if k == 0 else EACH) + FADE
    durs.append(t)
    args += ["-loop", "1", "-framerate", "30", "-t", f"{t:.2f}", "-i", f"{d}/{im}"]
total = sum(durs) - FADE * (len(imgs) - 1)
args += ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]

f = []
for k in range(len(imgs)):
    f.append(f"[{k}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
             f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color={BG},setsar=1,format=yuv420p,fps=30[v{k}]")
prev, off = "v0", 0.0
for k in range(1, len(imgs)):
    off += durs[k - 1] - FADE
    f.append(f"[{prev}][v{k}]xfade=transition=fade:duration={FADE}:offset={off:.2f}[x{k}]")
    prev = f"x{k}"
args += ["-filter_complex", ";".join(f), "-map", f"[{prev}]", "-map", f"{len(imgs)}:a",
         "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", f"{d}/reel.mp4"]
subprocess.run(args, check=True)
print(f"reel.mp4 생성: {len(imgs)}장, {total:.1f}초, {os.path.getsize(f'{d}/reel.mp4') // 1024}KB")
