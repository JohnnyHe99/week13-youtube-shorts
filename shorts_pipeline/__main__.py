"""Coordinate analysis, planning, rendering and independent output checks."""

import argparse
import json
import sys
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory

from .analysis_agent import analyze
from .media import encode, find_tool, make_original, run
from .plan_agent import create_plan, load_brief
from .qa_agent import verify_outputs
from .visual_agent import make_frames, make_thumbnail


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_crop_preview(source, measured, ffmpeg, directory):
    width, height = measured["width"], measured["height"]
    span = measured["selection"]
    cw = max(2, 2 * round(height * 9 / 32))
    left = 2 * round((span["focus_x"] * width - cw / 2) / 2)
    left = min(max(0, left), width - cw)
    run([ffmpeg, "-v", "error", "-y", "-ss", str(span["in"]), "-i", str(source),
         "-map", f"0:{measured['track']}", "-t", str(span["out"] - span["in"]), "-an",
         "-vf", f"crop={cw}:{height}:{left}:0,scale=288:512,fps=24",
         "-c:v", "mjpeg", "-q:v", "4", str(directory / "focus-%05d.jpg")])
    return [str(path) for path in sorted(directory.glob("focus-*.jpg"))]


def render(edit, source, ffmpeg, work, bundle, audio):
    output = edit["output"]
    width, height, fps = output["width"], output["height"], output["fps"]
    source_info = edit["source"]
    measured = {
        "source_preview": str(work / "source-preview.png"),
        "source_width": source_info["width"], "source_height": source_info["height"],
        "source_fps": source_info["fps"],
        "focus_x": source_info["selection"]["focus_x"],
    }
    focus_frames = make_crop_preview(source, source_info, ffmpeg, work)
    if not focus_frames:
        raise RuntimeError("Portrait extraction did not return any frames.")
    timeline = [
        {**scene, **measured, **({"source_frames": focus_frames} if scene["kind"] == "render" else {})}
        for scene in edit["timeline"]
    ]
    video = work / "short.mp4"
    thumbnail = bundle / output["thumbnail"]
    encode(ffmpeg, chain.from_iterable(make_frames(scene, width, height, fps) for scene in timeline),
           (width, height), fps, video, audio, bitrate="5M")
    make_thumbnail(width, height, source_preview=measured["source_preview"]).save(
        thumbnail, quality=92, optimize=True
    )
    video.replace(bundle / output["video"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source_mode = parser.add_mutually_exclusive_group(required=True)
    source_mode.add_argument("--demo", action="store_true", help="Generate an original horizontal test clip.")
    source_mode.add_argument("--source", type=Path, help="Analyze an existing local horizontal video.")
    parser.add_argument("--output", required=True, type=Path, help="A directory that does not exist yet.")
    parser.add_argument("--brief", type=Path, help="Optional JSON with five user-authored caption/narration beats.")
    parser.add_argument("--voice", default="Yuna", help="Installed macOS voice used for missing beat audio.")
    parser.add_argument("--ffmpeg", help="Path to FFmpeg.")
    parser.add_argument("--ffprobe", help="Path to ffprobe.")
    args = parser.parse_args()

    try:
        ffmpeg = find_tool("ffmpeg", args.ffmpeg)
        ffprobe = find_tool("ffprobe", args.ffprobe)
        brief = load_brief(args.brief)
        destination = args.output.resolve()
        if destination.exists():
            raise FileExistsError(f"Output already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)

        with TemporaryDirectory(prefix=".shorts-", dir=destination.parent) as tmp:
            work = Path(tmp)
            bundle = work / "deliverables"
            bundle.mkdir()
            if args.demo:
                source = work / "original.mp4"
                make_original(ffmpeg, source)
                source = source.replace(bundle / source.name)
            else:
                source = args.source.resolve(strict=True)

            measured = analyze(source, ffmpeg, ffprobe, work)
            print(f"[analysis] {measured['width']}×{measured['height']} · "
                  f"{measured['duration_seconds']:.2f}s · focus {measured['selection']['focus_x']:.2f}", flush=True)
            edit, audio = create_plan(brief, measured, ffmpeg, args.voice, work, bundle)
            save_json(bundle / "edit.json", edit)
            print(f"[planning] {len(edit['timeline'])} scenes", flush=True)
            render(edit, source, ffmpeg, work, bundle, audio)
            print("[rendering] MP4 + thumbnail", flush=True)

            qa = verify_outputs(bundle / "short.mp4", bundle / "thumbnail.jpg", edit, ffmpeg, ffprobe)
            if not qa["passed"]:
                raise RuntimeError("Verification failed: " + "; ".join(qa["errors"]))
            save_json(bundle / "qa.json", qa)
            print(f"[quality] PASS · {sum(qa['checks'].values())} checks", flush=True)
            bundle.rename(destination)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f"{error}\n")
    print(f"Saved to {destination}")


if __name__ == "__main__":
    sys.exit(main())
