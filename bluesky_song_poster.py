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

from templates import TEMPLATES as template_map, FALLBACK_TEMPLATES as fallback_templates

load_dotenv()

POPHITS_BLUESKY_USERNAME = os.environ.get('POPHITS_BLUESKY_USERNAME')
POPHITS_BLUESKY_PASSWORD = os.environ.get('POPHITS_BLUESKY_PASSWORD')
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')

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

def generate_hashtags(song):
    base_tags = ["#pophits", "#Hot100", "#Billboard"]
    artist_tag = f"#" + re.sub(r'[^a-zA-Z0-9]', '', song['artist'])
    return " ".join(base_tags + [artist_tag])

def generate_post(song):
    tags = tag_song(song)
    random.shuffle(tags)
    template_used = None
    text = ""
    available_length = 280 - len(f" Check it out at https://pophits.org/songs/{song['slug']}!\\n#pophits #Hot100 #Billboard")
    chosen_template = None

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
                    chosen_template = template
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
            weeks_on_chart=song["weeks_on_chart"],
        )
        chosen_template = template

    # Ensure artist, year, and chart performance are always included
    if "{artist}" not in chosen_template and "{title}" not in chosen_template:
        text = f'"{song["title"]}" by {song["artist"]} {text}'
    if "{year}" not in chosen_template:
        text = f'{text} Released in {song["year"]}'
    if "{peak_rank}" not in chosen_template:
        text = f'{text} Peaked at #{song["peak_rank"]} on the charts'

    # No YouTube URL fallback needed - we only post with images now

    link = f"https://pophits.org/songs/{song['slug']}"
    hashtags = generate_hashtags(song)
    if len(text) + len(f" Check it out at {link}!\n{hashtags}") <= 300:
        return f"{text} Check it out at {link}!\n{hashtags}"
    else:
        return text

def get_random_song():
    """Fetch a random song from PopHits API; only return if cover art is available."""
    def get_musicbrainz_release_id(artist, track):
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

    def get_cover_art_url(mbid):
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
            print(
                f"Cover Art Archive query for MBID {mbid} returned status code: "
                f"{response.status_code if 'response' in locals() else 'No Response'}"
            )

    url = "https://pophits.org/api/songs/random-song/"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        song_title = data['title']
        artist_name = data['artist'] if isinstance(data['artist'], str) else data['artist']['name']
        year = data['year']
        peak_rank = data['peak_rank']
        slug = data['slug']
        weeks_on_chart = data.get('weeks_on_chart', 0)

        mbid = get_musicbrainz_release_id(artist_name, song_title)
        cover_art_url = None
        if mbid:
            cover_art_url = get_cover_art_url(mbid)

        # Only return song if cover art is available
        if not cover_art_url:
            print(f"⚠️ No cover art found for '{song_title}' by {artist_name}. Skipping post.")
            return None

        song = {
            "title": song_title,
            "artist": artist_name,
            "year": year,
            "peak_rank": peak_rank,
            "weeks_on_chart": weeks_on_chart,
            "slug": slug,
            "cover_art_url": cover_art_url,
        }
        return song
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving random song: {e}")
        return None
    except (KeyError, TypeError) as e:
        print(f"Error parsing random song API response: {e}")
        return None

def create_bluesky_post(username, password, song, post_text, url, client=None, dry_run=False):
    try:
        print("--- DRY RUN OUTPUT ---" if dry_run else "", end="")
        print("\nPOST TEXT:\n", post_text)
        print("SONG INFO:", song)
        print("SONG URL:", url)
        print("COVER ART URL:", song.get('cover_art_url'))
        if dry_run:
            print("\n(DRY RUN: No post will be made)\n")
            return

        # Facet generation:
        facets = []
        
        # Find the FULL URL in the post text, not just the domain
        full_url = f"https://pophits.org/songs/{song['slug']}"
        url_start = post_text.find(full_url)
        
        if url_start != -1:
            url_end = url_start + len(full_url)
            byte_start = len(post_text[:url_start].encode('utf-8'))
            byte_end = len(post_text[:url_end].encode('utf-8'))
            facets.append(
                atproto_models.AppBskyRichtextFacet.Main(
                    features=[atproto_models.AppBskyRichtextFacet.Link(uri=full_url)],
                    index=atproto_models.AppBskyRichtextFacet.ByteSlice(byteStart=byte_start, byteEnd=byte_end),
                )
            )

        # Hashtag facets
        for match in re.finditer(r"#\w+", post_text):
            hashtag = match.group(0)
            hashtag_start = match.start()
            hashtag_end = match.end()
            hashtag_byte_start = len(post_text[:hashtag_start].encode('utf-8'))
            hashtag_byte_end = len(post_text[:hashtag_end].encode('utf-8'))
            facets.append(
                atproto_models.AppBskyRichtextFacet.Main(
                    features=[atproto_models.AppBskyRichtextFacet.Link(uri=f"https://bsky.app/search?q={hashtag[1:]}")],
                    index=atproto_models.AppBskyRichtextFacet.ByteSlice(
                        byteStart=hashtag_byte_start, byteEnd=hashtag_byte_end
                    ),
                )
            )

        # Rest of your code remains the same...
        if song.get('cover_art_url'):
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
            print("⚠️ Warning: Attempted to post without cover art - this shouldn't happen!")
            return

        print("✅ Bluesky post created successfully!")
    except Exception as e:
        print(f"🚫 Error: Failed to create Bluesky post: {e}")

def main():
    parser = argparse.ArgumentParser(description='Post a random song from pophits.org to Bluesky.')
    parser.add_argument('--dry-run', action='store_true', help='Only print the post, do not publish it.')
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
        if args.dry_run:
            create_bluesky_post(username, password, song, post_text, url, dry_run=True)
        else:
            client = Client()
            client.login(username, password)
            create_bluesky_post(username, password, song, post_text, url, client, dry_run=False)
    else:
        print("🚫 No song with cover art found. No post will be made.")

if __name__ == "__main__":
    main()
