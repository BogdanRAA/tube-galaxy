// Orbit layer for the concert globe: a starfield and seven toy-like satellites
// on their own orbits, rendered inside globe.gl's scene so Earth occludes them.
//
// Look: chunky toon shading with ink outlines (inverted-hull), bright panels,
// dashed orbit paths. Everything is built from primitives in code: no model
// files, nothing fetched besides three.js itself.
//
// three.js is pinned to r157, the revision bundled inside globe.gl 2.30, so
// objects built here render with globe.gl's renderer without surprises.
import * as THREE from 'https://unpkg.com/three@0.157.0/build/three.module.min.js';

const R = 100;                 // globe.gl's globe radius in scene units
const INK = 0x0b0820;          // outline colour
const SIZE = 0.85;             // global satellite scale
const SPEED = matchMedia('(prefers-reduced-motion: reduce)').matches ? 0.15 : 1;

// ─── materials ──────────────────────────────────────────────────────────────

const ramp = (() => {          // 3-step toon ramp: hard shadow, mid, lit
  const tx = new THREE.DataTexture(new Uint8Array([70, 150, 255]), 3, 1, THREE.RedFormat);
  tx.minFilter = tx.magFilter = THREE.NearestFilter;
  tx.needsUpdate = true;
  return tx;
})();
const toon = (color, extra = {}) => new THREE.MeshToonMaterial({ color, gradientMap: ramp, ...extra });
const outlineMat = new THREE.MeshBasicMaterial({ color: INK, side: THREE.BackSide });

function panelTexture(base, line) {
  const c = document.createElement('canvas');
  c.width = 64; c.height = 128;
  const g = c.getContext('2d');
  g.fillStyle = base; g.fillRect(0, 0, 64, 128);
  g.strokeStyle = line; g.lineWidth = 3;
  for (let x = 0; x <= 64; x += 16) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, 128); g.stroke(); }
  for (let y = 0; y <= 128; y += 16) { g.beginPath(); g.moveTo(0, y); g.lineTo(64, y); g.stroke(); }
  const tx = new THREE.CanvasTexture(c);
  tx.colorSpace = THREE.SRGBColorSpace;
  return tx;
}

const M = {
  panel: toon(0xffffff, { map: panelTexture('#1f56e0', '#9cc0ff') }),
  goldPanel: toon(0xffffff, { map: panelTexture('#d4901a', '#ffe28a') }),
  white: toon(0xf4f4ff),
  silver: toon(0xc9d2e6),
  grey: toon(0x7d86a3),
  dark: toon(0x2a2f45),
  gold: toon(0xffbf2e),
  orange: toon(0xff7a2e),
  red: toon(0xff3d5a),
};

// A mesh plus its ink outline (back faces of a slightly larger copy).
function part(geo, mat, { pos = [0, 0, 0], rot = [0, 0, 0], outline = true, grow = 1.07 } = {}) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(geo, mat));
  if (outline) {
    const o = new THREE.Mesh(geo, outlineMat);
    o.scale.setScalar(grow);
    g.add(o);
  }
  g.position.set(...pos);
  g.rotation.set(...rot);
  return g;
}
const box = (x, y, z) => new THREE.BoxGeometry(x, y, z);
const cyl = (r, h, s = 16) => new THREE.CylinderGeometry(r, r, h, s);
const blinker = (color, pos) => {
  const m = new THREE.Mesh(new THREE.SphereGeometry(0.22, 8, 8), new THREE.MeshBasicMaterial({ color }));
  m.position.set(...pos);
  m.userData.blink = true;
  return m;
};

// ─── satellites (+X = along-track, +Y = away from Earth) ────────────────────

