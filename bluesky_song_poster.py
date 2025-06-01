import requests
import argparse
import random
from atproto import Client
import os
from dotenv import load_dotenv
from atproto import models as atproto_models
from datetime import datetime
import re
import io
from PIL import Image

load_dotenv()

POPHITS_BLUESKY_USERNAME = os.environ.get('POPHITS_BLUESKY_USERNAME')
POPHITS_BLUESKY_PASSWORD = os.environ.get('POPHITS_BLUESKY_PASSWORD')

client = Client()
try:
    client.login(POPHITS_BLUESKY_USERNAME, POPHITS_BLUESKY_PASSWORD)
except Exception as e:
    print(f"Error logging in to Bluesky: {e}")
    client = None

# Define tag rules
def tag_song(song):
    tags = []
    year = song["year"]
    peak = song["peak_rank"]
    weeks = song["weeks_on_chart"]

    if peak == 1:
        tags.append("number_one")
    elif peak <= 10:
        tags.append("top_ten")
    if weeks >= 30:
        tags.append("longevity")
    if weeks < 5:
        tags.append("short_run")
    if year <= datetime.now().year - 50:
        tags.append("timeless")
    if 1960 <= year < 1970:
        tags.append("sixties")
    elif 1970 <= year < 1980:
        tags.append("seventies")
    elif 1980 <= year < 1990:
        tags.append("eighties")
    elif 1990 <= year < 2000:
        tags.append("nineties")
    elif 2000 <= year < 2010:
        tags.append("two_thousands")

    return tags

# Define emojis for categories
emoji_map = {
    "number_one": "🏆",
    "top_ten": "🔥",
    "longevity": "📈",
    "short_run": "💨",
    "timeless": "🎶",
    "sixties": "🕺",
    "seventies": "🌈",
    "eighties": "🎧",
    "nineties": "💿",
    "two_thousands": "📻",
}

# Post templates for different tags
template_map = {
    "number_one": [
        '"{title}" by {artist} topped the Hot 100 in {year} — a true chart classic {emoji}',
        'Back in {year}, "{title}" by {artist} hit #1 on the Billboard charts {emoji}',
        'A #1 smash from {year}: "{title}" by {artist} {emoji}',
    ],
    "top_ten": [
        '"{title}" by {artist} broke into the Top 10 in {year}, peaking at #{peak_rank} {emoji}',
        '"{title}" hit #{peak_rank} in {year} — one of the year\'s biggest hits {emoji}',
    ],
    "longevity": [
        '"{title}" by {artist} stayed on the charts for {weeks_on_chart} weeks — staying power! {emoji}',
        '{weeks_on_chart} weeks on the Hot 100 — {artist}\'s "{title}" really stuck around {emoji}',
    ],
    "short_run": [
        '"{title}" had a quick run — just {weeks_on_chart} weeks on the charts. Blink and you missed it! {emoji}',
        'Short but sweet: "{title}" by {artist} was on the Hot 100 for {weeks_on_chart} weeks {emoji}',
    ],
    "timeless": [
        'Timeless: "{title}" by {artist} still holds up decades after its {year} release {emoji}',
        '"{title}" by {artist} is over 50 years old, but still a fan favorite {emoji}',
    ],
    "sixties": [
        '"{title}" captured the spirit of the 60s when it hit #{peak_rank} in {year} {emoji}',
        'A 60s staple: "{title}" by {artist}, released in {year} {emoji}',
    ],
    "seventies": [
        'From the 70s vault: "{title}" by {artist} peaked at #{peak_rank} in {year} {emoji}',
    ],
    "eighties": [
        'An 80s essential: "{title}" by {artist} hit #{peak_rank} in {year} {emoji}',
    ],
    "nineties": [
        'Relive the 90s with "{title}" by {artist}, which hit #{peak_rank} in {year} {emoji}',
    ],
    "two_thousands": [
        '"{title}" by {artist} was a 2000s favorite, climbing to #{peak_rank} in {year} {emoji}',
    ],
}

