import os
import json
import re
import string
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import requests
import click
from flask import Flask, abort, jsonify, render_template, request
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "UC_VGGub9Va3XpVs4s-Ld2Zw")
YOUTUBE_UPLOAD_LIMIT = int(os.getenv("YOUTUBE_UPLOAD_LIMIT", "350"))
YOUTUBE_SYNC_LIMIT = int(os.getenv("YOUTUBE_SYNC_LIMIT", "0")) or None
FEATURED_VIDEO_COUNT = int(os.getenv("FEATURED_VIDEO_COUNT", "8"))
CACHE_TTL_SECONDS = int(os.getenv("YOUTUBE_CACHE_TTL_SECONDS", "900"))
API_CURRENT_TEAM_CACHE_TTL_SECONDS = int(os.getenv("API_CURRENT_TEAM_CACHE_TTL_SECONDS", str(7 * 24 * 60 * 60)))
BALLDONTLIE_API_KEY = os.getenv("BALLDONTLIE_API_KEY")
PLAYER_INDEX_LETTERS = list(string.ascii_uppercase)
DATA_DIR = Path(__file__).resolve().parent / "data"
VIDEO_INDEX_PATH = DATA_DIR / "youtube_video_index.json"
PLAYER_ENRICHMENT_PATH = DATA_DIR / "player_enrichment.json"
NBA_ROSTER_OVERRIDES_PATH = DATA_DIR / "nba_roster_overrides.json"

_video_cache = {
    "expires_at": 0,
    "videos": [],
    "loaded": 0,
    "loaded_all": False,
}

_video_stats_cache = {
    "expires_at": 0,
    "stats": {},
}

_player_search_cache = {}
_player_enrichment_cache = None
_nba_roster_overrides_cache = None

BASKETBALL_KEYWORDS = {
    "76ers",
    "atlanta hawks",
    "basketball",
    "boston celtics",
    "brooklyn nets",
    "charlotte hornets",
    "chicago bulls",
    "cleveland cavaliers",
    "dallas mavericks",
    "denver nuggets",
    "detroit pistons",
    "golden state warriors",
    "houston rockets",
    "indiana pacers",
    "la clippers",
    "los angeles clippers",
    "los angeles lakers",
    "memphis grizzlies",
    "miami heat",
    "milwaukee bucks",
    "minnesota timberwolves",
    "nba",
    "new orleans pelicans",
    "new york knicks",
    "oklahoma city thunder",
    "orlando magic",
    "philadelphia 76ers",
    "phoenix suns",
    "portland trail blazers",
    "sacramento kings",
    "san antonio spurs",
    "toronto raptors",
    "utah jazz",
    "washington bullets",
    "washington wizards",
    "wnba",
    "ncaa",
    "march madness",
    "final four",
    "playoffs",
    "hoops",
}

NBA_TEAM_NAMES = {
    "Atlanta Hawks",
    "Boston Celtics",
    "Brooklyn Nets",
    "Charlotte Hornets",
    "Chicago Bulls",
    "Cleveland Cavaliers",
    "Dallas Mavericks",
    "Denver Nuggets",
    "Detroit Pistons",
    "Golden State Warriors",
    "Houston Rockets",
    "Indiana Pacers",
    "LA Clippers",
    "Los Angeles Clippers",
    "Los Angeles Lakers",
    "Memphis Grizzlies",
    "Miami Heat",
    "Milwaukee Bucks",
    "Minnesota Timberwolves",
    "New Orleans Pelicans",
    "New York Knicks",
    "Oklahoma City Thunder",
    "Orlando Magic",
    "Philadelphia 76ers",
    "Phoenix Suns",
    "Portland Trail Blazers",
    "Sacramento Kings",
    "San Antonio Spurs",
    "Toronto Raptors",
    "Utah Jazz",
    "Washington Bullets",
    "Washington Wizards",
}

NBA_TEAM_NAMES_LOWER = {team.lower() for team in NBA_TEAM_NAMES}

NBA_TEAM_LOCATIONS = {
    "Atlanta Hawks": {"city": "Atlanta, GA", "x": 70.4, "y": 62.3},
    "Boston Celtics": {"city": "Boston, MA", "x": 88.0, "y": 30.6},
    "Brooklyn Nets": {"city": "Brooklyn, NY", "x": 84.6, "y": 37.2},
    "Charlotte Hornets": {"city": "Charlotte, NC", "x": 75.9, "y": 56.6},
    "Chicago Bulls": {"city": "Chicago, IL", "x": 63.4, "y": 38.5},
    "Cleveland Cavaliers": {"city": "Cleveland, OH", "x": 72.5, "y": 38.0},
    "Dallas Mavericks": {"city": "Dallas, TX", "x": 49.2, "y": 67.1},
    "Denver Nuggets": {"city": "Denver, CO", "x": 36.4, "y": 44.8},
    "Detroit Pistons": {"city": "Detroit, MI", "x": 70.2, "y": 35.9},
    "Golden State Warriors": {"city": "San Francisco, CA", "x": 8.4, "y": 43.2},
    "Houston Rockets": {"city": "Houston, TX", "x": 51.7, "y": 76.2},
    "Indiana Pacers": {"city": "Indianapolis, IN", "x": 66.0, "y": 44.5},
    "LA Clippers": {"city": "Inglewood, CA", "x": 12.9, "y": 56.9},
    "Los Angeles Clippers": {"city": "Inglewood, CA", "x": 12.9, "y": 56.9},
    "Los Angeles Lakers": {"city": "Los Angeles, CA", "x": 13.1, "y": 56.7},
    "Memphis Grizzlies": {"city": "Memphis, TN", "x": 60.5, "y": 59.4},
    "Miami Heat": {"city": "Miami, FL", "x": 80.2, "y": 84.7},
    "Milwaukee Bucks": {"city": "Milwaukee, WI", "x": 62.8, "y": 35.0},
    "Minnesota Timberwolves": {"city": "Minneapolis, MN", "x": 54.6, "y": 29.8},
    "New Orleans Pelicans": {"city": "New Orleans, LA", "x": 61.2, "y": 75.1},
    "New York Knicks": {"city": "New York, NY", "x": 84.5, "y": 37.1},
    "Oklahoma City Thunder": {"city": "Oklahoma City, OK", "x": 48.1, "y": 58.8},
    "Orlando Magic": {"city": "Orlando, FL", "x": 77.2, "y": 77.0},
    "Philadelphia 76ers": {"city": "Philadelphia, PA", "x": 83.1, "y": 39.9},
    "Phoenix Suns": {"city": "Phoenix, AZ", "x": 23.2, "y": 61.6},
    "Portland Trail Blazers": {"city": "Portland, OR", "x": 12.4, "y": 20.4},
    "Sacramento Kings": {"city": "Sacramento, CA", "x": 10.2, "y": 41.4},
    "San Antonio Spurs": {"city": "San Antonio, TX", "x": 46.1, "y": 77.2},
    "Toronto Raptors": {"city": "Toronto, ON", "x": 75.2, "y": 30.8},
    "Utah Jazz": {"city": "Salt Lake City, UT", "x": 26.0, "y": 39.6},
    "Washington Bullets": {"city": "Washington, DC", "x": 80.6, "y": 43.9},
    "Washington Wizards": {"city": "Washington, DC", "x": 80.6, "y": 43.9},
}

NBA_TEAM_ABBREVIATIONS = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BRK": "Brooklyn Nets",
    "NJN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHO": "Charlotte Hornets",
    "CHH": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOH": "New Orleans Pelicans",
    "NOK": "New Orleans Pelicans",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHO": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
    "WSB": "Washington Wizards",
}

PLAYER_NAME_STOP_WORDS = {
    "highlight",
    "highlights",
    "career",
    "season",
    "game",
    "games",
    "best",
    "top",
    "nba",
    "basketball",
    "playoff",
    "playoffs",
    "finals",
    "mix",
    "mixtape",
    "full",
    "rookie",
    "insane",
    "crazy",
    "plays",
}

PLAYER_NAME_OVERRIDES = {
    "lebron james": "LeBron James",
}

SUPPORTED_LEAGUES = {
    "nba": {
        "name": "NBA",
        "description": "Basketball player pages built from The Sports Report highlight archive.",
    },
    "nfl": {
        "name": "NFL",
        "description": "Football player database coming soon.",
    },
    "mlb": {
        "name": "MLB",
        "description": "Baseball player database coming soon.",
    },
    "nhl": {
        "name": "NHL",
        "description": "Hockey player database coming soon.",
    },
}


def read_json_file(path, default):
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return default


def write_json_file(path, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, sort_keys=True)


def load_video_index():
    data = read_json_file(VIDEO_INDEX_PATH, {"videos": [], "meta": {}})
    return data.get("videos", [])


