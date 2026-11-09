"""Tube Galaxy agent: find videos inside YOUR subscriptions only.

Pipeline for one request ("vlogs of people going through Amazonian forests"):
  1. decompose  - LLM breaks the request into concept groups (AND between
                  groups, OR inside a group), plus multilingual synonyms and
                  exclusions that kill false friends ("Amazon Prime", "FBA").
  2. retrieve   - lexical scoring over data/video_index.json (title > tags >
                  description, small boost when the channel itself is on-topic).
  3. verify     - LLM judges the top candidates against the original intent,
                  0-3, with a one-line reason. Keyword hits are not answers.
  4. report     - verdict: found / thin / not_in_subs. A "no" is a real answer:
                  it says what was searched, the nearest misses, and gives a
                  link to search YouTube outside your subs.

No third-party Python deps: models are called over REST with urllib.
Default model: a free NVIDIA Nemotron via OpenRouter (OPENROUTER_API_KEY).
Gemini (GOOGLE_API_KEY) also works. With no key it still works, using naive keyword splitting and no
verification; such findings are marked unverified.
"""

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data'
PUBLIC_DATA_DIR = ROOT / 'public' / 'data'
INDEX_PATH = DATA_DIR / 'video_index.json'
FINDINGS_PATH = DATA_DIR / 'findings.json'

CANDIDATES_TO_VERIFY = 60
MAX_PER_CHANNEL = 8          # keep one prolific channel from flooding the shortlist
MAX_RESULTS = 40

STOPWORDS = set("""a an and are as at be by find for from get give go going i in into is it
me my of on or people person show some something that the their them these this those through
to up video videos vlog vlogs want watch where which who with youtube""".split())


# ─── LLM ────────────────────────────────────────────────────────────────────
# Provider order: OpenRouter (default, free NVIDIA Nemotron models) > Gemini > none.
# OPENROUTER_MODEL pins a model; otherwise the agent asks OpenRouter which free
# NVIDIA models exist right now and falls back through them, because free model
# IDs get renamed and retired often.

OPENROUTER_URL = 'https://openrouter.ai/api/v1'
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
_free_models = {'at': 0, 'ids': [], 'json_ok': set()}


def provider():
    if os.environ.get('OPENROUTER_API_KEY'):
        return 'openrouter'
    if os.environ.get('GOOGLE_API_KEY'):
        return 'gemini'
    return None


def llm_available():
    return provider() is not None


def _http_json(url, body=None, headers=None, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 method='POST' if body is not None else 'GET',
                                 headers={'Content-Type': 'application/json', **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def openrouter_models():
    """Pinned model, or the live list of free NVIDIA models (refreshed hourly)."""
    pinned = os.environ.get('OPENROUTER_MODEL')
    if pinned:
        return [pinned]
    if time.time() - _free_models['at'] > 3600 or not _free_models['ids']:
        try:
            data = _http_json(f'{OPENROUTER_URL}/models', timeout=30)['data']
            free = [m for m in data if m['id'].startswith('nvidia/') and m['id'].endswith(':free')]
            # Prefer models that support JSON mode, then bigger context windows.
            free.sort(key=lambda m: ('response_format' in (m.get('supported_parameters') or []),
                                     m.get('context_length') or 0), reverse=True)
            _free_models.update(at=time.time(), ids=[m['id'] for m in free],
                                json_ok={m['id'] for m in free if 'response_format' in (m.get('supported_parameters') or [])})
        except Exception:
            pass
        if not _free_models['ids']:
            _free_models['ids'] = ['nvidia/nemotron-3.5-super-vl:free']  # last known good, Nov 2026
            _free_models['json_ok'] = set(_free_models['ids'])
    return _free_models['ids']


def current_model():
    p = provider()
    if p == 'openrouter':
        return openrouter_models()[0]
    return GEMINI_MODEL if p == 'gemini' else None


def parse_json_loose(text):
    """Models sometimes wrap JSON in fences or prose (or think out loud first)."""
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S).strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'[\[{].*[\]}]', text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def _openrouter_call(model, prompt):
    body = {'model': model, 'temperature': 0.2,
            'messages': [{'role': 'system', 'content': 'Reply with valid JSON only. No prose, no code fences.'},
                         {'role': 'user', 'content': prompt}]}
    if model in _free_models['json_ok'] or os.environ.get('OPENROUTER_MODEL'):
        body['response_format'] = {'type': 'json_object'}
    data = _http_json(f'{OPENROUTER_URL}/chat/completions', body, headers={
        'Authorization': f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        'HTTP-Referer': 'https://github.com/BogdanRAA/tube-galaxy', 'X-Title': 'Tube Galaxy'})
    if 'error' in data:
        raise RuntimeError(data['error'].get('message', str(data['error'])))
    return data['choices'][0]['message'].get('content') or ''


def _gemini_call(prompt):
    url = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'
    data = _http_json(url, {'contents': [{'parts': [{'text': prompt}]}],
                            'generationConfig': {'responseMimeType': 'application/json', 'temperature': 0.2}},
                      headers={'x-goog-api-key': os.environ['GOOGLE_API_KEY']})
    return data['candidates'][0]['content']['parts'][0]['text']


def llm_json(prompt):
    """Return parsed JSON (always an object) from whichever provider is configured.
    On OpenRouter, a failing or rate-limited free model hands over to the next one."""
    errors = []
    if provider() == 'openrouter':
        for model in openrouter_models():
            for attempt in range(2):
                try:
                    return parse_json_loose(_openrouter_call(model, prompt))
                except urllib.error.HTTPError as e:
                    errors.append(f'{model}: HTTP {e.code}')
                    if e.code == 429:
                        break  # rate-limited: move to the next free model
                    time.sleep(2)
                except Exception as e:
                    errors.append(f'{model}: {e}')
                    time.sleep(1)
    else:
        for attempt in range(3):
            try:
                return parse_json_loose(_gemini_call(prompt))
            except Exception as e:
                errors.append(str(e))
                time.sleep(2 * (attempt + 1))
    raise RuntimeError('LLM call failed: ' + '; '.join(errors[-4:]))


# ─── TEXT ───────────────────────────────────────────────────────────────────

def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s.lower())


