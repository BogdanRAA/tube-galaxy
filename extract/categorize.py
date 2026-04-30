#!/usr/bin/env python3
"""Categorize YouTube subscriptions and identify music artists using Gemini.

Reads extracted YouTube data, batches channels for Gemini classification,
and outputs categorized subscriptions, music artist profiles, and niche summaries.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import google.generativeai as genai

DATA_DIR = Path(__file__).parent.parent / "data"

NICHES = [
    "Tech/AI",
    "Music",
    "Documentary",
    "Gaming",
    "Finance",
    "Comedy",
    "Education",
    "Fitness",
    "News",
    "Cooking",
    "Travel",
    "Design/Art",
    "Business",
    "Science",
    "Lifestyle",
    "Entertainment",
    "Other",
]

ELECTRONIC_SUBGENRES = [
    "Minimal",
    "Micro House",
    "Raw",
    "Techno",
    "EDM",
    "Dance/Disco",
    "Deep House",
    "Progressive",
    "Ambient",
    "Drum & Bass",
    "Other Electronic",
    "Non-Electronic",
]

BATCH_SIZE = 12


def load_json(filename: str) -> dict | list:
    """Load a JSON file from the data directory, returning empty container on failure."""
    path = DATA_DIR / filename
    if not path.exists():
        print(f"  Warning: {filename} not found, skipping")
        return {} if filename == "channel_details.json" else []
    with open(path) as f:
        return json.load(f)


def save_json(filename: str, data: dict | list) -> None:
    """Write data as formatted JSON to the data directory."""
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved {filename} ({path.stat().st_size:,} bytes)")


def configure_gemini() -> genai.GenerativeModel:
    """Set up Gemini API and return the model instance."""
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable is required.")
        print("Set it via: export GOOGLE_API_KEY=your_key_here")
        sys.exit(1)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")


def build_channel_summary(sub: dict, details: dict) -> str:
    """Build a compact text summary for one channel to send to Gemini."""
    ch_id = sub["channel_id"]
    detail = details.get(ch_id, {})
    parts = [f"Name: {sub['title']}"]
    desc = detail.get("description", sub.get("description", ""))
    if desc:
        parts.append(f"Description: {desc[:200]}")
    topics = detail.get("topic_categories", [])
    if topics:
        labels = [t.split("/")[-1] for t in topics]
        parts.append(f"Topics: {', '.join(labels)}")
    keywords = detail.get("keywords", "")
    if keywords:
        parts.append(f"Keywords: {keywords[:150]}")
    return " | ".join(parts)


def classify_batch(
    model: genai.GenerativeModel, channels: list[dict], details: dict
) -> list[dict]:
    """Send a batch of channels to Gemini and parse the classification response."""
    entries = []
    for i, ch in enumerate(channels):
        summary = build_channel_summary(ch, details)
        entries.append(f"{i + 1}. {summary}")

    niche_list = ", ".join(NICHES)
    subgenre_list = ", ".join(ELECTRONIC_SUBGENRES)

    prompt = f"""Classify each YouTube channel below into exactly one niche and determine if it is a music artist/label/DJ.

Niches (pick exactly one): {niche_list}

For channels that ARE music-related, also classify the electronic music subgenre.
Subgenres (pick exactly one): {subgenre_list}
Use "Non-Electronic" if the music is not electronic. Only assign a subgenre if is_music_artist is true.

Channels:
{chr(10).join(entries)}

Respond with ONLY a JSON array. Each element must have:
- "index": integer (1-based, matching the channel number above)
- "niche": string (one of the niches listed)
- "is_music_artist": boolean
- "subgenre": string or null (one of the subgenres if is_music_artist is true, null otherwise)

Example: [{{"index": 1, "niche": "Tech/AI", "is_music_artist": false, "subgenre": null}}]

