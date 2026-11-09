#!/usr/bin/env python3
"""Bake the cartoon Earth texture for the concert globe from real NASA data.

Inputs (public-domain NASA imagery, from the MIT-licensed `earth-visualization`
npm package: `npm pack earth-visualization`, then extract package/dist/textures):
  earth_color_4096x2048.jpg       Blue Marble colour
  topography_2048x1024.png        elevation
  earth_landocean_4050x2025.png   land / ocean mask

Outputs (public/assets/), one colour map per theme:
  earth-dark.jpg   dark violet / navy / carbon palette (what the globe uses)
  earth-toon.jpg   bright cartoon palette
  each 4096x2048: flat biome colour bands, cel-shaded
                   relief from real elevation, snowcaps, shallow-water rings,
                   ink coastlines.
  earth-bump.jpg   2048x1024 elevation, used as a bump map so ranges catch the
                   light as the globe turns.

Usage: python3 bake_earth.py <textures_dir> [dark|toon ...]   (default: both)
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else 'textures')
THEMES = sys.argv[2:] or ['dark', 'toon']
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
# Typical Blue Marble colour of each biome (used to classify real pixels).
BIOMES = ['forest', 'grass', 'savanna', 'scrub', 'desert', 'red_desert', 'tundra', 'ice']
SRC_RGB = [(38, 58, 28), (72, 92, 48), (118, 118, 78), (150, 132, 96),
           (205, 172, 122), (170, 100, 62), (96, 86, 70), (235, 238, 242)]

PALETTES = {
    # Dark violet / navy / carbon: matches the page's dark UI. Land differs by
    # value and hue shift only, so biomes still read without going colourful.
    'dark': dict(
        biomes=[(36, 30, 84), (48, 38, 104), (60, 47, 118), (70, 55, 128),
                (84, 66, 140), (90, 58, 128), (44, 40, 82), (82, 78, 138)],
        rock=(96, 86, 150), snow=(176, 170, 228),
        deep=(5, 7, 16), mid=(9, 14, 38), shallow=(20, 30, 80),
        ink=(122, 104, 255), ink_width=1.6,
        shade=(0.70, 1.0, 1.22)),
    # Bright cartoon palette.
    'toon': dict(
        biomes=[(46, 158, 79), (92, 196, 84), (178, 205, 98), (214, 196, 120),
                (246, 206, 118), (234, 148, 92), (164, 148, 110), (244, 250, 255)],
        rock=(150, 128, 112), snow=(250, 252, 255),
        deep=(26, 64, 170), mid=(36, 104, 222), shallow=(72, 196, 246),
        ink=(16, 22, 58), ink_width=2.2,
        shade=(0.74, 1.0, 1.14)),
}
src = np.array(SRC_RGB, np.float32)

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
# Theme-independent geometry, computed once.
h = ndimage.gaussian_filter(topo, 1.8)
prom = h - ndimage.gaussian_filter(h, 24)      # height above the surrounding land
is_ice = (label == len(BIOMES) - 1)[..., None]
rock = (np.clip((prom - 0.05) / 0.08, 0, 1) * np.clip((h - 0.35) / 0.15, 0, 1))[..., None] * ~is_ice
snow = (np.clip((prom - 0.10) / 0.06, 0, 1) * np.clip((h - 0.55) / 0.1, 0, 1))[..., None]
gy, gx = np.gradient(h * 60)
shade = (-gx * 0.7 + gy * 0.7) / np.sqrt(1 + gx ** 2 + gy ** 2)
dist = ndimage.distance_transform_edt(~land)    # px from nearest land
inside = ndimage.distance_transform_edt(land)   # px from nearest water
shore = np.minimum(np.where(land, inside, np.inf), np.where(~land, dist, np.inf))
ramp = lambda x: np.clip(x, 0, 1)[..., None]     # soft 2 px edges, no stair-steps
OUT.mkdir(parents=True, exist_ok=True)


def render(name, P):
    f = lambda c: np.array(c, np.float32)
    img = np.array(P['biomes'], np.float32)[label]
    img = img * (1 - rock) + f(P['rock']) * rock
    img = img * (1 - snow) + f(P['snow']) * snow
    lo, mid_, hi = P['shade']                    # cel-shaded hillshade, 3 bands, light from NW
    img = np.clip(img * np.select([shade < -0.12, shade > 0.12], [lo, hi], mid_)[..., None], 0, 255)

    ocean = f(P['deep']) + (f(P['mid']) - f(P['deep'])) * ramp((34 - dist) / 2.5)
    ocean = ocean + (f(P['shallow']) - ocean) * ramp((10 - dist) / 2.0)
    img = img * ramp(inside) + ocean * (1 - ramp(inside))
    img = img + (f(P['ink']) - img) * ramp((P['ink_width'] - shore) / 1.2)

    img[:6] = img[6]                             # degenerate polar rows
    img[-6:] = img[-7]
    out = Image.fromarray(img.astype(np.uint8)).filter(ImageFilter.SMOOTH)
    out.save(OUT / name, quality=88, optimize=True, progressive=True)
    print('wrote', OUT / name)


for theme in THEMES:
    render('earth-dark.jpg' if theme == 'dark' else 'earth-toon.jpg', PALETTES[theme])
bump = Image.fromarray((np.clip(h, 0, 1) * 255).astype(np.uint8)).resize((2048, 1024), Image.LANCZOS)
bump.save(OUT / 'earth-bump.jpg', quality=90, optimize=True)
print('wrote', OUT / 'earth-bump.jpg')
