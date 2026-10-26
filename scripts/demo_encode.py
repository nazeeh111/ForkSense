#!/usr/bin/env python3
"""Transcode a genuine browser report recording; preserve every input and output.

Run: python3 scripts/demo_encode.py CAPTURE_DIRECTORY FRESH_OUTPUT_DIRECTORY
Requires ffmpeg and ffprobe on PATH. Captions describe the recording, not an
inference about general agent performance. Produces a silent 24-second clip.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def run(argv: list[str], cwd: Path, log_name: str) -> subprocess.CompletedProcess:
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    (cwd / log_name).write_text(result.stdout + result.stderr)
    result.check_returncode()
    return result


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    capture, output = args.capture.resolve(), args.output.resolve()
    if output.exists():
        parser.error('Output must be an absent directory; previous renders are preserved.')
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe:
        parser.error('Installed FFmpeg and ffprobe are required; no download is performed.')
    raw = capture / 'frames.ffconcat'
    source = json.loads((capture / 'capture-manifest.json').read_text())
    output.mkdir(parents=True)
    (output / 'header.txt').write_text('Recorded report walkthrough of a live Codex run')
    duration_seconds = source['source']['recorded_run_duration_seconds']
    (output / 'footer.txt').write_text(f'Report interaction only | Run: {duration_seconds:.2f} s | 1 probe | 1 repair | 4 contract tests')
    font = Path('/System/Library/Fonts/Supplemental/Arial.ttf')
    font_arg = f'fontfile={font}:' if font.exists() else ''
    filters = (
        'pad=1440:1000:0:64:color=0xf6f5ef,'
        f'drawtext={font_arg}textfile=header.txt:fontcolor=0x242923:fontsize=24:x=40:y=21,'
        f'drawtext={font_arg}textfile=footer.txt:fontcolor=0x5e665c:fontsize=17:x=40:y=974,'
        'fps=25'
    )
    run([ffmpeg, '-n', '-safe', '0', '-i', str(raw), '-t', '24', '-vf', filters,
         '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p',
         '-movflags', '+faststart', '-an', 'demo.mp4'], output, 'encode.log')
    run([ffmpeg, '-n', '-i', 'demo.mp4', '-vf',
         'fps=10,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer',
         '-loop', '0', 'demo-preview.gif'], output, 'gif.log')
    probe = run([ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', 'demo.mp4'], output, 'ffprobe.json')
    metadata = json.loads(probe.stdout)
    run([ffmpeg, '-v', 'error', '-i', 'demo.mp4', '-f', 'null', '-'], output, 'full-decode.log')
    for t in (1, 5, 10, 14, 17, 21, 23):
        run([ffmpeg, '-n', '-ss', str(t), '-i', 'demo.mp4', '-frames:v', '1', f'frame-{t:02}.png'], output, f'frame-{t:02}.log')
    streams = metadata['streams']
    assert len(streams) == 1 and streams[0]['codec_type'] == 'video'
    assert streams[0]['width'] == 1440 and streams[0]['height'] == 1000
    assert abs(float(metadata['format']['duration']) - 24) < .05
    manifest = {'description':source['description'], 'capture': source,
                'source_frame_concat_sha256': sha(raw), 'clip_start_seconds':0,
                'clip_duration_seconds':24, 'dimensions':[1440,1000], 'audio':False,
                'video_sha256':sha(output/'demo.mp4'), 'gif_sha256':sha(output/'demo-preview.gif'),
                'verification':'ffprobe metadata assertions and full FFmpeg decode passed. Representative frames require visual review.'}
    (output / 'media-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'output':str(output),'duration':metadata['format']['duration'],'size_bytes':metadata['format']['size'],'sha256':manifest['video_sha256']}, indent=2))

if __name__ == '__main__':
    main()
