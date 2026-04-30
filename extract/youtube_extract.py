#!/usr/bin/env python3
"""YouTube Data Extraction Pipeline - READ ONLY.
Extracts subscriptions, playlists, liked videos, and latest uploads.
Never modifies any YouTube data."""

import json
from pathlib import Path
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
DATA_DIR = Path(__file__).parent.parent / 'data'
TOKEN_PATH = Path(__file__).parent / 'token.json'
CLIENT_SECRET = Path(__file__).parent / 'client_secret.json'


def authenticate():
    """OAuth2 flow - opens browser first time, reuses token after."""
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
    return build('youtube', 'v3', credentials=creds)


def paginate(request_fn, **kwargs):
    """Generic paginator for YouTube API list endpoints."""
    items = []
    request = request_fn(**kwargs)
    while request:
        response = request.execute()
        items.extend(response.get('items', []))
        request = request_fn(**kwargs, pageToken=response.get('nextPageToken'))
        if not response.get('nextPageToken'):
            break
    return items


def get_subscriptions(youtube):
    """Get all channel subscriptions."""
    print('[1/5] Fetching subscriptions...')
    subs = []
    next_page = None
    while True:
        req = youtube.subscriptions().list(
            part='snippet,contentDetails',
            mine=True,
            maxResults=50,
            pageToken=next_page
        )
        resp = req.execute()
        for item in resp.get('items', []):
            snippet = item['snippet']
            subs.append({
                'channel_id': snippet['resourceId']['channelId'],
                'title': snippet['title'],
                'description': snippet.get('description', ''),
                'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', ''),
                'published_at': snippet.get('publishedAt', ''),
            })
        next_page = resp.get('nextPageToken')
        if not next_page:
            break
    print(f'  Found {len(subs)} subscriptions')
    return subs


def get_playlists(youtube):
    """Get all user playlists with their items."""
    print('[2/5] Fetching playlists...')
    playlists = []
    next_page = None
    while True:
        req = youtube.playlists().list(
            part='snippet,contentDetails',
            mine=True,
            maxResults=50,
            pageToken=next_page
        )
        resp = req.execute()
        for item in resp.get('items', []):
            snippet = item['snippet']
            pl = {
                'id': item['id'],
                'title': snippet['title'],
                'description': snippet.get('description', ''),
                'item_count': item['contentDetails']['itemCount'],
                'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', ''),
                'videos': []
            }
            playlists.append(pl)
        next_page = resp.get('nextPageToken')
        if not next_page:
            break

    # Fetch items for each playlist (max 200 per playlist to stay in quota)
    for i, pl in enumerate(playlists):
        print(f'  Playlist {i+1}/{len(playlists)}: {pl["title"]} ({pl["item_count"]} items)')
        next_page = None
        fetched = 0
        while fetched < 200:
            req = youtube.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=pl['id'],
                maxResults=50,
                pageToken=next_page
            )
            resp = req.execute()
            for vid in resp.get('items', []):
                vs = vid['snippet']
                pl['videos'].append({
                    'video_id': vs.get('resourceId', {}).get('videoId', ''),
                    'title': vs.get('title', ''),
                    'channel_title': vs.get('videoOwnerChannelTitle', ''),
                    'channel_id': vs.get('videoOwnerChannelId', ''),
                    'thumbnail': vs.get('thumbnails', {}).get('default', {}).get('url', ''),
                    'published_at': vs.get('publishedAt', ''),
                    'description': vs.get('description', '')[:200],
                })
                fetched += 1
            next_page = resp.get('nextPageToken')
            if not next_page:
                break

    print(f'  Found {len(playlists)} playlists')
    return playlists


def get_liked_videos(youtube):
    """Get liked videos (special playlist LL)."""
    print('[3/5] Fetching liked videos...')
    liked = []
    next_page = None
    while True:
        req = youtube.videos().list(
            part='snippet,contentDetails,statistics',
            myRating='like',
            maxResults=50,
            pageToken=next_page
        )
        resp = req.execute()
        for item in resp.get('items', []):
            snippet = item['snippet']
            liked.append({
                'video_id': item['id'],
                'title': snippet['title'],
                'channel_title': snippet.get('channelTitle', ''),
                'channel_id': snippet.get('channelId', ''),
                'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', ''),
                'published_at': snippet.get('publishedAt', ''),
                'description': snippet.get('description', '')[:200],
                'category_id': snippet.get('categoryId', ''),
                'tags': snippet.get('tags', [])[:10],
                'duration': item.get('contentDetails', {}).get('duration', ''),
                'view_count': item.get('statistics', {}).get('viewCount', '0'),
            })
        next_page = resp.get('nextPageToken')
        if not next_page:
            break
    print(f'  Found {len(liked)} liked videos')
    return liked