def write_video_index(videos, loaded_all):
    write_json_file(VIDEO_INDEX_PATH, {
        "meta": {
            "channel_id": YOUTUBE_CHANNEL_ID,
            "loaded_all": loaded_all,
            "video_count": len(videos),
            "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "videos": videos,
    })


def slugify(value):
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def title_case_name(value):
    small_words = {"jr", "sr", "ii", "iii", "iv"}
    words = []

    for word in value.split():
        clean_word = word.strip()
        if clean_word.lower() in small_words:
            words.append(clean_word.upper().replace("JR", "Jr").replace("SR", "Sr"))
        elif re.fullmatch(r"(?:[A-Za-z]\.){2,}", clean_word):
            words.append(clean_word.upper())
        else:
            hyphen_parts = []

            for hyphen_part in clean_word.split("-"):
                apostrophe_parts = []

                for index, part in enumerate(hyphen_part.split("'")):
                    if not part:
                        continue

                    if index > 0 and len(hyphen_part.split("'")[0]) > 1:
                        apostrophe_parts.append(part.lower())
                    else:
                        apostrophe_parts.append(part[:1].upper() + part[1:].lower())

                hyphen_parts.append("'".join(apostrophe_parts))

            words.append("-".join(hyphen_parts))

    return " ".join(words)


def request_youtube_uploads(max_results=YOUTUBE_UPLOAD_LIMIT):
    if not YOUTUBE_API_KEY:
        print("No YouTube API key found.")
        return [], True

    uploads_playlist_id = YOUTUBE_CHANNEL_ID.replace("UC", "UU", 1)
    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    videos = []
    page_token = None

    while max_results is None or len(videos) < max_results:
        params = {
            "key": YOUTUBE_API_KEY,
            "playlistId": uploads_playlist_id,
            "part": "snippet",
            "maxResults": 50 if max_results is None else min(50, max_results - len(videos)),
        }

        if page_token:
            params["pageToken"] = page_token

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException as error:
            print(f"YouTube upload fetch failed: {error.__class__.__name__}")
            return videos, False

        data = response.json()

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            resource = snippet.get("resourceId", {})
            video_id = resource.get("videoId")

            if not video_id:
                continue

            thumbnails = snippet.get("thumbnails", {})
            thumbnail = (
                thumbnails.get("maxres", {})
                or thumbnails.get("high", {})
                or thumbnails.get("medium", {})
                or thumbnails.get("default", {})
            )

            videos.append({
                "id": video_id,
                "title": snippet.get("title", "Untitled video"),
                "thumbnail": thumbnail.get("url", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "published_at": snippet.get("publishedAt", ""),
            })

        page_token = data.get("nextPageToken")

        if not page_token:
            break

    return videos, not page_token


def sync_youtube_index(max_results=YOUTUBE_SYNC_LIMIT, full=False):
    existing_videos = [] if full else load_video_index()
    existing_by_id = {
        video["id"]: video
        for video in existing_videos
        if video.get("id")
    }

    if not YOUTUBE_API_KEY:
        raise click.ClickException("YOUTUBE_API_KEY is required to sync the YouTube index.")

    uploads_playlist_id = YOUTUBE_CHANNEL_ID.replace("UC", "UU", 1)
    url = "https://www.googleapis.com/youtube/v3/playlistItems"
    fetched_videos = []
    page_token = None
    reached_existing = False
    loaded_all = False

    while max_results is None or len(fetched_videos) < max_results:
        params = {
            "key": YOUTUBE_API_KEY,
            "playlistId": uploads_playlist_id,
            "part": "snippet",
            "maxResults": 50 if max_results is None else min(50, max_results - len(fetched_videos)),
        }

        if page_token:
            params["pageToken"] = page_token

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
        except requests.RequestException as error:
            raise click.ClickException(f"YouTube upload sync failed: {error.__class__.__name__}") from error

        data = response.json()

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            resource = snippet.get("resourceId", {})
            video_id = resource.get("videoId")

            if not video_id:
                continue

            if video_id in existing_by_id and not full:
                reached_existing = True
                break

            thumbnails = snippet.get("thumbnails", {})
            thumbnail = (
                thumbnails.get("maxres", {})
                or thumbnails.get("high", {})
                or thumbnails.get("medium", {})
                or thumbnails.get("default", {})
            )

            fetched_videos.append({
                "id": video_id,
                "title": snippet.get("title", "Untitled video"),
                "thumbnail": thumbnail.get("url", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "published_at": snippet.get("publishedAt", ""),
            })

        if reached_existing:
            break

        page_token = data.get("nextPageToken")

        if not page_token:
            loaded_all = True
            break

    merged_by_id = {}

    for video in fetched_videos + existing_videos:
        video_id = video.get("id")

        if video_id and video_id not in merged_by_id:
            merged_by_id[video_id] = video

    merged_videos = sorted(
        merged_by_id.values(),
        key=lambda video: video.get("published_at", ""),
        reverse=True,
    )
    write_video_index(merged_videos, loaded_all or reached_existing)

    return {
        "fetched": len(fetched_videos),
        "total": len(merged_videos),
        "loaded_all": loaded_all,
        "reached_existing": reached_existing,
    }


def get_channel_uploads(max_results=YOUTUBE_UPLOAD_LIMIT):
    indexed_videos = load_video_index()

    if indexed_videos:
        if max_results is None:
            return indexed_videos

        return indexed_videos[:max_results]

    now = time.time()

    if (
        _video_cache["expires_at"] > now
        and (
            _video_cache["loaded_all"]
            or (max_results is not None and _video_cache["loaded"] >= max_results)
        )
    ):
        if max_results is None:
            return _video_cache["videos"]

        return _video_cache["videos"][:max_results]

    videos, loaded_all = request_youtube_uploads(max_results=max_results)

    if not videos and not loaded_all and _video_cache["videos"]:
        if max_results is None:
            return _video_cache["videos"]

        return _video_cache["videos"][:max_results]

    _video_cache["videos"] = videos
    _video_cache["loaded"] = len(videos)
    _video_cache["loaded_all"] = loaded_all
    _video_cache["expires_at"] = now + CACHE_TTL_SECONDS

    return videos


def get_latest_videos(max_results=6):
    return get_channel_uploads(max_results=max_results)


def request_video_stats(video_ids):
    if not YOUTUBE_API_KEY or not video_ids:
        return {}

    url = "https://www.googleapis.com/youtube/v3/videos"
    stats = {}

    for index in range(0, len(video_ids), 50):
        params = {
            "key": YOUTUBE_API_KEY,
            "id": ",".join(video_ids[index:index + 50]),
            "part": "statistics",
            "maxResults": 50,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException as error:
            print(f"YouTube video stats fetch failed: {error.__class__.__name__}")
            return stats

        for item in response.json().get("items", []):
            statistics = item.get("statistics", {})
            stats[item["id"]] = {
                "view_count": int(statistics.get("viewCount", 0)),
                "like_count": int(statistics.get("likeCount", 0)),
            }

    return stats


def request_channel_search(query, max_results=25):
    if not YOUTUBE_API_KEY:
        return []

    url = "https://www.googleapis.com/youtube/v3/search"
    videos = []
    page_token = None

    while len(videos) < max_results:
        params = {
            "key": YOUTUBE_API_KEY,
            "channelId": YOUTUBE_CHANNEL_ID,
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(25, max_results - len(videos)),
            "order": "relevance",
        }

        if page_token:
            params["pageToken"] = page_token

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException as error:
            print(f"YouTube channel search failed: {error.__class__.__name__}")
            return videos

        data = response.json()

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId")

            if not video_id:
                continue

            thumbnails = snippet.get("thumbnails", {})
            thumbnail = (
                thumbnails.get("high", {})
                or thumbnails.get("medium", {})
                or thumbnails.get("default", {})
            )

            videos.append({
                "id": video_id,
                "title": snippet.get("title", "Untitled video"),
                "thumbnail": thumbnail.get("url", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "published_at": snippet.get("publishedAt", ""),
                "related_match": True,
            })

        page_token = data.get("nextPageToken")

        if not page_token:
            break

    return videos


def get_video_stats(video_ids):
    now = time.time()
    requested_ids = [video_id for video_id in video_ids if video_id]

    if not requested_ids:
        return {}

    cached_stats = _video_stats_cache["stats"]

    if (
        _video_stats_cache["expires_at"] > now
        and all(video_id in cached_stats for video_id in requested_ids)
    ):
        return {video_id: cached_stats[video_id] for video_id in requested_ids}

    stats = request_video_stats(requested_ids)
    cached_stats.update(stats)
    _video_stats_cache["expires_at"] = now + CACHE_TTL_SECONDS

    return {video_id: cached_stats.get(video_id, {}) for video_id in requested_ids}


def format_count(value):
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".replace(".0M", "M")

    if value >= 1_000:
        return f"{value / 1_000:.1f}K".replace(".0K", "K")

    return str(value)


def load_player_enrichment_cache():
    global _player_enrichment_cache

    if _player_enrichment_cache is None:
        _player_enrichment_cache = read_json_file(PLAYER_ENRICHMENT_PATH, {})

    return _player_enrichment_cache


def save_player_enrichment_cache(cache):
    global _player_enrichment_cache

    _player_enrichment_cache = cache
    write_json_file(PLAYER_ENRICHMENT_PATH, cache)


def load_nba_roster_overrides():
    global _nba_roster_overrides_cache

    if _nba_roster_overrides_cache is None:
        _nba_roster_overrides_cache = read_json_file(NBA_ROSTER_OVERRIDES_PATH, {})

    return _nba_roster_overrides_cache


def save_nba_roster_overrides(overrides):
    global _nba_roster_overrides_cache

    _nba_roster_overrides_cache = overrides
    write_json_file(NBA_ROSTER_OVERRIDES_PATH, overrides)


def utc_timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_roster_override_entry(player):
    overrides = load_nba_roster_overrides()
    players = overrides.get("players", overrides)

    if not isinstance(players, dict):
        return {}

    for key in (player.get("slug", ""), normalize_lookup_name(player.get("name", ""))):
        entry = players.get(key)

        if isinstance(entry, str):
            return {"team": entry}

        if isinstance(entry, dict):
            return entry

    return {}


def get_roster_override_team(player):
    entry = get_roster_override_entry(player)
    team = entry.get("team") or entry.get("current_team") or ""

    if normalize_lookup_name(team) in NBA_TEAM_NAMES_LOWER:
        return team

    return ""


def find_wikidata_entity_id(player_name):
    try:
        response = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": player_name,
                "language": "en",
                "format": "json",
                "limit": 5,
            },
            headers={"User-Agent": "TheSportsReportPlayerDatabase/1.0"},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Wikidata entity search failed: {error.__class__.__name__}")
        return ""

    for candidate in response.json().get("search", []):
        description = candidate.get("description", "").lower()

        if "basketball" in description and "fictional" not in description:
            return candidate.get("id", "")

    first_result = response.json().get("search", [{}])[0]
    return first_result.get("id", "")


def request_wikidata_player(player_name):
    entity_id = find_wikidata_entity_id(player_name)

    if not entity_id:
        return {}

    query = f"""
    SELECT ?item ?itemLabel ?image ?birthDate ?birthPlaceLabel ?height ?countryLabel ?positionLabel ?basketballReferenceId WHERE {{
      BIND(wd:{entity_id} AS ?item)
      OPTIONAL {{ ?item wdt:P18 ?image. }}
      OPTIONAL {{ ?item wdt:P569 ?birthDate. }}
      OPTIONAL {{ ?item wdt:P19 ?birthPlace. }}
      OPTIONAL {{ ?item wdt:P2048 ?height. }}
      OPTIONAL {{ ?item wdt:P27 ?country. }}
      OPTIONAL {{ ?item wdt:P413 ?position. }}
      OPTIONAL {{ ?item wdt:P2685 ?basketballReferenceId. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 1
    """
    url = "https://query.wikidata.org/sparql"
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "TheSportsReportPlayerDatabase/1.0",
    }

    try:
        response = requests.get(url, params={"query": query}, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Wikidata player fetch failed: {error.__class__.__name__}")
        return {}

    bindings = response.json().get("results", {}).get("bindings", [])

    if not bindings:
        return {}

    player = bindings[0]
    image_url = player.get("image", {}).get("value", "")
    wikidata_url = player.get("item", {}).get("value", "")
    public_team_history = request_wikidata_team_history(wikidata_url)

    return {
        "source": "Wikidata",
        "wikidata_url": wikidata_url,
        "image": image_url,
        "birth_date": player.get("birthDate", {}).get("value", "")[:10],
        "birth_place": player.get("birthPlaceLabel", {}).get("value", ""),
        "height_m": player.get("height", {}).get("value", ""),
        "country": player.get("countryLabel", {}).get("value", ""),
        "position": player.get("positionLabel", {}).get("value", ""),
        "basketball_reference_id": player.get("basketballReferenceId", {}).get("value", ""),
        "public_team_history": public_team_history,
        "public_current_team": get_current_public_team(public_team_history),
    }


def request_wikidata_team_history(wikidata_url):
    if not wikidata_url:
        return []

    entity_id = wikidata_url.rstrip("/").split("/")[-1]
    query = f"""
    SELECT ?teamLabel ?start ?end WHERE {{
      wd:{entity_id} p:P54 ?teamStatement.
      ?teamStatement ps:P54 ?team.
      OPTIONAL {{ ?teamStatement pq:P580 ?start. }}
      OPTIONAL {{ ?teamStatement pq:P582 ?end. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    url = "https://query.wikidata.org/sparql"
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "TheSportsReportPlayerDatabase/1.0",
    }

    try:
        response = requests.get(url, params={"query": query}, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Wikidata team history fetch failed: {error.__class__.__name__}")
        return []

    teams = []

    for row in response.json().get("results", {}).get("bindings", []):
        start_date = row.get("start", {}).get("value", "")
        end_date = row.get("end", {}).get("value", "")
        start_year = int(start_date[:4]) if start_date[:4].isdigit() else None
        end_year = int(end_date[:4]) if end_date[:4].isdigit() else None

        teams.append({
            "team": row.get("teamLabel", {}).get("value", ""),
            "start_year": start_year,
            "end_year": end_year,
            "years": format_public_team_years(start_year, end_year),
            "current": end_year is None,
        })

    return sorted(
        [team for team in teams if team["team"]],
        key=lambda team: (team["start_year"] or 0, team["team"]),
    )


def request_wikidata_player_team_years(player_name, team_name):
    query = f"""
    SELECT ?start ?end WHERE {{
      ?player rdfs:label "{player_name}"@en.
      ?team rdfs:label "{team_name}"@en.
      ?player p:P54 ?teamStatement.
      ?teamStatement ps:P54 ?team.
      OPTIONAL {{ ?teamStatement pq:P580 ?start. }}
      OPTIONAL {{ ?teamStatement pq:P582 ?end. }}
    }}
    LIMIT 5
    """
    url = "https://query.wikidata.org/sparql"
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "TheSportsReportPlayerDatabase/1.0",
    }

    try:
        response = requests.get(url, params={"query": query}, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Wikidata player-team years fetch failed: {error.__class__.__name__}")
        return ""

    years = set()

    for row in response.json().get("results", {}).get("bindings", []):
        start_date = row.get("start", {}).get("value", "")
        end_date = row.get("end", {}).get("value", "")
        start_year = int(start_date[:4]) if start_date[:4].isdigit() else None
        end_year = int(end_date[:4]) if end_date[:4].isdigit() else None

        if start_year and end_year:
            years.update(range(start_year, end_year + 1))
        elif start_year:
            years.add(start_year)
        elif end_year:
            years.add(end_year)

    return ", ".join(merge_year_ranges(years)) if years else ""


def get_public_team_years(public_team_history, team_name):
    normalized_team_name = normalize_lookup_name(team_name)

    for team in public_team_history:
        if normalize_lookup_name(team.get("team", "")) == normalized_team_name:
            return team.get("years", "")

    return ""


def get_resolved_archive_team_years(player, team_name):
    cache = load_player_enrichment_cache()
    cache_key = player.get("slug", "")
    cached = cache.get(cache_key, {})
    data = cached.get("data", {})
    archive_team_years = data.setdefault("archive_team_years", {})

    if archive_team_years.get(team_name):
        return archive_team_years[team_name]

    years = get_public_team_years(data.get("public_team_history", []), team_name)

    if not years:
        years = request_basketball_reference_team_years(
            data.get("basketball_reference_id", ""),
            team_name,
        )

    if not years:
        years = request_wikidata_player_team_years(player.get("name", ""), team_name)

    archive_team_years[team_name] = years

    if cache_key:
        cached["data"] = data
        cache[cache_key] = cached
        save_player_enrichment_cache(cache)

    return years


def format_public_team_years(start_year, end_year):
    if start_year and end_year:
        return str(start_year) if start_year == end_year else f"{start_year}-{end_year}"

    if start_year:
        return f"{start_year}-present"

    if end_year:
        return str(end_year)

    return ""


def get_current_public_team(team_history):
    if not team_history:
        return ""

    current_teams = [team for team in team_history if team.get("current")]

    if current_teams:
        return max(current_teams, key=lambda team: team.get("start_year") or 0)["team"]

    return max(team_history, key=lambda team: team.get("start_year") or 0)["team"]


def get_balldontlie_search_name(player_name):
    no_periods = player_name.replace(".", "")

    if no_periods != player_name:
        return no_periods

    return player_name


def get_balldontlie_player_query(player_name):
    search_name = get_balldontlie_search_name(player_name)
    name_parts = search_name.split()

    if len(name_parts) >= 2:
        return {
            "first_name": name_parts[0],
            "last_name": " ".join(name_parts[1:]),
            "per_page": 10,
        }

    return {
        "search": search_name,
        "per_page": 10,
    }


def request_balldontlie_player(player_name):
    if not BALLDONTLIE_API_KEY:
        return {"lookup_error": "missing_api_key"}

    url = "https://api.balldontlie.io/v1/players"
    headers = {"Authorization": BALLDONTLIE_API_KEY}
    search_name = get_balldontlie_search_name(player_name)

    try:
        response = requests.get(
            url,
            headers=headers,
            params=get_balldontlie_player_query(player_name),
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        status_code = getattr(getattr(error, "response", None), "status_code", "")
        detail = f": {status_code}" if status_code else ""
        print(f"balldontlie player fetch failed{detail}: {error.__class__.__name__}")

        if status_code == 429:
            return {"lookup_error": "rate_limited"}

        return {"lookup_error": "api_error"}

    match = None
    candidates = response.json().get("data", [])
    normalized_variants = {
        normalize_lookup_name(player_name),
        normalize_lookup_name(search_name),
    }

    for candidate in candidates:
        candidate_name = f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip()

        if normalize_lookup_name(candidate_name) in normalized_variants:
            match = candidate
            break

    if not match and candidates:
        match = candidates[0]

    if not match:
        return {"lookup_error": "no_match"}

    team = match.get("team") or {}

    return {
        "source": "balldontlie",
        "balldontlie_id": match.get("id"),
        "position": match.get("position", ""),
        "height": match.get("height", ""),
        "weight": match.get("weight", ""),
        "jersey_number": match.get("jersey_number", ""),
        "college": match.get("college", ""),
        "country": match.get("country", ""),
        "draft_year": match.get("draft_year", ""),
        "draft_round": match.get("draft_round", ""),
        "draft_number": match.get("draft_number", ""),
        "current_team": team.get("full_name", ""),
        "lookup_error": "" if team.get("full_name", "") else "no_current_team",
    }


def get_stat_value(stats, *keys):
    for key in keys:
        if key in stats and stats[key] not in (None, ""):
            return stats[key]

    nested_stats = stats.get("stats") or {}

    for key in keys:
        if key in nested_stats and nested_stats[key] not in (None, ""):
            return nested_stats[key]

    return ""


def format_stat_value(value):
    if value in (None, ""):
        return ""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if number.is_integer():
        return str(int(number))

    return f"{number:.1f}"


def request_balldontlie_season_averages(player_id, draft_year=None):
    if not BALLDONTLIE_API_KEY or not player_id:
        return {}

    current_start = get_current_nba_season_start()
    first_season = max(int(draft_year or 1996), 1996)
    seasons = range(current_start, first_season - 1, -1)
    url = "https://api.balldontlie.io/v1/season_averages/general"
    headers = {"Authorization": BALLDONTLIE_API_KEY}

    for season in seasons:
        try:
            response = requests.get(
                url,
                headers=headers,
                params={
                    "season": season,
                    "season_type": "regular",
                    "type": "base",
                    "player_ids[]": player_id,
                    "per_page": 1,
                },
                timeout=10,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            print(f"balldontlie season averages fetch failed: {error.__class__.__name__}")
            return {}

        rows = response.json().get("data", [])

        if not rows:
            continue

        stats = rows[0]

        return {
            "season": season,
            "season_label": f"{season}-{season + 1}",
            "games_played": format_stat_value(get_stat_value(stats, "games_played", "gp")),
            "minutes": format_stat_value(get_stat_value(stats, "min", "minutes")),
            "points": format_stat_value(get_stat_value(stats, "pts", "points")),
            "rebounds": format_stat_value(get_stat_value(stats, "reb", "rebounds")),
            "assists": format_stat_value(get_stat_value(stats, "ast", "assists")),
            "steals": format_stat_value(get_stat_value(stats, "stl", "steals")),
            "blocks": format_stat_value(get_stat_value(stats, "blk", "blocks")),
        }

    return {}


def nba_stats_headers():
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Host": "stats.nba.com",
        "Origin": "https://www.nba.com",
        "Referer": "https://www.nba.com/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
    }


def normalize_lookup_name(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def request_nba_stats_player_id(player_name):
    url = "https://stats.nba.com/stats/playerindex"

    try:
        response = requests.get(
            url,
            headers=nba_stats_headers(),
            params={
                "LeagueID": "00",
                "Season": "",
                "Historical": 1,
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"NBA Stats player lookup failed: {error.__class__.__name__}")
        return None

    normalized_name = normalize_lookup_name(player_name)

    for result_set in response.json().get("resultSets", []):
        headers = result_set.get("headers", [])

        if "PERSON_ID" not in headers:
            continue

        person_index = headers.index("PERSON_ID")
        name_index = headers.index("PLAYER_FIRST_NAME") if "PLAYER_FIRST_NAME" in headers else None
        last_index = headers.index("PLAYER_LAST_NAME") if "PLAYER_LAST_NAME" in headers else None
        full_name_index = headers.index("PLAYER_SLUG") if "PLAYER_SLUG" in headers else None

        for row in result_set.get("rowSet", []):
            names = []

            if name_index is not None and last_index is not None:
                names.append(f"{row[name_index]} {row[last_index]}")

            if full_name_index is not None:
                names.append(str(row[full_name_index]).replace("-", " "))

            if any(normalize_lookup_name(name) == normalized_name for name in names):
                return row[person_index]

    return None


def request_nba_stats_season_averages(player_name):
    player_id = request_nba_stats_player_id(player_name)

    if not player_id:
        return {}

    url = "https://stats.nba.com/stats/playercareerstats"

    try:
        response = requests.get(
            url,
            headers=nba_stats_headers(),
            params={
                "PlayerID": player_id,
                "PerMode": "PerGame",
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"NBA Stats career stats fetch failed: {error.__class__.__name__}")
        return {}

    for result_set in response.json().get("resultSets", []):
        if result_set.get("name") != "SeasonTotalsRegularSeason":
            continue

        headers = result_set.get("headers", [])
        rows = result_set.get("rowSet", [])

        if not rows:
            return {}

        latest_row = sorted(
            rows,
            key=lambda row: str(row[headers.index("SEASON_ID")]),
            reverse=True,
        )[0]

        def value(header):
            return latest_row[headers.index(header)] if header in headers else ""

        return {
            "source": "NBA Stats",
            "season": value("SEASON_ID")[:4],
            "season_label": value("SEASON_ID"),
            "games_played": format_stat_value(value("GP")),
            "minutes": format_stat_value(value("MIN")),
            "points": format_stat_value(value("PTS")),
            "rebounds": format_stat_value(value("REB")),
            "assists": format_stat_value(value("AST")),
            "steals": format_stat_value(value("STL")),
            "blocks": format_stat_value(value("BLK")),
        }

    return {}


def strip_html(value):
    return re.sub(r"<[^>]+>", "", value).strip()


def extract_basketball_reference_cell(row_html, data_stat):
    match = re.search(
        rf'<(?:td|th)[^>]+data-stat="{re.escape(data_stat)}"[^>]*>(.*?)</(?:td|th)>',
        row_html,
        re.DOTALL,
    )

    if not match:
        return ""

    return strip_html(match.group(1))


def request_basketball_reference_season_averages(basketball_reference_id):
    if not basketball_reference_id:
        return {}

    url = f"https://www.basketball-reference.com/players/{basketball_reference_id}.html"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Basketball Reference stats fetch failed: {error.__class__.__name__}")
        return {}

    table_match = re.search(
        r'<table[^>]+id="per_game_stats"[^>]*>.*?</table>',
        response.text,
        re.DOTALL,
    )

    if not table_match:
        return {}

    rows = re.findall(
        r'<tr[^>]+id="per_game_stats\.(\d+)"[^>]*>(.*?)</tr>',
        table_match.group(0),
        re.DOTALL,
    )

    stat_rows = []

    for season_end, row_html in rows:
        if extract_basketball_reference_cell(row_html, "comp_name_abbr") != "NBA":
            continue

        stat_rows.append((int(season_end), row_html))

    if not stat_rows:
        return {}

    season_end, latest_row = sorted(stat_rows, key=lambda row: row[0], reverse=True)[0]
    season_label = extract_basketball_reference_cell(latest_row, "year_id") or f"{season_end - 1}-{season_end}"

    return {
        "source": "Basketball Reference",
        "season": season_end - 1,
        "season_label": season_label,
        "games_played": format_stat_value(extract_basketball_reference_cell(latest_row, "games")),
        "minutes": format_stat_value(extract_basketball_reference_cell(latest_row, "mp_per_g")),
        "points": format_stat_value(extract_basketball_reference_cell(latest_row, "pts_per_g")),
        "rebounds": format_stat_value(extract_basketball_reference_cell(latest_row, "trb_per_g")),
        "assists": format_stat_value(extract_basketball_reference_cell(latest_row, "ast_per_g")),
        "steals": format_stat_value(extract_basketball_reference_cell(latest_row, "stl_per_g")),
        "blocks": format_stat_value(extract_basketball_reference_cell(latest_row, "blk_per_g")),
    }


def parse_basketball_reference_season_years(season_label):
    match = re.match(r"((?:19|20)\d{2})-(\d{2})", season_label or "")

    if not match:
        return []

    start_year = int(match.group(1))
    end_year = int(match.group(2))
    end_year += 2000 if end_year < 50 else 1900

    return list(range(start_year, end_year + 1))


def request_basketball_reference_team_years(basketball_reference_id, team_name):
    if not basketball_reference_id:
        return ""

    url = f"https://www.basketball-reference.com/players/{basketball_reference_id}.html"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Basketball Reference team years fetch failed: {error.__class__.__name__}")
        return ""

    table_match = re.search(
        r'<table[^>]+id="per_game_stats"[^>]*>.*?</table>',
        response.text,
        re.DOTALL,
    )

    if not table_match:
        return ""

    years = set()

    for _, row_html in re.findall(
        r'<tr[^>]+id="per_game_stats\.(\d+)"[^>]*>(.*?)</tr>',
        table_match.group(0),
        re.DOTALL,
    ):
        team_abbr = extract_basketball_reference_cell(row_html, "team_name_abbr")

        if team_abbr == "TOT":
            continue

        if NBA_TEAM_ABBREVIATIONS.get(team_abbr) != team_name:
            continue

        years.update(
            parse_basketball_reference_season_years(
                extract_basketball_reference_cell(row_html, "year_id")
            )
        )

    return ", ".join(merge_year_ranges(years)) if years else ""


def find_basketball_reference_id_by_search(player_name):
    if not player_name:
        return ""

    try:
        response = requests.get(
            "https://www.basketball-reference.com/search/search.fcgi",
            params={"search": player_name},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Basketball Reference player search failed: {error.__class__.__name__}")
        return ""

    normalized_player_name = normalize_lookup_name(player_name)

    for match in re.finditer(
        r'href="(/players/[^"]+\.html)"[^>]*>(.*?)</a>',
        response.text,
    ):
        href = match.group(1)
        label = strip_html(match.group(2))
        label = re.sub(r"\s*\([^)]*\)", "", label)

        if normalize_lookup_name(label) != normalized_player_name:
            continue

        return href.removeprefix("/players/").removesuffix(".html")

    return ""


def request_basketball_reference_current_team(basketball_reference_id):
    if not basketball_reference_id:
        return ""

    url = f"https://www.basketball-reference.com/players/{basketball_reference_id}.html"

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        print(f"Basketball Reference current team fetch failed: {error.__class__.__name__}")
        return ""

    table_match = re.search(
        r'<table[^>]+id="per_game_stats"[^>]*>.*?</table>',
        response.text,
        re.DOTALL,
    )

    if not table_match:
        return ""

    rows = []

    for season_end, row_html in re.findall(
        r'<tr[^>]+id="per_game_stats\.(\d+)"[^>]*>(.*?)</tr>',
        table_match.group(0),
        re.DOTALL,
    ):
        team_abbr = extract_basketball_reference_cell(row_html, "team_name_abbr")

        if team_abbr == "TOT":
            continue

        season_label = extract_basketball_reference_cell(row_html, "year_id")
        season_years = parse_basketball_reference_season_years(season_label)
        team_name = NBA_TEAM_ABBREVIATIONS.get(team_abbr, "")

        if not season_years or not team_name:
            continue

        rows.append({
            "season_start": season_years[0],
            "season_end": int(season_end),
            "team": team_name,
        })

    if not rows:
        return ""

    latest_row = max(rows, key=lambda row: (row["season_start"], row["season_end"]))

    if latest_row["season_start"] < get_current_nba_season_start():
        return ""

    return latest_row["team"]


def get_api_current_team(player, resolve=False, resolve_missing_reference_id=False, force=False):
    override_team = get_roster_override_team(player)

    if override_team and not force:
        return override_team

    cache = load_player_enrichment_cache()
    cache_key = player.get("slug", "")
    cached = cache.get(cache_key, {})
    data = cached.get("data", {})
    current_team = data.get("api_current_team") or data.get("current_team") or ""

    if current_team and not force:
        return current_team

    if not resolve:
        return ""

    checked_at = data.get("api_current_team_checked_at", 0)

    if (
        not force
        and "api_current_team" in data
        and checked_at
        and checked_at + API_CURRENT_TEAM_CACHE_TTL_SECONDS > time.time()
    ):
        return data.get("api_current_team", "")

    basketball_reference_id = data.get("basketball_reference_id", "")

    if not basketball_reference_id and resolve_missing_reference_id:
        basketball_reference_id = find_basketball_reference_id_by_search(player.get("name", ""))

        if basketball_reference_id:
            data["basketball_reference_id"] = basketball_reference_id

    if not basketball_reference_id:
        public_current_team = data.get("public_current_team", "")

        if normalize_lookup_name(public_current_team) in NBA_TEAM_NAMES_LOWER:
            data["api_current_team"] = public_current_team
            data["api_current_team_checked_at"] = time.time()

            if cache_key:
                cached["data"] = data
                cache[cache_key] = cached
                save_player_enrichment_cache(cache)

            return public_current_team

        data["api_current_team"] = ""
        data["api_current_team_checked_at"] = time.time()

        if cache_key:
            cached["data"] = data
            cache[cache_key] = cached
            save_player_enrichment_cache(cache)

        return ""

    current_team = request_basketball_reference_current_team(basketball_reference_id)

    if not current_team:
        public_current_team = data.get("public_current_team", "")

        if normalize_lookup_name(public_current_team) in NBA_TEAM_NAMES_LOWER:
            current_team = public_current_team

    data["api_current_team"] = current_team
    data["api_current_team_checked_at"] = time.time()

    if cache_key:
        cached["data"] = data
        cache[cache_key] = cached
        save_player_enrichment_cache(cache)

    return current_team


def enrich_player(player):
    cache = load_player_enrichment_cache()
    cache_key = player["slug"]
    cached = cache.get(cache_key)
    now = time.time()

    cached_data = cached.get("data", {}) if cached else {}
    needs_stats_refresh = (
        not cached_data.get("stat_line")
    )
    needs_public_team_refresh = (
        bool(cached)
        and "public_team_history" not in cached_data
    )
    needs_basketball_reference_refresh = (
        bool(cached)
        and "basketball_reference_id" not in cached_data
    )

    if (
        cached
        and cached.get("expires_at", 0) > now
        and not needs_stats_refresh
        and not needs_public_team_refresh
        and not needs_basketball_reference_refresh
    ):
        data = cached.get("data", {})

        if data.get("height_m") and not data.get("balldontlie_id"):
            data.pop("height", None)

        player["bio"] = data
        return player

    wikidata = request_wikidata_player(player["name"])
    balldontlie = request_balldontlie_player(player["name"])
    data = {**wikidata, **{key: value for key, value in balldontlie.items() if value}}
    stat_line = request_balldontlie_season_averages(
        data.get("balldontlie_id"),
        data.get("draft_year"),
    )

    if not stat_line:
        stat_line = request_basketball_reference_season_averages(
            data.get("basketball_reference_id"),
        )

    if not stat_line:
        stat_line = request_nba_stats_season_averages(player["name"])

    if stat_line:
        data["stat_line"] = stat_line

    cache[cache_key] = {
        "expires_at": now + (CACHE_TTL_SECONDS * 24),
        "data": data,
    }
    save_player_enrichment_cache(cache)
    player["bio"] = data

    return player


def apply_cached_enrichment(player):
    cached = load_player_enrichment_cache().get(player["slug"], {})
    player["bio"] = cached.get("data", {})
    return player


def prepare_player_display(
    player,
    resolve_missing_team_years=False,
    resolve_api_current_team=False,
    resolve_missing_reference_id=False,
):
    bio = player.get("bio", {})
    draft_year = bio.get("draft_year") or infer_draft_year_from_videos(player.get("videos", []))

    if isinstance(draft_year, str) and draft_year.isdigit():
        draft_year = int(draft_year)

    player["public_team_history"] = bio.get("public_team_history") or []
    player["archive_team_history"] = player.get("team_history", [])
    player["display_team_history"] = []

    for team in player["archive_team_history"]:
        years = team.get("years_active") or ""

        if not years and team.get("seasons"):
            years = ", ".join(team["seasons"])

        if not years and resolve_missing_team_years:
            years = get_resolved_archive_team_years(player, team.get("team", ""))

        if not years:
            years = "Year unavailable"

        player["display_team_history"].append({
            "team": team.get("team", ""),
            "years": years,
            "video_count": team.get("video_count", 0),
        })

    player["latest_video_team"] = player.get("current_team", "")
    player["api_current_team"] = get_api_current_team(
        player,
        resolve=resolve_api_current_team,
        resolve_missing_reference_id=resolve_missing_reference_id,
    )
    player["display_current_team"] = (
        player["latest_video_team"]
        or player["api_current_team"]
        or get_current_public_team(player["public_team_history"])
    )
    player["draft_year"] = draft_year
    player["display_seasons"] = format_nba_seasons_from_year(draft_year) or player.get("seasons", [])

    return player


def is_basketball_video(video):
    title = video["title"].lower()
    return any(keyword in title for keyword in BASKETBALL_KEYWORDS)


def extract_player_name(title):
    candidate = re.sub(r"\([^)]*\)|\[[^]]*]", " ", title)
    candidate = candidate.replace("&amp;", "&")
    candidate = re.split(r"\s*\|\|\s*", candidate, maxsplit=1)[0]
    candidate = re.split(r"\s[-|:]\s", candidate, maxsplit=1)[0]
    candidate = re.split(
        r"\b(highlights?|career|season|game|games|best|top|nba|basketball|playoffs?|finals|mix|mixtape|full|rookie|insane|crazy|plays?)\b",
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    candidate = re.sub(r"\b(19|20)\d{2}\b", " ", candidate)
    candidate = re.sub(r"'s\b", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"[^A-Za-z .'-]", " ", candidate)
    words = [
        word
        for word in candidate.split()
        if word.lower().strip(".-'") not in PLAYER_NAME_STOP_WORDS
    ]

    if len(words) < 2:
        words = re.findall(r"[A-Z][a-zA-Z.'-]+", title)

    if not words:
        return "Unknown Player"

    player_name = title_case_name(" ".join(words[:4]))
    return PLAYER_NAME_OVERRIDES.get(player_name.lower(), player_name)


def normalize_team_name(value):
    cleaned = re.sub(r"\s+", " ", value.replace("&amp;", "&")).strip(" -")
    known_team = next(
        (team for team in NBA_TEAM_NAMES if team.lower() == cleaned.lower()),
        None,
    )
    return known_team or title_case_name(cleaned)


def extract_video_appearance(video):
    title = video["title"]
    parts = re.split(r"\s*\|\|\s*", title, maxsplit=1)
    player_name = extract_player_name(title)
    detail = parts[1] if len(parts) > 1 else title
    season_match = re.search(r"\b((?:19|20)\d{2})-(?:(?:19|20)?(\d{2,4}))\b", detail)

    if not season_match:
        return extract_team_prefix_appearance(title)

    start_year = int(season_match.group(1))
    end_year_text = season_match.group(2)
    end_year = int(end_year_text)

    if end_year < 100:
        end_year += 2000 if end_year < 50 else 1900

    teams_text = detail[season_match.end():]
    teams_text = re.sub(r"\bhighlights?\b.*$", "", teams_text, flags=re.IGNORECASE)
    teams_text = re.sub(r"\([^)]*\)|\[[^]]*]", " ", teams_text)
    teams = [
        normalize_team_name(team)
        for team in re.split(r"\s*/\s*|\s*,\s*|\s+\band\s+", teams_text)
        if team.strip()
    ]
    nba_teams = [
        team
        for team in teams
        if team.lower() in NBA_TEAM_NAMES_LOWER
    ]

    if not nba_teams:
        return None

    season_label = f"{start_year}-{end_year}"

    return {
        "player_name": player_name,
        "season": season_label,
        "start_year": start_year,
        "end_year": end_year,
        "teams": nba_teams,
    }


def extract_team_prefix_appearance(title):
    prefix_match = re.match(r"\s*([^:]{3,40}):\s*(.+)$", title)

    if not prefix_match:
        return None

    team_name = normalize_team_name(prefix_match.group(1))

    if team_name.lower() not in NBA_TEAM_NAMES_LOWER:
        return None

    player_text = re.sub(r"\s+ᴴᴰ.*$", "", prefix_match.group(2)).strip()
    player_text = re.sub(r"\bHD\b.*$", "", player_text, flags=re.IGNORECASE).strip()
    player_text = re.sub(r"[^A-Za-z .'-]", " ", player_text)
    player_name = title_case_name(" ".join(player_text.split()[:4]))

    if len(player_name.split()) < 2:
        return None

    player_name = PLAYER_NAME_OVERRIDES.get(player_name.lower(), player_name)

    return {
        "player_name": player_name,
        "season": "",
        "start_year": None,
        "end_year": None,
        "teams": [team_name],
    }


def merge_year_ranges(years):
    if not years:
        return []

    sorted_years = sorted(years)
    ranges = []
    start = sorted_years[0]
    end = sorted_years[0]

    for year in sorted_years[1:]:
        if year <= end + 1:
            end = year
        else:
            ranges.append((start, end))
            start = year
            end = year

    ranges.append((start, end))

    return [
        str(start) if start == end else f"{start}-{end}"
        for start, end in ranges
    ]


def build_team_history(appearances):
    teams = defaultdict(lambda: {
        "team": "",
        "seasons": set(),
        "years": set(),
        "video_count": 0,
        "latest_order": 0,
    })

    order = 0

    for appearance in appearances:
        for team in appearance["teams"]:
            order += 1
            teams[team]["team"] = team
            if appearance.get("season"):
                teams[team]["seasons"].add(appearance["season"])
            if appearance.get("start_year") and appearance.get("end_year"):
                teams[team]["years"].update(range(appearance["start_year"], appearance["end_year"] + 1))
            teams[team]["video_count"] += 1
            teams[team]["latest_order"] = order

    history = []

    for team in teams.values():
        years = sorted(team["years"])
        team["first_year"] = years[0] if years else None
        team["last_year"] = years[-1] if years else None
        team["years_active"] = ", ".join(merge_year_ranges(years)) if years else ""
        team["seasons"] = sorted(
            team["seasons"],
            key=lambda season: int(season.split("-")[0]),
            reverse=True,
        )
        history.append(team)

    return sorted(history, key=lambda team: (team["first_year"] or 9999, team["team"]))


def get_current_nba_season_start():
    current_time = time.localtime()
    return current_time.tm_year if current_time.tm_mon >= 10 else current_time.tm_year - 1


def format_nba_seasons_from_year(start_year):
    if not start_year:
        return []

    current_start = get_current_nba_season_start()

    if start_year > current_start:
        return []

    return [
        f"{season}-{season + 1}"
        for season in range(start_year, current_start + 1)
    ]


def infer_draft_year_from_videos(videos):
    for video in videos:
        match = re.search(r"\b((?:19|20)\d{2})\s+NBA\s+DRAFT\b", video.get("title", ""), re.IGNORECASE)

        if match:
            return int(match.group(1))

    return None


def get_current_team_from_history(team_history):
    if not team_history:
        return ""

    latest_team = max(team_history, key=lambda team: (team["last_year"] or -1, team["latest_order"]))
    return latest_team["team"]


def get_player_database(league_slug="nba"):
    if league_slug != "nba":
        return []

    players = defaultdict(lambda: {
        "name": "",
        "slug": "",
        "league": "NBA",
        "videos": [],
        "appearances": [],
        "seasons": set(),
    })

    for video in load_video_index():
        appearance = extract_video_appearance(video)

        if not appearance or not is_basketball_video(video):
            continue

        player_name = appearance["player_name"]
        player_slug = slugify(player_name)
        video["appearance"] = appearance

        players[player_slug]["name"] = player_name
        players[player_slug]["slug"] = player_slug
        players[player_slug]["videos"].append(video)
        players[player_slug]["appearances"].append(appearance)
        if appearance.get("season"):
            players[player_slug]["seasons"].add(appearance["season"])

    player_list = []

    for player in players.values():
        player["video_count"] = len(player["videos"])
        player["seasons"] = sorted(
            player["seasons"],
            key=lambda season: int(season.split("-")[0]) if season[:4].isdigit() else 0,
            reverse=True,
        )
        player["team_history"] = build_team_history(player["appearances"])

        if player["team_history"]:
            player["teams"] = ", ".join(team["team"] for team in player["team_history"])
            player["current_team"] = get_current_team_from_history(player["team_history"])
            player["years_active"] = ", ".join(
                merge_year_ranges({
                    year
                    for team in player["team_history"]
                    for year in team["years"]
                })
            )
        else:
            player["teams"] = "Team data unavailable"
            player["current_team"] = ""
            player["years_active"] = "Year data unavailable"

        player_list.append(player)

    return sorted(player_list, key=lambda item: item["name"])


def title_mentions_player(title, player_name):
    normalized_title = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    normalized_name = re.sub(r"[^a-z0-9]+", " ", player_name.lower()).strip()
    return f" {normalized_name} " in f" {normalized_title} "


def get_related_player_videos(player):
    cache_key = slugify(player["name"])
    now = time.time()
    cached = _player_search_cache.get(cache_key)

    if cached and cached["expires_at"] > now:
        return cached["videos"]

    videos_by_id = {
        video["id"]: video.copy()
        for video in player["videos"]
        if video.get("id")
    }

    for video in request_channel_search(player["name"]):
        if not title_mentions_player(video["title"], player["name"]):
            continue

        appearance = extract_video_appearance(video)

        if appearance:
            video["appearance"] = appearance

        videos_by_id[video["id"]] = video

    videos = sorted(
        videos_by_id.values(),
        key=lambda video: video.get("published_at", ""),
        reverse=True,
    )

    _player_search_cache[cache_key] = {
        "expires_at": now + CACHE_TTL_SECONDS,
        "videos": videos,
    }

    return videos


def get_players_by_letter(league_slug, letter):
    letter = letter.upper()

    return [
        player
        for player in get_player_database(league_slug)
        if player["name"].upper().startswith(letter)
    ]


def get_featured_basketball_videos(limit=FEATURED_VIDEO_COUNT):
    videos = []

    for video in load_video_index()[:YOUTUBE_UPLOAD_LIMIT]:
        appearance = extract_video_appearance(video)

        if not appearance or not is_basketball_video(video):
            continue

        video = video.copy()
        video["appearance"] = appearance
        videos.append(video)

    for video in videos:
        video["view_count"] = 0
        video["view_count_label"] = ""

    return sorted(
        videos,
        key=lambda video: video.get("published_at", ""),
        reverse=True,
    )[:limit]


def build_player_index(players):
    counts = {letter: 0 for letter in PLAYER_INDEX_LETTERS}

    for player in players:
        first_letter = player["name"][:1].upper()

        if first_letter in counts:
            counts[first_letter] += 1

    return [
        {
            "letter": letter,
            "count": counts[letter],
            "enabled": counts[letter] > 0,
        }
        for letter in PLAYER_INDEX_LETTERS
    ]


def score_database_search_result(item, query):
    normalized_name = normalize_lookup_name(item.get("name", ""))
    normalized_search = normalize_lookup_name(item.get("search", ""))

    if query in normalized_name:
        return 0 if item.get("type") == "team" else 1

    if query in normalized_search:
        return 2

    return 3


def prepare_players_for_team_views(players, resolve_api_current_team=False):
    return [
        prepare_player_display(
            apply_cached_enrichment(player.copy()),
            resolve_api_current_team=resolve_api_current_team,
        )
        for player in players
    ]


def build_team_directory(players, league_slug, resolve_api_current_team=False):
    prepared_players = prepare_players_for_team_views(
        players,
        resolve_api_current_team=resolve_api_current_team,
    )
    teams = defaultdict(lambda: {
        "name": "",
        "slug": "",
        "city": "",
        "url": "",
        "players": [],
        "videos": [],
        "video_ids": set(),
        "seasons": set(),
        "years": set(),
        "x": None,
        "y": None,
    })

    for player in prepared_players:
        for team in player.get("team_history", []):
            team_name = team.get("team")

            if not team_name:
                continue

            location = NBA_TEAM_LOCATIONS.get(team_name, {})
            team_slug = slugify(team_name)
            team_entry = teams[team_slug]
            team_entry["name"] = team_name
            team_entry["slug"] = team_slug
            team_entry["city"] = location.get("city", "")
            team_entry["url"] = f"/league/{league_slug}/teams/{team_slug}"
            team_entry["x"] = location.get("x")
            team_entry["y"] = location.get("y")
            team_entry["players"].append(player)
            team_entry["seasons"].update(team.get("seasons", []))
            team_entry["years"].update(team.get("years", []))

        for video in player.get("videos", []):
            appearance = video.get("appearance") or extract_video_appearance(video)

            if not appearance:
                continue

            for team_name in appearance.get("teams", []):
                team_slug = slugify(team_name)

                if team_slug not in teams:
                    continue

                video_id = video.get("id") or video.get("url") or video.get("title")

                if video_id in teams[team_slug]["video_ids"]:
                    continue

                team_video = video.copy()
                team_video["appearance"] = appearance
                teams[team_slug]["videos"].append(team_video)
                teams[team_slug]["video_ids"].add(video_id)

    team_list = []

    for team in teams.values():
        team["players"] = sorted(
            team["players"],
            key=lambda player: player["name"],
        )
        team["videos"] = sorted(
            team["videos"],
            key=lambda video: video.get("published_at", ""),
            reverse=True,
        )
        team["player_count"] = len(team["players"])
        team["video_count"] = len(team["videos"])
        current_players = []
        legacy_players = []

        for player in team["players"]:
            current_team = player.get("api_current_team") or ""
            player["team_label"] = f"API current: {current_team}" if current_team else "API current team unavailable"

            if slugify(current_team) == team["slug"]:
                current_players.append(player)
            else:
                legacy_players.append(player)

        current_player_slugs = {player["slug"] for player in current_players}
        team["current_players"] = current_players
        team["legacy_players"] = legacy_players
        team["current_videos"] = [
            video
            for video in team["videos"]
            if slugify(video.get("appearance", {}).get("player_name", "")) in current_player_slugs
        ]
        team["legacy_videos"] = [
            video
            for video in team["videos"]
            if slugify(video.get("appearance", {}).get("player_name", "")) not in current_player_slugs
        ]
        team["seasons"] = sorted(
            team["seasons"],
            key=lambda season: int(season.split("-")[0]) if season[:4].isdigit() else 0,
            reverse=True,
        )
        team["years_active"] = ", ".join(merge_year_ranges(team["years"])) if team["years"] else ""
        team.pop("video_ids", None)
        team_list.append(team)

    return sorted(team_list, key=lambda item: item["name"])


def split_team_current_and_legacy(team, resolve_api_current_team=False):
    current_players = []
    legacy_players = []

    for player in team["players"]:
        if resolve_api_current_team:
            player["api_current_team"] = get_api_current_team(player, resolve=True)

        current_team = player.get("api_current_team") or ""
        player["team_label"] = f"API current: {current_team}" if current_team else "API current team unavailable"

        if slugify(current_team) == team["slug"]:
            current_players.append(player)
        else:
            legacy_players.append(player)

    current_player_slugs = {player["slug"] for player in current_players}
    team["current_players"] = current_players
    team["legacy_players"] = legacy_players
    team["current_videos"] = [
        video
        for video in team["videos"]
        if slugify(video.get("appearance", {}).get("player_name", "")) in current_player_slugs
    ]
    team["legacy_videos"] = [
        video
        for video in team["videos"]
        if slugify(video.get("appearance", {}).get("player_name", "")) not in current_player_slugs
    ]

    return team


def build_database_search_index(players, league_slug):
    prepared_players = prepare_players_for_team_views(players)
    team_directory = build_team_directory(players, league_slug)
    player_entries = []

    for player in prepared_players:
        current_team = player.get("display_current_team") or "Team unavailable"
        player_entries.append({
            "type": "player",
            "name": player["name"],
            "team": current_team,
            "url": f"/league/{league_slug}/players/{player['slug']}",
            "search": " ".join([
                player["name"],
                current_team,
                player.get("teams", ""),
            ]),
        })

    team_entries = []

    for team in team_directory:
        player_names = [player["name"] for player in team["players"]]
        team_entries.append({
            "type": "team",
            "name": team["name"],
            "team": f"{team['player_count']} listed player{'' if team['player_count'] == 1 else 's'}",
            "players": player_names,
            "url": team["url"],
            "search": " ".join([team["name"], team.get("city", ""), *player_names]),
        })

    return sorted(
        player_entries + team_entries,
        key=lambda item: (item["type"] != "player", item["name"]),
    )


@app.route("/")
def home():
    videos = get_latest_videos()

    return render_template("index.html", videos=videos)


@app.route("/league/<league_slug>")
def league_page(league_slug):
    league = SUPPORTED_LEAGUES.get(league_slug)

    if not league:
        abort(404)

    players = get_player_database(league_slug) if league_slug == "nba" else []
    player_index = build_player_index(players) if league_slug == "nba" else []
    featured_videos = get_featured_basketball_videos() if league_slug == "nba" else []
    search_index = build_database_search_index(players, league_slug) if league_slug == "nba" else []
    team_map = build_team_directory(players, league_slug) if league_slug == "nba" else []

    return render_template(
        "league.html",
        league=league,
        league_slug=league_slug,
        player_count=len(players),
        player_index=player_index,
        featured_videos=featured_videos,
        search_index=search_index,
        team_map=team_map,
        has_youtube_key=bool(YOUTUBE_API_KEY),
    )


@app.route("/league/<league_slug>/search")
def league_search(league_slug):
    league = SUPPORTED_LEAGUES.get(league_slug)

    if not league:
        abort(404)

    players = get_player_database(league_slug) if league_slug == "nba" else []
    query = normalize_lookup_name(request.args.get("q", ""))
    search_index = build_database_search_index(players, league_slug)

    if not query:
        return jsonify([])

    results = [
        item
        for item in search_index
        if query in normalize_lookup_name(item.get("search", ""))
    ]
    results = sorted(
        results,
        key=lambda item: (score_database_search_result(item, query), item["name"]),
    )

    return jsonify(results[:10])


@app.route("/league/<league_slug>/teams/<team_slug>")
def team_page(league_slug, team_slug):
    league = SUPPORTED_LEAGUES.get(league_slug)

    if not league:
        abort(404)

    players = get_player_database(league_slug)
    teams = build_team_directory(players, league_slug)
    team = next((item for item in teams if item["slug"] == team_slug), None)

    if not team:
        abort(404)

    team = split_team_current_and_legacy(team)

    return render_template(
        "team.html",
        league=league,
        league_slug=league_slug,
        team=team,
    )


@app.route("/league/<league_slug>/players")
def player_index_page(league_slug):
    league = SUPPORTED_LEAGUES.get(league_slug)

    if not league:
        abort(404)

    letter = (request.args.get("letter") or "A")[:1].upper()

    if letter not in PLAYER_INDEX_LETTERS:
        abort(404)

    all_players = get_player_database(league_slug)
    players = [
        player
        for player in all_players
        if player["name"].upper().startswith(letter)
    ]
    players = [
        prepare_player_display(apply_cached_enrichment(player))
        for player in players
    ]

    return render_template(
        "players_by_letter.html",
        league=league,
        league_slug=league_slug,
        letter=letter,
        player_index=build_player_index(all_players),
        players=players,
    )


@app.route("/league/<league_slug>/players/<player_slug>")
def player_page(league_slug, player_slug):
    league = SUPPORTED_LEAGUES.get(league_slug)

    if not league:
        abort(404)

    players = get_player_database(league_slug)
    player = next((item for item in players if item["slug"] == player_slug), None)

    if not player:
        abort(404)

    player["videos"] = sorted(
        player["videos"],
        key=lambda video: video.get("published_at", ""),
        reverse=True,
    )
    player["video_count"] = len(player["videos"])
    player = apply_cached_enrichment(player)
    player = prepare_player_display(
        player,
        resolve_missing_team_years=False,
        resolve_api_current_team=False,
        resolve_missing_reference_id=False,
    )

    return render_template(
        "player.html",
        league=league,
        league_slug=league_slug,
        player=player,
    )


@app.cli.command("sync-youtube-index")
@click.option("--full", is_flag=True, help="Rebuild the index from the start of the uploads playlist.")
@click.option("--limit", default=None, type=int, help="Maximum uploads to scan during this sync.")
def sync_youtube_index_command(full, limit):
    result = sync_youtube_index(max_results=limit or YOUTUBE_SYNC_LIMIT, full=full)
    click.echo(
        "Fetched {fetched} new videos. Indexed {total} videos. "
        "loaded_all={loaded_all} reached_existing={reached_existing}".format(**result)
    )


@app.cli.command("warm-player-data")
@click.option("--limit", default=0, type=int, help="Maximum player records to enrich. Use 0 for all.")
def warm_player_data_command(limit):
    players = get_player_database("nba")

    if limit:
        players = players[:limit]

    for player in players:
        enrich_player(player)
        click.echo(f"Warmed {player['name']}")

    click.echo(f"Warmed {len(players)} player profiles.")


@app.cli.command("refresh-roster-overrides")
@click.option("--limit", default=0, type=int, help="Maximum player records to check. Use 0 for all.")
@click.option("--start", default=0, type=int, help="Zero-based player offset to start from.")
@click.option("--delay", default=20.0, type=float, help="Seconds to wait between balldontlie lookups.")
@click.option("--team", "team_slug", default="", help="Only refresh players attached to this team slug, such as miami-heat.")
@click.option("--force", is_flag=True, help="Refresh players even when an override already exists.")
@click.option("--dry-run", is_flag=True, help="Call balldontlie and print results without writing JSON.")
def refresh_roster_overrides_command(limit, start, delay, team_slug, force, dry_run):
    if not BALLDONTLIE_API_KEY:
        click.echo("BALLDONTLIE_API_KEY is not configured. Add it to .env before refreshing rosters.")
        return

    players = get_player_database("nba")

    if team_slug:
        players = [
            player
            for player in players
            if any(slugify(team.get("team", "")) == team_slug for team in player.get("team_history", []))
        ]

    if start:
        players = players[start:]

    if limit:
        players = players[:limit]

    overrides = load_nba_roster_overrides()

    if not isinstance(overrides, dict):
        overrides = {}

    override_players = overrides.setdefault("players", {})
    metadata = overrides.setdefault("meta", {})
    cache = load_player_enrichment_cache()
    checked = 0
    updated = 0
    skipped = 0

    for index, player in enumerate(players):
        existing = override_players.get(player["slug"])

        if existing and not force:
            skipped += 1
            click.echo(f"Skipped {player['name']}: override already exists")
            continue

        balldontlie = request_balldontlie_player(player["name"])
        checked += 1
        team = balldontlie.get("current_team", "")

        if team:
            timestamp = utc_timestamp()

            if not dry_run:
                override_players[player["slug"]] = {
                    "team": team,
                    "source": "balldontlie",
                    "updated_at": timestamp,
                }

                cached = cache.get(player["slug"], {})
                data = cached.get("data", {})
                data["api_current_team"] = team
                data["api_current_team_checked_at"] = time.time()
                cached["data"] = data
                cache[player["slug"]] = cached

            updated += 1
            click.echo(f"Updated {player['name']}: {team}")
        else:
            reason = balldontlie.get("lookup_error") or "unknown"
            click.echo(f"Unavailable {player['name']}: {reason}")

            if reason == "rate_limited":
                click.echo("Stopping early because balldontlie returned 429. Increase --delay before continuing.")
                break

        if index < len(players) - 1 and delay > 0:
            time.sleep(delay)

    if not dry_run:
        metadata["source"] = "balldontlie"
        metadata["updated_at"] = utc_timestamp()
        save_nba_roster_overrides(overrides)
        save_player_enrichment_cache(cache)

    if dry_run:
        click.echo("Dry run complete. No JSON files were written.")

    click.echo(f"Checked {checked} players. Updated {updated}. Skipped {skipped}.")


@app.cli.command("rebuild-roster-overrides-from-youtube")
@click.option("--limit", default=0, type=int, help="Maximum player records to write. Use 0 for all.")
@click.option("--team", "team_slug", default="", help="Only write players attached to this team slug, such as miami-heat.")
@click.option("--force", is_flag=True, help="Overwrite manual override entries too.")
def rebuild_roster_overrides_from_youtube_command(limit, team_slug, force):
    players = get_player_database("nba")

    if team_slug:
        players = [
            player
            for player in players
            if any(slugify(team.get("team", "")) == team_slug for team in player.get("team_history", []))
        ]

    if limit:
        players = players[:limit]

    overrides = load_nba_roster_overrides()

    if not isinstance(overrides, dict):
        overrides = {}

    override_players = overrides.setdefault("players", {})
    metadata = overrides.setdefault("meta", {})
    timestamp = utc_timestamp()
    written = 0
    skipped = 0
    unavailable = 0

    for player in players:
        current_team = player.get("current_team", "")

        if not current_team:
            unavailable += 1
            click.echo(f"Unavailable {player['name']}: no_youtube_team")
            continue

        existing = override_players.get(player["slug"])
        existing_source = existing.get("source") if isinstance(existing, dict) else ""

        if existing and existing_source == "manual" and not force:
            skipped += 1
            click.echo(f"Skipped {player['name']}: manual override")
            continue

        override_players[player["slug"]] = {
            "team": current_team,
            "source": "youtube_archive",
            "updated_at": timestamp,
        }
        written += 1
        click.echo(f"Wrote {player['name']}: {current_team}")

    metadata["source"] = "youtube_archive"
    metadata["updated_at"] = timestamp
    save_nba_roster_overrides(overrides)
    click.echo(f"Wrote {written} players. Skipped {skipped}. Unavailable {unavailable}.")


@app.cli.command("warm-current-teams")
@click.option("--limit", default=0, type=int, help="Maximum player records to check. Use 0 for all.")
@click.option("--delay", default=12.0, type=float, help="Seconds to wait between uncached API lookups.")
@click.option("--team", "team_slug", default="", help="Only warm players attached to this team slug, such as miami-heat.")
@click.option("--force", is_flag=True, help="Refresh current-team cache even when a value already exists.")
def warm_current_teams_command(limit, delay, team_slug, force):
    players = get_player_database("nba")

    if team_slug:
        players = [
            player
            for player in players
            if any(slugify(team.get("team", "")) == team_slug for team in player.get("team_history", []))
        ]

    if limit:
        players = players[:limit]

    cache = load_player_enrichment_cache()
    checked = 0
    attempted_api = 0

    for index, player in enumerate(players):
        cached_data = cache.get(player["slug"], {}).get("data", {})
        checked_at = cached_data.get("api_current_team_checked_at", 0)
        has_fresh_cache = (
            not force
            and "api_current_team" in cached_data
            and checked_at
            and checked_at + API_CURRENT_TEAM_CACHE_TTL_SECONDS > time.time()
        )
        has_current_team = bool(cached_data.get("api_current_team") or cached_data.get("current_team"))

        if has_current_team and not force:
            team = get_api_current_team(player)
            click.echo(f"Cached {player['name']}: {team}")
            checked += 1
            continue

        if has_fresh_cache:
            click.echo(f"Recently checked {player['name']}: unavailable")
            checked += 1
            continue

        team = get_api_current_team(
            player,
            resolve=True,
            resolve_missing_reference_id=True,
            force=force,
        )
        attempted_api += 1
        checked += 1
        click.echo(f"Warmed {player['name']}: {team or 'unavailable'}")

        if index < len(players) - 1 and delay > 0:
            time.sleep(delay)

    click.echo(f"Checked {checked} players. Attempted {attempted_api} uncached API lookup(s).")


if __name__ == "__main__":
    app.run(debug=True)
