# Tube Galaxy

> 936 subs. 12 subgenres. One galaxy.

Self-host an actual map of your YouTube subscriptions. Niche-classified channels, music artists tagged by subgenre, and a 3D globe pinning every concert near you.

[**Live demo (mine)**](https://youtube-dashboard-chi-swart.vercel.app) · [**Landing page**](https://tube-galaxy.vercel.app) · [Maker](https://github.com/BogdanRAA)

---

## What it does

YouTube gives you a flat list of every channel you've ever followed. Tube Galaxy turns it into:

- **Subscription Universe** — sidebar of every niche (Music · Tech · Documentary · etc.) with expandable channel cards
- **Music Artists** — 12 subgenre tabs (techno · house · ambient · D&B · etc.) with track lists
- **Concert Globe** — Globe.gl 3D render. Every artist's upcoming shows pinned to a world map, colored by subgenre

All your data, your machine, your keys. No SaaS. No telemetry. MIT licensed.

## Quick start (5 min)

### 1. Clone

```bash
git clone https://github.com/BogdanRAA/tube-galaxy.git
cd tube-galaxy
```

### 2. Set up Python deps

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install google-auth-oauthlib google-api-python-client google-generativeai requests
```

### 3. Get your three API keys

| Key | Where | Cost |
|---|---|---|
| Google OAuth (`client_secret.json`) | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → Create OAuth client ID → Desktop app → Download JSON, save as `extract/client_secret.json` | Free |
| Gemini API key | [aistudio.google.com](https://aistudio.google.com/apikey) → Create API key, set as `GOOGLE_API_KEY` env var | Free tier: 15 RPM (enough) |
| Ticketmaster Discovery API key | [developer.ticketmaster.com](https://developer.ticketmaster.com/) → My Apps → Create, set as `TICKETMASTER_API_KEY` env var | Free: 5,000 req/day |

### 4. Run the pipeline

```bash
export GOOGLE_API_KEY=your-gemini-key
export TICKETMASTER_API_KEY=your-ticketmaster-key
npm run pipeline   # extracts subs → categorizes → fetches concerts → builds public/data/
```

First run takes ~8-12 min for ~900 subs. Re-run anytime.

### 5. View locally

```bash
npx serve public
# open http://localhost:3000
```

Or deploy to Vercel:

```bash
vercel --prod
```

## The pipeline

| # | Script | What it does | Output |
|---|---|---|---|
| 1 | `extract/youtube_extract.py` | OAuth via Google API client. Pulls subs, playlists, liked videos. UC→UU playlist trick = 1 quota unit per channel for latest videos. | `data/subscriptions.json`, `data/playlists.json`, `data/liked_videos.json`, `data/channel_details.json` |
| 2 | `extract/categorize.py` | Sends each channel's name + description + recent video titles to Gemini 2.5 Flash. Batches of 12, 5s throttle. Tags niches + subgenres. | `data/categorized_subscriptions.json`, `data/niche_summary.json`, `data/music_artists.json` |
| 3 | `extract/concerts.py` | For each music artist, queries Ticketmaster Discovery + Bandsintown public endpoint. Geocodes venues. | `data/concerts.json` |
| 4 | `extract/index_videos.py` | Indexes videos from every subscribed channel for the agent. Incremental, quota-checkpointed. | `data/video_index.json` (local only) |
| 5 | `build.js` | Copies `data/*.json` to `public/data/` (skips the index). | `public/data/*.json` |
| 6 | `public/{index,music,globe,findings}.html` | Static HTML. Reads JSON at runtime. `findings.html` talks to the local agent when it's running. | Live in browser |

## The agent: search inside your own subscriptions

Ask in plain language ("vlogs of people going through Amazonian forests") and a local agent finds matching videos **only from channels you subscribe to**. Each request becomes its own tab under **Findings**. If your subs don't hold it, the agent says so instead of padding results, shows the nearest misses, and links a YouTube-wide search.

How one request runs:

1. **Decompose.** The model splits the request into concept groups with synonyms and other-language terms (rainforest, selva, floresta amazônica, Iquitos...) plus exclusions for false friends (Amazon Prime, Echo).
2. **Retrieve.** Keyword scoring over your local video index: title beats tags beats description, with a small boost when the channel itself is on-topic.
3. **Verify.** The model judges the top 60 candidates against your intent (0-3, one-line reason). Keyword hits are not answers.
4. **Report.** Found, thin, or not in your subs.

```bash
npm run index    # one-time: index your subs' videos (~1 quota unit per 50 videos; re-runs are incremental)
export OPENROUTER_API_KEY=sk-or-...   # free key at openrouter.ai
npm run agent    # serves the dashboard + agent on http://localhost:8787
```

Open `http://localhost:8787/findings.html`.

- **Model.** Defaults to a free NVIDIA Nemotron model on OpenRouter. The agent reads OpenRouter's live model list and falls back through the free `nvidia/*:free` models, since free IDs change. Pin one with `OPENROUTER_MODEL=...`. `GOOGLE_API_KEY` (Gemini) works too. With no key it falls back to plain keyword matching and marks findings unverified.
- **Depth.** `npm run index -- --max 1000` indexes deeper back catalogues; `--with-tags` adds video tags for better recall (doubles quota).
- **Privacy.** The server binds to 127.0.0.1. `video_index.json` is never copied to `public/` or deployed. Findings are, so a deployed site shows them read-only.

## Sign in with Google: live sync

The deployed dashboard shows the subscriptions baked in at the last `npm run pipeline`. Sign in with Google and it pulls your **current** subscriptions straight from YouTube: new channels appear (sorted into niches by `/api/categorize`, or filed under **New** if that isn't configured), unsubscribed ones disappear, and a badge shows `+added −removed`. The result is cached in that browser.

- The browser gets a short-lived, read-only token (`youtube.readonly`). It is held in memory only and never stored server-side.
- `/api/categorize` checks your Google token and only answers for emails in `ALLOWED_EMAILS`, so nobody else can spend your model quota.
- Sync costs about 1 YouTube quota unit per 50 subscriptions, plus 1 per new channel.

**One-time setup**

1. Google Cloud Console → APIs & Services → Credentials → **Create OAuth client ID → Web application**. Authorized JavaScript origins: your Vercel URL(s) and `http://localhost:8787`. (The extractor's existing *Desktop* client can't be used for this.)
2. OAuth consent screen → add your Google account as a **test user** (the YouTube scope shows an "unverified app" notice until Google verifies the app; for personal use you click through it).
3. Vercel → Project → Settings → Environment Variables:

| Variable | Value |
|---|---|
| `GOOGLE_CLIENT_ID` | the Web client ID from step 1 |
| `ALLOWED_EMAILS` | your Google email (comma-separate several) |
| `OPENROUTER_API_KEY` | free key from openrouter.ai (niche-sorting new channels) |

**Deploy** from the machine that has your `data/` (it's gitignored, so a GitHub-linked build would ship an empty site):

```bash
git pull && npm run build && vercel --prod
```

## Customizing

- **Niche taxonomy** — edit the prompt template in `extract/categorize.py`
- **Music subgenre palette** — CSS variables in `public/globe.html`
- **Globe look** — the cartoon Earth is baked from public-domain NASA imagery by `extract/bake_earth.py` (biome palette, snowline, ocean bands are all tunable there); wonders and scenery live in `public/landmarks.js`, satellites and stars in `public/orbit.js`
- **Concert sources** — add Spotify Concerts API or RA.co scraping in `concerts.py`
- **Layout** — the three HTML files are self-contained, no framework

## Privacy

- Your tokens never leave your machine. `client_secret.json` and `token.json` are gitignored.
- Your data lives in `data/` and gets copied to `public/data/` on build. Nothing else.
- The site has zero analytics, zero telemetry, zero third-party SDKs.
- Deploy to Vercel as a private project (only your Vercel auth can access) if you don't want public access.

## What about a SaaS version?

Three reasons it's self-host only for now:

1. **Per-user Gemini API costs** would be real (~$0.20-0.50 per ~900-channel account) — passing through subscription pricing gets clunky.
2. **YouTube Data API quotas** are per-project — multi-tenant means we'd hit caps fast and rate-limit you.
3. **Privacy story is cleaner** if your tokens never leave your machine.

A multi-tenant V2 with Supabase Auth + BYO Gemini key may come if there's real demand. For now, self-host is the right model.

## License

MIT — see [LICENSE](./LICENSE).

## Maker

Built by [Bogdan](https://github.com/BogdanRAA). Two more tools: [Tab Orbit](https://tab-orbit.vercel.app) (auto-organize Chrome tabs, free extension) and [Meta Ad Analyzer](https://meta-ad-analyzer-eight.vercel.app) (Apify actor that decomposes competitor video ads, $0.20/video).
