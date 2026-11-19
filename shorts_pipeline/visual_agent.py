"""Draw the Shorts explainer and its matching cover using original graphics."""

from functools import lru_cache
from math import cos, pi
from pathlib import Path
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps


CANVAS = (1080, 1920)
INK = "#f3f1e7"
MINT = "#93f4cf"
GOLD = "#f2cd81"
MUTED = "#a0b5b3"
PANEL = "#14262a"
STROKE = "#335156"
RULE = "#284145"
DARK = "#101b1f"
LEFT, RIGHT = 84, 926
FONT_PATHS = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
)
MONO_PATHS = (
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
)
STAGES = {
    "hook": ("YOUTUBE SHORTS", ("가로 영상을", "쇼츠로"), "LANDSCAPE TO PORTRAIT"),
    "analyze": ("01 / ANALYZE", ("먼저, 원본을", "분석합니다"), "SOURCE PROBE"),
    "plan": ("02 / PLAN", ("중심을 잡고", "세로로 구성"), "PORTRAIT REFRAME"),
    "render": ("03 / RENDER", ("자막과 음성을", "한 편으로"), "VIDEO COMPOSITION"),
    "verify": ("04 / VERIFY", ("마지막으로", "출력을 검사"), "QUALITY CHECK"),
}


@lru_cache(maxsize=48)
def font(size, bold=False, mono=False):
    if mono:
        for path in MONO_PATHS:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
    custom = os.environ.get("SHORTS_KOREAN_FONT")
    if custom:
        return ImageFont.truetype(custom, size)
    for path in FONT_PATHS:
        if Path(path).exists():
            index = 6 if bold and "AppleSDGothicNeo" in path else 0
            return ImageFont.truetype(path, size, index=index)
    raise RuntimeError("Install a Korean font or set SHORTS_KOREAN_FONT.")


def label(draw, xy, text, size=26, fill=MUTED):
    draw.text(xy, text, font=font(size, mono=True), fill=fill, anchor="lt")


def title(draw, xy, text, size, fill=INK):
    draw.text(xy, text, font=font(size, bold=True), fill=fill, anchor="lt")


@lru_cache(maxsize=1)
def background():
    image = Image.new("RGB", CANVAS, "#10191e")
    glow = Image.radial_gradient("L").point(lambda p: int((255 - p) * 0.60))
    glow = glow.resize((1060, 1250), Image.Resampling.BILINEAR)
    image.paste(Image.new("RGB", glow.size, "#233f3d"), (80, 60), glow)
    second = Image.radial_gradient("L").point(lambda p: int((255 - p) * 0.33))
    second = second.resize((820, 1000), Image.Resampling.BILINEAR)
    image.paste(Image.new("RGB", second.size, "#493b2a"), (-270, 800), second)
    draw = ImageDraw.Draw(image)
    for x in range(84, 1000, 48):
        for y in range(185, 1800, 48):
            draw.point((x, y), fill="#436064")
    draw.line((LEFT, 196, RIGHT, 196), fill=STROKE, width=2)
    return image


def fallback_source():
    red = Image.linear_gradient("L").rotate(90, expand=True).resize((960, 540))
    image = ImageOps.colorize(red, "#173448", "#446b59").convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.polygon(((0, 540), (323, 190), (590, 540)), fill="#365b61")
    draw.polygon(((428, 540), (793, 128), (960, 270), (960, 540)), fill="#224754")
    draw.ellipse((395, 110, 565, 280), fill="#f5ce84")
    draw.polygon(((0, 540), (435, 367), (647, 540)), fill="#152b37")
    draw.polygon(((480, 540), (636, 360), (960, 470), (960, 540)), fill="#152631")
    return image


@lru_cache(maxsize=4)
def source_image(path):
    if path:
        with Image.open(path) as image:
            return image.convert("RGB")
    return fallback_source()


def paste_card(image, photo, box, *, outlined=True, fit_center=0.5, corner=18):
    x, y, right, bottom = box
    size = (right - x, bottom - y)
    crop = ImageOps.fit(photo, size, Image.Resampling.LANCZOS, centering=(fit_center, 0.5))
    mask = Image.new("L", size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=corner, fill=255)
    image.paste(crop, (x, y), mask)
    if outlined:
        ImageDraw.Draw(image).rounded_rectangle(box, radius=corner, outline=STROKE, width=3)


def bounds(draw, box, color=MINT, length=26, width=4):
    x, y, right, bottom = box
    for xx, yy, sx, sy in ((x, y, 1, 1), (right, y, -1, 1), (x, bottom, 1, -1), (right, bottom, -1, -1)):
        draw.line((xx + sx * length, yy, xx, yy, xx, yy + sy * length), fill=color, width=width)


