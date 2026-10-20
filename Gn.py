#!/usr/bin/env python3
"""
goodnight.py — an animated "goodnight" for the person you love.

    python goodnight.py "Emma"
    python goodnight.py                 # works without a name too

Pure standard library. No dependencies.
Runs on macOS, Linux, and Windows 10+ (Windows Terminal / modern conhost).
Press Ctrl+C to leave.
"""

from __future__ import annotations

import math
import os
import random
import shutil
import sys
import time

# ─────────────────────────────────────────────────────────────────────
#  Design tokens — tweak these and the whole scene adapts.
#  Everything below is expressed in 0–255 RGB so it stays readable.
# ─────────────────────────────────────────────────────────────────────

BACKGROUND    = (8, 10, 22)      # deep night blue
STAR_COOL     = (170, 190, 255)  # blue-white stars
STAR_WARM     = (255, 224, 196)  # golden stars
MOON_CORE     = (255, 250, 232)
MOON_EDGE     = (206, 200, 172)
MOON_GLOW     = (74, 96, 168)
TEXT_START    = (216, 222, 255)  # moonlight lavender
TEXT_END      = (255, 186, 212)  # soft rose
HEART_EDGE    = (150, 96, 180)
HEART_CORE    = (255, 122, 172)
SHOOTING_STAR = (255, 255, 245)

FPS            = 30
TEXT_CHARS_PER_SEC = 32
TEXT_START_TIME    = 1.7   # seconds before the first word appears
LINE_GAP           = 0.42  # pause between message lines


# ─────────────────────────────────────────────────────────────────────
#  Small math / colour helpers
# ─────────────────────────────────────────────────────────────────────

Color = tuple[int, int, int]


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def smoothstep(edge_a: float, edge_b: float, value: float) -> float:
    """Smooth 0→1 ramp between two edges (works in either direction)."""
    if edge_a == edge_b:
        return 0.0
    t = clamp01((value - edge_a) / (edge_b - edge_a))
    return t * t * (3.0 - 2.0 * t)


def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - clamp01(t)) ** 3


def mix_color(a: Color, b: Color, t: float) -> Color:
    t = clamp01(t)
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def scale_color(color: Color, factor: float) -> Color:
    return (
        max(0, min(255, round(color[0] * factor))),
        max(0, min(255, round(color[1] * factor))),
        max(0, min(255, round(color[2] * factor))),
    )


# ─────────────────────────────────────────────────────────────────────
#  Canvas — a grid of characters + colours that renders to one ANSI write
# ─────────────────────────────────────────────────────────────────────

class Canvas:
    def __init__(self, width: int, height: int, background: Color = BACKGROUND):
        self.width = width
        self.height = height
        self.background = background
        self.chars: list[list[str]] = [[" "] * width for _ in range(height)]
        self.colors: list[list[Color | None]] = [[None] * width for _ in range(height)]

    def clear(self) -> None:
        blank = [" "] * self.width
        empty = [None] * self.width
        for row in range(self.height):
            self.chars[row][:] = blank
            self.colors[row][:] = empty

    def plot(self, x: int, y: int, char: str, color: Color | None) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.chars[y][x] = char
            self.colors[y][x] = color

    def render(self) -> str:
        """Emit the frame with run-length-merged colour codes (no flicker)."""
        chunks = ["\x1b[H", f"\x1b[48;2;{self.background[0]};"
                            f"{self.background[1]};{self.background[2]}m"]
        for row in range(self.height):
            row_chars = self.chars[row]
            row_colors = self.colors[row]
            active: Color | None = "unset"  # type: ignore[assignment]
            for column in range(self.width):
                color = row_colors[column]
                if color != active:
                    chunks.append("\x1b[39m" if color is None
                                  else f"\x1b[38;2;{color[0]};{color[1]};{color[2]}m")
                    active = color
                chunks.append(row_chars[column])
            if row < self.height - 1:
                chunks.append("\x1b[39m\n")
        return "".join(chunks)


# ─────────────────────────────────────────────────────────────────────
#  Scene pieces
# ─────────────────────────────────────────────────────────────────────

