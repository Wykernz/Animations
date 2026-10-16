"""Render a small looping pixel-art rain game for a GitHub profile README.

The renderer uses only the Python standard library, so the source can live in
the same public repository as the generated GIF and be rerun without a build
toolchain or image packages.
"""

from __future__ import annotations

import argparse
import math
import struct
import zlib
from pathlib import Path
from typing import Iterable, TYPE_CHECKING

WIDTH = 800
HEIGHT = 420
FRAME_COUNT = 40
FRAME_DELAY_CENTISECONDS = 9
PIXELS_PER_DROP_STEP = 8
GIF_PALETTE_SIZE = 256

# One restrained night palette keeps the sky calm while the warm umbrella
# gives the eye a clear place to land.
PALETTE: tuple[tuple[int, int, int], ...] = (
    (8, 14, 27),       # 0  night
    (13, 22, 40),      # 1  sky
    (18, 30, 52),      # 2  panel
    (24, 39, 66),      # 3  deep blue
    (33, 51, 82),      # 4  mountain
    (43, 64, 99),      # 5  ridge
    (60, 84, 122),     # 6  distant light
    (89, 111, 151),    # 7  slate
    (132, 155, 190),   # 8  mist
    (207, 224, 248),   # 9  moonlight
    (241, 240, 255),   # 10 cloud highlight
    (196, 187, 255),   # 11 cloud
    (158, 146, 230),   # 12 lavender
    (111, 104, 190),   # 13 cloud shade
    (188, 248, 255),   # 14 rain glint
    (110, 226, 243),   # 15 rain
    (55, 178, 209),    # 16 rain shade
    (255, 218, 125),   # 17 umbrella light
    (245, 169, 91),    # 18 umbrella shade
    (255, 132, 141),   # 19 jacket
    (255, 198, 162),   # 20 skin
    (67, 48, 67),      # 21 hair
    (86, 178, 138),    # 22 grass
    (135, 214, 164),   # 23 grass light
    (54, 123, 119),    # 24 puddle
    (87, 177, 173),    # 25 puddle glint
    (255, 255, 255),   # 26 sparkle
    (137, 199, 255),   # 27 blue sparkle
    (78, 96, 130),     # 28 border
    (34, 48, 75),      # 29 panel edge
    (255, 161, 189),   # 30 blush
    (246, 193, 114),   # 31 star
)

COLOR = {
    "night": 0,
    "sky": 1,
    "panel": 2,
    "deep_blue": 3,
    "mountain": 4,
    "ridge": 5,
    "distant_light": 6,
    "slate": 7,
    "mist": 8,
    "moonlight": 9,
    "cloud_highlight": 10,
    "cloud": 11,
    "lavender": 12,
    "cloud_shade": 13,
    "rain_glint": 14,
    "rain": 15,
    "rain_shade": 16,
    "umbrella_light": 17,
    "umbrella_shade": 18,
    "jacket": 19,
    "skin": 20,
    "hair": 21,
    "grass": 22,
    "grass_light": 23,
    "puddle": 24,
    "puddle_glint": 25,
    "white": 26,
    "blue_sparkle": 27,
    "border": 28,
    "panel_edge": 29,
    "blush": 30,
    "star": 31,
}

# 5x7 Pixel Font subset for UI overlays
FONT: dict[str, list[str]] = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "11001", "01111"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "01110", "00001", "00001", "10001", "01110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    ":": ["00000", "00100", "00000", "00000", "00100", "00000", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "0": ["01110", "10011", "10101", "11001", "01110", "00000", "00000"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
}


