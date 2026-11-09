#!/usr/bin/env python3
"""Bake the cartoon Earth texture for the concert globe from real NASA data.

Inputs (public-domain NASA imagery, from the MIT-licensed `earth-visualization`
npm package: `npm pack earth-visualization`, then extract package/dist/textures):
  earth_color_4096x2048.jpg       Blue Marble colour
  topography_2048x1024.png        elevation
  earth_landocean_4050x2025.png   land / ocean mask

Outputs (public/assets/):
  earth-toon.jpg   4096x2048 colour map: flat biome colour bands, cel-shaded
                   relief from real elevation, snowcaps, shallow-water rings,
                   ink coastlines.
  earth-bump.jpg   2048x1024 elevation, used as a bump map so ranges catch the
                   light as the globe turns.

Usage: python3 bake_earth.py <textures_dir>
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else 'textures')
OUT = Path(__file__).resolve().parent.parent / 'public' / 'assets'
W, H = 4096, 2048


def load(name, mode='RGB', size=(W, H), resample=Image.LANCZOS):
    return np.asarray(Image.open(SRC / name).convert(mode).resize(size, resample), dtype=np.float32)


color = load('earth_color_4096x2048.jpg')
topo = load('topography_2048x1024.png', 'L', resample=Image.BICUBIC) / 255.0
land = load('earth_landocean_4050x2025.png', 'L') < 128
# Fill small inland water (thousands of 1-3 px lakes read as pixel noise);
# keep big lakes like the Great Lakes, Caspian and Victoria.
water_parts, n = ndimage.label(~land)
sizes = ndimage.sum(np.ones_like(land), water_parts, range(1, n + 1))
ocean_id = water_parts[H // 2, 0]  # mid-Pacific seam pixel belongs to the world ocean
small = np.isin(water_parts, 1 + np.flatnonzero(sizes < 1500)) & (water_parts != ocean_id)
land |= small

# ─── 1. biome classes: nearest cartoon colour to the smoothed real colour ───
# (real Blue Marble colour -> flat toon colour). Smoothing + a majority filter
# turn noisy satellite pixels into clean cartoon blobs.
BIOMES = [  # (typical Blue Marble RGB, cartoon RGB)
    ((38, 58, 28), (46, 158, 79)),      # dense forest / rainforest
    ((72, 92, 48), (92, 196, 84)),      # temperate forest, grassland
    ((118, 118, 78), (178, 205, 98)),   # savanna, steppe
    ((150, 132, 96), (214, 196, 120)),  # dry scrub
    ((205, 172, 122), (246, 206, 118)), # sand desert
    ((170, 100, 62), (234, 148, 92)),   # red desert (outback, Namib)
    ((96, 86, 70), (164, 148, 110)),    # tundra, bare ground
    ((235, 238, 242), (244, 250, 255)), # ice and snow
]
src = np.array([b[0] for b in BIOMES], np.float32)
dst = np.array([b[1] for b in BIOMES], np.float32)

smooth = ndimage.uniform_filter(color, size=(9, 9, 1))
best = np.full((H, W), np.inf, np.float32)
label = np.zeros((H, W), np.int64)
for i, c in enumerate(src):                     # loop keeps memory flat (no H x W x 8 x 3 tensor)
    di = ((smooth - c) ** 2).sum(-1)
    better = di < best
    best[better], label[better] = di[better], i
# majority filter: replace each label with the most common one nearby
best = np.zeros((H, W), np.float32)
major = label.copy()
for i in range(len(BIOMES)):
    ci = ndimage.uniform_filter((label == i).astype(np.float32), 11)
    better = ci > best
    best[better], major[better] = ci[better], i
label = major
img = dst[label]

# ─── 2. relief from real elevation ──────────────────────────────────────────
h = ndimage.gaussian_filter(topo, 1.8)
# Rock and snow follow prominence (height above the surrounding land), not raw
# altitude: Tibet is a high plateau, not an ice sheet.
prom = h - ndimage.gaussian_filter(h, 24)
is_ice = (label == len(BIOMES) - 1)[..., None]
rock = (np.clip((prom - 0.05) / 0.08, 0, 1) * np.clip((h - 0.35) / 0.15, 0, 1))[..., None] * ~is_ice
snow = (np.clip((prom - 0.10) / 0.06, 0, 1) * np.clip((h - 0.55) / 0.1, 0, 1))[..., None]
img = img * (1 - rock) + np.array([150, 128, 112], np.float32) * rock
img = img * (1 - snow) + np.array([250, 252, 255], np.float32) * snow

# cel-shaded hillshade: light from the north-west, quantised into 3 bands
gy, gx = np.gradient(h * 60)
shade = (-gx * 0.7 + gy * 0.7) / np.sqrt(1 + gx ** 2 + gy ** 2)
bands = np.select([shade < -0.12, shade > 0.12], [0.74, 1.14], 1.0)[..., None]
img = np.clip(img * bands, 0, 255)

# ─── 3. stylised ocean: deep -> mid -> bright shallow ring at the coast ─────
dist = ndimage.distance_transform_edt(~land)                 # px from nearest land
inside = ndimage.distance_transform_edt(land)                # px from nearest water
ramp = lambda x: np.clip(x, 0, 1)[..., None]                 # soft 2 px edges, no stair-steps
deep, mid, shallow = (np.array(c, np.float32) for c in ([26, 64, 170], [36, 104, 222], [72, 196, 246]))
ocean = deep + (mid - deep) * ramp((34 - dist) / 2.5)
ocean = ocean + (shallow - ocean) * ramp((10 - dist) / 2.0)
img = img * ramp(inside) + ocean * (1 - ramp(inside))        # anti-aliased shoreline

# ─── 4. ink coastlines (soft-edged band straddling the shore) ───────────────
ink = np.array([16, 22, 58], np.float32)
shore = np.minimum(np.where(land, inside, np.inf), np.where(~land, dist, np.inf))
img = img + (ink - img) * ramp((2.2 - shore) / 1.2)

# Polar seam rows: equirectangular poles are degenerate, keep them clean.
img[:6] = img[6]
img[-6:] = img[-7]

OUT.mkdir(parents=True, exist_ok=True)
out = Image.fromarray(img.astype(np.uint8)).filter(ImageFilter.SMOOTH)  # soften stair-steps
out.save(OUT / 'earth-toon.jpg', quality=88, optimize=True, progressive=True)

bump = Image.fromarray((np.clip(h, 0, 1) * 255).astype(np.uint8)).resize((2048, 1024), Image.LANCZOS)
bump.save(OUT / 'earth-bump.jpg', quality=90, optimize=True)
print('wrote', OUT / 'earth-toon.jpg', OUT / 'earth-bump.jpg')