def term_re(term):
    """Whole-word / whole-phrase match; trailing 's' tolerated (forest/forests)."""
    t = re.escape(norm(term).strip())
    return re.compile(rf'(?<![a-z0-9]){t}s?(?![a-z0-9])')


# ─── 1. DECOMPOSE ───────────────────────────────────────────────────────────

DECOMPOSE_PROMPT = """You turn a request for YouTube videos into a keyword search plan.
The search runs ONLY over titles, tags and descriptions of videos from channels the user subscribes to,
so recall matters: include synonyms, related phrasings, place names, and the same terms in other
languages creators commonly use (Spanish, Portuguese, French, German, etc.).

Request: "{query}"

Return JSON:
{{
  "intent": "one sentence: what a correct result looks like",
  "concepts": [
    {{"name": "short label", "required": true, "terms": ["8-25 lowercase terms or short phrases"]}}
  ],
  "exclude": ["phrases that signal a false match, e.g. a homonym (amazon prime, amazon fba)"]
}}

Rules:
- 1 to 4 concepts. A concept is one facet of the request (subject, place, format, activity).
- required=true only for facets a result cannot lack. Format words like "vlog" are usually
  required=false, because creators rarely write "vlog" in titles.
- Terms are what would literally appear in a title or description, not abstractions.
- Prefer specific terms ("rainforest", "selva", "amazonas", "iquitos", "manaus") over vague ones ("nature").
"""


def decompose(query):
    if not llm_available():
        words = [w for w in re.findall(r'[a-z0-9]+', norm(query)) if w not in STOPWORDS and len(w) > 2]
        return {
            'intent': query,
            'concepts': [{'name': w, 'required': True, 'terms': [w]} for w in words] or
                        [{'name': query, 'required': True, 'terms': [norm(query)]}],
            'exclude': [],
        }
    plan = llm_json(DECOMPOSE_PROMPT.format(query=query.replace('"', "'")))
    concepts = []
    for c in plan.get('concepts', [])[:4]:
        terms = sorted({norm(t).strip() for t in c.get('terms', []) if t and t.strip()})
        if terms:
            concepts.append({'name': c.get('name', terms[0]), 'required': bool(c.get('required', True)), 'terms': terms})
    if not concepts:
        raise RuntimeError('Could not decompose the request into search terms.')
    if not any(c['required'] for c in concepts):
        concepts[0]['required'] = True
    return {
        'intent': plan.get('intent', query),
        'concepts': concepts,
        'exclude': sorted({norm(t).strip() for t in plan.get('exclude', []) if t and t.strip()}),
    }


# ─── 2. RETRIEVE ────────────────────────────────────────────────────────────

_index_cache = {'mtime': None, 'data': None, 'channel_text': {}}