# Fallback template if no tag-specific template found
fallback_templates = [
    '"{title}" by {artist} hit #{peak_rank} in {year} — a pop hit to remember.',
    'In {year}, "{title}" by {artist} climbed to #{peak_rank} on the Hot 100.',
    'Remember this one? "{title}" reached #{peak_rank} in {year}.',
]

# Hashtag generator
def generate_hashtags(song):
    base_tags = ["#pophits", "#Hot100", "#Billboard"]
    artist_tag = f"#" + re.sub(r'[^a-zA-Z0-9]', '', song['artist'])
    return " ".join(base_tags + [artist_tag])

# Generate the final post
def generate_post(song):
    tags = tag_song(song)
    random.shuffle(tags)  # Add variety
    template_used = None
    text = ""
    available_length = 280 - len(f" Check it out at https://pophits.org/songs/{song['slug']}!\\n#pophits #Hot100 #Billboard")
    for tag in tags:
        templates = template_map.get(tag)
        if templates:
            emoji = emoji_map.get(tag, "")
            template = random.choice(templates)
            new_text = template.format(
                title=song["title"],
                artist=song["artist"],
                year=song["year"],
                peak_rank=song["peak_rank"],
                weeks_on_chart=song["weeks_on_chart"],
                emoji=emoji
            )
            if len(text) + len(new_text) <= available_length:
                if new_text not in text:
                    text = new_text
                    template_used = tag
            else:
                break

    if not template_used:
        template = random.choice(fallback_templates)
        emoji = ""
        text = template.format(
            title=song["title"],
            artist=song["artist"],
            year=song["year"],
            peak_rank=song["peak_rank"],
            weeks_on_chart=weeks_on_chart,
        )

    # Ensure artist, year, and chart performance are always included
    if "{artist}" not in template and "{title}" not in template:
        text = f'"{song["title"]}" by {song["artist"]} {text}'
    if "{year}" not in template:
        text = f'{text} Released in {song["year"]}'
    if "{peak_rank}" not in template:
        text = f'{text} Peaked at #{song["peak_rank"]} on the charts'

    link = f"https://pophits.org/songs/{song['slug']}"
    hashtags = generate_hashtags(song)
    domain = "pophits.org"

    if len(text) + len(f" Check it out at {domain}!\n{hashtags}") <= 300:
        return f"{text} Check it out at {domain}!\n{hashtags}"
    else:
        return text

