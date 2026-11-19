"""Build a frame-accurate edit plan from a five-beat brief and measured narration."""

import json
import math
import sys
import wave
from pathlib import Path

from .media import run

FPS = 24
SAMPLE_RATE = 48_000
LEAD_SECONDS = 0.125
END_SECONDS = 0.25
KINDS = ("hook", "analyze", "plan", "render", "verify")
DEFAULT_BEATS = (
    ("가로 영상 한 편,\n쇼츠로 바꿔볼까요?", "가로 영상 한 편, 쇼츠로 바꿔 볼까요?"),
    ("해상도와 길이,\n움직임을 먼저 확인합니다.", "해상도와 길이, 움직임을 먼저 확인합니다."),
    ("움직임이 큰 구간을 골라,\n세로 구도를 잡아요.", "움직임이 큰 구간을 골라, 세로 구도를 잡아요."),
    ("자막과 목소리를 맞춰,\n세로 영상으로 내보냅니다.", "자막과 목소리를 맞춰, 세로 영상으로 내보냅니다."),
    ("화면과 소리를 검사하면,\n쇼츠 한 편이 완성됩니다.", "화면과 소리를 검사하면, 쇼츠 한 편이 완성됩니다."),
)


def load_brief(path):
    if not path:
        return [dict(caption=caption, narration=narration) for caption, narration in DEFAULT_BEATS]
    beats = json.loads(path.read_text(encoding="utf-8"))["beats"]
    if len(beats) != len(KINDS):
        raise ValueError(f"Brief must contain {len(KINDS)} beats.")
    for beat in beats:
        if not beat.get("caption", "").strip() or not beat.get("narration", "").strip():
            raise ValueError("Each beat needs a caption and narration.")
        lines = beat["caption"].splitlines()
        if len(lines) > 2 or any(len(line) > 25 for line in lines):
            raise ValueError("Give each caption at most two lines of 25 characters.")
        if beat.get("audio"):
            beat["audio"] = (path.parent / beat["audio"]).resolve(strict=True)
    return beats


def timecode(frames):
    millis = round(frames * 1000 / FPS)
    seconds, millis = divmod(millis, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def create_plan(brief, analysis, ffmpeg, voice, work_dir, output_dir):
    scenes, audio, captions = [], [], []
    position = 0
    for index, (kind, beat) in enumerate(zip(KINDS, brief), start=1):
        pcm = work_dir / f"voice-{index:02}.wav"
        source = beat.get("audio")
        if source is None:
            if sys.platform != "darwin":
                raise RuntimeError("Provide a local audio file per beat or use macOS text-to-speech.")
            source = work_dir / f"voice-{index:02}.aiff"
            text = work_dir / f"voice-{index:02}.txt"
            text.write_text(beat["narration"], encoding="utf-8")
            run(["say", "-v", voice, "-r", "170", "-f", str(text), "-o", str(source)])
            if source.stat().st_size <= 4096:
                raise RuntimeError("The local voice produced no narration. Check macOS speech access or pass beat audio.")
        run([ffmpeg, "-v", "error", "-y", "-i", str(source), "-ac", "1", "-ar", str(SAMPLE_RATE),
             "-c:a", "pcm_s16le", str(pcm)])
        with wave.open(str(pcm), "rb") as speech:
            samples = speech.getnframes()
            if samples == 0:
                raise ValueError("Narration is empty.")
            signal = speech.readframes(samples)
        lead = int(LEAD_SECONDS * SAMPLE_RATE)
        duration_frames = math.ceil((samples / SAMPLE_RATE + LEAD_SECONDS + END_SECONDS) * FPS)
        total_samples = duration_frames * SAMPLE_RATE // FPS
        audio.append(bytes(lead * 2) + signal + bytes((total_samples - lead - samples) * 2))
        scenes.append({
            "kind": kind, "start_frame": position, "duration_frames": duration_frames,
            "caption": beat["caption"], "narration": beat["narration"],
            "transition": "cut",
        })
        captions.append(f"{index}\n{timecode(position)} --> {timecode(position+duration_frames)}\n{beat['caption']}\n")
        position += duration_frames

    if position > FPS * 60:
        raise ValueError("Keep demo narration below one minute.")
    track = work_dir / "voice.wav"
    with wave.open(str(track), "wb") as voice_file:
        voice_file.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
        voice_file.writeframes(b"".join(audio))
    (output_dir / "captions.srt").write_text("\n".join(captions), encoding="utf-8")
    return {
        "output": {"width": 1080, "height": 1920, "fps": FPS, "video": "short.mp4",
                   "thumbnail": "thumbnail.jpg", "captions": "captions.srt"},
        "source": analysis,
        "timeline": scenes,
    }, track
