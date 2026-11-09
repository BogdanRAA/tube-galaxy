// Cartoon relief layer for the concert globe: mountain ranges, wonders of the
// world at their real coordinates, and regional scenery (forests, jungle,
// palms, cacti, dunes, ice, whales). Same toon look as orbit.js.
//
// Scenery is scattered with a seeded RNG (stable layout on every load) and
// each candidate point is tested against the country polygons, so trees and
// cacti only grow on land and icebergs only float at sea. Repeated items are
// GPU-instanced: hundreds of trees cost a handful of draw calls.
import * as THREE from 'https://unpkg.com/three@0.157.0/build/three.module.min.js';

const INK = 0x0b0820;
const Y = new THREE.Vector3(0, 1, 0);
const TREE = 1.4;               // scenery scale
const WONDER = 1.3;             // landmark scale

// ─── materials ──────────────────────────────────────────────────────────────

const ramp = (() => {
  const tx = new THREE.DataTexture(new Uint8Array([80, 160, 255]), 3, 1, THREE.RedFormat);
  tx.minFilter = tx.magFilter = THREE.NearestFilter;
  tx.needsUpdate = true;
  return tx;
})();
const toon = (color, extra = {}) => new THREE.MeshToonMaterial({ color, gradientMap: ramp, ...extra });
const outlineMat = new THREE.MeshBasicMaterial({ color: INK, side: THREE.BackSide });
const C = {
  rock: toon(0x8b7d9e), rockDark: toon(0x6a5f80), snow: toon(0xffffff), pine: toon(0x2fbf71),
  jungle: toon(0x3fe05a), jungleDark: toon(0x22a64a), trunk: toon(0x9a5b34), palm: toon(0x5ee36b),
  cactus: toon(0x46c46a), sand: toon(0xf2c46d), ice: toon(0xd9f6ff), iceBlue: toon(0x9fe3ff),
  whale: toon(0x3a6fd8), whaleBelly: toon(0xcfe2ff), stone: toon(0xd8c8a8), sandstone: toon(0xe8b866),
  iron: toon(0x9a6a3a), copper: toon(0x58d6b0), gold: toon(0xffcf3a), white: toon(0xf6f3ff),
  red: toon(0xe84a3a), redDome: toon(0xff5a6e), blueDome: toon(0x4a8cff), greenDome: toon(0x3fd48a),
  steel: toon(0xb8c6e0), brick: toon(0xc9874f), grey: toon(0x8a90a8), roof: toon(0x3a3f5c),
};

function part(geo, mat, pos = [0, 0, 0], rot = [0, 0, 0], scale = [1, 1, 1], outline = true) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(geo, mat));
  if (outline) { const o = new THREE.Mesh(geo, outlineMat); o.scale.setScalar(1.08); g.add(o); }
  g.position.set(...pos); g.rotation.set(...rot); g.scale.set(...scale);
  return g;
}
const box = (x, y, z) => new THREE.BoxGeometry(x, y, z);
const cone = (r, h, s = 12) => new THREE.ConeGeometry(r, h, s);
const cyl = (rt, rb, h, s = 12, open = false, t0 = 0, tl = Math.PI * 2) => new THREE.CylinderGeometry(rt, rb, h, s, 1, open, t0, tl);
const sph = (r, ws = 14, hs = 10) => new THREE.SphereGeometry(r, ws, hs);
const onion = (r, mat, y) => {                    // onion dome: squashed sphere + spike
  const g = new THREE.Group();
  g.add(part(sph(r), mat, [0, y, 0], [0, 0, 0], [1, 1.15, 1]));
  g.add(part(cone(r * 0.35, r * 1.2, 8), mat, [0, y + r * 1.4, 0]));
  return g;
};

// ─── wonders (built +Y up, base at y = 0, roughly 1 unit = 1 globe unit) ────

