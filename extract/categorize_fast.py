#!/usr/bin/env python3
"""Fast categorization using YouTube's own topic categories.
No LLM needed - uses Wikipedia topic URLs from channel metadata."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / 'data'

# Map Wikipedia topic URLs to our niche categories
TOPIC_TO_NICHE = {
    'Music': 'Music', 'Electronic_music': 'Music', 'Hip_hop_music': 'Music',
    'Pop_music': 'Music', 'Rock_music': 'Music', 'Soul_music': 'Music',
    'Rhythm_and_blues': 'Music', 'Jazz': 'Music', 'Classical_music': 'Music',
    'Country_music': 'Music', 'Reggae': 'Music', 'Blues': 'Music',
    'Punk_rock': 'Music', 'Heavy_metal_music': 'Music', 'Folk_music': 'Music',
    'Indie_rock': 'Music', 'Alternative_rock': 'Music', 'Funk': 'Music',
    'Disco': 'Music', 'Ambient_music': 'Music', 'Drum_and_bass': 'Music',
    'Techno': 'Music', 'House_music': 'Music', 'Trance_music': 'Music',
    'Dubstep': 'Music', 'Music_of_Latin_America': 'Music',
    'Christian_music': 'Music', 'Gospel_music': 'Music',
    'Music_of_Asia': 'Music', 'Music_video': 'Music',
    'Independent_music': 'Music', 'Singing': 'Music',
    'Song': 'Music', 'Record_label': 'Music', 'Concert': 'Music',
    'DJ': 'Music', 'Musician': 'Music', 'Entertainment': 'Entertainment',
    'Film': 'Entertainment', 'Television_program': 'Entertainment',
    'Humour': 'Comedy', 'Comedy': 'Comedy', 'Stand-up_comedy': 'Comedy',
    'Performing_arts': 'Entertainment', 'Animation': 'Entertainment',
    'Technology': 'Tech/AI', 'Computer_science': 'Tech/AI',
    'Artificial_intelligence': 'Tech/AI', 'Software': 'Tech/AI',
    'Computer_programming': 'Tech/AI', 'Machine_learning': 'Tech/AI',
    'Gadget': 'Tech/AI', 'Robotics': 'Tech/AI',
    'Video_game_culture': 'Gaming', 'Video_game': 'Gaming',
    'Action_game': 'Gaming', 'Role-playing_video_game': 'Gaming',
    'Massively_multiplayer_online_role-playing_game': 'Gaming',
    'Strategy_video_game': 'Gaming', 'Action-adventure_game': 'Gaming',
    'Racing_video_game': 'Gaming', 'Simulation_video_game': 'Gaming',
    'Sports_game': 'Gaming', 'Puzzle_video_game': 'Gaming',
    'Business': 'Business', 'Entrepreneurship': 'Business',
    'Marketing': 'Business', 'Finance': 'Finance',
    'Investing': 'Finance', 'Stock_market': 'Finance',
    'Accounting': 'Finance', 'Economy': 'Finance',
    'Knowledge': 'Education', 'Education': 'Education',
    'University': 'Education', 'Mathematics': 'Education',
    'Philosophy': 'Education', 'History': 'Education',
    'Psychology': 'Education', 'Linguistics': 'Education',
    'Physics': 'Science', 'Chemistry': 'Science', 'Biology': 'Science',
    'Astronomy': 'Science', 'Science': 'Science', 'Medicine': 'Science',
    'Neuroscience': 'Science', 'Geology': 'Science',
    'Physical_fitness': 'Fitness', 'Sport': 'Fitness',
    'Exercise': 'Fitness', 'Yoga': 'Fitness', 'Martial_arts': 'Fitness',
    'Mixed_martial_arts': 'Fitness', 'Boxing': 'Fitness',
    'Wrestling': 'Fitness', 'Bodybuilding': 'Fitness',
    'Cooking': 'Cooking', 'Food': 'Cooking', 'Recipe': 'Cooking',
    'Cuisine': 'Cooking', 'Restaurant': 'Cooking',
    'Tourism': 'Travel', 'Travel': 'Travel', 'Hotel': 'Travel',
    'Politics': 'News', 'Society': 'News', 'Journalism': 'News',
    'News': 'News', 'Military': 'News', 'Government': 'News',
    'Lifestyle_(sociology)': 'Lifestyle', 'Fashion': 'Lifestyle',
    'Health': 'Lifestyle', 'Beauty': 'Lifestyle', 'Pet': 'Lifestyle',
    'Home': 'Lifestyle', 'Interior_design': 'Lifestyle',
    'Vehicle': 'Lifestyle', 'Automobile': 'Lifestyle',
    'Visual_arts': 'Design/Art', 'Design': 'Design/Art',
    'Graphic_design': 'Design/Art', 'Photography': 'Design/Art',
    'Architecture': 'Design/Art', 'Drawing': 'Design/Art',
    'Painting': 'Design/Art', 'Sculpture': 'Design/Art',
    'Documentary_film': 'Documentary', 'Nature': 'Documentary',
    'Wildlife': 'Documentary', 'Environment': 'Documentary',
}

# Music topic keywords that indicate electronic subgenres
MUSIC_SUBGENRE_MAP = {
    'Electronic_music': 'Other Electronic',
    'Techno': 'Techno',
    'House_music': 'Deep House',
    'Trance_music': 'Progressive',
    'Dubstep': 'EDM',
    'Drum_and_bass': 'Drum & Bass',
    'Ambient_music': 'Ambient',
    'Disco': 'Dance/Disco',
    'Funk': 'Dance/Disco',
}

# Keywords in channel names/descriptions that hint at subgenres
SUBGENRE_KEYWORDS = {
    'Minimal': ['minimal', 'mnml'],
    'Micro House': ['micro house', 'microhouse'],
    'Raw': ['raw', 'industrial'],
    'Techno': ['techno', 'berghain', 'warehouse'],
    'EDM': ['edm', 'festival', 'mainstage', 'bass music'],
    'Dance/Disco': ['disco', 'dance', 'funk', 'nu-disco', 'nu disco'],
    'Deep House': ['deep house', 'deep tech', 'melodic house'],
    'Progressive': ['progressive', 'afterlife', 'tale of us', 'melodic techno'],
    'Ambient': ['ambient', 'downtempo', 'chill'],
    'Drum & Bass': ['drum and bass', 'dnb', 'd&b', 'jungle'],
}


def extract_topic_name(url):
    """Extract the topic name from a Wikipedia URL."""
    return url.rstrip('/').split('/')[-1]


def classify_channel(details):
    """Classify a channel using its topic categories."""
    topics = details.get('topic_categories', [])
    topic_names = [extract_topic_name(t) for t in topics]
    keywords = details.get('keywords', '').lower()
    desc = details.get('description', '').lower()

    # Count niche votes from topics
    niche_votes = {}
    is_music = False
    music_topics = []

    for name in topic_names:
        niche = TOPIC_TO_NICHE.get(name)
        if niche:
            niche_votes[niche] = niche_votes.get(niche, 0) + 1
        if niche == 'Music':
            is_music = True
            music_topics.append(name)

    # Winner is the niche with most votes
    if niche_votes:
        niche = max(niche_votes, key=niche_votes.get)
    else:
        niche = 'Other'

    # Determine subgenre for music channels
    subgenre = ''
    if is_music:
        # First check topic-based subgenre
        for topic in music_topics:
            if topic in MUSIC_SUBGENRE_MAP:
                subgenre = MUSIC_SUBGENRE_MAP[topic]
                break

        # Then check keyword-based subgenre (more specific)
        combined_text = f"{keywords} {desc} {details.get('title', '').lower()}"
        for sg, kws in SUBGENRE_KEYWORDS.items():
            if any(kw in combined_text for kw in kws):
                subgenre = sg
                break

        if not subgenre:
            subgenre = 'Other Electronic'

    return niche, is_music, subgenre


def main():
    print('=== Fast YouTube Categorization ===\n')

    # Load data
    with open(DATA_DIR / 'subscriptions.json') as f:
        subs = json.load(f)
    with open(DATA_DIR / 'channel_details.json') as f:
        details = json.load(f)
    with open(DATA_DIR / 'playlists.json') as f:
        playlists = json.load(f)
    with open(DATA_DIR / 'liked_videos.json') as f:
        liked = json.load(f)
    with open(DATA_DIR / 'latest_videos.json') as f:
        latest = json.load(f)

    # Categorize subscriptions
    print(f'[1/3] Categorizing {len(subs)} subscriptions...')
    categorized = []
    niche_counts = {}
    music_artists = []

    for sub in subs:
        ch_id = sub['channel_id']
        ch_details = details.get(ch_id, {})
        niche, is_music, subgenre = classify_channel(ch_details)

        entry = {**sub, **ch_details, 'niche': niche, 'is_music_artist': is_music}
        if subgenre:
            entry['subgenre'] = subgenre
        categorized.append(entry)

        niche_counts[niche] = niche_counts.get(niche, 0) + 1

        if is_music:
            ch_latest = latest.get(ch_id, [])
            music_artists.append({
                'name': sub['title'],
                'channel_id': ch_id,
                'subgenre': subgenre,
                'source': 'subscription',
                'thumbnail': ch_details.get('thumbnail', sub.get('thumbnail', '')),
                'description': ch_details.get('description', '')[:200],
                'latest_tracks': [
                    {
                        'title': v.get('title', ''),
                        'video_id': v.get('video_id', ''),
                        'published_at': v.get('published_at', ''),
                    }
                    for v in ch_latest[:5]
                ],
            })

    print(f'  Niches: {dict(sorted(niche_counts.items(), key=lambda x: -x[1]))}')
    print(f'  Music artists from subs: {len(music_artists)}')

    # Cross-reference liked videos for additional music artists
    print(f'\n[2/3] Scanning {len(liked)} liked videos for music artists...')
    music_channel_ids = {a['channel_id'] for a in music_artists}
    liked_artists = {}

    for vid in liked:
        cat_id = vid.get('category_id', '')
        tags = [t.lower() for t in vid.get('tags', [])]
        ch_id = vid.get('channel_id', '')
        ch_title = vid.get('channel_title', '')

        # Category 10 = Music on YouTube
        is_music_vid = (cat_id == '10' or any(
            t in tags for t in ['music', 'song', 'remix', 'dj', 'set', 'mix', 'techno', 'house']
        ))

        if is_music_vid and ch_id and ch_id not in music_channel_ids:
            if ch_id not in liked_artists:
                liked_artists[ch_id] = {
                    'name': ch_title,
                    'channel_id': ch_id,
                    'subgenre': 'Other Electronic',
                    'source': 'liked',
                    'thumbnail': '',
                    'description': '',
                    'latest_tracks': [],
                }
            liked_artists[ch_id]['latest_tracks'].append({
                'title': vid.get('title', ''),
                'video_id': vid.get('video_id', ''),
                'published_at': vid.get('published_at', ''),
            })

    # Cap tracks per artist and add to main list
    for artist in liked_artists.values():
        artist['latest_tracks'] = artist['latest_tracks'][:5]
        # Try to refine subgenre from track titles
        combined = ' '.join(t['title'].lower() for t in artist['latest_tracks'])
        for sg, kws in SUBGENRE_KEYWORDS.items():
            if any(kw in combined for kw in kws):
                artist['subgenre'] = sg
                break
        music_artists.append(artist)

    print(f'  Additional music artists from likes: {len(liked_artists)}')

    # Scan playlists for music artists too
    playlist_artists = {}
    for pl in playlists:
        for vid in pl.get('videos', []):
            ch_id = vid.get('channel_id', '')
            ch_title = vid.get('channel_title', '')
            if ch_id and ch_id not in music_channel_ids and ch_id not in liked_artists:
                title_lower = vid.get('title', '').lower()
                is_music_vid = any(kw in title_lower for kw in [
                    'mix', 'set', 'dj', 'live', 'remix', 'track', 'ambient',
                    'techno', 'house', 'minimal', 'deep',
                ])
                if is_music_vid and ch_id not in playlist_artists:
                    playlist_artists[ch_id] = {
                        'name': ch_title,
                        'channel_id': ch_id,
                        'subgenre': 'Other Electronic',
                        'source': 'playlist',
                        'thumbnail': '',
                        'description': '',
                        'latest_tracks': [],
                    }
                if ch_id in playlist_artists:
                    if len(playlist_artists[ch_id]['latest_tracks']) < 5:
                        playlist_artists[ch_id]['latest_tracks'].append({
                            'title': vid.get('title', ''),
                            'video_id': vid.get('video_id', ''),
                            'published_at': vid.get('published_at', ''),
                        })

    for artist in playlist_artists.values():
        combined = ' '.join(t['title'].lower() for t in artist['latest_tracks'])
        for sg, kws in SUBGENRE_KEYWORDS.items():
            if any(kw in combined for kw in kws):
                artist['subgenre'] = sg
                break
        music_artists.append(artist)

    print(f'  Additional music artists from playlists: {len(playlist_artists)}')

    # Build niche summary
    print(f'\n[3/3] Building outputs...')
    niche_summary = {}
    for entry in categorized:
        niche = entry['niche']
        if niche not in niche_summary:
            niche_summary[niche] = {'count': 0, 'channels': []}
        niche_summary[niche]['count'] += 1
        niche_summary[niche]['channels'].append(entry['channel_id'])

    # Sort by count
    niche_summary = dict(sorted(niche_summary.items(), key=lambda x: -x[1]['count']))

    # Save outputs
    with open(DATA_DIR / 'categorized_subscriptions.json', 'w') as f:
        json.dump(categorized, f, indent=2, ensure_ascii=False)

    with open(DATA_DIR / 'music_artists.json', 'w') as f:
        json.dump(music_artists, f, indent=2, ensure_ascii=False)

    with open(DATA_DIR / 'niche_summary.json', 'w') as f:
        json.dump(niche_summary, f, indent=2, ensure_ascii=False)

    print(f'\n=== Categorization Complete ===')
    print(f'Total subscriptions: {len(categorized)}')
    print(f'Total music artists: {len(music_artists)}')
    print(f'Niches found: {len(niche_summary)}')
    print(f'\nNiche breakdown:')
    for niche, data in niche_summary.items():
        print(f'  {niche}: {data["count"]}')
    print(f'\nSubgenre breakdown:')
    sg_counts = {}
    for a in music_artists:
        sg = a.get('subgenre', 'Unknown')
        sg_counts[sg] = sg_counts.get(sg, 0) + 1
    for sg, count in sorted(sg_counts.items(), key=lambda x: -x[1]):
        print(f'  {sg}: {count}')
    print(f'\nFiles saved to {DATA_DIR}/')


if __name__ == '__main__':
    main()
