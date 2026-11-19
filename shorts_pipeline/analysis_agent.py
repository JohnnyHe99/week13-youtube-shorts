"""Measure input and select an energetic interval and a portrait framing."""

import json
from fractions import Fraction

from PIL import Image, ImageChops, ImageFilter, ImageStat

from .media import run


def analyze(source, ffmpeg, ffprobe, work_dir):
    probe = json.loads(run([
        ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)
    ]))
    stream = next((item for item in probe["streams"]
                   if item.get("codec_type") == "video" and not item.get("disposition", {}).get("attached_pic")), None)
    if stream is None:
        raise ValueError("The input has no video stream.")
    width, height = stream["width"], stream["height"]
    track = stream["index"]
    side_data = stream.get("side_data_list", [])
    orientation = next((item["rotation"] for item in side_data if "rotation" in item), 0)
    if abs(orientation) % 180 == 90:
        width, height = height, width
    seconds = float(stream.get("duration") or probe["format"]["duration"])
    average = stream.get("avg_frame_rate")
    fps = float(Fraction(average if average and average != "0/0" else stream["r_frame_rate"]))
    if width < height or seconds < 1 or fps <= 0:
        raise ValueError("Provide a horizontal video of at least one second with a valid frame rate.")

    # Compare adjacent samples using their mean absolute pixel difference.
    sample_count = min(9, max(4, int(seconds * 2)))
    times = [seconds * (0.05 + 0.88 * i / (sample_count - 1)) for i in range(sample_count)]
    samples = []
    sample_path = work_dir / "source-sample.png"
    for timestamp in times:
        sample_path.unlink(missing_ok=True)
        run([
            ffmpeg, "-v", "error", "-y", "-ss", f"{timestamp:.6f}", "-i", str(source),
            "-map", f"0:{track}", "-frames:v", "1", "-vf", "scale=432:-2",
            "-c:v", "png", "-update", "1", str(sample_path),
        ])
        with Image.open(sample_path) as image:
            samples.append(image.convert("RGB"))
    gray = [frame.convert("L") for frame in samples]
    differences = [ImageStat.Stat(ImageChops.difference(a, b)).mean[0]
                   for a, b in zip(gray, gray[1:])]
    pivot = max(range(len(differences)), key=differences.__getitem__) + 1
    # Inspect the neighboring samples so the column retains detail across the selected cut.
    neighbors = gray[max(0, pivot-1):min(len(gray), pivot+2)]
    details = [frame.filter(ImageFilter.FIND_EDGES) for frame in neighbors]
    sw, sh = gray[pivot].size
    crop_width = round(sh * 9 / 16)

    def detail_score(center):
        left = max(0, min(sw-crop_width, round(center*sw-crop_width/2)))
        area = (max(2, left), 2, min(sw-2, left+crop_width), sh-2)
        return sum(ImageStat.Stat(frame.crop(area)).mean[0] for frame in details) / len(details)

    centers = (0.50, 0.40, 0.60, 0.29, 0.71)
    focus = max(centers, key=detail_score)
    length = min(4.25, seconds)
    start = max(0, min(seconds - length, times[pivot] - length / 2))
    preview = work_dir / "source-preview.png"
    samples[pivot].save(preview)
    return {
        "source": source.name, "track": track, "width": width, "height": height, "fps": round(fps, 3),
        "duration_seconds": round(seconds, 6),
        "selection": {"in": round(start, 6), "out": round(start + length, 6), "focus_x": focus},
        "samples": [
            {"second": round(time, 3), "change_from_previous": round(delta, 3)}
            for time, delta in zip(times, [0] + differences)
        ],
    }
