// Sign in with Google + live subscription sync for the Universe page.
//
// Flow: Google Identity Services gives this browser a short-lived, read-only
// YouTube token (scope youtube.readonly). The browser pulls your current
// subscriptions straight from the YouTube Data API, diffs them against the
// baked data, adds new channels (niche-sorted by /api/categorize when it is
// configured, otherwise filed under "New"), drops unsubscribed ones, and
// caches the result in this browser so it survives reloads.
//
// The token lives in memory only and expires within the hour. Config comes
// from /config.js, which build.js writes from the GOOGLE_CLIENT_ID env var.
(() => {
  const CFG = window.TG_CONFIG || {};
  const SCOPES = 'https://www.googleapis.com/auth/youtube.readonly openid email profile';
  const CACHE_KEY = 'tg_sync_v1';
  const YT = 'https://www.googleapis.com/youtube/v3';
  let token = null;
  let baseChannels = null;     // the baked list, kept so a re-sync diffs against it

  const store = {
    get() { try { return JSON.parse(localStorage.getItem(CACHE_KEY)); } catch { return null; } },
    set(v) { try { localStorage.setItem(CACHE_KEY, JSON.stringify(v)); } catch { /* private mode */ } },
    clear() { try { localStorage.removeItem(CACHE_KEY); } catch { /* ignore */ } },
  };

  // ── UI ────────────────────────────────────────────────────────────────────
  const css = document.createElement('style');
  css.textContent = `
    .tg-auth { display:flex; align-items:center; gap:10px; }
    .tg-btn { display:flex; align-items:center; gap:8px; background:#fff; color:#1f1f1f; border:0; border-radius:6px;
      padding:6px 12px; font-size:12.5px; font-weight:600; cursor:pointer; white-space:nowrap; }
    .tg-btn:disabled { opacity:.6; cursor:wait; }
    .tg-btn.ghost { background:transparent; color:var(--text-muted,#888); border:1px solid var(--border-light,#2a2a2a); }
    .tg-btn svg { width:15px; height:15px; }
    .tg-user { display:flex; align-items:center; gap:7px; font-size:12px; color:var(--text-muted,#888); }
    .tg-user img { width:22px; height:22px; border-radius:50%; }
    .tg-badge { font-size:11px; color:var(--text-dim,#666); }
    .tg-badge b { color:#3ddc84; font-weight:600; } .tg-badge i { color:#ff6b6b; font-style:normal; font-weight:600; }
  `;
  document.head.appendChild(css);

  const G_ICON = '<svg viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>';

  const slot = document.createElement('div');
  slot.className = 'tg-auth';
  (document.querySelector('.nav-meta') || document.querySelector('nav') || document.body).prepend(slot);

  function renderAuth(state = {}) {
    if (!CFG.googleClientId) {
      slot.innerHTML = '';                          // not configured: stay out of the way
      return;
    }
    const cache = store.get();
    const badge = cache ? `<span class="tg-badge">synced ${ago(cache.synced_at)} · <b>+${cache.added.length}</b> <i>−${cache.removed.length}</i></span>` : '';
    if (state.user) {
      slot.innerHTML = `${badge}
        <span class="tg-user">${state.user.picture ? `<img src="${esc(state.user.picture)}" alt="">` : ''}${esc(state.user.given_name || state.user.email)}</span>
        <button class="tg-btn ghost" id="tgSync">${state.busy ? 'Syncing…' : 'Sync now'}</button>
        <button class="tg-btn ghost" id="tgOut">Sign out</button>`;
      slot.querySelector('#tgSync').onclick = () => sync();
      slot.querySelector('#tgSync').disabled = !!state.busy;
      slot.querySelector('#tgOut').onclick = signOut;
    } else {
      slot.innerHTML = `${badge}<button class="tg-btn" id="tgIn">${G_ICON}${state.busy ? 'Connecting…' : 'Sign in with Google'}</button>`;
      slot.querySelector('#tgIn').onclick = signIn;
      slot.querySelector('#tgIn').disabled = !!state.busy;
    }
  }

  // ── Google sign-in (GIS token model) ──────────────────────────────────────
  let tokenClient = null;
  function loadGis() {
    return new Promise((res, rej) => {
      if (window.google?.accounts?.oauth2) return res();
      const s = document.createElement('script');
      s.src = 'https://accounts.google.com/gsi/client';
      s.async = true; s.onload = res; s.onerror = () => rej(new Error('Could not load Google sign-in'));
      document.head.appendChild(s);
    });
  }

  async function signIn() {
    renderAuth({ busy: true });
    try {
      await loadGis();
      tokenClient = tokenClient || google.accounts.oauth2.initTokenClient({
        client_id: CFG.googleClientId, scope: SCOPES, callback: () => {},
      });
      const resp = await new Promise((res, rej) => {
        tokenClient.callback = r => (r.error ? rej(new Error(r.error)) : res(r));
        tokenClient.error_callback = e => rej(new Error(e.type || 'popup closed'));
        tokenClient.requestAccessToken({ prompt: '' });
      });
      token = resp.access_token;
      const user = await api('https://www.googleapis.com/oauth2/v3/userinfo');
      renderAuth({ user });
      await sync(user);
    } catch (e) {
      console.warn('[sync] sign-in failed:', e);
      renderAuth();
    }
  }

  function signOut() {
    if (token && window.google?.accounts?.oauth2) google.accounts.oauth2.revoke(token, () => {});
    token = null;
    store.clear();
    if (baseChannels) applyChannels(baseChannels, {});
    renderAuth();
  }

  // ── YouTube Data API (1 quota unit per page of 50) ────────────────────────
  async function api(url) {
    const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) throw new Error(`${r.status} ${url.split('?')[0]}`);
    return r.json();
  }

  async function fetchSubscriptions() {
    const out = [];
    let page = '';
    do {
      const d = await api(`${YT}/subscriptions?part=snippet&mine=true&maxResults=50&order=alphabetical${page ? `&pageToken=${page}` : ''}`);
      for (const it of d.items || []) {
        const s = it.snippet;
        out.push({ channel_id: s.resourceId.channelId, title: s.title, description: s.description || '',
          thumbnail: s.thumbnails?.default?.url || '', published_at: s.publishedAt || '' });
      }
      page = d.nextPageToken || '';
    } while (page);
    return out;
  }

  async function fetchDetails(ids) {
    const out = {};
    for (let i = 0; i < ids.length; i += 50) {
      const d = await api(`${YT}/channels?part=statistics,snippet&id=${ids.slice(i, i + 50).join(',')}`);
      for (const it of d.items || []) out[it.id] = { subscriber_count: it.statistics?.subscriberCount || '0',
        video_count: it.statistics?.videoCount || '0', custom_url: it.snippet?.customUrl || '' };
    }
    return out;
  }

  async function fetchLatest(ids) {
    const out = {};
    await Promise.all(ids.map(async id => {
      try {
        const d = await api(`${YT}/playlistItems?part=snippet&maxResults=5&playlistId=UU${id.slice(2)}`);
        out[id] = (d.items || []).map(it => ({ video_id: it.snippet.resourceId?.videoId, title: it.snippet.title,
          thumbnail: it.snippet.thumbnails?.medium?.url || '', published_at: it.snippet.publishedAt }));
      } catch { out[id] = []; }
    }));
    return out;
  }

  async function categorize(channels) {
    if (!channels.length) return {};
    try {
      const r = await fetch('/api/categorize', { method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ channels: channels.map(c => ({ channel_id: c.channel_id, title: c.title, description: c.description })) }) });
      if (!r.ok) throw new Error(r.status);
      return Object.fromEntries((await r.json()).results.map(x => [x.channel_id, x]));
    } catch (e) {
      console.info('[sync] categorizer unavailable, filing new channels under "New":', e.message);
      return {};
    }
  }

  // ── Sync + merge ──────────────────────────────────────────────────────────
  async function sync(user) {
    if (!token) return signIn();
    const u = user || { email: '' };
    renderAuth({ user: u, busy: true });
    try {
      const live = await fetchSubscriptions();
      const base = baseChannels || [];
      const known = new Set(base.map(c => c.channel_id));
      const liveIds = new Set(live.map(c => c.channel_id));
      const fresh = live.filter(c => !known.has(c.channel_id));
      const removed = base.filter(c => !liveIds.has(c.channel_id)).map(c => c.channel_id);

      const [details, latest, cats] = await Promise.all([
        fetchDetails(fresh.map(c => c.channel_id)), fetchLatest(fresh.map(c => c.channel_id)), categorize(fresh)]);
      const added = fresh.map(c => ({ ...c, ...(details[c.channel_id] || {}),
        niche: cats[c.channel_id]?.niche || 'New',
        is_music_artist: !!cats[c.channel_id]?.is_music_artist,
        subgenre: cats[c.channel_id]?.subgenre || null, _new: true }));

      const cache = { synced_at: new Date().toISOString(), added, removed, latest };
      store.set(cache);
      applyCache(cache);
      renderAuth({ user: u });
    } catch (e) {
      console.warn('[sync] failed:', e);
      renderAuth({ user: u });
    }
  }

  function applyCache(cache) {
    const gone = new Set(cache.removed);
    const merged = (baseChannels || []).filter(c => !gone.has(c.channel_id)).concat(cache.added);
    applyChannels(merged, cache.latest || {});
  }

  function applyChannels(list, extraVideos) {
    // Universe page globals (top-level lets in index.html's script).
    allChannels = list;
    latestVideos = { ...latestVideos, ...extraVideos };
    nicheSummary = buildNicheSummaryLocal(list);
    document.getElementById('navSubCount').textContent = list.length.toLocaleString();
    buildSidebar();
    renderChannels();
  }

  // ── helpers ───────────────────────────────────────────────────────────────
  function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
  function ago(iso) {
    const m = Math.round((Date.now() - new Date(iso)) / 60000);
    return m < 1 ? 'just now' : m < 60 ? `${m}m ago` : m < 1440 ? `${Math.round(m / 60)}h ago` : `${Math.round(m / 1440)}d ago`;
  }

  // Wait for index.html to finish its own load, then layer any cached sync on top.
  const wait = setInterval(() => {
    if (typeof allChannels === 'undefined' || !allChannels.length) return;
    clearInterval(wait);
    baseChannels = allChannels.slice();
    const cache = store.get();
    if (cache) applyCache(cache);
    renderAuth();
  }, 150);
  renderAuth();
})();