const W = {
  eiffel() {
    const g = new THREE.Group();
    g.add(part(cyl(1.4, 2.6, 2.2, 4), C.iron, [0, 1.1, 0], [0, Math.PI / 4, 0]));
    g.add(part(cyl(0.7, 1.3, 2.6, 4), C.iron, [0, 3.5, 0], [0, Math.PI / 4, 0]));
    g.add(part(cyl(0.15, 0.65, 3.4, 4), C.iron, [0, 6.5, 0], [0, Math.PI / 4, 0]));
    g.add(part(box(2.2, 0.25, 2.2), C.iron, [0, 2.25, 0]));
    g.add(part(cyl(0.04, 0.04, 1.2, 4), C.iron, [0, 8.7, 0], [0, 0, 0], [1, 1, 1], false));
    return g;
  },
  pyramids() {
    const g = new THREE.Group();
    [[0, 0, 3.4], [2.9, -1.4, 2.8], [5.2, -2.6, 1.8]].forEach(([x, z, s]) =>
      g.add(part(cone(s, s * 1.25, 4), C.sandstone, [x, s * 0.62, z], [0, Math.PI / 4, 0])));
    return g;
  },
  liberty() {
    const g = new THREE.Group();
    g.add(part(box(2.2, 2.2, 2.2), C.stone, [0, 1.1, 0]));
    g.add(part(cyl(0.55, 0.9, 3.4, 10), C.copper, [0, 3.9, 0]));
    g.add(part(sph(0.45), C.copper, [0, 5.9, 0]));
    g.add(part(cone(0.55, 0.5, 7), C.copper, [0, 6.35, 0]));                       // crown
    g.add(part(cyl(0.14, 0.18, 1.8, 6), C.copper, [0.55, 6.1, 0], [0, 0, -0.25]));  // raised arm
    g.add(part(cone(0.28, 0.6, 8), C.gold, [0.8, 7.3, 0], [Math.PI, 0, 0]));         // torch
    return g;
  },
  bigben() {
    const g = new THREE.Group();
    g.add(part(box(1.4, 6, 1.4), C.sandstone, [0, 3, 0]));
    g.add(part(box(1.6, 1.4, 1.6), C.sandstone, [0, 6.6, 0]));
    for (const [x, z, ry] of [[0.81, 0, Math.PI / 2], [-0.81, 0, Math.PI / 2], [0, 0.81, 0], [0, -0.81, 0]])
      g.add(part(new THREE.CircleGeometry(0.5, 16), C.white, [x, 6.6, z], [0, ry, 0], [1, 1, 1], false));
    g.add(part(cone(1.05, 2.4, 4), C.roof, [0, 8.5, 0], [0, Math.PI / 4, 0]));
    return g;
  },
  colosseum() {
    const g = new THREE.Group();
    const wall = cyl(3, 3, 2.2, 28, true, 0, Math.PI * 1.65);
    const m = toon(0xe0c79a, { side: THREE.DoubleSide });
    g.add(part(wall, m, [0, 1.1, 0], [0, 0, 0], [1, 1, 0.78]));
    g.add(part(cyl(2.3, 2.3, 1.4, 28, true), m, [0, 0.7, 0], [0, 0, 0], [1, 1, 0.78]));
    return g;
  },
  taj() {
    const g = new THREE.Group();
    g.add(part(box(5, 0.5, 5), C.white, [0, 0.25, 0]));
    g.add(part(box(3, 2.4, 3), C.white, [0, 1.7, 0]));
    g.add(onion(1.2, C.white, 3.8));
    for (const [x, z] of [[2.2, 2.2], [-2.2, 2.2], [2.2, -2.2], [-2.2, -2.2]]) {
      g.add(part(cyl(0.18, 0.24, 3.8, 8), C.white, [x, 2.4, z]));
      g.add(part(sph(0.28), C.white, [x, 4.4, z]));
    }
    return g;
  },
  greatwall() {
    const g = new THREE.Group();
    const pts = [[-7, 0], [-4.5, 1.6], [-2, 0.2], [0.5, 1.8], [3, 0.4], [5.5, 2.0], [7.5, 1.0]];
    for (let i = 0; i < pts.length - 1; i++) {
      const [x1, z1] = pts[i], [x2, z2] = pts[i + 1];
      const len = Math.hypot(x2 - x1, z2 - z1);
      g.add(part(box(len, 0.9, 0.6), C.stone, [(x1 + x2) / 2, 0.45, (z1 + z2) / 2], [0, -Math.atan2(z2 - z1, x2 - x1), 0]));
      g.add(part(box(0.9, 1.5, 0.9), C.stone, [x1, 0.75, z1]));                    // watchtowers
    }
    return g;
  },
  redeemer() {
    const g = new THREE.Group();
    g.add(part(cone(2.4, 3, 9), C.jungleDark, [0, 1.5, 0]));                        // Corcovado
    g.add(part(cyl(0.3, 0.45, 2.6, 8), C.white, [0, 4.2, 0]));
    g.add(part(box(3.6, 0.45, 0.45), C.white, [0, 5.1, 0]));                        // open arms
    g.add(part(sph(0.35), C.white, [0, 5.75, 0]));
    return g;
  },
  opera() {
    const g = new THREE.Group();
    g.add(part(box(5.5, 0.6, 2.6), C.stone, [0, 0.3, 0]));
    [[-1.8, 1.5], [-0.3, 1.9], [1.4, 1.6], [2.6, 1.1]].forEach(([x, s]) => {
      const shell = new THREE.SphereGeometry(s, 16, 8, 0, Math.PI, 0, Math.PI / 2);
      g.add(part(shell, toon(0xffffff, { side: THREE.DoubleSide }), [x, 0.6, 0], [0, Math.PI / 2, -0.5]));
    });
    return g;
  },
  fuji() {
    const g = new THREE.Group();
    g.add(part(cyl(0.6, 4.2, 4.2, 16), C.blueDome, [0, 2.1, 0]));
    g.add(part(cyl(0.6, 1.6, 1.4, 16), C.snow, [0, 3.55, 0]));
    return g;
  },
  moai() {
    const g = new THREE.Group();
    [-1.6, 0, 1.6].forEach((x, i) => {
      g.add(part(box(1, 2.6, 0.9), C.grey, [x, 1.3, 0]));
      g.add(part(box(1.1, 0.6, 0.5), C.grey, [x, 1.9, 0.55]));                    // brow and nose
      g.add(part(box(0.9, 0.35, 0.9), C.brick, [x, 2.78, 0]));                    // topknot
    });
    return g;
  },
  burj() {
    const g = new THREE.Group();
    [[1.4, 3], [1.0, 3], [0.7, 2.6], [0.45, 2.2]].reduce((y, [r, h]) => {
      g.add(part(cyl(r * 0.8, r, h, 6), C.steel, [0, y + h / 2, 0])); return y + h;
    }, 0);
    g.add(part(cone(0.3, 3.2, 6), C.steel, [0, 12.4, 0]));
    return g;
  },
  stbasil() {
    const g = new THREE.Group();
    g.add(part(box(4, 1.6, 4), C.red, [0, 0.8, 0]));
    g.add(part(cyl(0.55, 0.65, 3.2, 8), C.brick, [0, 3.2, 0]));
    g.add(part(cone(0.7, 2.2, 8), C.greenDome, [0, 5.9, 0]));
    [[1.4, 1.4, C.redDome], [-1.4, 1.4, C.blueDome], [1.4, -1.4, C.gold], [-1.4, -1.4, C.greenDome]].forEach(([x, z, m]) => {
      g.add(part(cyl(0.4, 0.45, 1.6, 8), C.brick, [x, 2.4, z]));
      g.add(onion(0.6, m, 3.6).translateX(x).translateZ(z));
    });
    return g;
  },
  goldengate() {
    const g = new THREE.Group();
    for (const x of [-3, 3]) g.add(part(box(0.5, 5, 0.6), C.red, [x, 2.5, 0]));
    g.add(part(box(9, 0.3, 0.9), C.red, [0, 1.2, 0]));
    const curve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(-3, 5, 0), new THREE.Vector3(0, 1.6, 0), new THREE.Vector3(3, 5, 0));
    g.add(part(new THREE.TubeGeometry(curve, 16, 0.08, 5), C.red, [0, 0, 0.3], [0, 0, 0], [1, 1, 1], false));
    g.add(part(new THREE.TubeGeometry(curve, 16, 0.08, 5), C.red, [0, 0, -0.3], [0, 0, 0], [1, 1, 1], false));
    return g;
  },
  watarun() {
    const g = new THREE.Group();
    const prang = (h, x, z) => {
      [[1, 0.35], [0.75, 0.3], [0.5, 0.25]].reduce((y, [r, f]) => {
        const hh = h * f;
        g.add(part(cyl(r * 0.7, r, hh, 8), C.white, [x, y + hh / 2, z])); return y + hh;
      }, 0);
      g.add(part(cone(0.3, h * 0.35, 8), C.gold, [x, h * 0.9 + h * 0.17, z]));
    };
    prang(6.5, 0, 0);
    for (const [x, z] of [[2.2, 2.2], [-2.2, 2.2], [2.2, -2.2], [-2.2, -2.2]]) prang(3.2, x, z);
    return g;
  },
  bran() {
    const g = new THREE.Group();
    g.add(part(cone(2.6, 2.4, 7), C.rockDark, [0, 1.2, 0]));                        // the crag
    g.add(part(box(2.2, 2, 1.8), C.white, [0, 3.4, 0]));
    g.add(part(cone(1.6, 1.4, 4), C.red, [0, 5.1, 0], [0, Math.PI / 4, 0]));
    g.add(part(cyl(0.5, 0.5, 2.8, 10), C.white, [1.2, 3.8, 0.6]));
    g.add(part(cone(0.7, 1.6, 10), C.red, [1.2, 6, 0.6]));
    return g;
  },
  chichen() {
    const g = new THREE.Group();
    [[5, 0.9], [4, 0.9], [3, 0.9], [2.1, 0.9]].reduce((y, [w, h]) => {
      g.add(part(box(w, h, w), C.stone, [0, y + h / 2, 0])); return y + h;
    }, 0);
    g.add(part(box(1.3, 1, 1.3), C.stone, [0, 4.1, 0]));
    g.add(part(box(0.9, 3.6, 0.2), C.grey, [0, 1.8, 2.4], [-0.75, 0, 0], [1, 1, 1], false)); // stairs
    return g;
  },
};

