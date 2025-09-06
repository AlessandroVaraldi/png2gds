# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright © 2025 Alessandro Varaldi
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the Licence, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https:#www.gnu.org/licenses/>.

import sys, os

# ---------------- Configuration ----------------
# GDS units
GDS_UNIT_M       = 1e-6        # 1 µm = 1e-6 m
GDS_PREC_M       = 1e-9        # precision of 1 nm

# Grid parameters
MAX_CELLS        = 500_000     # safety cap for Nx*Ny
CELL_UM          = 10.0        # side of each square [µm]
GAP_UM           = 2.0         # edge-to-edge gap [µm]

# Sizing constraints (optional)
CELLS_X          = None        # if set, fixes Nx; Ny scales by aspect from input image
TARGET_WIDTH_UM  = 3000.0      # final width INCLUDING margins (optional)
TARGET_HEIGHT_UM = 2000.0      # final height INCLUDING margins (optional)
MARGIN_UM        = 150.0       # margin on each side [µm]

# PNG Binarization
INVERT           = False       # invert before threshold
THRESHOLD        = 128         # binarization threshold [0..255]

# Image processing
RESAMPLE         = "nearest"   # "nearest" | "lanczos" | "bilinear"
FIT_MODE         = "contain"   # "contain" | "fit_width" | "fit_height"

# Numeric GDS layer/datatype
LAYER_NUM        = 0
DATATYPE_NUM     = 0

# ---------------- Backend selection ----------------
try:
    import gdspy as gds
    GDSPY = True
except Exception:
    try:
        import gdstk as gds
        GDSPY = False
    except Exception:
        print("Error: install gdspy (or gdstk): pip install gdspy", file=sys.stderr)
        raise

from PIL import Image

LAYER_KW = {"layer": LAYER_NUM, "datatype": DATATYPE_NUM}

# ---------------- Image helpers ----------------
def _load_png_grayscale(path: str) -> Image.Image:
    ext = os.path.splitext(path)[1].lower()
    if ext != ".png":
        raise ValueError("Only PNG input is accepted. Please provide a .png file.")
    return Image.open(path).convert("L")

def _binarize(img: Image.Image, threshold: int, invert: bool) -> Image.Image:
    if invert:
        img = Image.eval(img, lambda x: 255 - x)
    # Produce a 1-bit image with pixels {0,255}
    return img.point(lambda x: 255 if x >= threshold else 0, mode="1")

import math

def _compute_grid_dims_inclusive(
    img_w, img_h,
    cells_x, target_w_um, target_h_um,
    pitch_um, side_um, margin_um,
    max_cells=500_000,
    verbose=True
):
    r = (img_h / img_w) if img_w > 0 else 1.0  # aspect = H/W
    s = float(side_um)
    p = float(pitch_um)
    margin = float(margin_um)

    def nx_max_from_width(draw_w):
        return max(1, int(math.floor((draw_w - s) / p)) + 1)

    def ny_max_from_height(draw_h):
        return max(1, int(math.floor((draw_h - s) / p)) + 1)

    # User forces Nx
    if cells_x is not None and cells_x > 0:
        nx = int(cells_x)
        ny = max(1, int(math.floor(r * nx)))
    else:
        draw_w = None if target_w_um is None else max(target_w_um - 2.0 * margin, s)
        draw_h = None if target_h_um is None else max(target_h_um - 2.0 * margin, s)

        if draw_w is not None and draw_h is not None:
            nx_w = nx_max_from_width(draw_w)
            ny_h = ny_max_from_height(draw_h)

            if FIT_MODE == "fit_width":
                nx = nx_w
                ny = min(ny_h, max(1, int(math.floor(r * nx))))
            elif FIT_MODE == "fit_height":
                ny = ny_h
                nx = min(nx_w, max(1, int(math.floor(ny / r)))) if r > 0 else nx_w
            else:  # "contain"
                nx_h_cap = max(1, int(math.floor(ny_h / r))) if r > 0 else nx_w
                nx = max(1, min(nx_w, nx_h_cap))
                ny = max(1, min(ny_h, int(math.floor(r * nx))))
        elif draw_w is not None:
            nx = nx_max_from_width(draw_w)
            ny = max(1, int(math.floor(r * nx)))
        elif draw_h is not None:
            ny = ny_max_from_height(draw_h)
            nx = max(1, int(math.floor(ny / r))) if r > 0 else ny
        else:
            nx, ny = int(img_w), int(img_h)

    # Enforce MAX_CELLS with aspect preserved
    total = nx * ny
    if total > max_cells:
        scale = math.sqrt(max_cells / total)
        nx_before, ny_before = nx, ny
        nx = max(1, int(math.floor(nx * scale)))
        ny = max(1, int(math.floor(ny * scale)))
        if verbose:
            print(f"[WARN] Downscaled for MAX_CELLS={max_cells}: {nx_before}x{ny_before} -> {nx}x{ny}")

    return nx, ny