def get_latest_videos(youtube, subscriptions, max_per_channel=5):
    """Get latest videos for each subscribed channel via uploads playlist.

    Uses playlistItems.list (1 quota unit) instead of search.list (100 units).
    The uploads playlist ID is the channel ID with 'UC' replaced by 'UU'.
    """
    print(f'[4/5] Fetching latest videos for {len(subscriptions)} channels...')
    latest = {}
    for i, sub in enumerate(subscriptions):
        ch_id = sub['channel_id']
        if (i + 1) % 50 == 0:
            print(f'  Processing channel {i+1}/{len(subscriptions)}...')
        # Derive uploads playlist ID from channel ID
        uploads_id = 'UU' + ch_id[2:] if ch_id.startswith('UC') else ch_id
        try:
            req = youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_id,
                maxResults=max_per_channel,
            )
            resp = req.execute()
            vids = []
            for item in resp.get('items', []):
                s = item['snippet']
                vids.append({
                    'video_id': s.get('resourceId', {}).get('videoId', ''),
                    'title': s.get('title', ''),
                    'description': s.get('description', '')[:200],
                    'thumbnail': s.get('thumbnails', {}).get('medium', {}).get('url', ''),
                    'published_at': s.get('publishedAt', ''),
                })
            latest[ch_id] = vids
        except Exception as e:
            print(f'  Warning: Failed for {sub["title"]}: {e}')
            latest[ch_id] = []
    print(f'  Fetched latest videos for {len(latest)} channels')
    return latest


def get_channel_details(youtube, channel_ids):
    """Get detailed info for channels (category, subscriber count, etc.)."""
    print(f'[5/5] Fetching channel details for {len(channel_ids)} channels...')
    details = {}
    # YouTube API allows max 50 IDs per request
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i:i+50]
        req = youtube.channels().list(
            part='snippet,statistics,topicDetails,brandingSettings',
            id=','.join(batch)
        )
        resp = req.execute()
        for item in resp.get('items', []):
            ch_id = item['id']
            snippet = item['snippet']
            stats = item.get('statistics', {})
            topics = item.get('topicDetails', {}).get('topicCategories', [])
            details[ch_id] = {
                'title': snippet.get('title', ''),
                'description': snippet.get('description', '')[:500],
                'custom_url': snippet.get('customUrl', ''),
                'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', ''),
                'country': snippet.get('country', ''),
                'subscriber_count': stats.get('subscriberCount', '0'),
                'video_count': stats.get('videoCount', '0'),
                'view_count': stats.get('viewCount', '0'),
                'topic_categories': topics,
                'keywords': item.get('brandingSettings', {}).get('channel', {}).get('keywords', ''),
            }
    print(f'  Got details for {len(details)} channels')
    return details


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print('=== YouTube Data Extraction ===')
    print(f'Data will be saved to: {DATA_DIR}\n')

    youtube = authenticate()
    print('Authenticated successfully.\n')

    # 1. Subscriptions
    subs = get_subscriptions(youtube)
    with open(DATA_DIR / 'subscriptions.json', 'w') as f:
        json.dump(subs, f, indent=2, ensure_ascii=False)

    # 2. Playlists
    playlists = get_playlists(youtube)
    with open(DATA_DIR / 'playlists.json', 'w') as f:
        json.dump(playlists, f, indent=2, ensure_ascii=False)

    # 3. Liked videos
    liked = get_liked_videos(youtube)
    with open(DATA_DIR / 'liked_videos.json', 'w') as f:
        json.dump(liked, f, indent=2, ensure_ascii=False)

    # 4. Channel details
    channel_ids = list(set(s['channel_id'] for s in subs))
    details = get_channel_details(youtube, channel_ids)
    with open(DATA_DIR / 'channel_details.json', 'w') as f:
        json.dump(details, f, indent=2, ensure_ascii=False)

    # 5. Latest videos per channel
    latest = get_latest_videos(youtube, subs)
    with open(DATA_DIR / 'latest_videos.json', 'w') as f:
        json.dump(latest, f, indent=2, ensure_ascii=False)

    # Summary
    print('\n=== Extraction Complete ===')
    print(f'Subscriptions: {len(subs)}')
    print(f'Playlists: {len(playlists)}')
    print(f'Liked videos: {len(liked)}')
    print(f'Channel details: {len(details)}')
    print(f'Latest videos: {sum(len(v) for v in latest.values())} across {len(latest)} channels')
    print(f'\nAll data saved to {DATA_DIR}/')

    # Save metadata
    meta = {
        'extracted_at': datetime.utcnow().isoformat(),
        'subscription_count': len(subs),
        'playlist_count': len(playlists),
        'liked_count': len(liked),
        'channel_count': len(details),
    }
    with open(DATA_DIR / 'meta.json', 'w') as f:
        json.dump(meta, f, indent=2)


if __name__ == '__main__':
    main()