function iss() {
  const s = new THREE.Group();
  s.add(part(box(15, 0.45, 0.45), M.grey));                                    // main truss
  for (const x of [-6.6, -4.7, 4.7, 6.6]) for (const z of [2.6, -2.6]) {
    s.add(part(box(1.3, 0.06, 4.4), M.goldPanel, { pos: [x, 0, z], grow: 1.04 })); // solar wings
  }
  s.add(part(cyl(0.65, 5.2), M.white, { rot: [Math.PI / 2, 0, 0] }));          // lab modules
  s.add(part(new THREE.SphereGeometry(0.85, 16, 12), M.white));                // node
  s.add(part(cyl(0.55, 2.6), M.silver, { pos: [0, 0, -3.6], rot: [Math.PI / 2, 0, 0] }));
  s.add(part(box(0.06, 2.2, 1.6), M.white, { pos: [2.2, -1.3, 0] }));          // radiators
  s.add(part(box(0.06, 2.2, 1.6), M.white, { pos: [-2.2, -1.3, 0] }));
  s.add(blinker(0xff3d5a, [7.6, 0, 0]), blinker(0x3dff8a, [-7.6, 0, 0]));
  return s;
}

function telescope() {
  const s = new THREE.Group();
  s.add(part(cyl(1.05, 5.2, 20), M.silver, { rot: [0, 0, Math.PI / 2] }));    // tube
  s.add(part(cyl(1.08, 0.5, 20), M.dark, { pos: [2.5, 0, 0], rot: [0, 0, Math.PI / 2] })); // aperture ring
  s.add(part(box(0.1, 0.06, 2.1), M.grey, { pos: [3.1, 1.0, 0], rot: [0, 0, -0.9] }));    // open door
  for (const z of [2.4, -2.4]) s.add(part(box(2.6, 0.06, 1.7), M.panel, { pos: [-0.6, 0, z], grow: 1.04 }));
  s.add(blinker(0xffe94a, [-2.8, 0, 0]));
  return s;
}

function gps() {
  const s = new THREE.Group();
  s.add(part(box(1.7, 1.7, 1.7), M.gold));
  s.add(part(box(0.9, 0.5, 0.9), M.white, { pos: [0, -1.1, 0] }));            // Earth-facing antenna block
  for (const z of [3.1, -3.1]) s.add(part(box(1.6, 0.06, 4.2), M.panel, { pos: [0, 0, z], grow: 1.04 }));
  for (const z of [0.95, -0.95]) s.add(part(cyl(0.08, 0.5), M.grey, { pos: [0, 0, z * 1.1], rot: [Math.PI / 2, 0, 0], outline: false }));
  return s;
}

function relay() {
  const s = new THREE.Group();
  s.add(part(box(1.9, 1.5, 1.5), M.orange));
  const dish = new THREE.SphereGeometry(2.1, 28, 12, 0, Math.PI * 2, 0, 0.62);
  const dishMat = toon(0xf4f4ff, { side: THREE.DoubleSide });
  s.add(part(dish, dishMat, { pos: [0, -3.0, 0], outline: false }));          // big dish facing Earth
  s.add(part(cyl(0.09, 2.2), M.grey, { pos: [0, -1.6, 0], outline: false }));  // feed arm
  for (const z of [3.7, -3.7]) s.add(part(box(1.4, 0.06, 5.2), M.panel, { pos: [0, 0.2, z], grow: 1.04 }));
  s.add(blinker(0xff3d5a, [0, 0.9, 0]));
  return s;
}

function cubesat() {
  const s = new THREE.Group();
  s.add(part(box(1.1, 1.1, 1.1), M.dark));
  s.add(part(box(1.12, 0.12, 1.12), M.gold, { pos: [0, 0.5, 0], outline: false }));
  for (const [x, z] of [[1.2, 0], [-1.2, 0], [0, 1.2], [0, -1.2]]) {
    s.add(part(box(x ? 1.3 : 1.05, 0.05, z ? 1.3 : 1.05), M.panel, { pos: [x, -0.55, z], grow: 1.05 }));
  }
  s.add(part(cyl(0.03, 1.6, 6), M.silver, { pos: [0, 1.3, 0], outline: false }));
  s.userData.tumble = new THREE.Vector3(0.21, 0.37, 0.13);
  return s;
}