const WONDERS = [
  ['Eiffel Tower', 'Paris, France', 48.858, 2.294, W.eiffel, 1.0],
  ['Pyramids of Giza', 'Cairo, Egypt', 29.979, 31.134, W.pyramids, 1.0],
  ['Statue of Liberty', 'New York, USA', 40.689, -74.044, W.liberty, 1.0],
  ['Big Ben', 'London, UK', 51.5007, -0.1246, W.bigben, 0.9],
  ['Colosseum', 'Rome, Italy', 41.890, 12.492, W.colosseum, 1.0],
  ['Taj Mahal', 'Agra, India', 27.175, 78.042, W.taj, 1.0],
  ['Great Wall', 'Beijing, China', 40.43, 116.57, W.greatwall, 0.9],
  ['Christ the Redeemer', 'Rio de Janeiro, Brazil', -22.951, -43.211, W.redeemer, 1.0],
  ['Sydney Opera House', 'Sydney, Australia', -33.857, 151.215, W.opera, 1.0],
  ['Mount Fuji', 'Honshu, Japan', 35.36, 138.73, W.fuji, 1.0],
  ['Moai', 'Rapa Nui (Easter Island)', -27.12, -109.37, W.moai, 1.1],
  ['Burj Khalifa', 'Dubai, UAE', 25.197, 55.274, W.burj, 0.85],
  ["St Basil's Cathedral", 'Moscow, Russia', 55.752, 37.623, W.stbasil, 0.9],
  ['Golden Gate Bridge', 'San Francisco, USA', 37.819, -122.478, W.goldengate, 0.9],
  ['Wat Arun', 'Bangkok, Thailand', 13.744, 100.489, W.watarun, 0.9],
  ['Bran Castle', 'Transylvania, Romania', 45.515, 25.367, W.bran, 0.9],
  ['Chichen Itza', 'Yucatán, Mexico', 20.684, -88.568, W.chichen, 1.0],
];

