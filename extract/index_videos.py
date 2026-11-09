#!/usr/bin/env python3
"""Build a searchable local index of videos from your subscribed channels - READ ONLY.

The agent (agent/server.py) searches this index, never YouTube at large,
so every result it returns comes from a channel you actually follow.

Quota math (YouTube Data API, default 10,000 units/day):
  playlistItems.list = 1 unit per page of 50 videos.
  ~900 channels x 300 videos each = ~5,400 units on the first run.
  Re-runs are incremental: paging stops at the first video already indexed,
  so a weekly refresh usually costs ~1 unit per channel.

Usage:
  python3 index_videos.py                 # default: up to 300 videos per channel
  python3 index_videos.py --max 1000      # deeper back catalogues (more quota)
  python3 index_videos.py --with-tags     # +1 unit per 50 videos, better recall
  python3 index_videos.py --full          # ignore the existing index, rebuild
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.errors import HttpError

from youtube_extract import authenticate

DATA_DIR = Path(__file__).parent.parent / 'data'
INDEX_PATH = DATA_DIR / 'video_index.json'
DESC_LIMIT = 1000  # chars of description kept per video; enough for keyword search


def load_index():
    if INDEX_PATH.exists():
        with open(INDEX_PATH) as f:
            return json.load(f)
    return {'built_at': None, 'channels': {}}


def save_index(index):
    index['built_at'] = datetime.now(timezone.utc).isoformat()
    tmp = INDEX_PATH.with_suffix('.tmp')
    with open(tmp, 'w') as f:
        json.dump(index, f, ensure_ascii=False)
    tmp.replace(INDEX_PATH)


def fetch_new_uploads(youtube, channel_id, known_ids, max_videos):
    """Page through the channel's uploads playlist, newest first.

    Stops when it reaches a video already in the index (incremental refresh)
    or when max_videos is reached. Returns (new_videos, units_spent).
    """
    uploads_id = 'UU' + channel_id[2:] if channel_id.startswith('UC') else channel_id
    new, units, page = [], 0, None
    while len(new) < max_videos:
        resp = youtube.playlistItems().list(
            part='snippet', playlistId=uploads_id, maxResults=50, pageToken=page
        ).execute()
        units += 1
        hit_known = False
        for item in resp.get('items', []):
            s = item['snippet']
            vid = s.get('resourceId', {}).get('videoId', '')
            if not vid:
                continue
            if vid in known_ids:
                hit_known = True
                break
            new.append({
                'id': vid,
                't': s.get('title', ''),
                'd': (s.get('description', '') or '')[:DESC_LIMIT],
                'p': s.get('publishedAt', ''),
                'th': s.get('thumbnails', {}).get('medium', {}).get('url', ''),
            })
            if len(new) >= max_videos:
                break
        page = resp.get('nextPageToken')
        if hit_known or not page:
            break
    return new, units


def add_tags(youtube, videos):
    """videos.list returns tags; 1 unit per 50 ids."""
    units = 0
    by_id = {v['id']: v for v in videos}
    ids = list(by_id)
    for i in range(0, len(ids), 50):
        resp = youtube.videos().list(part='snippet', id=','.join(ids[i:i + 50])).execute()
        units += 1
        for item in resp.get('items', []):
            tags = item.get('snippet', {}).get('tags', [])
            if tags:
                by_id[item['id']]['tags'] = tags[:25]
    return units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=300, help='max videos per channel')
    ap.add_argument('--with-tags', action='store_true', help='also fetch video tags')
    ap.add_argument('--full', action='store_true', help='rebuild from scratch')
    args = ap.parse_args()

    subs_path = DATA_DIR / 'subscriptions.json'
    if not subs_path.exists():
        sys.exit('data/subscriptions.json not found. Run `npm run extract` first.')
    subs = json.loads(subs_path.read_text())

    index = {'built_at': None, 'channels': {}} if args.full else load_index()
    youtube = authenticate()
    units_total = 0
    print(f'=== Indexing videos for {len(subs)} subscribed channels (max {args.max}/channel) ===')

    # Drop channels you have unsubscribed from, so results stay inside your subs.
    sub_ids = {s['channel_id'] for s in subs}
    for gone in [c for c in index['channels'] if c not in sub_ids]:
        del index['channels'][gone]

    try:
        for i, sub in enumerate(subs, 1):
            ch_id = sub['channel_id']
            entry = index['channels'].setdefault(ch_id, {'title': sub['title'], 'videos': []})
            entry['title'] = sub['title']
            known = {v['id'] for v in entry['videos']}
            try:
                new, units = fetch_new_uploads(youtube, ch_id, known, args.max)
                if args.with_tags and new:
                    units += add_tags(youtube, new)
            except HttpError as e:
                if e.resp.status == 403 and b'quota' in (e.content or b'').lower():
                    print(f'\nQuota exhausted at channel {i}/{len(subs)}. Progress saved; re-run tomorrow to continue.')
                    break
                print(f'  Warning: {sub["title"]}: {e}')
                continue
            units_total += units
            entry['videos'] = (new + entry['videos'])[: max(args.max, len(entry['videos']))]
            if i % 25 == 0:
                save_index(index)  # checkpoint, so a crash or quota stop loses little
                print(f'  {i}/{len(subs)} channels, ~{units_total} quota units used')
    finally:
        save_index(index)

    n_videos = sum(len(c['videos']) for c in index['channels'].values())
    print(f'\nIndexed {n_videos} videos across {len(index["channels"])} channels.')
    print(f'Quota spent this run: ~{units_total} units. Saved to {INDEX_PATH}')


if __name__ == '__main__':
    main()