Return ONLY the JSON array, no markdown fences, no explanation."""

    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            # Strip markdown fences if the model wraps them anyway
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            results = json.loads(text)
            if isinstance(results, list) and len(results) == len(channels):
                return results
            # Partial result -- pad missing entries
            if isinstance(results, list):
                indexed = {r["index"]: r for r in results}
                padded = []
                for i in range(1, len(channels) + 1):
                    if i in indexed:
                        padded.append(indexed[i])
                    else:
                        padded.append(
                            {
                                "index": i,
                                "niche": "Other",
                                "is_music_artist": False,
                                "subgenre": None,
                            }
                        )
                return padded
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            if attempt < 2:
                print(f"    Retry {attempt + 1}/3 (parse error: {exc})")
                time.sleep(2)
            else:
                print("    Failed after 3 attempts, defaulting batch to Other")
                return [
                    {
                        "index": i + 1,
                        "niche": "Other",
                        "is_music_artist": False,
                        "subgenre": None,
                    }
                    for i in range(len(channels))
                ]
        except Exception as exc:
            if attempt < 2:
                wait = 5 * (attempt + 1)
                print(f"    API error: {exc} -- retrying in {wait}s")
                time.sleep(wait)
            else:
                print("    Failed after 3 attempts, defaulting batch to Other")
                return [
                    {
                        "index": i + 1,
                        "niche": "Other",
                        "is_music_artist": False,
                        "subgenre": None,
                    }
                    for i in range(len(channels))
                ]
    # Unreachable but satisfies the return type
    return []


def classify_additional_artists(
    model: genai.GenerativeModel, artists: list[dict]
) -> list[dict]:
    """Classify a batch of artist names found in playlists/likes into subgenres."""
    if not artists:
        return []

    entries = []
    for i, a in enumerate(artists):
        parts = [f"Name: {a['name']}"]
        if a.get("sample_titles"):
            parts.append(f"Tracks: {', '.join(a['sample_titles'][:5])}")
        entries.append(f"{i + 1}. {' | '.join(parts)}")

    subgenre_list = ", ".join(ELECTRONIC_SUBGENRES)
    prompt = f"""These are music artists/channels found on YouTube. Classify each into an electronic music subgenre.

Subgenres (pick exactly one): {subgenre_list}
Use "Non-Electronic" if the music is not electronic.

Artists:
{chr(10).join(entries)}

Respond with ONLY a JSON array. Each element must have:
- "index": integer (1-based)
- "subgenre": string (one of the subgenres listed)