// ─── scenery primitives (instanced) ─────────────────────────────────────────

const KIT = {
  pine: [[cone(0.9, 2.2, 7), C.pine, [0, 1.6, 0]], [cyl(0.15, 0.2, 0.6, 5), C.trunk, [0, 0.3, 0]]],
  jungle: [[sph(0.9, 8, 6), C.jungle, [0, 1.4, 0]], [sph(0.6, 8, 6), C.jungleDark, [0.5, 1.1, 0.3]], [cyl(0.14, 0.18, 0.8, 5), C.trunk, [0, 0.4, 0]]],
  palm: [[cyl(0.1, 0.16, 2.2, 5), C.trunk, [0, 1.1, 0]], [cone(1.1, 0.5, 6), C.palm, [0, 2.3, 0]]],
  cactus: [[cyl(0.28, 0.28, 2, 7), C.cactus, [0, 1, 0]], [cyl(0.18, 0.18, 0.9, 6), C.cactus, [0.5, 1.2, 0]], [cyl(0.18, 0.18, 0.7, 6), C.cactus, [-0.5, 1.0, 0]]],
  dune: [[sph(1.4, 10, 6), C.sand, [0, 0, 0], [1.4, 0.45, 0.9]]],
  mountain: [[cone(1.7, 4.4, 6), C.rock, [0, 2.2, 0]], [cone(0.85, 2.2, 6), C.snow, [0, 3.3, 0]]],
  peak: [[cone(1.3, 3.4, 5), C.ice, [0, 1.7, 0]], [cone(0.6, 1.4, 5), C.snow, [0, 2.7, 0]]],
  iceberg: [[cyl(0.7, 1.3, 1.2, 6), C.ice, [0, 0.3, 0]], [cone(0.7, 1.0, 6), C.iceBlue, [0.2, 1.3, 0]]],
};

