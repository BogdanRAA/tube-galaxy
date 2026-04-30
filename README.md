# Tube Galaxy

> 936 subs. 12 subgenres. One galaxy.

Self-host an actual map of your YouTube subscriptions. Niche-classified channels, music artists tagged by subgenre, and a 3D globe pinning every concert near you.

[**Live demo (mine)**](https://youtube-dashboard-chi-swart.vercel.app) · [**Landing page**](https://tube-galaxy.vercel.app) · [Maker](https://github.com/BogdanAlRa)

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
git clone https://github.com/BogdanAlRa/tube-galaxy.git
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

## Five steps, one Python script each

| # | Script | What it does | Output |
|---|---|---|---|
| 1 | `extract/youtube_extract.py` | OAuth via Google API client. Pulls subs, playlists, liked videos. UC→UU playlist trick = 1 quota unit per channel for latest videos. | `data/subscriptions.json`, `data/playlists.json`, `data/liked_videos.json`, `data/channel_details.json` |
| 2 | `extract/categorize.py` | Sends each channel's name + description + recent video titles to Gemini 2.5 Flash. Batches of 12, 5s throttle. Tags niches + subgenres. | `data/categorized_subscriptions.json`, `data/niche_summary.json`, `data/music_artists.json` |
| 3 | `extract/concerts.py` | For each music artist, queries Ticketmaster Discovery + Bandsintown public endpoint. Geocodes venues. | `data/concerts.json` |
| 4 | `build.js` | Copies all `data/*.json` to `public/data/`. | `public/data/*.json` |
| 5 | `public/{index,music,globe}.html` | Static HTML. Reads JSON at runtime. No backend. | Live in browser |

## Customizing

- **Niche taxonomy** — edit the prompt template in `extract/categorize.py`
- **Music subgenre palette** — CSS variables in `public/globe.html`
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

Built by [Bogdan](https://github.com/BogdanAlRa). Two more tools: [Tab Orbit](https://tab-orbit.vercel.app) (auto-organize Chrome tabs, free extension) and [Meta Ad Analyzer](https://meta-ad-analyzer-eight.vercel.app) (Apify actor that decomposes competitor video ads, $0.20/video).