class Star:
    """A single twinkling star."""

    __slots__ = ("x", "y", "base", "phase", "speed", "char", "tint")

    def __init__(self, width: int, height: int, rng: random.Random) -> None:
        self.x = rng.randrange(width)
        self.y = rng.randrange(max(1, int(height * 0.94)))
        self.base = rng.uniform(0.30, 0.90)
        self.phase = rng.uniform(0.0, math.tau)
        self.speed = rng.uniform(0.7, 2.0)
        self.char = rng.choices("·.+*", weights=[46, 30, 17, 7])[0]
        self.tint = rng.random()


class ShootingStar:
    """A short streak that crosses the sky every ~8 seconds."""

    __slots__ = ("start", "duration", "x0", "y0", "vx", "vy")

    def __init__(self, width: int, height: int, rng: random.Random, start_time: float) -> None:
        self.start = start_time
        self.duration = rng.uniform(0.6, 1.0)
        self.x0 = rng.uniform(0.05, 0.95) * width
        self.y0 = rng.uniform(0.03, 0.40) * height
        self.vx = rng.choice((-1, 1)) * rng.uniform(30.0, 55.0)
        self.vy = rng.uniform(6.0, 12.0)


class Scene:
    """All the layout maths, computed once from the terminal size."""

    def __init__(self, width: int, height: int, rng: random.Random, lines: list[str]) -> None:
        self.width = width
        self.height = height

        star_count = max(30, int(width * height * 0.035))
        self.stars = [Star(width, height, rng) for _ in range(star_count)]

        self.moon_x = width * 0.80
        self.moon_y = height * 0.20
        self.moon_radius = max(2.5, min(height * 0.13, 6.0))

        self.lines = lines
        self.text_center_x = width / 2.0
        self.text_top = int(height * 0.44)
        self.schedule = build_text_schedule(lines)

        self.heart_center_x = width / 2.0
        self.heart_center_y = height * 0.79
        self.heart_half_w = max(6.0, width * 0.115)
        self.heart_half_h = max(2.8, height * 0.115)
        self.heart_start = self.schedule[-1][1] + 0.9


def build_text_schedule(lines: list[str]) -> list[tuple[float, float]]:
    """When does each line start typing, and when does it finish?"""
    schedule: list[tuple[float, float]] = []
    cursor = TEXT_START_TIME
    for line in lines:
        typing_duration = max(0.28, len(line) / TEXT_CHARS_PER_SEC)
        schedule.append((cursor, cursor + typing_duration))
        cursor += typing_duration + LINE_GAP
    return schedule


# ─────────────────────────────────────────────────────────────────────
#  Drawing routines
# ─────────────────────────────────────────────────────────────────────

def draw_stars(canvas: Canvas, scene: Scene, time_now: float) -> None:
    fade_in = smoothstep(0.0, 1.2, time_now)
    if fade_in <= 0.0:
        return
    for star in scene.stars:
        twinkle = 0.55 + 0.45 * math.sin(time_now * star.speed + star.phase)
        brightness = star.base * twinkle * fade_in
        color = mix_color(STAR_COOL, STAR_WARM, star.tint)
        canvas.plot(star.x, star.y, star.char, scale_color(color, 0.28 + 0.72 * brightness))


def draw_moon(canvas: Canvas, center_x: float, center_y: float,
              radius: float, progress: float) -> None:
    """A crescent built from two overlapping discs, with a soft halo."""
    if progress <= 0.0:
        return

    halo_radius = radius * 2.0
    cut_offset_x = radius * 0.62    # in square visual units
    cut_offset_y = -radius * 0.52
    cut_radius = radius * 0.94

    left = int(center_x - halo_radius * 2 - 2)
    right = int(center_x + halo_radius * 2 + 2)
    top = int(center_y - halo_radius - 1)
    bottom = int(center_y + halo_radius + 1)

    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            # Terminal cells are ~2× taller than wide, so squash the x axis
            # into square "visual" units before doing any circle maths.
            dx = (x - center_x) * 0.5
            dy = y - center_y
            distance = math.hypot(dx, dy)

            body = smoothstep(radius + 0.7, radius - 0.7, distance)
            cut = smoothstep(cut_radius + 0.7, cut_radius - 0.7,
                             math.hypot(dx - cut_offset_x, dy - cut_offset_y))
            crescent = body * (1.0 - cut)
            halo = smoothstep(halo_radius, radius, distance) * 0.28 * (1.0 - crescent)

            light = max(crescent, halo)
            if light < 0.06:
                continue

            ramp = " ░▒▓█"
            char = ramp[min(len(ramp) - 1, int(light * len(ramp)))]
            base_color = (mix_color(MOON_EDGE, MOON_CORE, crescent)
                          if crescent >= halo else MOON_GLOW)
            canvas.plot(x, y, char, scale_color(base_color, light * progress))