# ---------------- PNG → GDS ----------------
def png_to_gds(input_path: str, output_path: str):
    cell_um = float(CELL_UM)
    gap_um  = float(GAP_UM)
    margin  = float(MARGIN_UM)
    pitch_um = cell_um + gap_um

    img_gray = _load_png_grayscale(input_path)
    img_bin  = _binarize(img_gray, int(THRESHOLD), bool(INVERT))

    nx, ny = _compute_grid_dims_inclusive(
        img_gray.width, img_gray.height,
        CELLS_X, TARGET_WIDTH_UM, TARGET_HEIGHT_UM,
        pitch_um, cell_um, margin, max_cells=int(MAX_CELLS)
    )

    resample_map = {"nearest": Image.NEAREST, "lanczos": Image.LANCZOS, "bilinear": Image.BILINEAR}
    resample = RESAMPLE.lower()
    if resample not in resample_map:
        raise ValueError("RESAMPLE must be one of: nearest | lanczos | bilinear")

    img_grid = img_bin.resize((nx, ny), resample=resample_map[resample])
    pixels = img_grid.load()

    # GDS lib/cell
    if GDSPY:
        lib = gds.GdsLibrary(unit=GDS_UNIT_M, precision=GDS_PREC_M)
        cell = lib.new_cell("LOGO")
    else:
        lib = gds.Library(unit=GDS_UNIT_M, precision=GDS_PREC_M)
        cell = lib.new_cell("LOGO")

    rects = []
    side  = float(cell_um)
    pitch = float(pitch_um)

    # Flip Y: image (top→bottom) → GDS (bottom→top)
    for j_img in range(ny):
        j = ny - 1 - j_img
        y0 = margin + j * pitch
        y1 = y0 + side
        for i in range(nx):
            if pixels[i, j_img] == 255:
                x0 = margin + i * pitch
                x1 = x0 + side
                if GDSPY:
                    rects.append(gds.Rectangle((x0, y0), (x1, y1), **LAYER_KW))
                else:
                    rects.append(gds.rectangle((x0, y0), (x1, y1), **LAYER_KW))

    if rects:
        if GDSPY:
            cell.add(rects)
        else:
            for r in rects:
                cell.add(r)

    width_um  = (nx - 1) * pitch + side + 2 * margin
    height_um = (ny - 1) * pitch + side + 2 * margin
    print(f"[INFO] Cells: {nx} x {ny}  -> squares {len(rects)}")
    print(f"[INFO] Side={side} µm, Gap={gap_um} µm, Pitch={pitch} µm, Margin={margin} µm (per side)")
    print(f"[INFO] Bounding box ~ {width_um:.3f} µm x {height_um:.3f} µm (inclusive of margins)")
    if TARGET_WIDTH_UM is not None or TARGET_HEIGHT_UM is not None:
        print(f"[INFO] Targets (inclusive): W={TARGET_WIDTH_UM} µm, H={TARGET_HEIGHT_UM} µm")

    lib.write_gds(output_path)
    print(f"[OK] Saved: {output_path}")

# ---------------- Main ----------------
def main():
    if len(sys.argv) < 3:
        print("Usage: python3 img2gds.py <input.png> <output.gds>", file=sys.stderr)
        sys.exit(1)

    input_path  = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")

    png_to_gds(input_path, output_path)

if __name__ == "__main__":
    main()
