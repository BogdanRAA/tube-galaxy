// Build script: copies data JSON files to public/data/ for Vercel serving
const fs = require('fs');
const path = require('path');

const dataDir = path.join(__dirname, 'data');
const publicDataDir = path.join(__dirname, 'public', 'data');

// Create public/data if it doesn't exist
if (!fs.existsSync(publicDataDir)) {
  fs.mkdirSync(publicDataDir, { recursive: true });
}

// Copy all JSON files from data/ to public/data/
const files = fs.readdirSync(dataDir).filter(f => f.endsWith('.json'));
for (const file of files) {
  fs.copyFileSync(path.join(dataDir, file), path.join(publicDataDir, file));
  console.log(`Copied ${file} to public/data/`);
}

console.log(`Build complete: ${files.length} data files copied.`);
