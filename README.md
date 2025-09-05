# png2gds (PNG → GDS)

Convert a **PNG** image into a **GDSII** cell made of a grid of rectangles on a single layer. PNG input only.

---

## Quick start

```bash
# optional: isolated environment
python3 -m venv .venv && source .venv/bin/activate

# dependencies (gdspy as default)
pip install gdspy Pillow
# or, if you keep a requirements file that lists gdspy:
# pip install -r requirements.txt

# run
python3 png2gds.py input.png output.gds
```

Open `output.gds` in KLayout (or any GDS viewer).

---

## What it does

* Converts the PNG to **grayscale**, optionally **inverts**, then applies a **binary threshold**.
* Resamples the mask to an `Nx × Ny` grid.
* Emits one **rectangle per white pixel** on the configured **GDS layer/datatype**.
* Places the grid with **margins**; flips **Y** so image top maps to positive GDS Y.

---

## Configuration (edit constants in `# png2gds.py`)

```python
# Numeric GDS layer/datatype
LAYER_NUM        = 0
DATATYPE_NUM     = 0

# Grid parameters
MAX_CELLS        = 500_000     # safety cap for Nx*Ny
CELL_UM          = 10.0        # side of each square [µm]
GAP_UM           = 2.0         # edge-to-edge gap [µm]

# Sizing constraints (optional)
CELLS_X          = None        # if set, fixes Nx; Ny scales by aspect from input image
TARGET_WIDTH_UM  = 3000.0      # final width INCLUDING margins (optional)
TARGET_HEIGHT_UM = 2000.0      # final height INCLUDING margins (optional)
MARGIN_UM        = 150.0       # margin on each side [µm]

# Image processing
RESAMPLE = "nearest"   # "nearest" | "lanczos" | "bilinear"
FIT_MODE = "contain"  # "contain" | "fit_width" | "fit_height"

# Binarization
INVERT           = False       # invert before threshold
THRESHOLD        = 128         # binarization threshold [0..255]
```

---

## Sizing (inclusive of margins)

Let:

* `side = CELL_UM`
* `pitch = CELL_UM + GAP_UM`
* `margin = MARGIN_UM`

When `TARGET_WIDTH_UM` / `TARGET_HEIGHT_UM` are set:

```
drawable_w = target_w - 2*margin
drawable_h = target_h - 2*margin

model_w ≈ (Nx - 1)*pitch + side
model_h ≈ (Ny - 1)*pitch + side
```

If `CELLS_X` is set, `Nx` is fixed and `Ny` follows the PNG aspect ratio.
If neither is set, `Nx, Ny` default to the PNG width/height.

Final printed size:

```
width_um  = (Nx - 1)*pitch + side + 2*margin
height_um = (Ny - 1)*pitch + side + 2*margin
```

---

## Coordinate system

* Image origin (top-left) maps to **bottom-left** in GDS: **Y is flipped**.
* **GDS units**: unit = `1e-6 m` (µm), precision = `1e-9 m`.