function sputnik() {
  const s = new THREE.Group();
  s.add(part(new THREE.SphereGeometry(0.95, 24, 18), M.silver));
  for (const [y, z] of [[0.35, 0.35], [0.35, -0.35], [-0.35, 0.35], [-0.35, -0.35]]) {
    const a = part(cyl(0.035, 4.6, 6), M.silver, { outline: false });
    a.position.set(-2.5, y, z);
    a.rotation.set(0, 0, Math.PI / 2 + (y > 0 ? -0.12 : 0.12));
    a.rotation.y = z > 0 ? 0.12 : -0.12;
    s.add(a);
  }
  s.userData.tumble = new THREE.Vector3(0.6, 0, 0);
  return s;
}

function weather() {
  const s = new THREE.Group();
  s.add(part(box(1.5, 1.9, 1.5), M.white));
  s.add(part(cyl(0.45, 0.7), M.dark, { pos: [0, -1.25, 0] }));                // imager
  s.add(part(cyl(0.06, 2.2), M.grey, { pos: [0, 0, 1.8], rot: [Math.PI / 2, 0, 0], outline: false })); // boom
  s.add(part(box(2.4, 0.06, 3.6), M.panel, { pos: [0, 0, 4.6], grow: 1.04 })); // single wing
  s.add(part(cyl(0.03, 3.2, 6), M.silver, { pos: [0, 0, -2.2], rot: [Math.PI / 2, 0, 0], outline: false })); // magnetometer
  s.add(blinker(0x3dd6ff, [0, 1.1, 0]));
  return s;
}

// alt = orbit radius in globe radii. incl / node in degrees. period in seconds.
const FLEET = [
  { name: 'ISS', note: 'International Space Station · crewed', build: iss, alt: 1.28, incl: 51.6, node: 20, period: 46, phase: 0.0, color: 0xffd23f, scale: 1.25 },
  { name: 'Space Telescope', note: 'Optical observatory', build: telescope, alt: 1.38, incl: 28.5, node: 140, period: 58, phase: 0.35, color: 0x9cc0ff, scale: 1.4 },
  { name: 'GPS', note: 'Navigation constellation', build: gps, alt: 1.62, incl: 55, node: 250, period: 84, phase: 0.6, color: 0x7dff4a, scale: 1.3 },
  { name: 'Comms Relay', note: 'High-orbit relay, big dish', build: relay, alt: 1.74, incl: 4, node: 0, period: 98, phase: 0.15, color: 0xff7a2e, scale: 1.2 },
  { name: 'CubeSat', note: 'Shoebox-sized research sat', build: cubesat, alt: 1.22, incl: 97, node: 300, period: 40, phase: 0.8, color: 0xff4fd8, scale: 1.6 },
  { name: 'Sputnik', note: 'First artificial satellite, 1957', build: sputnik, alt: 1.46, incl: 65, node: 80, period: 64, phase: 0.5, color: 0xe8e8ff, scale: 1.5 },
  { name: 'Weather Sat', note: 'Polar weather imager', build: weather, alt: 1.33, incl: 98.7, node: 200, period: 52, phase: 0.25, color: 0x3dd6ff, scale: 1.35 },
];

// ─── orbit maths ────────────────────────────────────────────────────────────

function orbitBasis(incl, node) {
  // Equatorial circle in globe.gl's frame (Y = north), tilted by inclination
  // about X, then swung about Y to its ascending node.
  return new THREE.Quaternion().setFromEuler(
    new THREE.Euler(THREE.MathUtils.degToRad(incl), THREE.MathUtils.degToRad(node), 0, 'YXZ'));
}

function orbitLine(r, q, color) {
  const pts = [];
  for (let i = 0; i <= 160; i++) {
    const a = (i / 160) * Math.PI * 2;
    pts.push(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r).applyQuaternion(q));
  }
  const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineDashedMaterial({ color, dashSize: 3, gapSize: 4, transparent: true, opacity: 0.32 }));
  line.computeLineDistances();
  return line;
}

// ─── starfield ──────────────────────────────────────────────────────────────

