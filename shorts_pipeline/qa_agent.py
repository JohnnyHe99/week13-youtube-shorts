"""Inspect rendered Shorts assets against the edit manifest."""

from __future__ import annotations

import json
import math
import re
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any


SILENCE_FLOOR_DB = -40
SILENCE_SCAN_SECONDS = 1.0
MAX_INTERIOR_SILENCE_SECONDS = 1.05
MAX_EDGE_SILENCE_SECONDS = 1.25
_SILENCE_START = re.compile(r"silence_start:\s*(-?[0-9.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?[0-9.]+)")


def _run(executable: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [executable, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        check=False,
    )


def _issue(result: subprocess.CompletedProcess[str]) -> str:
    return result.stderr.strip().splitlines()[-1] if result.stderr.strip() else (
        f"工具退出码 {result.returncode}"
    )


def _probe(ffprobe: str, path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"文件不存在或为空：{path.name}")
    result = _run(ffprobe, [
        "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path),
    ])
    if result.returncode:
        raise ValueError(f"{path.name} 无法读取：{_issue(result)}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} 的 ffprobe 输出不是有效的 JSON") from exc


def _number(text: Any) -> float | None:
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _fraction(text: Any) -> Fraction | None:
    try:
        return Fraction(str(text))
    except (ValueError, ZeroDivisionError):
        return None


def _stream(metadata: dict[str, Any], kind: str) -> dict[str, Any]:
    return next((s for s in metadata.get("streams", []) if s["codec_type"] == kind), {})


def _is_vertical(width: Any, height: Any) -> bool:
    return isinstance(width, int) and isinstance(height, int) and (
        width > 0 and height > 0 and width * 16 == height * 9
    )


def _decode(ffmpeg: str, path: Path, *, is_thumbnail: bool) -> subprocess.CompletedProcess[str]:
    streams = ["-map", "0:v:0", "-frames:v", "1"] if is_thumbnail else [
        "-map", "0:v:0", "-map", "0:a:0",
    ]
    return _run(ffmpeg, [
        "-hide_banner", "-nostdin", "-v", "error", "-xerror",
        "-i", str(path), *streams, "-f", "null", "-",
    ])


def _silence_measurements(ffmpeg: str, video: Path, duration: float) -> list[dict[str, Any]]:
    result = _run(ffmpeg, [
        "-hide_banner", "-nostdin", "-nostats", "-v", "info",
        "-i", str(video), "-map", "0:a:0",
        "-af", f"silencedetect=noise={SILENCE_FLOOR_DB}dB:d={SILENCE_SCAN_SECONDS}",
        "-f", "null", "-",
    ])
    if result.returncode:
        raise ValueError(f"静音分析失败：{_issue(result)}")

    intervals = []
    start = None
    for line in result.stderr.splitlines():
        start_match = _SILENCE_START.search(line)
        end_match = _SILENCE_END.search(line)
        if start_match:
            start = max(0.0, float(start_match[1]))
        if end_match and start is not None:
            intervals.append((start, float(end_match[1])))
            start = None
    if start is not None:
        intervals.append((start, duration))

    measurements = []
    for start, end in intervals:
        at_edge = start <= 0.06 or end >= duration - 0.06
        limit = MAX_EDGE_SILENCE_SECONDS if at_edge else MAX_INTERIOR_SILENCE_SECONDS
        measurements.append({
            "start_seconds": round(start, 4),
            "end_seconds": round(end, 4),
            "duration_seconds": round(end - start, 4),
            "at_edge": at_edge,
            "exceeds_limit": end - start > limit,
        })
    return measurements


def verify_outputs(
    video: Path,
    thumbnail: Path,
    edit: dict[str, Any],
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    """Return actual measured values and pass status for the MP4 and its cover."""
    output = edit["output"]
    expected_width = output["width"]
    expected_height = output["height"]
    expected_fps = _fraction(output["fps"])
    timeline = edit["timeline"]
    expected_frames = sum(scene["duration_frames"] for scene in timeline)
    if (not _is_vertical(expected_width, expected_height) or not expected_fps
            or expected_fps < 0 or expected_frames <= 0):
        raise ValueError("edit.json 必须给出 9:16 输出尺寸、正帧率及非空时间线")

    expected_duration = float(expected_frames / expected_fps)
    tolerance = float(2 / expected_fps) + 0.00001
    checks: dict[str, bool] = {}
    errors: list[str] = []
    warnings: list[str] = []
    report: dict[str, Any] = {
        "passed": False,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "expected": {
            "width": expected_width,
            "height": expected_height,
            "fps": float(expected_fps),
            "frames": expected_frames,
            "duration_seconds": round(expected_duration, 6),
            "duration_tolerance_seconds": round(tolerance, 6),
        },
    }

    def check(name: str, passed: bool, message: str) -> None:
        checks[name] = passed
        if not passed:
            errors.append(message)

    def test_decode(name: str, path: Path, *, is_thumbnail: bool) -> bool:
        try:
            result = _decode(ffmpeg, path, is_thumbnail=is_thumbnail)
        except OSError as exc:
            check(name, False, f"{path.name} 解码失败：{exc}")
            return False
        ok = result.returncode == 0
        check(name, ok, f"{path.name} 解码失败：{_issue(result)}")
        return ok

    try:
        video_probe = _probe(ffprobe, video)
    except (OSError, ValueError) as exc:
        check("video_probe", False, str(exc))
    else:
        check("video_probe", True, "")
        video_stream = _stream(video_probe, "video")
        audio_stream = _stream(video_probe, "audio")
        width, height = video_stream.get("width"), video_stream.get("height")
        fps = _fraction(video_stream.get("avg_frame_rate"))
        video_duration = _number(video_stream.get("duration"))
        container_duration = _number(video_probe.get("format", {}).get("duration"))
        audio_duration = _number(audio_stream.get("duration"))
        sample_ratio = video_stream.get("sample_aspect_ratio")
        measured_durations = (video_duration, container_duration)
        actual = {
            "path": video.name,
            "video_codec": video_stream.get("codec_name"),
            "audio_codec": audio_stream.get("codec_name"),
            "width": width,
            "height": height,
            "sample_aspect_ratio": sample_ratio,
            "fps": float(fps) if fps else None,
            "video_duration_seconds": video_duration,
            "container_duration_seconds": container_duration,
            "audio_duration_seconds": audio_duration,
        }
        report["video"] = actual
        check("video_codec_h264", actual["video_codec"] == "h264", "视频编码应为 H.264")
        check("audio_codec_aac", actual["audio_codec"] == "aac", "音频编码应为 AAC")
        check("video_9_16", _is_vertical(width, height) and sample_ratio in (None, "1:1", "N/A"),
              "视频画幅应为 9:16，且像素不可拉伸")
        check("video_resolution", (width, height) == (expected_width, expected_height),
              "视频分辨率偏离 edit.json")
        check("video_frame_rate", fps == expected_fps, "视频帧率偏离 edit.json")
        check("duration_within_two_frames", all(
            duration is not None and abs(duration - expected_duration) <= tolerance
            for duration in measured_durations
        ), "成片时长偏离时间线超过两帧或无法读取")

        decoded = test_decode("video_full_decode", video, is_thumbnail=False)

        if audio_stream and (audio_duration or container_duration) and decoded:
            try:
                intervals = _silence_measurements(ffmpeg, video, audio_duration or container_duration)
            except (OSError, ValueError) as exc:
                check("audio_silence", False, str(exc))
            else:
                report["audio_silence"] = {
                    "threshold_db": SILENCE_FLOOR_DB,
                    "detection_minimum_seconds": SILENCE_SCAN_SECONDS,
                    "max_interior_seconds": MAX_INTERIOR_SILENCE_SECONDS,
                    "max_edge_seconds": MAX_EDGE_SILENCE_SECONDS,
                    "intervals": intervals,
                }
                check("audio_silence", not any(gap["exceeds_limit"] for gap in intervals),
                      "成片有超过允许长度的静音区间")
                for gap in intervals:
                    if gap["at_edge"] and not gap["exceeds_limit"]:
                        warnings.append(
                            f"片头或片尾测得 {gap['duration_seconds']:.2f} 秒静音，在容许范围内"
                        )

    try:
        cover_probe = _probe(ffprobe, thumbnail)
    except (OSError, ValueError) as exc:
        check("thumbnail_probe", False, str(exc))
    else:
        check("thumbnail_probe", True, "")
        cover_stream = _stream(cover_probe, "video")
        width, height = cover_stream.get("width"), cover_stream.get("height")
        report["thumbnail"] = {
            "path": thumbnail.name,
            "width": width,
            "height": height,
            "codec": cover_stream.get("codec_name"),
        }
        check("thumbnail_9_16", _is_vertical(width, height), "封面画幅应为 9:16")
        test_decode("thumbnail_decode", thumbnail, is_thumbnail=True)

    report["passed"] = all(checks.values())
    return report
