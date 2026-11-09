// Build script: copies data JSON files to public/data/ for Vercel serving
const fs = require('fs');
const path = require('path');

const dataDir = path.join(__dirname, 'data');
const publicDataDir = path.join(__dirname, 'public', 'data');

// Create public/data if it doesn't exist
if (!fs.existsSync(publicDataDir)) {
  fs.mkdirSync(publicDataDir, { recursive: true });
}

// No local data (e.g. building on Vercel from GitHub, where data/ is gitignored)?
// Pull it from an existing deployment: TG_DATA_URL=https://<old-site>/data
const DATA_FILES = ['categorized_subscriptions.json', 'latest_videos.json', 'niche_summary.json', 'meta.json',
  'music_artists.json', 'concerts.json', 'subscriptions.json', 'channel_details.json', 'playlists.json', 'liked_videos.json'];

async function pullRemoteData() {
  const base = (process.env.TG_DATA_URL || '').replace(/\/$/, '');
  const hasLocal = fs.existsSync(dataDir) && fs.readdirSync(dataDir).some(f => f.endsWith('.json') && f !== '.gitkeep.json');
  if (!base || hasLocal) return;
  fs.mkdirSync(dataDir, { recursive: true });
  for (const f of DATA_FILES) {
    try {
      const r = await fetch(`${base}/${f}`);
      if (!r.ok) { console.log(`  skip ${f} (${r.status})`); continue; }
      fs.writeFileSync(path.join(dataDir, f), Buffer.from(await r.arrayBuffer()));
      console.log(`Pulled ${f} from ${base}`);
    } catch (e) { console.log(`  skip ${f} (${e.message})`); }
  }
}

(async () => {
await pullRemoteData();

// Copy all JSON files from data/ to public/data/
// video_index.json is the agent's private search index: large, local-only, never deployed.
const LOCAL_ONLY = new Set(['video_index.json']);
const files = fs.readdirSync(dataDir).filter(f => f.endsWith('.json') && !LOCAL_ONLY.has(f));
for (const file of files) {
  fs.copyFileSync(path.join(dataDir, file), path.join(publicDataDir, file));
  console.log(`Copied ${file} to public/data/`);
}

console.log(`Build complete: ${files.length} data files copied.`);

// Public runtime config for the browser (a Google OAuth client ID is public by
// design; secrets such as OPENROUTER_API_KEY stay server-side in /api).
const config = { googleClientId: process.env.GOOGLE_CLIENT_ID || '' };
fs.writeFileSync(path.join(__dirname, 'public', 'config.js'),
  `window.TG_CONFIG = ${JSON.stringify(config)};\n`);
console.log(`Wrote public/config.js (Google sign-in ${config.googleClientId ? 'enabled' : 'disabled: set GOOGLE_CLIENT_ID'}).`);
})();