def draw_shooting_stars(canvas: Canvas, streaks: list[ShootingStar], time_now: float) -> None:
    for streak in streaks:
        age = time_now - streak.start
        if age < 0.0 or age > streak.duration:
            continue
        fade = 1.0 - smoothstep(streak.duration * 0.55, streak.duration, age)
        for step in range(9):
            trail_age = age - step * 0.035
            if trail_age < 0.0:
                break
            x = round(streak.x0 + streak.vx * trail_age)
            y = round(streak.y0 + streak.vy * trail_age)
            brightness = (1.0 - step / 9.0) ** 2 * fade
            canvas.plot(x, y, "*" if step == 0 else "·",
                        scale_color(SHOOTING_STAR, 0.20 + 0.80 * brightness))


def draw_message(canvas: Canvas, scene: Scene, time_now: float) -> None:
    for index, line in enumerate(scene.lines):
        if not line:
            continue
        start, end = scene.schedule[index]
        if time_now < start:
            continue

        typing_progress = clamp01((time_now - start) / max(1e-6, end - start))
        visible = min(len(line), int(typing_progress * len(line) + 1e-6))

        start_x = round(scene.text_center_x - len(line) / 2)
        span = max(1, len(line) - 1)
        for char_index in range(visible):
            char = line[char_index]
            if char == " ":
                continue
            base = mix_color(TEXT_START, TEXT_END, char_index / span)
            # A slow shimmer rolls across the line so it never feels static.
            shimmer = 0.88 + 0.12 * math.sin(time_now * 1.8 - char_index * 0.22)
            canvas.plot(start_x + char_index, scene.text_top + index, char,
                        scale_color(base, shimmer))


def heart_vertices(samples: int = 14) -> list[tuple[float, float]]:
    """Points along the classic parametric heart curve."""
    points: list[tuple[float, float]] = []
    for i in range(samples):
        t = math.tau * i / samples
        x = 16.0 * math.sin(t) ** 3
        y = (13.0 * math.cos(t) - 5.0 * math.cos(2 * t)
             - 2.0 * math.cos(3 * t) - math.cos(4 * t))
        points.append((x, -y))  # flip: terminal y grows downward
    return points


def draw_heart(canvas: Canvas, scene: Scene, time_now: float) -> None:
    """A constellation that draws itself into a heart, then twinkles."""
    elapsed = time_now - scene.heart_start
    if elapsed <= 0.0:
        return
    progress = ease_out_cubic(elapsed / 2.2)
    if progress <= 0.0:
        return

    raw = heart_vertices()
    xs = [p[0] for p in raw]
    ys = [p[1] for p in raw]
    span_x = max(max(xs) - min(xs), 1e-6)
    span_y = max(max(ys) - min(ys), 1e-6)
    mid_x = (max(xs) + min(xs)) / 2.0
    mid_y = (max(ys) + min(ys)) / 2.0

    # One "visual" unit = 1 row tall, 2 columns wide.
    scale = min((2.0 * scene.heart_half_h) / span_y,
                scene.heart_half_w / span_x)

    points = [
        (scene.heart_center_x + (px - mid_x) * scale * 2.0,
         scene.heart_center_y + (py - mid_y) * scale)
        for px, py in raw
    ]

    # Walk the perimeter, drawing up to `progress` of the total length.
    segment_lengths = [
        math.dist(points[i], points[(i + 1) % len(points)])
        for i in range(len(points))
    ]
    total_length = sum(segment_lengths)
    target_length = total_length * progress

    walked = 0.0
    head: tuple[float, float] = points[0]
    for i, segment_length in enumerate(segment_lengths):
        if walked >= target_length:
            break
        a = points[i]
        b = points[(i + 1) % len(points)]
        portion = min(1.0, (target_length - walked) / max(segment_length, 1e-6))
        draw_segment(canvas, a, b, portion)
        walked += segment_length
        head = (a[0] + (b[0] - a[0]) * portion, a[1] + (b[1] - a[1]) * portion)

    # Star nodes, fading in as the line reaches them.
    walked = 0.0
    for i, point in enumerate(points):
        if walked <= target_length + 0.5:
            twinkle = 0.72 + 0.28 * math.sin(time_now * 2.2 + i * 1.1)
            canvas.plot(round(point[0]), round(point[1]), "*",
                        scale_color(HEART_CORE, twinkle))
        walked += segment_lengths[i]

    # A bright comet head at the drawing front while it's still drawing.
    if progress < 1.0:
        head_x, head_y = round(head[0]), round(head[1])
        canvas.plot(head_x, head_y, "*", HEART_CORE)
        for offset_x, offset_y in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            canvas.plot(head_x + offset_x, head_y + offset_y, "·",
                        scale_color(HEART_CORE, 0.45))


