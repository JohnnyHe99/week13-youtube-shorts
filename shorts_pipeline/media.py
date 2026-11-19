"""Local media tools and a reproducible, original horizontal demo clip."""

import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

BUNDLE = Path("/Applications/VideoFusion-macOS.app/Contents/Resources")


def find_tool(name, override):
    tool = override or shutil.which(name)
    if tool is None and (BUNDLE / name).is_file():
        tool = str(BUNDLE / name)
    if tool is None:
        raise RuntimeError(f"Install FFmpeg or pass --{name}.")
    return tool


def run(command, **kwargs):
    result = subprocess.run(command, capture_output=True, **kwargs)
    if result.returncode:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"{Path(command[0]).name}: {error or 'command failed'}")
    return result.stdout


def encode(ffmpeg, frames, size, fps, output, narration=None, bitrate="4M"):
    available = run([ffmpeg, "-hide_banner", "-encoders"]).decode(errors="replace")
    if "libx264 " in available:
        encoder = ["-c:v", "libx264", "-preset", "fast", "-crf", "19"]
    elif "h264_videotoolbox " in available:
        encoder = ["-c:v", "h264_videotoolbox", "-allow_sw", "1", "-b:v", bitrate]
    else:
        raise RuntimeError("FFmpeg needs libx264 or h264_videotoolbox.")
    width, height = size
    args = [
        ffmpeg, "-hide_banner", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
        "-framerate", str(fps), "-i", "pipe:0",
    ]
    if narration:
        args += ["-i", str(narration), "-map", "0:v:0", "-map", "1:a:0",
                 "-c:a", "aac", "-b:a", "128k"]
    args += encoder + ["-vf", "format=yuv420p", "-movflags", "+faststart", str(output)]
    log_path = output.with_suffix(".encode.log")
    with log_path.open("wb") as log:
        with subprocess.Popen(args, stdin=subprocess.PIPE, stderr=log) as process:
            try:
                for frame in frames:
                    if frame.mode != "RGB" or frame.size != size:
                        raise ValueError("Rendered frame does not match RGB encoding profile.")
                    process.stdin.write(frame.tobytes())
            except BrokenPipeError:
                pass
            except BaseException:
                process.kill()
                raise
            finally:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass
            result = process.wait()
    if result:
        raise RuntimeError(log_path.read_text(encoding="utf-8", errors="replace").strip())


def source_frames(width, height, fps):
    gradient = Image.new("RGB", (1, height))
    gradient.putdata([(11 + y * 19 // height, 24 + y * 24 // height, 29 + y * 27 // height)
                      for y in range(height)])
    backdrop = gradient.resize((width, height))
    base = ImageDraw.Draw(backdrop)
    for index in range(1, 8):
        x = index * width / 8
        base.line((x, 0, x - width / 5, height), fill=(38, 59, 67), width=1)
    for index in range(1, 6):
        y = height * index / 6
        base.line((0, y, width, y), fill=(35, 52, 63), width=1)
    for number in range(fps * 7):
        phase = number / (fps * 7)
        x = width * (0.5 + 0.26 * math.sin((phase - 0.13) * math.tau))
        y = height * (0.50 + 0.12 * math.cos(phase * math.tau * 1.83))
        frame = backdrop.copy()
        draw = ImageDraw.Draw(frame)
        for radius in range(194, 36, -4):
            strength = ((194 - radius) / 158) ** 2.0
            color = (int(40 + 117 * strength), int(64 + 66 * strength), int(69 + 7 * strength))
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline=color, width=4)
        draw.ellipse((x-37, y-37, x+37, y+37), fill=(255, 209, 130))
        draw.ellipse((x-27, y-28, x+8, y+9), fill=(255, 235, 188))
        for index in range(4):
            radius = 87 + 22 * index
            angle = phase * math.tau * (1.1 + index * 0.12) + index * 1.6
            dx, dy = radius * math.cos(angle), radius * math.sin(angle)
            p = 3 + index
            draw.ellipse((x+dx-p, y+dy-p, x+dx+p, y+dy+p), fill=(133, 234, 216))
        yield frame


def make_original(ffmpeg, output):
    encode(ffmpeg, source_frames(1280, 720, 24), (1280, 720), 24, output)