def get_random_song():
    def get_musicbrainz_release_id(artist, track):
        """
        Searches MusicBrainz API for a single release MBID.
        """
        base_url = "https://musicbrainz.org/ws/2/release/"
        query = f'recording:"{track}" AND artist:"{artist}" AND primarytype:single'
        url = f"{base_url}?query={query}&fmt=json"

        headers = {
            'User-Agent': 'PopHits Bluesky Automation Script (pophits.org)'
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data and 'releases' in data and len(data['releases']) > 0:
                return data['releases'][0]['id']
            else:
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error querying MusicBrainz: {e}")
            return None
        finally:
            print(f"MusicBrainz query for {artist}, {track} returned MBID: {data['releases'][0]['id'] if data and 'releases' in data and len(data['releases']) > 0 else None}")

    def get_cover_art_url(mbid):
        """
        Fetches cover art URL from Cover Art Archive.
        """
        base_url = "https://coverartarchive.org/release/"
        url = f"{base_url}{mbid}/front"
        print(f"Querying Cover Art Archive with MBID: {mbid}")

        try:
            response = requests.get(url)
            if response.status_code == 200:
                return url
            else:
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error querying Cover Art Archive: {e}")
            return None
        finally:
            print(f"Cover Art Archive query for MBID {mbid} returned status code: {response.status_code if 'response' in locals() else 'No Response'}")

    url = "https://pophits.org/api/songs/"
    page = 1
    all_songs = []
    max_pages = 5  # Limit to 5 pages
    try:
        while page <= max_pages:
            response = requests.get(f"{url}?page={page}")
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and 'results' in data and isinstance(data['results'], list) and len(data['results']) > 0:
                all_songs.extend(data['results'])
                page += 1
            else:
                break

        if all_songs:
            random_song = random.choice(all_songs)
            song_title = random_song['title']
            artist_name = random_song['artist']
            artist_name = artist_name if isinstance(artist_name, str) else random_song['artist']['name']
            year = random_song['year']
            peak_rank = random_song['peak_rank']
            slug = random_song['slug']
            weeks_on_chart = random_song.get('weeks_on_chart', 0)

            mbid = get_musicbrainz_release_id(artist_name, song_title)
            cover_art_url = None
            if mbid:
                cover_art_url = get_cover_art_url(mbid)

            song = {
                "title": song_title,
                "artist": artist_name,
                "year": year,
                "peak_rank": peak_rank,
                "weeks_on_chart": weeks_on_chart,
                "slug": slug,
                "cover_art_url": cover_art_url
            }
            return song
        else:
            print("Error: No songs found in the API response.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to retrieve song information: {e}")
        return None
    except (KeyError, TypeError) as e:
        print(f"Error: Could not parse song information from the API response: {e}")
        return None

from atproto import models as atproto_models

def create_bluesky_post(username, password, song, post_text, url, client=None):
    try:
        facets = []

        # Add link for the song URL
        domain = "pophits.org"
        url_start = post_text.find(domain)
        byte_start = len(post_text[:url_start].encode('utf-8'))
        byte_end = byte_start + len(domain.encode('utf-8'))
        facets.append(
            atproto_models.AppBskyRichtextFacet.Main(
                features=[atproto_models.AppBskyRichtextFacet.Link(uri=url)],
                index=atproto_models.AppBskyRichtextFacet.ByteSlice(byteStart=byte_start, byteEnd=byte_end),
            )
        )

        # Find hashtags and create facets for them
        for match in re.finditer(r"#\w+", post_text):
            hashtag = match.group(0)
            hashtag_start = match.start()
            hashtag_end = match.end()

            # Convert character indices to byte indices
            hashtag_byte_start = len(post_text[:hashtag_start].encode('utf-8'))
            hashtag_byte_end = len(post_text[:hashtag_end].encode('utf-8'))

            # Create facet for the hashtag
            facets.append(
                atproto_models.AppBskyRichtextFacet.Main(
                    features=[atproto_models.AppBskyRichtextFacet.Link(uri=f"https://bsky.app/search?q={hashtag[1:]}")],
                    index=atproto_models.AppBskyRichtextFacet.ByteSlice(byteStart=hashtag_byte_start, byteEnd=hashtag_byte_end),
                )
            )
        
        if song['cover_art_url']:
            image_url = song['cover_art_url']
            image_response = requests.get(image_url, stream=True)
            image_response.raise_for_status()

            image = Image.open(io.BytesIO(image_response.content))
            image_bytes = io.BytesIO()
            image.save(image_bytes, format='JPEG')
            image_bytes.seek(0)

            upload = client.upload_blob(image_bytes.read())

            client.post(
                text=post_text,
                embed=atproto_models.AppBskyEmbedImages.Main(
                    images=[
                        atproto_models.AppBskyEmbedImages.Image(
                            alt="Cover Art",
                            image=upload.blob,
                        ),
                    ],
                ),
                facets=facets,
            )
        else:
            client.post(text=post_text, facets=facets)

        print("✅ Bluesky post created successfully!")
    except Exception as e:
        print(f"🚫 Error: Failed to create Bluesky post: {e}")

def main():
    parser = argparse.ArgumentParser(description='Post a random song from pophits.org to Bluesky.')
    args = parser.parse_args()

    username = POPHITS_BLUESKY_USERNAME
    password = POPHITS_BLUESKY_PASSWORD
    
    if not username or not password:
        print(f"Error: Bluesky username and password for pophits account must be set in environment variables.")
        return

    song = get_random_song()
    if song:
        post_text = generate_post(song)
        url = f"https://pophits.org/songs/{song['slug']}"

        client = Client()
        client.login(username, password)

        create_bluesky_post(username, password, song, post_text, url, client)

if __name__ == "__main__":
    main()