def load_index():
    if not INDEX_PATH.exists():
        raise FileNotFoundError('No video index yet. Run `npm run index` first.')
    mtime = INDEX_PATH.stat().st_mtime
    if _index_cache['mtime'] != mtime:
        data = json.loads(INDEX_PATH.read_text())
        # Pre-normalise once; searches then run over plain strings.
        for ch in data['channels'].values():
            for v in ch['videos']:
                v['_t'] = norm(v.get('t'))
                v['_d'] = norm(v.get('d'))
                v['_g'] = norm(' | '.join(v.get('tags', [])))
        _index_cache.update(mtime=mtime, data=data, channel_text=load_channel_text())
    return _index_cache['data'], _index_cache['channel_text']


def load_channel_text():
    """Channel-level context (description, niche) for a small on-topic boost."""
    out = {}
    cat = DATA_DIR / 'categorized_subscriptions.json'
    det = DATA_DIR / 'channel_details.json'
    if cat.exists():
        for s in json.loads(cat.read_text()):
            out[s['channel_id']] = norm(f"{s.get('title','')} {s.get('description','')} {s.get('niche','')}")
    if det.exists():
        for cid, d in json.loads(det.read_text()).items():
            out[cid] = out.get(cid, '') + ' ' + norm(f"{d.get('description','')} {d.get('keywords','')}")
    return out


def score_video(v, compiled, excl, ch_text):
    if any(r.search(v['_t']) for r in excl):
        return 0, []
    total, matched, req_hit, req_n = 0.0, [], 0, 0
    for c in compiled:
        best, best_term = 0, None
        for term, r in c['res']:
            s = 3 if r.search(v['_t']) else 2 if r.search(v['_g']) else 1 if r.search(v['_d']) else 0
            if s > best:
                best, best_term = s, term
                if s == 3:
                    break
        if c['required']:
            req_n += 1
            req_hit += 1 if best else 0
        if best:
            total += best
            matched.append(best_term)
        elif ch_text and any(r.search(ch_text) for _, r in c['res']):
            total += 0.5  # the channel is about this, even if this video doesn't say it
    if req_hit == 0:
        return 0, []
    total *= (req_hit / req_n) ** 2       # punish missing required facets hard
    if any(r.search(v['_d']) for r in excl):
        total *= 0.4
    return total, matched


def retrieve(plan):
    index, channel_text = load_index()
    compiled = [{'required': c['required'], 'res': [(t, term_re(t)) for t in c['terms']]} for c in plan['concepts']]
    excl = [term_re(t) for t in plan['exclude']]
    scored, n_videos = [], 0
    for cid, ch in index['channels'].items():
        ch_text = channel_text.get(cid, '')
        for v in ch['videos']:
            n_videos += 1
            s, matched = score_video(v, compiled, excl, ch_text)
            if s > 0:
                scored.append((s, v.get('p', ''), cid, v, matched))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    shortlist, per_channel = [], {}
    for s, _, cid, v, matched in scored:
        if per_channel.get(cid, 0) >= MAX_PER_CHANNEL:
            continue
        per_channel[cid] = per_channel.get(cid, 0) + 1
        shortlist.append({
            'video_id': v['id'], 'title': v.get('t', ''), 'description': v.get('d', '')[:300],
            'published_at': v.get('p', ''), 'thumb': v.get('th', ''),
            'channel_id': cid, 'channel_title': index['channels'][cid]['title'],
            'lexical': round(s, 2), 'matched': matched,
        })
        if len(shortlist) >= CANDIDATES_TO_VERIFY:
            break
    stats = {'channels': len(index['channels']), 'videos': n_videos,
             'keyword_hits': len(scored), 'index_built_at': index.get('built_at')}
    return shortlist, stats


# ─── 3. VERIFY ──────────────────────────────────────────────────────────────

VERIFY_PROMPT = """The user asked for: "{query}"
A correct result is: {intent}

Below are candidate videos from channels the user subscribes to, found by keyword match.
Keyword matches are often wrong (homonyms, passing mentions). Judge each one strictly from its
title, channel and description:
3 = clearly what they asked for
2 = probably it, or a close variant they'd likely want
1 = related topic but not what they asked for
0 = false match

Candidates:
{items}

Return JSON: {{"judgments": [{{"i": <number>, "score": 0-3, "why": "max 12 words"}}]}} covering every candidate."""


