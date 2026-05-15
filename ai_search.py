#!/usr/bin/env python3
"""
AI Search Script - Groq (PRIMARY) / Gemini Flash (BACKUP)
Discovers all anime content: Episodes, Movies, Specials, OVA, ONA
Then searches Nyaa.si for each and extracts magnet links.

IMPORTANT: Only the final JSON is printed to stdout (for pipeline capture).
All progress/info is printed to stderr.
"""

import sys
import os
import json
import time
import re
import requests
from urllib.parse import quote

# ===== Configuration =====
# Hardcoded fallback keys as requested by user
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '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')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
JIKAN_BASE = 'https://api.jikan.moe/v4'
ANILIST_BASE = 'https://graphql.anilist.co'
NYAA_BASE = 'https://nyaa.si'

def log(msg):
    """Print to stderr so it doesn't corrupt stdout JSON output"""
    print(msg, file=sys.stderr)

# ===== Groq AI (PRIMARY) =====
def groq_chat(prompt, system_prompt="", max_retries=3):
    """Use Groq as primary AI for lightweight tasks"""
    if not GROQ_API_KEY or GROQ_API_KEY.strip() == "":
        log("[Groq] No API key set, skipping")
        return None

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)

        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model='llama-3.1-8b-instant',  # Fast & lightweight
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=4096,
                )
                return response.choices[0].message.content
            except Exception as e:
                log(f"Groq attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
    except ImportError:
        log("[Groq] groq package not installed, skipping")

    return None

# ===== Gemini Flash (BACKUP) =====
def gemini_chat(prompt, system_prompt="", max_retries=3):
    """Use Gemini Flash as backup AI - uses the new google-genai package"""
    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "":
        log("[Gemini] No API key set, skipping")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        for attempt in range(max_retries):
            try:
                config = types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                    system_instruction=system_prompt if system_prompt else None
                )

                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt,
                    config=config,
                )
                return response.text
            except Exception as e:
                log(f"Gemini attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

    except ImportError:
        log("[Gemini] google-genai not installed, skipping")

    return None

def ai_chat(prompt, system_prompt=""):
    """Try Groq first, fall back to Gemini"""
    result = groq_chat(prompt, system_prompt)
    if result:
        log("[AI] Used Groq (primary)")
        return result

    log("[AI] Groq failed or skipped, falling back to Gemini Flash...")
    result = gemini_chat(prompt, system_prompt)
    if result:
        log("[AI] Used Gemini Flash (backup)")
        return result

    log("[AI] Both AI providers failed or were skipped!")
    return None

# ===== MAL/AniList Data Fetching =====
def fetch_mal_anime(query):
    """Fetch anime data from MyAnimeList via Jikan API"""
    try:
        res = requests.get(f'{JIKAN_BASE}/anime', params={'q': query, 'limit': 5, 'sfw': 'true'}, timeout=15)
        if res.status_code == 429:
            time.sleep(2)
            res = requests.get(f'{JIKAN_BASE}/anime', params={'q': query, 'limit': 5, 'sfw': 'true'}, timeout=15)
        res.raise_for_status()
        data = res.json().get('data', [])
        if data:
            # Get full details of first match
            mal_id = data[0]['mal_id']
            time.sleep(0.5)  # Rate limit
            full_res = requests.get(f'{JIKAN_BASE}/anime/{mal_id}/full', timeout=15)
            if full_res.status_code == 429:
                time.sleep(2)
                full_res = requests.get(f'{JIKAN_BASE}/anime/{mal_id}/full', timeout=15)
            if full_res.status_code == 200:
                return full_res.json().get('data', data[0])
        return data[0] if data else None
    except Exception as e:
        log(f"MAL fetch error: {e}")
        return None

def fetch_anilist_anime(query):
    """Fetch anime data from AniList"""
    gql = """
    query ($search: String) {
        Page(page: 1, perPage: 5) {
            media(search: $search, type: ANIME, isAdult: false) {
                id idMal
                title { romaji english native }
                episodes format status seasonYear
                nextAiringEpisode { episode airingAt }
                airingSchedule { nodes { episode airingAt } }
                relations { edges { relationType node { id title { romaji english } format episodes type } } }
            }
        }
    }
    """
    try:
        res = requests.post(ANILIST_BASE, json={'query': gql, 'variables': {'search': query}}, timeout=15)
        res.raise_for_status()
        data = res.json().get('data', {}).get('Page', {}).get('media', [])
        return data[0] if data else None
    except Exception as e:
        log(f"AniList fetch error: {e}")
        return None

# ===== AI Content Discovery =====
def discover_all_content(anime_name, mal_data=None, anilist_data=None):
    """Use AI to list ALL anime content: Episodes, Movies, Specials, OVA, ONA"""

    # Build context from API data
    context = f"Anime: {anime_name}\n"

    if mal_data:
        relations_str = 'None'
        try:
            relations_str = json.dumps([
                {'type': r.get('relation',''), 'name': r.get('entry',[{}])[0].get('name','') if r.get('entry') else ''}
                for r in (mal_data.get('relations') or [])[:10]
            ])
        except Exception:
            pass

        context += f"""
MAL Data:
- Title: {mal_data.get('title', '')}
- English: {mal_data.get('title_english', '')}
- Japanese: {mal_data.get('title_japanese', '')}
- Type: {mal_data.get('type', '')}
- Episodes: {mal_data.get('episodes', 'Unknown')}
- Status: {mal_data.get('status', '')}
- Score: {mal_data.get('score', 'N/A')}
- Season: {mal_data.get('season', '')} {mal_data.get('year', '')}
- Relations: {relations_str}
"""

    if anilist_data:
        next_ep = anilist_data.get('nextAiringEpisode') or {}
        relations_str = 'None'
        try:
            relations_str = json.dumps([
                {'type': e.get('relationType',''), 'name': e.get('node',{}).get('title',{}).get('romaji','')}
                for e in ((anilist_data.get('relations') or {}).get('edges') or [])[:10]
            ])
        except Exception:
            pass

        context += f"""
AniList Data:
- Format: {anilist_data.get('format', '')}
- Episodes: {anilist_data.get('episodes', 'Unknown')}
- Status: {anilist_data.get('status', '')}
- Next Episode: {next_ep.get('episode', 'N/A')} at {next_ep.get('airingAt', 'N/A')}
- Relations: {relations_str}
"""

    mal_id_val = mal_data.get('mal_id', 'null') if mal_data else 'null'

    system_prompt = """You are an anime content discovery expert. Your job is to list ALL content for a given anime series, including:
1. Regular Episodes (TV episodes)
2. Movies
3. Specials
4. OVAs
5. ONAs
6. Recap episodes
7. Extra episodes

You MUST output valid JSON only, no other text. Do NOT wrap it in markdown code blocks."""

    prompt = f"""Based on the following anime information, list ALL content available for this anime.
Include every episode, movie, special, OVA, and ONA.

{context}

Return a JSON object with this exact structure (output ONLY the JSON, nothing else):
{{
    "anime_title": "Full anime title in English",
    "anime_title_japanese": "Japanese title if known",
    "anime_title_romaji": "Romaji title if known",
    "mal_id": {mal_id_val},
    "status": "Currently Airing / Finished Airing / Not yet aired",
    "total_episodes": number_or_null,
    "next_episode": number_or_null,
    "content": [
        {{
            "type": "episode",
            "number": 1,
            "title": "Episode 1",
            "search_query": "anime title Episode 1 1080p",
            "search_query_alt": "anime title EP01 1080p"
        }},
        {{
            "type": "movie",
            "number": 1,
            "title": "Movie Name",
            "search_query": "anime title Movie 1080p",
            "search_query_alt": "anime title Movie 1080p BluRay"
        }},
        {{
            "type": "special",
            "number": 1,
            "title": "Special Name",
            "search_query": "anime title Special 1080p",
            "search_query_alt": "anime title SP01 1080p"
        }},
        {{
            "type": "ova",
            "number": 1,
            "title": "OVA Name",
            "search_query": "anime title OVA 1080p",
            "search_query_alt": "anime title OVA 1080p"
        }}
    ],
    "search_queries": {{
        "batch_query": "anime title batch 1080p",
        "batch_query_alt": "anime title complete 1080p",
        "movie_query": "anime title movie 1080p",
        "special_query": "anime title specials 1080p"
    }}
}}

For episodes, if the anime has many episodes (50+), group them in batches (e.g., 1-12, 13-24).
For ongoing anime, list only confirmed aired episodes.
For each item, provide TWO search queries: one natural and one abbreviated.
Make sure to include MOVIES, SPECIALS, OVAs as separate entries.
Output ONLY valid JSON. No markdown, no explanation."""

    result = ai_chat(prompt, system_prompt)

    if not result:
        # Fallback: generate basic content list from API data
        log("[AI] AI failed, generating basic content list from API data")
        return generate_fallback_content(anime_name, mal_data, anilist_data)

    # Parse JSON from AI response
    try:
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(.*?)```', result, re.DOTALL)
        if json_match:
            result = json_match.group(1)

        # Also try to find the first { ... } block
        result = result.strip()
        if not result.startswith('{'):
            brace_start = result.find('{')
            if brace_start >= 0:
                result = result[brace_start:]

        content_data = json.loads(result)
        return content_data
    except json.JSONDecodeError as e:
        log(f"[AI] Failed to parse AI response as JSON: {e}")
        log(f"Raw response (first 500 chars): {result[:500]}")
        return generate_fallback_content(anime_name, mal_data, anilist_data)

def generate_fallback_content(anime_name, mal_data=None, anilist_data=None):
    """Fallback content list when AI fails"""
    episodes = None
    if mal_data:
        episodes = mal_data.get('episodes')
    if not episodes and anilist_data:
        episodes = anilist_data.get('episodes')

    content = []
    if episodes:
        for i in range(1, episodes + 1):
            content.append({
                "type": "episode",
                "number": i,
                "title": f"Episode {i}",
                "search_query": f"{anime_name} Episode {i} 1080p",
                "search_query_alt": f"{anime_name} EP{i:02d} 1080p"
            })

    return {
        "anime_title": anime_name,
        "anime_title_japanese": "",
        "anime_title_romaji": "",
        "mal_id": mal_data.get('mal_id') if mal_data else None,
        "status": mal_data.get('status', 'Unknown') if mal_data else 'Unknown',
        "total_episodes": episodes,
        "next_episode": None,
        "content": content,
        "search_queries": {
            "batch_query": f"{anime_name} batch 1080p",
            "batch_query_alt": f"{anime_name} complete 1080p",
            "movie_query": f"{anime_name} movie 1080p",
            "special_query": f"{anime_name} specials 1080p"
        }
    }

# ===== Main =====
def main():
    import argparse
    parser = argparse.ArgumentParser(description='AI Anime Content Discovery')
    parser.add_argument('anime_name', help='Anime name to search for')
    parser.add_argument('--type', dest='anime_type', default='all',
                       help='Content type filter (all, episode, movie, special, ova, ona)')
    args = parser.parse_args()

    anime_name = args.anime_name
    anime_type = args.anime_type
    log(f"\n{'='*60}")
    log(f"  AI Content Discovery: {anime_name}")
    log(f"{'='*60}\n")

    # Log API key status (don't log the actual keys)
    log(f"  Groq API key: {'SET' if GROQ_API_KEY else 'NOT SET'}")
    log(f"  Gemini API key: {'SET' if GEMINI_API_KEY else 'NOT SET'}")

    # Step 1: Fetch data from MAL and AniList
    log("[1/2] Fetching anime data from MAL & AniList...")
    mal_data = fetch_mal_anime(anime_name)
    if mal_data:
        log(f"  MAL: {mal_data.get('title')} ({mal_data.get('type')}, {mal_data.get('episodes', '?')} eps)")

    anilist_data = fetch_anilist_anime(anime_name)
    if anilist_data:
        title = anilist_data.get('title', {}).get('english') or anilist_data.get('title', {}).get('romaji')
        log(f"  AniList: {title} ({anilist_data.get('format')}, {anilist_data.get('episodes', '?')} eps)")

    # Step 2: AI discovers all content
    log("\n[2/2] AI discovering all anime content...")
    content_data = discover_all_content(anime_name, mal_data, anilist_data)

    # Summary (to stderr only)
    episodes = [c for c in content_data.get('content', []) if c.get('type') == 'episode']
    movies = [c for c in content_data.get('content', []) if c.get('type') == 'movie']
    specials = [c for c in content_data.get('content', []) if c.get('type') == 'special']
    ovas = [c for c in content_data.get('content', []) if c.get('type') in ('ova', 'ona')]

    log(f"\n  Found: {len(episodes)} Episodes, {len(movies)} Movies, {len(specials)} Specials, {len(ovas)} OVAs/ONAs")
    log(f"  Status: {content_data.get('status', 'Unknown')}")

    # Apply content type filter if specified
    if anime_type and anime_type != 'all':
        type_map = {
            'episodes': 'episode', 'episode': 'episode',
            'movies': 'movie', 'movie': 'movie',
            'specials': 'special', 'special': 'special',
            'ova': 'ova', 'ona': 'ona',
        }
        target_type = type_map.get(anime_type.lower(), anime_type.lower())
        original_count = len(content_data.get('content', []))
        content_data['content'] = [c for c in content_data.get('content', []) if c.get('type') == target_type]
        log(f"  Filtered to type '{target_type}': {original_count} -> {len(content_data['content'])} items")

    # Output ONLY pure JSON to stdout (for pipeline capture)
    print(json.dumps(content_data, indent=2))

if __name__ == '__main__':
    main()
