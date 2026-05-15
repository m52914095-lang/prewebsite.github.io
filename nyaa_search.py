#!/usr/bin/env python3
"""
Nyaa.si Search - Searches for each content item and extracts magnet links.
Supports batch downloads, segmented downloads for large files.

IMPORTANT: Only the final JSON is printed to stdout (for pipeline capture).
All progress/info is printed to stderr.
"""

import sys
import os
import json
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin

NYAA_BASE = 'https://nyaa.si'
NYAA_SEARCH = f'{NYAA_BASE}/'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

session = requests.Session()
session.headers.update({'User-Agent': USER_AGENT})

def log(msg):
    """Print to stderr so it doesn't corrupt stdout JSON output"""
    print(msg, file=sys.stderr)

def search_nyaa(query, category='1_2', sort='seeders', order='desc', max_pages=3):
    """
    Search Nyaa.si for torrents.
    category: 1_2 = English-translated Anime
    sort: seeders, size, date
    """
    results = []
    for page in range(1, max_pages + 1):
        try:
            params = {
                'f': 0,  # filter: 0=no filter, 2=trusted, 3=remakes
                'c': category,
                'q': query,
                's': sort,
                'o': order,
                'p': page,
            }
            res = session.get(NYAA_SEARCH, params=params, timeout=20)
            res.raise_for_status()

            soup = BeautifulSoup(res.text, 'lxml')
            rows = soup.select('table.torrent-list tbody tr')

            if not rows:
                break

            for row in rows:
                try:
                    # Check if it's a trusted torrent
                    is_trusted = 'success' in row.get('class', [])
                    is_remake = 'danger' in row.get('class', [])

                    # Get links
                    links = row.select('td:nth-child(3) a')
                    if not links:
                        continue

                    # Title link is the last <a> in the comments/links cell
                    title_cell = row.select('td:nth-child(2) a')[-1] if row.select('td:nth-child(2) a') else None
                    title = title_cell.get_text(strip=True) if title_cell else ''

                    # Magnet link
                    magnet_link = None
                    torrent_link = None
                    for link in links:
                        href = link.get('href', '')
                        if href.startswith('magnet:'):
                            magnet_link = href
                        elif href.endswith('.torrent'):
                            torrent_link = urljoin(NYAA_BASE, href)

                    if not magnet_link:
                        continue

                    # Size
                    size_cell = row.select('td:nth-child(4)')
                    size = size_cell[0].get_text(strip=True) if size_cell else '0'

                    # Seeders
                    seeders_cell = row.select('td:nth-child(6)')
                    seeders = int(seeders_cell[0].get_text(strip=True)) if seeders_cell else 0

                    # Date
                    date_cell = row.select('td:nth-child(5)')
                    date = date_cell[0].get('title', '') if date_cell else ''

                    results.append({
                        'title': title,
                        'magnet': magnet_link,
                        'torrent_url': torrent_link,
                        'size': size,
                        'seeders': seeders,
                        'date': date,
                        'trusted': is_trusted,
                        'remake': is_remake,
                    })
                except Exception as e:
                    continue

            # Be nice to Nyaa
            time.sleep(1.5)

        except Exception as e:
            log(f"  Nyaa search page {page} error: {e}")
            break

    return results

def find_best_torrent(results, min_seeders=1, prefer_trusted=True, max_size_gb=30):
    """Find the best torrent from search results"""
    if not results:
        return None

    # Filter by minimum seeders
    filtered = [r for r in results if r['seeders'] >= min_seeders]

    # Filter out remakes if we have non-remake options
    if prefer_trusted and any(not r['remake'] for r in filtered):
        filtered = [r for r in filtered if not r['remake']]

    # Filter by max size
    if max_size_gb and max_size_gb > 0:
        filtered = [r for r in filtered if size_to_gb(r['size']) <= max_size_gb]

    # Prefer 1080p
    preferred = [r for r in filtered if '1080' in r['title']]
    if preferred:
        filtered = preferred

    # Sort by seeders (most popular first)
    filtered.sort(key=lambda x: x['seeders'], reverse=True)

    return filtered[0] if filtered else None

def find_batch_torrent(anime_title):
    """Find a batch torrent for all episodes"""
    queries = [
        f"{anime_title} batch 1080p",
        f"{anime_title} complete 1080p",
        f"{anime_title} season 1080p",
        f"{anime_title} batch",
        f"{anime_title} complete",
    ]

    for query in queries:
        log(f"  Searching batch: {query}")
        results = search_nyaa(query)
        best = find_best_torrent(results)
        if best:
            log(f"  Found batch: {best['title']} ({best['size']}, {best['seeders']} seeders)")
            return best
        time.sleep(1)

    return None

def size_to_gb(size_str):
    """Convert size string like '4.2 GiB' to GB float"""
    try:
        parts = size_str.strip().split()
        value = float(parts[0])
        unit = parts[1].lower()
        if 'gib' in unit or 'gb' in unit:
            return value
        elif 'mib' in unit or 'mb' in unit:
            return value / 1024
        elif 'tib' in unit or 'tb' in unit:
            return value * 1024
        elif 'kib' in unit or 'kb' in unit:
            return value / (1024 * 1024)
    except Exception:
        pass
    return 0