function stars(count, rMin, rMax, size, opacity) {
  const pos = new Float32Array(count * 3);
  const col = new Float32Array(count * 3);
  const tint = [[1, 1, 1], [0.8, 0.85, 1], [1, 0.92, 0.8], [0.85, 0.8, 1]];
  for (let i = 0; i < count; i++) {
    const v = new THREE.Vector3().randomDirection().multiplyScalar(rMin + Math.random() * (rMax - rMin));
    pos.set([v.x, v.y, v.z], i * 3);
    col.set(tint[i % tint.length], i * 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({
    size, sizeAttenuation: false, vertexColors: true, transparent: true, opacity, depthWrite: false }));
}

// ─── wire into globe.gl ─────────────────────────────────────────────────────

function waitForGlobe() {
  return new Promise(res => {
    const t = setInterval(() => {
      // `globe` / `globeReady` are top-level lets in globe.html's classic script.
      if (typeof globeReady !== 'undefined' && globeReady && globe) { clearInterval(t); res(globe); }
    }, 100);
  });
}

waitForGlobe().then(globe => {
  const scene = globe.scene();
  const camera = globe.camera();
  if (camera.far < 6000) { camera.far = 6000; camera.updateProjectionMatrix(); }

  const root = new THREE.Group();
  root.name = 'orbit-layer';
  scene.add(root);

  const farStars = stars(2600, 2200, 3200, 1.3, 0.75);
  const nearStars = stars(260, 1800, 2200, 2.4, 0.95);
  root.add(farStars, nearStars);

  const sats = FLEET.map(def => {
    const obj = def.build();
    obj.scale.setScalar(def.scale * SIZE);
    obj.userData.def = def;
    obj.traverse(o => { if (o.isMesh) o.userData.sat = obj; });
    const r = R * def.alt;
    const q = orbitBasis(def.incl, def.node);
    root.add(orbitLine(r, q, def.color));
    root.add(obj);
    return { obj, def, r, q };
  });
  const state = window.__orbit = { sats, root, paused: false }; // console handle; set paused to freeze

  // Hover a satellite -> name tag (reuses the pin popup styling).
  const container = document.getElementById('globe-container');
  const tag = document.createElement('div');
  tag.className = 'globe-popup';
  tag.style.pointerEvents = 'none';
  tag.style.minWidth = '0';
  container.parentElement.appendChild(tag);
  const ray = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  const targets = sats.map(s => s.obj);
  container.addEventListener('mousemove', e => {
    const rect = container.getBoundingClientRect();
    ndc.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(targets, true).find(h => h.object.userData.sat);
    if (hit) {
      const d = hit.object.userData.sat.userData.def;
      tag.innerHTML = `<div class="popup-title">🛰 ${d.name}</div><div class="popup-artist">${d.note}</div>`;
      tag.style.left = `${e.clientX - rect.left + 14}px`;
      tag.style.top = `${e.clientY - rect.top - 10}px`;
      tag.classList.add('visible');
    } else {
      tag.classList.remove('visible');
    }
  });
  container.addEventListener('mouseleave', () => tag.classList.remove('visible'));

  // Animate. globe.gl renders every frame; we just move things before it does.
  const p = new THREE.Vector3(), v = new THREE.Vector3(), up = new THREE.Vector3();
  let t = 0, last = performance.now();
  (function tick() {
    const now = performance.now();
    if (!state.paused) t += ((now - last) / 1000) * SPEED;
    last = now;
    for (const { obj, def, r, q } of sats) {
      const a = (t / def.period + def.phase) * Math.PI * 2;
      p.set(Math.cos(a) * r, 0, Math.sin(a) * r).applyQuaternion(q);
      v.set(-Math.sin(a), 0, Math.cos(a)).applyQuaternion(q);          // along-track
      up.copy(p).normalize();                                           // away from Earth
      obj.position.copy(p);
      obj.up.copy(up);
      obj.lookAt(p.clone().add(v));
      obj.rotateY(-Math.PI / 2);                                        // models are built nose-along +X
      if (obj.userData.tumble) {
        const s = obj.userData.tumble;
        obj.rotateX(s.x * t); obj.rotateY(s.y * t); obj.rotateZ(s.z * t);
      }
      obj.traverse(o => { if (o.userData.blink) o.visible = Math.sin(t * 5 + def.phase * 10) > 0.2; });
    }
    nearStars.material.opacity = 0.75 + Math.sin(t * 1.7) * 0.2;        // gentle twinkle
    requestAnimationFrame(tick);
  })();
});