def intro_card(image, photo):
    draw = ImageDraw.Draw(image)
    landscape = (LEFT + 20, 648, 724, 996)
    portrait = (548, 555, 900, 1180)
    paste_card(image, photo, landscape)
    bounds(draw, (landscape[0] + 11, landscape[1] + 11, landscape[2] - 11, landscape[3] - 11), GOLD)
    label(draw, (landscape[0], 1019), "16:9", fill=GOLD)
    draw.rounded_rectangle((portrait[0] - 13, portrait[1] - 13, portrait[2] + 13, portrait[3] + 13),
                           fill=DARK, outline=STROKE, width=3, radius=34)
    paste_card(image, photo, portrait)
    bounds(draw, (portrait[0] + 12, portrait[1] + 12, portrait[2] - 12, portrait[3] - 12))
    label(draw, (portrait[0], 1215), "9:16", fill=MINT)
    draw.line((345, 1137, 468, 1137), fill=MINT, width=4)
    draw.line((452, 1121, 468, 1137, 452, 1153), fill=MINT, width=4)


def analyze_card(image, photo, scene):
    draw = ImageDraw.Draw(image)
    view = (LEFT, 581, RIGHT, 1055)
    paste_card(image, photo, view)
    bounds(draw, (LEFT + 18, 599, RIGHT - 18, 1037), MINT)
    values = (
        ("RESOLUTION", f"{scene.get('source_width', 1920)} × {scene.get('source_height', 1080)}"),
        ("FRAME RATE", f"{float(scene.get('source_fps', 24)):g} fps"),
    )
    for x, (name, value) in zip((LEFT, LEFT + 430), values):
        draw.rounded_rectangle((x, 1100, x + 406, 1245), radius=18, fill=PANEL, outline=STROKE, width=2)
        label(draw, (x + 23, 1122), name, 21)
        title(draw, (x + 23, 1167), value, 45, MINT)


def plan_card(image, photo, focus_x):
    draw = ImageDraw.Draw(image)
    scaled_photo = ImageOps.contain(photo, (RIGHT - LEFT, 474), Image.Resampling.LANCZOS)
    display_width, display_height = scaled_photo.size
    left = LEFT + (RIGHT - LEFT - display_width) // 2
    top = 663 + (474 - display_height) // 2
    view = (left, top, left + display_width, top + display_height)
    paste_card(image, Image.blend(photo, Image.new("RGB", photo.size, DARK), 0.67), view)
    window_width = round(display_height * 9 / 16)
    window_left = min(max(0, round(focus_x * display_width - window_width / 2)),
                      display_width - window_width)
    window = (left + window_left, top, left + window_left + window_width, top + display_height)
    extracted = scaled_photo.crop((window_left, 0, window_left + window_width, display_height))
    paste_card(image, extracted, window)
    bounds(draw, window, MINT, length=40)
    middle = (window[0] + window[2]) // 2
    for y in range(window[1] + 14, window[3] - 8, 27):
        draw.line((middle, y, middle, y + 9), fill="#b8f9df", width=2)
    radius = 24
    draw.ellipse((middle - radius, 799 - radius, middle + radius, 799 + radius), outline=GOLD, width=4)
    draw.line((middle - 12, 799, middle + 12, 799), fill=GOLD, width=3)
    draw.line((middle, 787, middle, 811), fill=GOLD, width=3)
    label(draw, (LEFT + 16, 1187), "HORIZONTAL SOURCE", fill=GOLD)
    label(draw, (577, 1187), "9:16 SAFE AREA", fill=MINT)


def render_phone(image, photo):
    draw = ImageDraw.Draw(image)
    phone = (332, 548, 680, 1168)
    paste_card(image, photo, phone)
    bounds(draw, (phone[0] + 11, phone[1] + 11, phone[2] - 11, phone[3] - 11))
    draw.rounded_rectangle((365, 1032, 647, 1094), fill="#102025", radius=10)
    title(draw, (385, 1050), "가로 영상을 쇼츠로", 32)


def render_card(image, photo):
    render_phone(image, photo)
    draw = ImageDraw.Draw(image)
    for left, top, right, name in (
        (LEFT, 1198, 312, "VIDEO"),
        (324, 1198, 560, "CAPTIONS"),
        (572, 1198, RIGHT, "VOICE"),
    ):
        draw.rounded_rectangle((left, top, right, top + 75), radius=12, fill=PANEL, outline=STROKE, width=2)
        label(draw, (left + 19, top + 19), name, 22, MINT)
        draw.line((left + 20, top + 55, right - 20, top + 55), fill=RULE, width=4)


def verify_card(image, width, height):
    draw = ImageDraw.Draw(image)
    rows = (
        ("비율과 해상도", f"9:16  /  {width} × {height}"),
        ("영상과 음성", "H.264  /  AAC"),
        ("프레임과 재생", "FRAME  /  DECODE"),
    )
    for index, (name, spec) in enumerate(rows):
        top = 597 + 198 * index
        draw.rounded_rectangle((LEFT, top, RIGHT, top + 170), radius=24, fill=PANEL, outline=STROKE, width=2)
        title(draw, (LEFT + 36, top + 39), name, 49)
        label(draw, (LEFT + 37, top + 104), spec, 24, MINT)
        draw.ellipse((806, top + 52, 875, top + 121), fill="#233d3b", outline=STROKE, width=2)