def search_content_item(item, anime_title):
    """Search for a specific content item (episode, movie, special, etc.)"""
    queries = [item.get('search_query', ''), item.get('search_query_alt', '')]

    for query in queries:
        if not query:
            continue
        log(f"  Searching: {query}")
        results = search_nyaa(query)
        best = find_best_torrent(results)
        if best:
            return best
        time.sleep(1)

    # Try broader search
    content_type = item.get('type', 'episode')
    fallback_queries = []

    if content_type == 'episode':
        ep_num = item.get('number', 0)
        try:
            ep_int = int(ep_num)
        except (ValueError, TypeError):
            ep_int = 0
        fallback_queries = [
            f"{anime_title} {ep_int:02d} 1080p",
            f"{anime_title} episode {ep_int} 1080p",
            f"{anime_title} {ep_int:02d}",
        ]
    elif content_type == 'movie':
        fallback_queries = [
            f"{anime_title} movie 1080p",
            f"{anime_title} film 1080p",
            f"{anime_title} movie",
        ]
    else:
        fallback_queries = [
            f"{anime_title} {content_type} 1080p",
            f"{anime_title} {content_type}",
        ]

    for query in fallback_queries:
        log(f"  Fallback search: {query}")
        results = search_nyaa(query)
        best = find_best_torrent(results)
        if best:
            return best
        time.sleep(1)

    return None

def main():
    if len(sys.argv) < 2:
        log("Usage: python nyaa_search.py <anime_content.json>")
        sys.exit(1)

    input_file = sys.argv[1]
    with open(input_file, 'r') as f:
        content_data = json.load(f)

    anime_title = content_data.get('anime_title', '')
    content_items = content_data.get('content', [])
    search_queries = content_data.get('search_queries', {})

    log(f"\n{'='*60}")
    log(f"  Nyaa Search: {anime_title}")
    log(f"{'='*60}\n")

    magnet_results = {
        'anime_title': anime_title,
        'anime_title_japanese': content_data.get('anime_title_japanese', ''),
        'anime_title_romaji': content_data.get('anime_title_romaji', ''),
        'mal_id': content_data.get('mal_id'),
        'status': content_data.get('status', ''),
        'total_episodes': content_data.get('total_episodes'),
        'magnets': [],
        'batch_magnets': [],
    }

    # Step 1: Try batch downloads first
    log("[1/2] Searching for batch torrents...")
    batch_queries = [
        search_queries.get('batch_query', ''),
        search_queries.get('batch_query_alt', ''),
    ]

    for bq in batch_queries:
        if not bq:
            continue
        log(f"  Searching batch: {bq}")
        results = search_nyaa(bq)
        best = find_best_torrent(results)
        if best:
            magnet_results['batch_magnets'].append({
                'type': 'batch',
                'query': bq,
                'magnet': best['magnet'],
                'title': best['title'],
                'size': best['size'],
                'seeders': best['seeders'],
            })
            break
        time.sleep(1)

    # Fallback: try generic batch search if AI queries didn't find anything
    if not magnet_results['batch_magnets']:
        log("  AI batch queries found nothing, trying generic batch search...")
        batch = find_batch_torrent(anime_title)
        if batch:
            magnet_results['batch_magnets'].append({
                'type': 'batch',
                'query': 'generic',
                'magnet': batch['magnet'],
                'title': batch['title'],
                'size': batch['size'],
                'seeders': batch['seeders'],
            })

    # Step 2: Search for individual items not covered by batch
    log("\n[2/2] Searching for individual content items...")

    # If we found a batch, only search for non-episode items
    if magnet_results['batch_magnets']:
        non_episodes = [item for item in content_items if item.get('type') != 'episode']
        search_items = non_episodes
        log(f"  Batch found! Only searching for {len(search_items)} non-episode items")
    else:
        search_items = content_items
        log(f"  No batch found. Searching for all {len(search_items)} items individually")

    for idx, item in enumerate(search_items):
        log(f"\n  [{idx+1}/{len(search_items)}] {item.get('type', '?').upper()}: {item.get('title', '?')}")

        result = search_content_item(item, anime_title)

        if result:
            item_size_gb = size_to_gb(result['size'])
            magnet_results['magnets'].append({
                'type': item.get('type', 'episode'),
                'number': item.get('number'),
                'title': item.get('title', ''),
                'search_query': item.get('search_query', ''),
                'magnet': result['magnet'],
                'torrent_title': result['title'],
                'size': result['size'],
                'size_gb': item_size_gb,
                'seeders': result['seeders'],
                'trusted': result['trusted'],
                'segmented': item_size_gb > 30,
            })
            log(f"    Found: {result['title']} ({result['size']}, {result['seeders']} seeders)")
        else:
            log(f"    No torrent found for: {item.get('title', '?')}")
            magnet_results['magnets'].append({
                'type': item.get('type', 'episode'),
                'number': item.get('number'),
                'title': item.get('title', ''),
                'search_query': item.get('search_query', ''),
                'magnet': None,
                'status': 'not_found',
            })

        time.sleep(1.5)  # Rate limit

    # Summary (to stderr only)
    found = sum(1 for m in magnet_results['magnets'] if m.get('magnet'))
    not_found = sum(1 for m in magnet_results['magnets'] if not m.get('magnet'))
    batches = len(magnet_results['batch_magnets'])

    log(f"\n{'='*60}")
    log(f"  Search Summary")
    log(f"  Batch torrents: {batches}")
    log(f"  Individual items found: {found}")
    log(f"  Items not found: {not_found}")
    log(f"{'='*60}\n")

    # Output ONLY pure JSON to stdout (for pipeline capture)
    print(json.dumps(magnet_results, indent=2))

if __name__ == '__main__':
    main()
