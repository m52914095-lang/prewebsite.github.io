#!/usr/bin/env python3
"""
Configuration file for the anime pipeline.
Update these values or set environment variables.
"""

import os

# ===== AI Configuration =====
# Groq is PRIMARY, Gemini is BACKUP
# Hardcoded fallback key as requested by user
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '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')
GROQ_MODEL = 'llama-3.1-8b-instant'  # Fast lightweight model

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')  # Set by workflow from secrets.ai
GEMINI_MODEL = 'gemini-2.0-flash'  # Lightweight Flash model (uses google-genai package)

# ===== StreamP2P Configuration =====
# Hardcoded fallback key as requested by user
STREAMP2P_API_KEY = os.environ.get('STREAMP2P_API_KEY', '46d3af3546d3931092a5b078')
STREAMP2P_API_BASE = 'https://streamp2p.com/api/v1'
STREAMP2P_UPLOAD_CHUNK_SIZE = 52_428_800  # 50MB - tus protocol implemented natively with requests

# ===== Folder Structure =====
# Parent folder -> Anime subfolders -> Sub-type subfolders
PARENT_FOLDER_NAME = 'Anime'  # Top-level folder on StreamP2P

# ===== Download Configuration =====
MAX_CONCURRENT_DOWNLOADS = 3
DOWNLOAD_TIMEOUT = 7200  # 2 hours
LARGE_FILE_THRESHOLD_GB = 30  # Split downloads >30GB
ARIA2C_MAX_CONNECTIONS = 4

# ===== Video Processing =====
HARD_SUB_CRF = 20  # Quality (lower = better, 18-28 range)
HARD_SUB_PRESET = 'medium'  # Encoding speed: ultrafast, fast, medium, slow
AUDIO_BITRATE = '192k'
VIDEO_CODEC = 'libx264'
AUDIO_CODEC = 'aac'

# ===== Nyaa Search =====
NYAA_BASE_URL = 'https://nyaa.si'
NYAA_CATEGORY = '1_2'  # English-translated Anime
NYAA_MIN_SEEDERS = 1
NYAA_PREFER_TRUSTED = True
NYAA_RATE_LIMIT_SECONDS = 1.5

# ===== MyAnimeList / AniList =====
JIKAN_BASE_URL = 'https://api.jikan.moe/v4'
ANILIST_BASE_URL = 'https://graphql.anilist.co'

# ===== Auto-Monitor =====
MONITOR_CHECK_INTERVAL_HOURS = 6
MONITOR_FILE = 'monitored_anime.json'
MONITOR_STATE_FILE = 'monitor_state.json'