def verify(query, plan, shortlist):
    if not shortlist:
        return shortlist, True
    if not llm_available():
        n_req = sum(1 for c in plan['concepts'] if c['required'])
        for c in shortlist:
            c['score'] = 2 if len(c['matched']) >= max(n_req, 1) else 1
            c['why'] = 'keyword match: ' + ', '.join(c['matched'])
        return shortlist, False
    items = '\n'.join(
        f"{i}. [{c['channel_title']}] {c['title']} :: {c['description'][:220].replace(chr(10), ' ')}"
        for i, c in enumerate(shortlist))
    judged = llm_json(VERIFY_PROMPT.format(query=query.replace('"', "'"), intent=plan['intent'], items=items))
    if isinstance(judged, dict):
        judged = judged.get('judgments') or next((v for v in judged.values() if isinstance(v, list)), [])
    by_i = {}
    for j in judged:
        if isinstance(j, dict):
            try:
                by_i[int(j.get('i'))] = j
            except (TypeError, ValueError):
                pass
    for i, c in enumerate(shortlist):
        j = by_i.get(i, {})
        c['score'] = int(j.get('score', 0) or 0)
        c['why'] = j.get('why', '')
    return shortlist, True


# ─── 4. REPORT ──────────────────────────────────────────────────────────────

def verdict_for(results, near):
    strong = sum(1 for r in results if r['score'] == 3)
    if strong >= 1 or len(results) >= 3:
        return 'found'
    if results:
        return 'thin'
    return 'not_in_subs'


def summary_for(verdict, results, stats, verified):
    chans = len({r['channel_id'] for r in results})
    base = f"Searched {stats['videos']:,} videos from {stats['channels']:,} subscribed channels."
    tag = '' if verified else ' Unverified: no model key set, keyword matching only.'
    if verdict == 'found':
        return f"{len(results)} videos across {chans} of your channels. {base}{tag}"
    if verdict == 'thin':
        return f"Only {len(results)} likely match{'es' if len(results) != 1 else ''} in your subs; coverage is thin. {base}{tag}"
    return f"Your subscriptions don't hold this. {base}{tag}"


def run(query):
    query = query.strip()
    if not query:
        raise ValueError('Empty request.')
    t0 = time.time()
    plan = decompose(query)
    shortlist, stats = retrieve(plan)
    shortlist, verified = verify(query, plan, shortlist)

    results = sorted([c for c in shortlist if c['score'] >= 2],
                     key=lambda c: (c['score'], c['lexical']), reverse=True)[:MAX_RESULTS]
    near = sorted([c for c in shortlist if c['score'] == 1],
                  key=lambda c: c['lexical'], reverse=True)[:5]
    verdict = verdict_for(results, near)
    finding = {
        'id': uuid.uuid4().hex[:10],
        'query': query,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'intent': plan['intent'],
        'concepts': plan['concepts'],
        'exclude': plan['exclude'],
        'verdict': verdict,
        'verified': verified,
        'summary': summary_for(verdict, results, stats, verified),
        'results': [strip(c) for c in results],
        'near_misses': [strip(c) for c in near],
        'stats': stats,
        'wider_search': 'https://www.youtube.com/results?search_query=' + urllib.parse.quote_plus(query),
        'elapsed_s': round(time.time() - t0, 1),
    }
    save_finding(finding)
    return finding


def strip(c):
    return {k: c[k] for k in ('video_id', 'title', 'published_at', 'thumb', 'channel_id',
                              'channel_title', 'score', 'why', 'matched')}


# ─── STORE ──────────────────────────────────────────────────────────────────

def load_findings():
    if FINDINGS_PATH.exists():
        return json.loads(FINDINGS_PATH.read_text())
    return []


def write_findings(findings):
    payload = json.dumps(findings, indent=2, ensure_ascii=False)
    for d in (DATA_DIR, PUBLIC_DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / 'findings.json.tmp'
        tmp.write_text(payload)
        tmp.replace(d / 'findings.json')


def save_finding(f):
    write_findings([f] + load_findings())


def delete_finding(fid):
    findings = load_findings()
    kept = [f for f in findings if f['id'] != fid]
    write_findings(kept)
    return len(kept) != len(findings)


def status():
    out = {'agent': True, 'llm': llm_available(), 'provider': provider(), 'model': current_model()}
    try:
        index, _ = load_index()
        out['index'] = {'channels': len(index['channels']),
                        'videos': sum(len(c['videos']) for c in index['channels'].values()),
                        'built_at': index.get('built_at')}
    except FileNotFoundError as e:
        out['index'] = None
        out['index_error'] = str(e)
    return out