class Canvas:
    """A compact indexed-color surface used by both image encoders."""

    def __init__(self, width: int, height: int, background: int) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray([background]) * (width * height)

    def rect(self, x: int, y: int, width: int, height: int, color: int) -> None:
        left = max(0, x)
        top = max(0, y)
        right = min(self.width, x + width)
        bottom = min(self.height, y + height)
        if left >= right or top >= bottom:
            return
        row = bytes([color]) * (right - left)
        for row_y in range(top, bottom):
            start = row_y * self.width + left
            self.pixels[start : start + len(row)] = row

    def pixel(self, x: int, y: int, color: int) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = color

    def text(self, x: int, y: int, value: str, color: int, scale: int = 1) -> None:
        cursor_x = x
        for character in value.upper():
            glyph = FONT.get(character)
            if glyph is not None:
                for row_index, row in enumerate(glyph):
                    for column_index, active in enumerate(row):
                        if active == "1":
                            self.rect(
                                cursor_x + column_index * scale,
                                y + row_index * scale,
                                scale,
                                scale,
                                color,
                            )
            cursor_x += 6 * scale


def draw_mountain(canvas: Canvas, left: int, top: int, width: int, height: int, color: int) -> None:
    """Build a stepped silhouette that matches the scene's pixel scale."""
    for row in range(height):
        half_width = (row * width) // (height * 2)
        canvas.rect(left + width // 2 - half_width, top + row, half_width * 2 + 1, 1, color)


def draw_star(canvas: Canvas, x: int, y: int, color: int, bright: bool) -> None:
    canvas.rect(x, y + 2, 5, 1, color)
    canvas.rect(x + 2, y, 1, 5, color)
    if bright:
        canvas.pixel(x + 2, y + 2, COLOR["white"])


def draw_background(canvas: Canvas, frame: int) -> None:
    canvas.rect(0, 0, WIDTH, HEIGHT, COLOR["night"])
    for y in range(0, HEIGHT, 2):
        canvas.rect(0, y, WIDTH, 1, COLOR["sky"])

    # Distant stars and moon
    draw_star(canvas, 120, 70, COLOR["star"], frame % 10 < 5)
    draw_star(canvas, 240, 45, COLOR["star"], frame % 12 >= 6)
    draw_star(canvas, 680, 60, COLOR["star"], frame % 15 < 8)
    canvas.rect(720, 50, 24, 24, COLOR["moonlight"])
    canvas.pixel(721, 51, COLOR["night"])


def draw_scene_frame(frame: int) -> Canvas:
    canvas = Canvas(WIDTH, HEIGHT, COLOR["night"])
    draw_background(canvas, frame)

    # Mountains & Scenery
    draw_mountain(canvas, 40, 180, 320, 120, COLOR["mountain"])
    draw_mountain(canvas, 300, 150, 400, 150, COLOR["ridge"])
    canvas.rect(0, 300, WIDTH, 120, COLOR["grass"])

    # Animated Rain
    for i in range(120):
        rx = (i * 73 + frame * 4) % WIDTH
        ry = (i * 37 + frame * PIXELS_PER_DROP_STEP) % HEIGHT
        canvas.pixel(rx, ry, COLOR["rain"])
        canvas.pixel(rx + 1, ry + 1, COLOR["rain_glint"])

    # Floating Cloud
    cloud_x = 350 + int(math.sin(frame * 2 * math.pi / FRAME_COUNT) * 9)
    cloud_y = 60 + int(math.cos(frame * 2 * math.pi / FRAME_COUNT) * 4)
    canvas.rect(cloud_x, cloud_y, 120, 35, COLOR["cloud"])
    canvas.rect(cloud_x + 10, cloud_y - 10, 80, 15, COLOR["cloud_highlight"])
    canvas.rect(cloud_x - 10, cloud_y + 10, 140, 25, COLOR["cloud_shade"])

    # UI / Footer details
    canvas.text(20, 20, "QUEST: RAINBOW VALLEY", COLOR["white"], scale=1)
    return canvas


def gif_lzw_encode(pixels: bytearray) -> bytes:
    clear_code = 1 << 8
    end_code = clear_code + 1
    next_code_limit = 500
    output = bytearray()
    bit_buffer = 0
    bit_count = 0

    def emit(code: int) -> None:
        nonlocal bit_buffer, bit_count
        bit_buffer |= code << bit_count
        bit_count += 9
        while bit_count >= 8:
            output.append(bit_buffer & 0xFF)
            bit_buffer >>= 8
            bit_count -= 8

    dictionary: dict[bytes, int] = {bytes([index]): index for index in range(256)}
    next_code = 258
    emit(clear_code)
    if not pixels:
        emit(end_code)
    else:
        prefix = bytes([pixels[0]])
        for pixel_value in pixels[1:]:
            candidate = prefix + bytes([pixel_value])
            if candidate in dictionary:
                prefix = candidate
                continue

            emit(dictionary[prefix])
            if next_code < next_code_limit:
                dictionary[candidate] = next_code
                next_code += 1
            else:
                emit(clear_code)
                dictionary = {bytes([index]): index for index in range(256)}
                next_code = 258
            prefix = bytes([pixel_value])
        emit(dictionary[prefix])
        emit(end_code)

    if bit_count:
        output.append(bit_buffer & 0xFF)
    return bytes(output)


def gif_sub_blocks(data: bytes) -> bytes:
    blocks = bytearray()
    for start in range(0, len(data), 255):
        block = data[start : start + 255]
        blocks.append(len(block))
        blocks.extend(block)
    blocks.append(0)
    return bytes(blocks)


def write_gif(path: Path, frames: Iterable[Canvas]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    palette_bytes = bytearray()
    for red, green, blue in PALETTE:
        palette_bytes.extend((red, green, blue))
    palette_bytes.extend(bytes((GIF_PALETTE_SIZE - len(PALETTE)) * 3))

    with path.open("wb") as image_file:
        image_file.write(b"GIF89a")
        image_file.write(struct.pack("<HHBBB", WIDTH, HEIGHT, 0xF7, 0, 0))
        image_file.write(palette_bytes)
        image_file.write(b"!\xFF\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")

        for frame in frames:
            image_file.write(b"!\xF9\x04\x04")
            image_file.write(struct.pack("<H", FRAME_DELAY_CENTISECONDS))
            image_file.write(b"\x00\x00")
            image_file.write(b",")
            image_file.write(struct.pack("<HHHHB", 0, 0, WIDTH, HEIGHT, 0x00))
            encoded_pixels = gif_lzw_encode(frame.pixels)
            image_file.write(gif_sub_blocks(encoded_pixels))

        image_file.write(b";")


def write_png(path: Path, canvas: Canvas) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw_data = bytearray()
    for y in range(HEIGHT):
        raw_data.append(0)  # Filter type: None
        start = y * WIDTH
        raw_data.extend(canvas.pixels[start : start + WIDTH])

    compressed = zlib.compress(bytes(raw_data), level=9)
    palette_bytes = bytearray()
    for red, green, blue in PALETTE:
        palette_bytes.extend((red, green, blue))

    with path.open("wb") as png_file:
        png_file.write(b"\x89PNG\r\n\x1a\n")
        
        def write_chunk(tag: bytes, data: bytes) -> None:
            png_file.write(struct.pack(">I", len(data)))
            png_file.write(tag)
            png_file.write(data)
            checksum = zlib.crc32(tag)
            checksum = zlib.crc32(data, checksum)
            png_file.write(struct.pack(">I", checksum & 0xFFFFFFFF))

        write_chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 3, 0, 0, 0))
        write_chunk(b"PLTE", bytes(palette_bytes))
        write_chunk(b"IDAT", compressed)
        write_chunk(b"IEND", b"")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render rainy-day pixel art assets.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("assets"),
        help="Directory where generated GIF and PNG files will be saved.",
    )
    args = parser.parse_args()

    print("Rendering frames...")
    frames = [draw_scene_frame(frame_idx) for frame_idx in range(FRAME_COUNT)]

    gif_path = args.output_dir / "rainy-day-quest.gif"
    png_path = args.output_dir / "rainy-day-quest.png"

    print(f"Writing GIF to {gif_path}...")
    write_gif(gif_path, frames)

    print(f"Writing PNG poster to {png_path}...")
    write_png(png_path, frames[0])

    print("Done!")


if __name__ == "__main__":
    main()