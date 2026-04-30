#!/usr/bin/env python3
"""Fetch upcoming concerts for music artists via Ticketmaster Discovery API."""

import json
import os
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

DATA_DIR = Path(__file__).parent.parent / 'data'
API_KEY = os.environ['TICKETMASTER_API_KEY']
BASE_URL = 'https://app.ticketmaster.com/discovery/v2'


def search_events(artist_name, size=10):
    """Search Ticketmaster for upcoming events by artist name."""
    encoded = quote(artist_name)
    url = (
        f'{BASE_URL}/events.json'
        f'?apikey={API_KEY}'
        f'&keyword={encoded}'
        f'&classificationName=music'
        f'&sort=date,asc'
        f'&size={size}'
    )
    try:
        req = Request(url, headers={'Accept': 'application/json'})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        events = data.get('_embedded', {}).get('events', [])
        return [parse_event(e) for e in events]
    except HTTPError as e:
        if e.code == 429:
            print('  Rate limited, waiting 2s...')
            time.sleep(2)
            return search_events(artist_name, size)
        print(f'  HTTP {e.code} for {artist_name}')
        return []
    except Exception as e:
        print(f'  Error for {artist_name}: {e}')
        return []


def parse_event(event):
    """Extract structured event data from Ticketmaster event object."""
    venue_data = {}
    venues = event.get('_embedded', {}).get('venues', [])
    if venues:
        v = venues[0]
        venue_data = {
            'venue_name': v.get('name', ''),
            'city': v.get('city', {}).get('name', ''),
            'country': v.get('country', {}).get('name', ''),
            'country_code': v.get('country', {}).get('countryCode', ''),
            'state': v.get('state', {}).get('name', ''),
            'latitude': v.get('location', {}).get('latitude', ''),
            'longitude': v.get('location', {}).get('longitude', ''),
            'address': v.get('address', {}).get('line1', ''),
        }

    # Price ranges
    price_ranges = event.get('priceRanges', [])
    price = {}
    if price_ranges:
        p = price_ranges[0]
        price = {
            'min': p.get('min', ''),
            'max': p.get('max', ''),
            'currency': p.get('currency', ''),
        }

    # Images - get the largest
    images = event.get('images', [])
    image_url = ''
    if images:
        best = max(images, key=lambda i: i.get('width', 0) * i.get('height', 0))
        image_url = best.get('url', '')

    # Attractions (artists performing)
    attractions = event.get('_embedded', {}).get('attractions', [])
    artists = [a.get('name', '') for a in attractions]

    return {
        'event_id': event.get('id', ''),
        'name': event.get('name', ''),
        'date': event.get('dates', {}).get('start', {}).get('localDate', ''),
        'time': event.get('dates', {}).get('start', {}).get('localTime', ''),
        'timezone': event.get('dates', {}).get('timezone', ''),
        'status': event.get('dates', {}).get('status', {}).get('code', ''),
        'url': event.get('url', ''),
        'image': image_url,
        'artists': artists,
        'price': price,
        **venue_data,
    }


def fetch_concerts_for_artists(artists_file):
    """Load music artists and fetch upcoming concerts for each."""
    if not artists_file.exists():
        print(f'Music artists file not found: {artists_file}')
        print('Run categorize.py first to identify music artists.')
        return []

    with open(artists_file) as f:
        artists = json.load(f)

    print(f'=== Fetching concerts for {len(artists)} music artists ===\n')

    all_events = []
    seen_event_ids = set()

    for i, artist in enumerate(artists):
        name = artist.get('name', artist.get('title', ''))
        if not name:
            continue

        print(f'[{i+1}/{len(artists)}] {name}...', end=' ')
        events = search_events(name, size=5)

        new_events = []
        for event in events:
            eid = event['event_id']
            if eid not in seen_event_ids:
                seen_event_ids.add(eid)
                event['searched_artist'] = name
                event['artist_subgenre'] = artist.get('subgenre', '')
                new_events.append(event)

        all_events.extend(new_events)
        print(f'{len(new_events)} events')

        # Rate limiting: ~5 requests/second is safe
        time.sleep(0.25)

    # Sort by date
    all_events.sort(key=lambda e: e.get('date', ''))

    print(f'\n=== Found {len(all_events)} unique events ===')
    return all_events


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    artists_file = DATA_DIR / 'music_artists.json'
    events = fetch_concerts_for_artists(artists_file)

    output_file = DATA_DIR / 'concerts.json'
    with open(output_file, 'w') as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

    print(f'Saved to {output_file}')

    # Summary by country
    countries = {}
    for e in events:
        c = e.get('country', 'Unknown')
        countries[c] = countries.get(c, 0) + 1

    if countries:
        print('\nEvents by country:')
        for country, count in sorted(countries.items(), key=lambda x: -x[1])[:10]:
            print(f'  {country}: {count}')


if __name__ == '__main__':
    main()