function instanced(kit, placements, root) {
  if (!placements.length) return;
  const m4 = new THREE.Matrix4(), local = new THREE.Matrix4(), out = new THREE.Matrix4();
  for (const [geo, mat, pos, scl = [1, 1, 1]] of kit) {
    local.compose(new THREE.Vector3(...pos), new THREE.Quaternion(), new THREE.Vector3(...scl));
    const body = new THREE.InstancedMesh(geo, mat, placements.length);
    const line = new THREE.InstancedMesh(geo, outlineMat, placements.length);
    const grow = new THREE.Matrix4().makeScale(1.1, 1.1, 1.1);
    placements.forEach((pm, i) => {
      m4.multiplyMatrices(pm, local);
      body.setMatrixAt(i, m4);
      out.multiplyMatrices(m4, grow);
      line.setMatrixAt(i, out);
    });
    root.add(body, line);
  }
}

// ─── geography helpers ──────────────────────────────────────────────────────

function rng(seed) {                               // mulberry32: same layout every load
  return () => {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function landIndex(geo) {
  const rings = [];
  for (const f of geo.features) {
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const p of polys) {
      const ring = p[0];
      let minX = 180, maxX = -180, minY = 90, maxY = -90;
      for (const [x, y] of ring) { minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y); }
      rings.push({ ring, minX, maxX, minY, maxY });
    }
  }
  return (lat, lng) => rings.some(r => {
    if (lng < r.minX || lng > r.maxX || lat < r.minY || lat > r.maxY) return false;
    let inside = false;
    for (let i = 0, j = r.ring.length - 1; i < r.ring.length; j = i++) {
      const [xi, yi] = r.ring[i], [xj, yj] = r.ring[j];
      if ((yi > lat) !== (yj > lat) && lng < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  });
}

function scatter(rand, isLand, boxes, n, { onLand = true, scale = [0.8, 1.3] } = {}) {
  const out = [];
  let tries = 0;
  while (out.length < n && tries++ < n * 40) {
    const [la0, la1, ln0, ln1] = boxes[Math.floor(rand() * boxes.length)];
    const lat = la0 + rand() * (la1 - la0), lng = ln0 + rand() * (ln1 - ln0);
    if (isLand(lat, lng) === onLand) out.push([lat, lng, scale[0] + rand() * (scale[1] - scale[0]), rand() * Math.PI * 2]);
  }
  return out;
}

function alongRange(rand, path, step = 1.4, jitter = 0.9) {
  const out = [];
  for (let i = 0; i < path.length - 1; i++) {
    const [a1, o1] = path[i], [a2, o2] = path[i + 1];
    const n = Math.max(1, Math.round(Math.hypot(a2 - a1, o2 - o1) / step));
    for (let k = 0; k < n; k++) {
      const t = k / n;
      for (let c = 0; c < 2; c++) {                 // two staggered rows read as a range
        out.push([a1 + (a2 - a1) * t + (rand() - 0.5) * jitter * 2, o1 + (o2 - o1) * t + (rand() - 0.5) * jitter * 2,
          0.75 + rand() * 0.75, rand() * Math.PI * 2]);
      }
    }
  }
  return out;
}

const RANGES = {
  Himalaya: [[35.5, 74], [34, 77], [31, 80], [29, 84], [28, 87], [27.8, 90], [28, 94]],
  Andes: [[8, -73], [2, -77], [-5, -79], [-12, -76], [-17, -70], [-23, -68], [-30, -70], [-36, -71], [-42, -72], [-48, -73]],
  Rockies: [[60, -128], [55, -122], [50, -116], [45, -112], [40, -106], [36, -106]],
  Alps: [[44.5, 7], [46, 7.5], [46.5, 9.5], [47, 11.5], [47.2, 13.5]],
  Atlas: [[31, -8], [32.5, -4], [34, 0], [35.5, 5]],
  Urals: [[66, 62], [60, 59], [55, 59], [51, 58]],
  Scandes: [[68, 17], [64, 13], [61, 9]],
  Caucasus: [[43.5, 40], [42.8, 44], [41.5, 48]],
};

// ─── wire into globe.gl ─────────────────────────────────────────────────────

function waitForGlobe() {
  return new Promise(res => {
    const t = setInterval(() => {
      if (typeof globeReady !== 'undefined' && globeReady && globe) { clearInterval(t); res(globe); }
    }, 100);
  });
}

Promise.all([waitForGlobe(), fetch('./assets/countries-110m.geojson').then(r => r.json())]).then(([globe, geo]) => {
  const isLand = landIndex(geo);
  const rand = rng(20261110);
  const root = new THREE.Group();
  root.name = 'relief-layer';
  globe.scene().add(root);

  const q = new THREE.Quaternion(), spin = new THREE.Quaternion();
  const placeMatrix = (lat, lng, s, rot, alt = 0.004) => {
    const c = globe.getCoords(lat, lng, alt);
    const p = new THREE.Vector3(c.x, c.y, c.z);
    q.setFromUnitVectors(Y, p.clone().normalize());
    spin.setFromAxisAngle(Y, rot);
    return new THREE.Matrix4().compose(p, q.clone().multiply(spin), new THREE.Vector3(s, s, s));
  };
  const place = (list, k = 1) => list.map(([lat, lng, s, rot]) => placeMatrix(lat, lng, s * k, rot));

  // Relief
  instanced(KIT.mountain, place(Object.values(RANGES).flatMap(r => alongRange(rand, r))
    .concat([[-3.07, 37.35, 1.6, 0], [63.07, -151, 1.5, 1], [-0.68, 29.87, 1.1, 2]])), root);
  instanced(KIT.peak, place(scatter(rand, isLand, [[64, 80, -52, -24]], 45, { scale: [0.8, 1.4] })), root);

  // Biomes
  instanced(KIT.pine, place(scatter(rand, isLand, [[50, 62, -125, -65], [56, 68, 60, 140], [59, 68, 10, 30], [56, 64, 30, 60]], 230, { scale: [0.7, 1.1] }), TREE), root);
  instanced(KIT.jungle, place(scatter(rand, isLand, [[-12, 2, -75, -50], [-5, 4, 12, 28], [-3, 4, 100, 118], [-8, -2, 136, 148]], 190, { scale: [0.8, 1.2] }), TREE), root);
  instanced(KIT.palm, place(scatter(rand, isLand, [[15, 27, -90, -75], [5, 15, 98, 106], [8, 15, 74, 80], [-12, -3, -40, -35], [-18, -12, 125, 145], [18, 23, -160, -154]], 90, { scale: [0.8, 1.2] }), TREE), root);
  instanced(KIT.cactus, place(scatter(rand, isLand, [[24, 36, -116, -103], [-28, -20, -71, -66]], 55, { scale: [0.7, 1.1] }), TREE), root);
  instanced(KIT.dune, place(scatter(rand, isLand, [[18, 30, -10, 30], [18, 28, 44, 55], [-30, -20, 120, 140], [-26, -18, 15, 22]], 120, { scale: [0.8, 1.4] })), root);
  instanced(KIT.iceberg, place(scatter(rand, isLand, [[68, 80, -70, 40], [-62, -55, -70, 30]], 22, { onLand: false, scale: [0.8, 1.4] })), root);

  // Whales: bob and spout in open water
  const whales = [[-10, -140], [35, -42], [-40, 80], [-45, -20]].map(([lat, lng], i) => {
    const w = new THREE.Group();
    w.add(part(sph(1.2, 12, 8), C.whale, [0, 0.2, 0], [0, 0, 0], [2, 0.75, 1]));
    w.add(part(sph(1.0, 12, 8), C.whaleBelly, [0.2, -0.05, 0], [0, 0, 0], [1.7, 0.45, 0.85], false));
    w.add(part(box(0.25, 0.9, 1.6), C.whale, [-2.6, 0.75, 0], [0, 0, 0.5]));      // tail
    const spout = part(cone(0.35, 1.2, 8), C.iceBlue, [1.2, 1.4, 0], [Math.PI, 0, 0], [1, 1, 1], false);
    w.add(spout);
    w.applyMatrix4(placeMatrix(lat, lng, 1, i * 1.7, 0.002));
    w.userData = { spout, base: w.position.clone(), n: w.position.clone().normalize(), i };
    root.add(w);
    return w;
  });

  // Wonders with hover tags
  const wonderObjs = WONDERS.map(([name, place_, lat, lng, build, s]) => {
    const obj = build();
    obj.applyMatrix4(placeMatrix(lat, lng, s * WONDER, 0));
    obj.userData.wonder = { name, place: place_ };
    obj.traverse(o => { if (o.isMesh) o.userData.owner = obj; });
    root.add(obj);
    return obj;
  });

  const container = document.getElementById('globe-container');
  const tag = document.createElement('div');
  tag.className = 'globe-popup';
  tag.style.pointerEvents = 'none';
  tag.style.minWidth = '0';
  container.parentElement.appendChild(tag);
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  container.addEventListener('mousemove', e => {
    const rect = container.getBoundingClientRect();
    ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    ray.setFromCamera(ndc, globe.camera());
    const hit = ray.intersectObjects(wonderObjs, true).find(h => h.object.userData.owner);
    if (hit) {
      const w = hit.object.userData.owner.userData.wonder;
      tag.innerHTML = `<div class="popup-title">🏛 ${w.name}</div><div class="popup-artist">${w.place}</div>`;
      tag.style.left = `${e.clientX - rect.left + 14}px`;
      tag.style.top = `${e.clientY - rect.top - 10}px`;
      tag.classList.add('visible');
    } else tag.classList.remove('visible');
  });
  container.addEventListener('mouseleave', () => tag.classList.remove('visible'));

  window.__relief = { root, wonders: wonderObjs, whales };
  const t0 = performance.now();
  (function tick() {
    const t = (performance.now() - t0) / 1000;
    for (const w of whales) {
      const { base, n, spout, i } = w.userData;
      w.position.copy(base).addScaledVector(n, Math.sin(t * 1.3 + i) * 0.35);
      spout.visible = Math.sin(t * 0.9 + i * 2) > 0.55;
    }
    requestAnimationFrame(tick);
  })();
});