def draw_segment(canvas: Canvas, start: tuple[float, float],
                 end: tuple[float, float], portion: float) -> None:
    """Dotted line from `start` to `portion` of the way toward `end`."""
    x0, y0 = start
    x1 = x0 + (end[0] - x0) * portion
    y1 = y0 + (end[1] - y0) * portion
    steps = max(1, int(math.dist((x0, y0), (x1, y1)) * 2))
    for step in range(steps + 1):
        fraction = step / steps
        canvas.plot(round(x0 + (x1 - x0) * fraction),
                    round(y0 + (y1 - y0) * fraction),
                    "·", scale_color(HEART_EDGE, 0.78))


# ─────────────────────────────────────────────────────────────────────
#  Terminal plumbing
# ─────────────────────────────────────────────────────────────────────

class TerminalSession:
    """Alternate screen + hidden cursor, always restored on exit."""

    def __enter__(self) -> "TerminalSession":
        self._enable_vt_on_windows()
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")
        sys.stdout.flush()
        return self

    def __exit__(self, *exc_info: object) -> bool:
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()
        return False

    @staticmethod
    def _enable_vt_on_windows() -> None:
        if os.name != "nt":
            return
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)


# ─────────────────────────────────────────────────────────────────────
#  Main loop
# ─────────────────────────────────────────────────────────────────────

def build_message(name: str) -> list[str]:
    greeting = f"Goodnight, {name}." if name else "Goodnight, Babi Siliberimuch."
    return [
        greeting,
        "",
        "Sleep well Sweet Dreams —",
        "Pray always Ayaw na Papiraw turog na dayun",
        "I love You always and Forever Babi Mwawawaw.",
    ]


def main() -> None:
    name = " ".join(sys.argv[1:]).strip()[:24]
    lines = build_message(name)

    size = shutil.get_terminal_size(fallback=(80, 24))
    width = max(40, size.columns)
    height = max(18, size.lines)

    rng = random.Random()
    canvas = Canvas(width, height)
    scene = Scene(width, height, rng, lines)
    streaks: list[ShootingStar] = []

    with TerminalSession():
        started_at = time.perf_counter()
        while True:
            frame_started = time.perf_counter()
            time_now = frame_started - started_at

            # Shooting stars: retire the finished ones, occasionally spawn one.
            streaks[:] = [s for s in streaks if time_now - s.start < s.duration + 0.3]
            if not streaks and rng.random() < 0.004:
                streaks.append(ShootingStar(width, height, rng, time_now))

            canvas.clear()
            draw_stars(canvas, scene, time_now)
            draw_moon(canvas, scene.moon_x, scene.moon_y, scene.moon_radius,
                      smoothstep(0.4, 2.0, time_now))
            draw_shooting_stars(canvas, streaks, time_now)
            draw_message(canvas, scene, time_now)
            draw_heart(canvas, scene, time_now)

            sys.stdout.write(canvas.render())
            sys.stdout.flush()

            frame_time = time.perf_counter() - frame_started
            time.sleep(max(0.0, 1.0 / FPS - frame_time))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # The TerminalSession context manager already restored the screen.
        print("goodnight. ♥")