Return ONLY the JSON array, no markdown fences, no explanation."""

    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            results = json.loads(text)
            if isinstance(results, list):
                indexed = {r["index"]: r for r in results}
                out = []
                for i in range(1, len(artists) + 1):
                    if i in indexed:
                        out.append(indexed[i])
                    else:
                        out.append({"index": i, "subgenre": "Other Electronic"})
                return out
        except (json.JSONDecodeError, KeyError, ValueError):
            if attempt < 2:
                time.sleep(2)
        except Exception as exc:
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
            else:
                print(f"    Artist classification failed: {exc}")

    return [{"index": i + 1, "subgenre": "Other Electronic"} for i in range(len(artists))]


def categorize_subscriptions(
    model: genai.GenerativeModel, subscriptions: list[dict], details: dict
) -> list[dict]:
    """Categorize all subscriptions via batched Gemini calls."""
    total = len(subscriptions)
    print(f"\n[1/3] Categorizing {total} subscriptions ({BATCH_SIZE} per batch)...")

    categorized = []
    for start in range(0, total, BATCH_SIZE):
        batch = subscriptions[start : start + BATCH_SIZE]
        end = min(start + BATCH_SIZE, total)
        print(f"  Processing {start + 1}-{end} of {total}...", end=" ", flush=True)

        results = classify_batch(model, batch, details)
        for ch, result in zip(batch, results):
            ch_copy = dict(ch)
            ch_copy["niche"] = result.get("niche", "Other")
            ch_copy["is_music_artist"] = result.get("is_music_artist", False)
            ch_copy["subgenre"] = result.get("subgenre")
            categorized.append(ch_copy)
        print("done")

        # Rate limit buffer: Gemini free tier = 15 RPM, so ~4s between calls
        if end < total:
            time.sleep(5)

    return categorized


def extract_music_from_playlists(playlists: list[dict]) -> dict[str, dict]:
    """Pull unique channel names and sample titles from playlist videos."""
    artists: dict[str, dict] = {}
    for pl in playlists:
        for vid in pl.get("videos", []):
            ch_title = vid.get("channel_title", "").strip()
            if not ch_title:
                continue
            ch_id = vid.get("channel_id", "")
            if ch_id not in artists:
                artists[ch_id] = {
                    "name": ch_title,
                    "channel_id": ch_id,
                    "sample_titles": [],
                    "source": "playlist",
                    "playlist_names": set(),
                }
            artists[ch_id]["sample_titles"].append(vid.get("title", ""))
            artists[ch_id]["playlist_names"].add(pl.get("title", ""))
    # Convert sets to lists for JSON
    for a in artists.values():
        a["playlist_names"] = list(a["playlist_names"])
        a["sample_titles"] = a["sample_titles"][:10]
    return artists


def extract_music_from_liked(liked_videos: list[dict]) -> dict[str, dict]:
    """Pull unique channel names and sample titles from liked videos."""
    artists: dict[str, dict] = {}
    for vid in liked_videos:
        ch_title = vid.get("channel_title", "").strip()
        if not ch_title:
            continue
        ch_id = vid.get("channel_id", "")
        # YouTube music category is 10
        is_music_category = vid.get("category_id") == "10"
        tags = vid.get("tags", [])
        tag_text = " ".join(tags).lower()
        music_signals = is_music_category or any(
            kw in tag_text for kw in ["music", "dj", "mix", "techno", "house", "remix", "electronic"]
        )
        if not music_signals:
            continue
        if ch_id not in artists:
            artists[ch_id] = {
                "name": ch_title,
                "channel_id": ch_id,
                "sample_titles": [],
                "source": "liked",
            }
        artists[ch_id]["sample_titles"].append(vid.get("title", ""))
    for a in artists.values():
        a["sample_titles"] = a["sample_titles"][:10]
    return artists


def cross_reference_music(
    model: genai.GenerativeModel,
    categorized_subs: list[dict],
    playlists: list[dict],
    liked_videos: list[dict],
) -> list[dict]:
    """Identify music artists from playlists and likes not already in subscriptions."""
    print("\n[2/3] Cross-referencing playlists and liked videos for music artists...")

    # Collect already-known music subscription channel IDs
    sub_channel_ids = {s["channel_id"] for s in categorized_subs}
    known_music_ids = {s["channel_id"] for s in categorized_subs if s.get("is_music_artist")}

    # Gather candidates from playlists and liked videos
    playlist_artists = extract_music_from_playlists(playlists)
    liked_artists = extract_music_from_liked(liked_videos)

    # Merge, preferring playlist data, excluding channels already categorized as music
    additional: dict[str, dict] = {}
    for ch_id, data in playlist_artists.items():
        if ch_id not in known_music_ids:
            additional[ch_id] = data
    for ch_id, data in liked_artists.items():
        if ch_id not in known_music_ids and ch_id not in additional:
            additional[ch_id] = data
        elif ch_id in additional:
            # Merge sample titles
            existing = additional[ch_id]
            titles = set(existing["sample_titles"]) | set(data["sample_titles"])
            existing["sample_titles"] = list(titles)[:10]
            if existing["source"] != "liked":
                existing["source"] = "playlist+liked"

    if not additional:
        print("  No additional music artists found")
        return []

    # Filter: only classify those not already in subscriptions at all,
    # or those in subscriptions but not identified as music yet
    candidates = list(additional.values())
    print(f"  Found {len(candidates)} potential music artists to classify")

    # Batch classify subgenres
    classified = []
    for start in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[start : start + BATCH_SIZE]
        end = min(start + BATCH_SIZE, len(candidates))
        print(f"  Classifying artists {start + 1}-{end} of {len(candidates)}...", end=" ", flush=True)
        results = classify_additional_artists(model, batch)
        for artist, result in zip(batch, results):
            artist_entry = {
                "name": artist["name"],
                "channel_id": artist["channel_id"],
                "subgenre": result.get("subgenre", "Other Electronic"),
                "source": artist["source"],
                "sample_titles": artist["sample_titles"],
                "in_subscriptions": artist["channel_id"] in sub_channel_ids,
            }
            if "playlist_names" in artist:
                artist_entry["playlist_names"] = artist["playlist_names"]
            classified.append(artist_entry)
        print("done")
        if end < len(candidates):
            time.sleep(5)

    return classified


def build_music_artist_list(
    categorized_subs: list[dict],
    additional_artists: list[dict],
    latest_videos: dict,
) -> list[dict]:
    """Compile the final music artists list from subscriptions + cross-referenced sources."""
    artists = []

    # From subscriptions
    for sub in categorized_subs:
        if not sub.get("is_music_artist"):
            continue
        ch_id = sub["channel_id"]
        latest = latest_videos.get(ch_id, [])
        recent_tracks = [v["title"] for v in latest[:5]]
        artists.append({
            "name": sub["title"],
            "channel_id": ch_id,
            "subgenre": sub.get("subgenre", "Other Electronic"),
            "source": "subscription",
            "latest_tracks": recent_tracks,
            "in_subscriptions": True,
        })

    # From playlists/liked
    for a in additional_artists:
        artists.append({
            "name": a["name"],
            "channel_id": a["channel_id"],
            "subgenre": a.get("subgenre", "Other Electronic"),
            "source": a["source"],
            "latest_tracks": a.get("sample_titles", [])[:5],
            "in_subscriptions": a.get("in_subscriptions", False),
            "playlist_names": a.get("playlist_names", []),
        })

    return artists


def build_niche_summary(categorized_subs: list[dict]) -> dict:
    """Build a summary of niches with counts and channel lists."""
    summary: dict[str, dict] = {}
    for sub in categorized_subs:
        niche = sub.get("niche", "Other")
        if niche not in summary:
            summary[niche] = {"count": 0, "channels": []}
        summary[niche]["count"] += 1
        summary[niche]["channels"].append({
            "title": sub["title"],
            "channel_id": sub["channel_id"],
            "is_music_artist": sub.get("is_music_artist", False),
        })

    # Sort niches by count descending
    sorted_summary = dict(sorted(summary.items(), key=lambda x: x[1]["count"], reverse=True))
    return {
        "total_channels": len(categorized_subs),
        "niche_count": len(sorted_summary),
        "niches": sorted_summary,
    }


def main() -> None:
    """Run the full categorization pipeline."""
    if not DATA_DIR.exists():
        print(f"Data directory not found: {DATA_DIR}")
        print("Run youtube_extract.py first to generate the input data.")
        sys.exit(1)

    print("=== YouTube Channel Categorization ===\n")

    # Load input data
    print("Loading extracted data...")
    subscriptions = load_json("subscriptions.json")
    playlists = load_json("playlists.json")
    liked_videos = load_json("liked_videos.json")
    channel_details = load_json("channel_details.json")
    latest_videos = load_json("latest_videos.json")

    if not subscriptions:
        print("No subscriptions found. Run youtube_extract.py first.")
        sys.exit(1)

    print(
        f"  Loaded: {len(subscriptions)} subs, "
        f"{len(playlists)} playlists, "
        f"{len(liked_videos)} liked videos, "
        f"{len(channel_details)} channel details"
    )

    # Configure Gemini
    model = configure_gemini()

    # Step 1: Categorize subscriptions
    categorized = categorize_subscriptions(model, subscriptions, channel_details)

    # Step 2: Cross-reference playlists and liked videos
    additional_artists = cross_reference_music(model, categorized, playlists, liked_videos)

    # Step 3: Build outputs
    print("\n[3/3] Building output files...")

    music_artists = build_music_artist_list(categorized, additional_artists, latest_videos)
    niche_summary = build_niche_summary(categorized)

    save_json("categorized_subscriptions.json", categorized)
    save_json("music_artists.json", music_artists)
    save_json("niche_summary.json", niche_summary)

    # Print summary
    music_count = sum(1 for s in categorized if s.get("is_music_artist"))
    additional_count = len(additional_artists)
    print("\n=== Categorization Complete ===")
    print(f"Subscriptions categorized: {len(categorized)}")
    print(f"Music artists from subs:   {music_count}")
    print(f"Additional artists found:  {additional_count}")
    print(f"Total music artists:       {music_count + additional_count}")
    print(f"Niches found:              {niche_summary['niche_count']}")
    print("\nTop niches:")
    for niche, data in list(niche_summary["niches"].items())[:5]:
        print(f"  {niche}: {data['count']} channels")


if __name__ == "__main__":
    main()