def caption_card(draw, caption):
    words = caption.split()
    if not words:
        return
    draw.rounded_rectangle((LEFT, 1374, RIGHT, 1539), radius=21, fill="#101e22", outline=STROKE, width=2)
    caption_lines = caption.strip().splitlines()
    if len(caption_lines) > 2:
        caption_lines = [" ".join(caption_lines)]
    for size in range(49, 17, -1):
        face = font(size, bold=True)
        lines = caption_lines
        if len(lines) == 1 and draw.textlength(lines[0], font=face) > 773 and len(words) > 1:
            split = min(range(1, len(words)), key=lambda i: abs(
                draw.textlength(" ".join(words[:i]), font=face) - draw.textlength(" ".join(words[i:]), font=face)))
            lines = [" ".join(words[:split]), " ".join(words[split:])]
        if all(draw.textlength(line, font=face) <= 773 for line in lines):
            break
    for index, line in enumerate(lines):
        y = 1453 + int((index - (len(lines) - 1) / 2) * (size + 12))
        draw.text(((LEFT + RIGHT) // 2, y), line, font=face, anchor="mm", fill=INK)


def base_frame(kind, scene, width, height, *, cover=False):
    image = background().copy()
    draw = ImageDraw.Draw(image)
    tag, lines, demo = STAGES[kind]
    label(draw, (LEFT, 139), "EDITING LAB  /  13", fill=MINT)
    label(draw, (596, 139), tag, fill=MUTED)
    for index, line in enumerate(lines):
        title(draw, (LEFT - 3, 239 + 128 * index), line, 125, INK if index == 0 else MINT)
    photo = source_image(scene.get("source_preview"))
    if kind == "hook":
        intro_card(image, photo)
    elif kind == "analyze":
        analyze_card(image, photo, scene)
    elif kind == "plan":
        plan_card(image, photo, scene.get("focus_x", 0.5))
    elif kind == "render":
        render_card(image, photo)
    elif kind == "verify":
        verify_card(image, width, height)
    endline = "SHORTS GENERATION PIPELINE" if cover else demo
    label(draw, (LEFT, 1318), endline, fill=GOLD if cover else MUTED)
    if not cover:
        caption_card(draw, str(scene.get("caption", "")))
    return image


def animate(draw, kind, progress):
    if kind == "analyze":
        y = int(611 + 407 * (0.5 - 0.5 * cos(progress * pi)))
        draw.line((LEFT + 20, y, RIGHT - 20, y), fill=MINT, width=3)
        draw.ellipse((LEFT + 19, y - 6, LEFT + 31, y + 6), fill=MINT)
    if kind == "plan":
        tick = int(28 * (0.5 + 0.5 * cos(2 * pi * progress)))
        draw.line((340, 781 - tick, 340, 811 + tick), fill=MINT, width=4)
        draw.line((670, 781 - tick, 670, 811 + tick), fill=MINT, width=4)
    if kind == "render":
        for a, b in ((104, 292), (344, 540), (592, 906)):
            draw.line((a, 1253, int(a + (b - a) * progress), 1253), fill=MINT, width=4)
    if kind == "verify":
        for index in range(3):
            if progress >= 0.1 + 0.19 * index:
                y = 684 + 198 * index
                draw.line((825, y, 837, y + 11, 855, y - 12), fill=MINT, width=5, joint="curve")
    if kind == "hook":
        pos = int(345 + 120 * progress)
        draw.ellipse((pos - 6, 1131, pos + 6, 1143), fill=GOLD)


def scaled(image, width, height):
    if image.size == (width, height):
        return image
    return image.resize((width, height), Image.Resampling.LANCZOS)


def make_frames(scene, width, height, fps):
    """Yield RGB frames for one scene; no frame list is held in memory."""
    del fps
    kind = scene["kind"]
    frames = scene["duration_frames"]
    base = base_frame(kind, scene, width, height)
    source_frames = scene.get("source_frames", ()) if kind == "render" else ()
    for index in range(frames):
        frame = base.copy()
        if source_frames:
            with Image.open(source_frames[index % len(source_frames)]) as photo:
                render_phone(frame, photo.convert("RGB"))
        progress = index / max(frames - 1, 1)
        animate(ImageDraw.Draw(frame), kind, progress)
        yield scaled(frame, width, height)


def make_thumbnail(width, height, *, source_preview=None):
    """Return an original, matching portrait cover."""
    scene = {"source_preview": source_preview}
    return scaled(base_frame("hook", scene, width, height, cover=True), width, height)
