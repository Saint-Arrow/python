"""
UYVY422 (packed) image downscale (W/2, H/2).

Input format (packed 4:2:2):
  For every 2 pixels: U0 Y0 V0 Y1
  Total bytes = width * height * 2

This script provides:
  - CLI: python uyvy_scale.py -i in_uyvy.bin -s 3840x2160 -o out_uyvy.bin
  - Functions:
      parse_resolution
      parse_debug_pos
      read_uyvy422
      dump_uyvy_at
      scale_uyvy422_half
      write_bin
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Tuple


def parse_resolution(size: str) -> Tuple[int, int]:
    """将 '3840x2160' 解析为 (3840, 2160)。非法格式抛 ValueError。"""
    m = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", size or "")
    if not m:
        raise ValueError(f"Invalid resolution format: {size!r}, expected 'WxH' like '3840x2160'")
    w = int(m.group(1))
    h = int(m.group(2))
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid resolution values: {w}x{h} (must be positive)")
    return w, h


def parse_debug_pos(pos: str) -> Tuple[int, int]:
    """将 '0x0' 解析为 (0, 0)。非法格式抛 ValueError。"""
    m = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", pos or "")
    if not m:
        raise ValueError(f"Invalid debug pos format: {pos!r}, expected 'XxY' like '0x0'")
    x = int(m.group(1))
    y = int(m.group(2))
    if x < 0 or y < 0:
        raise ValueError(f"Invalid debug pos values: {x}x{y} (must be non-negative)")
    return x, y


def read_uyvy422(path: str, width: int, height: int) -> bytes:
    """
    读取 UYVY422 packed 原始数据。
    校验数据长度 == width * height * 2；不通过则抛 ValueError / OSError。
    """
    expected = width * height * 2
    try:
        st = os.stat(path)
    except OSError as e:
        raise OSError(f"Failed to stat input file: {path!r}: {e}") from e

    if st.st_size != expected:
        raise ValueError(
            f"Input file size mismatch: got {st.st_size} bytes, expected {expected} bytes "
            f"for {width}x{height} UYVY422"
        )

    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        raise OSError(f"Failed to read input file: {path!r}: {e}") from e

    if len(data) != expected:
        raise ValueError(f"Short read: got {len(data)} bytes, expected {expected} bytes")
    return data


def dump_uyvy_at(src: bytes, width: int, height: int, x: int, y: int) -> None:
    """
    打印坐标 (x, y) 所在的 UYVY422 packed 采样组（4 字节）：U, Y0, V, Y1。
    说明：
      - UYVY 是每 2 像素一组；若 x 为奇数，仍会打印其所在的“那一组”(x-1, x)。
    """
    if width % 2 != 0:
        raise ValueError(f"width must be even for UYVY422 packed, got {width}")
    if not (0 <= x < width) or not (0 <= y < height):
        raise ValueError(f"debug position out of range: ({x}, {y}) for {width}x{height}")
    expected = width * height * 2
    if len(src) != expected:
        raise ValueError(f"src length mismatch: got {len(src)} bytes, expected {expected} bytes")

    gx = x & ~1  # group start x (even)
    row_bytes = width * 2
    group_offset = y * row_bytes + (gx // 2) * 4
    b0, b1, b2, b3 = src[group_offset : group_offset + 4]

    # U Y0 V Y1 for pixels (gx, gx+1)
    print(
        f"(x, y)=({x}, {y}), group_x=({gx}, {gx + 1}), "
        f"UYVY=[U={b0} Y0={b1} V={b2} Y1={b3}] "
        f"(hex: {b0:02X} {b1:02X} {b2:02X} {b3:02X})"
    )


def _require_numpy():
    try:
        import numpy as np  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "This script requires numpy. Please install it first, e.g.:\n"
            "  pip install -r requirements.txt\n"
            f"Original import error: {e}"
        ) from e
    return np


def scale_uyvy422_half(src: bytes, width: int, height: int) -> bytes:
    """
    输入:
      - src: UYVY422 packed, 分辨率 width x height
    输出:
      - UYVY422 packed, 分辨率 (width//2) x (height//2)

    规则（按 2x2 像素块）:
      - Y: 取 4 个 Y 的平均值
      - U: 先取上下两行对应的 2 个 U 的平均值；再按输出 UYVY 4:2:2 的打包要求，
           将相邻两个 2x2 块的 U 再做一次水平平均（生成 1 个 U 对应 2 个输出像素）
      - V: 同 U

    约束:
      - width 必须为偶数
      - width 与 height 必须能被 2 整除
      - 为保证输出仍为 UYVY422 packed（输出宽度必须为偶数），要求 width 必须能被 4 整除
    """
    if width % 2 != 0:
        raise ValueError(f"width must be even for UYVY422 packed, got {width}")
    if height % 2 != 0:
        raise ValueError(f"height must be divisible by 2 for half scaling, got {height}")
    if (width // 2) % 2 != 0:
        raise ValueError(
            f"output width must be even for UYVY422 packed: width//2={width//2}; "
            f"input width must be divisible by 4, got {width}"
        )
    expected = width * height * 2
    if len(src) != expected:
        raise ValueError(f"src length mismatch: got {len(src)} bytes, expected {expected} bytes")

    np = _require_numpy()

    h = height
    w = width
    row_bytes = w * 2

    buf = np.frombuffer(src, dtype=np.uint8)
    rows = buf.reshape((h, row_bytes))

    # Extract packed components.
    # U and V are sampled per 2 pixels (width/2 samples per row).
    u = rows[:, 0::4]
    v = rows[:, 2::4]

    # Y for every pixel (width samples per row).
    y = np.empty((h, w), dtype=np.uint8)
    y[:, 0::2] = rows[:, 1::4]  # even pixels
    y[:, 1::2] = rows[:, 3::4]  # odd pixels

    # Downsample Y by 2x2 average.
    y00 = y[0::2, 0::2].astype(np.uint16)
    y01 = y[0::2, 1::2].astype(np.uint16)
    y10 = y[1::2, 0::2].astype(np.uint16)
    y11 = y[1::2, 1::2].astype(np.uint16)
    y_ds = ((y00 + y01 + y10 + y11) // 4).astype(np.uint8)  # (h/2, w/2)

    # Downsample chroma:
    # - vertical average: combine two rows -> (h/2, w/2)
    # - horizontal average: combine two adjacent chroma samples -> (h/2, w/4)
    u_v = ((u[0::2, :].astype(np.uint16) + u[1::2, :].astype(np.uint16)) // 2)
    v_v = ((v[0::2, :].astype(np.uint16) + v[1::2, :].astype(np.uint16)) // 2)
    u_ds = ((u_v[:, 0::2] + u_v[:, 1::2]) // 2).astype(np.uint8)
    v_ds = ((v_v[:, 0::2] + v_v[:, 1::2]) // 2).astype(np.uint8)

    out_h = h // 2
    out_w = w // 2
    out_row_bytes = out_w * 2  # equals w

    out = np.empty((out_h, out_row_bytes), dtype=np.uint8)
    out[:, 0::4] = u_ds
    out[:, 2::4] = v_ds
    out[:, 1::4] = y_ds[:, 0::2]
    out[:, 3::4] = y_ds[:, 1::2]

    return out.tobytes()


def write_bin(path: str, data: bytes) -> None:
    """将二进制数据写出到 path。"""
    try:
        with open(path, "wb") as f:
            f.write(data)
    except OSError as e:
        raise OSError(f"Failed to write output file: {path!r}: {e}") from e


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Downscale UYVY422 packed raw image to half size (W/2, H/2).")
    p.add_argument("-i", "--input", required=True, help="Input UYVY422 (packed) raw file path")
    p.add_argument("-s", "--size", required=True, help="Input resolution as WxH, e.g. 3840x2160")
    p.add_argument("-o", "--output", default="out_uyvy.bin", help="Output file path (default: out_uyvy.bin)")
    p.add_argument(
        "-d",
        "--debug",
        default=None,
        help="Debug position 'XxY' (e.g. 0x0). If set, only dump UYVY group and exit without scaling.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    try:
        w, h = parse_resolution(args.size)
        src = read_uyvy422(args.input, w, h)
        if args.debug:
            x, y = parse_debug_pos(args.debug)
            dump_uyvy_at(src, w, h, x, y)
            return 0
        dst = scale_uyvy422_half(src, w, h)
        write_bin(args.output, dst)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

