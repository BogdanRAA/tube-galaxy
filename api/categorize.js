// Vercel serverless function: sort newly found subscriptions into niches.
//
// POST /api/categorize
//   Authorization: Bearer <Google access token from the browser sign-in>
//   body: { channels: [{ channel_id, title, description }] }
// -> { results: [{ channel_id, niche, is_music_artist, subgenre }] }
//
// Guarded: the Google token is verified with Google and its email must be in
// ALLOWED_EMAILS, so only you can spend the model quota. The token is used for
// that one check and never stored.
//
// Env (Vercel project settings):
//   OPENROUTER_API_KEY  required  free key from openrouter.ai
//   ALLOWED_EMAILS      required  comma-separated Google emails allowed to call this
//   OPENROUTER_MODEL    optional  pin a model; default = live list of free nvidia/* models

const NICHES = ['Tech/AI', 'Music', 'Documentary', 'Gaming', 'Finance', 'Comedy', 'Education', 'Fitness',
  'News', 'Cooking', 'Travel', 'Design/Art', 'Business', 'Science', 'Lifestyle', 'Entertainment', 'Other'];
const SUBGENRES = ['Minimal', 'Micro House', 'Raw', 'Techno', 'EDM', 'Dance/Disco', 'Deep House',
  'Progressive', 'Ambient', 'Drum & Bass', 'Other Electronic', 'Non-Electronic'];
const OR = 'https://openrouter.ai/api/v1';
const BATCH = 25;

async function verifyGoogle(token) {
  const r = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) return null;
  const u = await r.json();
  return u.email_verified ? u.email.toLowerCase() : null;
}

async function freeNvidiaModels() {
  if (process.env.OPENROUTER_MODEL) return [process.env.OPENROUTER_MODEL];
  try {
    const { data } = await (await fetch(`${OR}/models`)).json();
    const free = data.filter(m => m.id.startsWith('nvidia/') && m.id.endsWith(':free'))
      .sort((a, b) => (b.context_length || 0) - (a.context_length || 0)).map(m => m.id);
    if (free.length) return free;
  } catch { /* fall through */ }
  return ['nvidia/nemotron-3.5-super-vl:free'];
}

function parseLoose(text) {
  text = (text || '').replace(/<think>[\s\S]*?<\/think>/g, '').trim().replace(/^```(?:json)?\s*|\s*```$/g, '');
  try { return JSON.parse(text); } catch { const m = text.match(/[\[{][\s\S]*[\]}]/); return m ? JSON.parse(m[0]) : null; }
}

async function classify(models, batch) {
  const prompt = `Classify each YouTube channel into exactly one niche and say whether it is a music artist, label or DJ.
Niches: ${NICHES.join(', ')}
If is_music_artist is true, also pick one subgenre: ${SUBGENRES.join(', ')} ("Non-Electronic" if not electronic).

Channels:
${batch.map((c, i) => `${i + 1}. ${c.title} | ${(c.description || '').replace(/\s+/g, ' ').slice(0, 300)}`).join('\n')}

Return JSON: {"results":[{"index":1,"niche":"...","is_music_artist":false,"subgenre":null}]} covering every channel.`;
  for (const model of models) {
    try {
      const r = await fetch(`${OR}/chat/completions`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`, 'Content-Type': 'application/json',
          'X-Title': 'Tube Galaxy' },
        body: JSON.stringify({ model, temperature: 0.1, response_format: { type: 'json_object' },
          messages: [{ role: 'system', content: 'Reply with valid JSON only.' }, { role: 'user', content: prompt }] }),
      });
      if (!r.ok) continue;                     // rate-limited or retired: next free model
      const out = parseLoose((await r.json()).choices?.[0]?.message?.content);
      const rows = Array.isArray(out) ? out : out?.results;
      if (Array.isArray(rows)) return rows;
    } catch { /* next model */ }
  }
  return [];
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  if (!process.env.OPENROUTER_API_KEY || !process.env.ALLOWED_EMAILS) {
    return res.status(501).json({ error: 'Categorizer not configured (OPENROUTER_API_KEY, ALLOWED_EMAILS).' });
  }
  const token = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  const email = token && await verifyGoogle(token);
  const allowed = process.env.ALLOWED_EMAILS.split(',').map(s => s.trim().toLowerCase());
  if (!email || !allowed.includes(email)) return res.status(403).json({ error: 'Not allowed.' });

  const channels = (req.body?.channels || []).slice(0, 300);
  const models = await freeNvidiaModels();
  const results = [];
  for (let i = 0; i < channels.length; i += BATCH) {
    const batch = channels.slice(i, i + BATCH);
    const rows = await classify(models, batch);
    batch.forEach((c, j) => {
      const row = rows.find(r => Number(r.index) === j + 1) || {};
      const niche = NICHES.includes(row.niche) ? row.niche : 'Other';
      const music = !!row.is_music_artist;
      results.push({ channel_id: c.channel_id, niche, is_music_artist: music,
        subgenre: music && SUBGENRES.includes(row.subgenre) ? row.subgenre : null });
    });
  }
  res.status(200).json({ results });
};
