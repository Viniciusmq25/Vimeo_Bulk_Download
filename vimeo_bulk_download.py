#!/usr/bin/env python3
"""
Vimeo bulk downloader
---------------------
Downloads *all* videos from your Vimeo account, walking through every folder ("Projects")
plus anything not in a folder. Chooses the best direct MP4 file available and saves
metadata alongside each download.

Requirements:
  pip install requests tqdm tenacity

Auth:
  - Create a **Personal Access Token** at https://developer.vimeo.com/apps
  - Scopes needed: public, private, video_files
  - Export it before running:
        export VIMEO_TOKEN="your_actual_vimeo_token_here"
  - Or use .env file (recommended - copy .env.example to .env)

Usage:
  python vimeo_bulk_download.py --out "./vimeo_backup"

Notes:
  - Respects pagination; retries on transient network errors.
  - Skips files that already exist (by filename) unless --overwrite is passed.
  - Saves JSON metadata next to each video.
  - NEVER commit your token to version control!

Examples:
  # Using environment variable:
  export VIMEO_TOKEN="your_actual_token"
  python vimeo_bulk_download.py --out "./vimeo_backup"
  
  # Using --token parameter:
  python vimeo_bulk_download.py --token "your_actual_token" --out "./vimeo_backup" --overwrite
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
from urllib.parse import urlparse
import sys
import time
from typing import Dict, Iterable, List, Optional

import requests
from requests import exceptions as req_exc
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from tqdm import tqdm

API = "https://api.vimeo.com"
PAGE_SIZE = 50  # Vimeo API max is typically 100; 50 is a safe default
DEFAULT_OUTPUT_DIR = Path("./vimeo_backup")

class VimeoError(Exception):
    pass

def bearer_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.vimeo.*+json;version=3.4",
        "User-Agent": "vimeo-bulk-downloader/1.0"
    }

@retry(wait=wait_exponential(multiplier=1, min=1, max=20), stop=stop_after_attempt(5), reraise=True,
       retry=retry_if_exception_type((requests.RequestException, VimeoError)))
def api_get(url: str, headers: Dict[str, str], params: Dict[str, str] | None = None) -> Dict:
    r = requests.get(url, headers=headers, params=params, timeout=60)
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", "5"))
        time.sleep(retry_after)
        raise VimeoError("Rate limited; retrying")
    r.raise_for_status()
    return r.json()

def paginate(url: str, headers: Dict[str, str], query: Dict[str, str] | None = None) -> Iterable[Dict]:
    params = dict(per_page=PAGE_SIZE)
    if query:
        params.update(query)
    while True:
        data = api_get(url, headers, params)
        items = data.get('data', [])
        for it in items:
            yield it
        paging = data.get('paging', {})
        next_url = paging.get('next')
        if not next_url:
            break
        if next_url.startswith('http'):
            url = next_url
        else:
            url = f"{API}{next_url}"
        params = None

def extract_vimeo_id(uri: Optional[str]) -> str:
    if not uri:
        return "?"
    return uri.rstrip("/").split("/")[-1]

def build_folder_hierarchy(headers: Dict[str, str]) -> Dict[Optional[str], List[Dict]]:
    """Constrói hierarquia de pastas usando parent_folder da API."""
    todos = list(
        paginate(
            f"{API}/me/projects",
            headers,
            {"fields": "uri,name,metadata.connections.parent_folder.uri"}
        )
    )
    
    mapa: Dict[Optional[str], List[Dict]] = {}
    for folder in todos:
        folder_id = extract_vimeo_id(folder.get("uri"))
        folder["_id"] = folder_id
        
        connections = folder.get("metadata", {}).get("connections")
        if not connections:
            parent_info = {}
        elif isinstance(connections, list):
            parent_info = connections[0].get("parent_folder", {}) if connections else {}
        else:
            parent_info = connections.get("parent_folder", {})
        
        if isinstance(parent_info, list):
            parent_info = parent_info[0] if parent_info else {}
        
        parent_uri = parent_info.get("uri") if isinstance(parent_info, dict) else None
        parent_id = extract_vimeo_id(parent_uri) if parent_uri else None
        folder["_parent_id"] = parent_id
        
        mapa.setdefault(parent_id, []).append(folder)
    
    mapa.setdefault(None, [])
    return mapa

def list_project_videos(project_uri: str, headers: Dict[str, str]) -> Iterable[Dict]:
    url = f"{API}{project_uri}/videos"
    yield from paginate(url, headers, {"fields": "uri,name,files,download"})

def list_all_videos(headers: Dict[str, str]) -> Iterable[Dict]:
    url = f"{API}/me/videos"
    yield from paginate(url, headers, {"fields": "uri,name,files,download"})

def choose_best_file(video: Dict) -> Optional[Dict]:
    def infer_ext(link: str) -> str:
        try:
            path = urlparse(link).path or ''
        except Exception:
            path = ''
        ext = Path(path).suffix.lower()
        if ext not in {'.mp4', '.mov', '.m4v', '.mpg', '.mpeg', '.avi', '.wmv', '.mkv'}:
            ext = '.mp4'
        return ext

    files = video.get('files') or []
    progressive = [f for f in files if f.get('type') == 'video/mp4' and f.get('link')]
    if progressive:
        progressive.sort(key=lambda f: (f.get('height') or 0, f.get('bitrate') or 0), reverse=True)
        top = progressive[0]
        return {**top, 'ext': infer_ext(top.get('link', ''))}
    direct = [f for f in files if f.get('link')]
    if direct:
        direct.sort(key=lambda f: (f.get('height') or 0, f.get('bitrate') or 0), reverse=True)
        top = direct[0]
        return {**top, 'ext': infer_ext(top.get('link', ''))}
    dl = video.get('download') or []
    dl = [d for d in dl if d.get('link')]
    if dl:
        def score(d):
            return (d.get('height') or 0, 1 if (d.get('type') in ('source', 'original')) else 0)
        dl.sort(key=score, reverse=True)
        top = dl[0]
        link = top.get('link')
        return {'link': link, 'ext': infer_ext(link), 'quality': top.get('quality'), 'source': 'download'}
    return None

def safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in (" ", "-", "_", ".") else "_" for c in name).strip()

def download_file(url: str, dest: Path, headers: Dict[str, str], max_attempts: int = 5) -> None:
    attempt = 0
    backoff = 5
    while attempt < max_attempts:
        resume_pos = dest.stat().st_size if dest.exists() else 0
        mode = 'ab' if resume_pos else 'wb'
        dl_headers = dict(headers)
        if resume_pos:
            dl_headers['Range'] = f'bytes={resume_pos}-'

        try:
            with requests.get(
                url,
                headers=dl_headers,
                stream=True,
                timeout=(15, 300),
                allow_redirects=True
            ) as r:
                if r.status_code == 416 and resume_pos:
                    dest.unlink(missing_ok=True)
                    attempt += 1
                    time.sleep(backoff)
                    continue

                if r.status_code not in (200, 206):
                    r.raise_for_status()

                content_length = r.headers.get('Content-Length')
                total = resume_pos + int(content_length) if content_length and content_length.isdigit() else None

                with open(dest, mode) as f, tqdm(
                    total=total,
                    initial=resume_pos,
                    unit='B',
                    unit_scale=True,
                    desc=dest.name,
                    leave=False
                ) as pbar:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        pbar.update(len(chunk))

                if total is None:
                    tqdm.write(f"Completed download: {dest.name}")
                return

        except (req_exc.Timeout, req_exc.ConnectionError, req_exc.ChunkedEncodingError, req_exc.RequestException) as exc:
            attempt += 1
            if attempt >= max_attempts:
                raise
            wait_time = min(backoff * attempt, 60)
            print(f"[retry] {dest.name}: {exc.__class__.__name__} - retrying in {wait_time}s (attempt {attempt}/{max_attempts})")
            time.sleep(wait_time)

    raise RuntimeError(f"Failed to download {dest} after {max_attempts} attempts")

def get_video_details(uri: str, headers: Dict[str, str]) -> Dict:
    return api_get(f"{API}{uri}", headers, params={"fields": "uri,name,files,download"})

def main():
    parser = argparse.ArgumentParser(description="Download all videos from your Vimeo account")
    parser.add_argument('--out', type=Path, default=DEFAULT_OUTPUT_DIR, help='Output directory')
    parser.add_argument('--token', type=str, default=os.environ.get('VIMEO_TOKEN'), help='Vimeo personal access token (scopes: public, private, video_files)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files')
    args = parser.parse_args()

    if not args.token:
        print("Error: provide --token or set VIMEO_TOKEN", file=sys.stderr)
        sys.exit(2)

    headers = bearer_headers(args.token)
    outdir = args.out
    outdir.mkdir(parents=True, exist_ok=True)

    print("Fetching folder hierarchy ...")
    mapa = build_folder_hierarchy(headers)
    seen_video_uris = set()

    def process_video(video: Dict, subdir: Path):
        uri = video.get('uri')
        if not uri or uri in seen_video_uris:
            return
        seen_video_uris.add(uri)
        name = video.get('name') or f"video_{uri.split('/')[-1]}"
        base = safe_filename(name)
        subdir.mkdir(parents=True, exist_ok=True)

        f = choose_best_file(video)
        if not f:
            try:
                details = get_video_details(uri, headers)
                f = choose_best_file(details)
            except Exception:
                f = None
        if not f:
            print(f"[skip] No downloadable file link for: {name}")
            return

        dest = subdir / f"{base}{f.get('ext', '.mp4')}"

        if dest.exists() and not args.overwrite:
            print(f"[skip] Exists: {dest}")
        else:
            print(f"Downloading: {name} -> {dest}")
            download_file(f['link'], dest, headers)

        meta_path = dest.with_suffix(dest.suffix + '.json')
        with open(meta_path, 'w', encoding='utf-8') as m:
            json.dump(video, m, ensure_ascii=False, indent=2)

    def process_folder(folder: Dict, base_path: Path, visited: set):
        uri = folder.get("uri")
        if not uri or uri in visited:
            return
        visited.add(uri)

        name = safe_filename(folder.get("name") or f"folder_{extract_vimeo_id(uri)}")
        folder_path = base_path / name

        print(f"\n== Pasta: {folder_path.relative_to(outdir)} ==")

        # Baixa vídeos da pasta atual
        for vid in list_project_videos(uri, headers):
            process_video(vid, folder_path)

        # Processa subpastas recursivamente
        folder_id = folder.get("_id")
        subfolders = mapa.get(folder_id, [])
        for sub in sorted(subfolders, key=lambda x: x.get("name", "").lower()):
            process_folder(sub, folder_path, visited)

    visited_folders = set()
    root_folders = sorted(mapa.get(None, []), key=lambda x: x.get("name", "").lower())

    for folder in root_folders:
        process_folder(folder, outdir, visited_folders)

    print("\n== Videos not in any folder ==")
    for vid in list_all_videos(headers):
        if vid.get("uri") not in seen_video_uris:
            process_video(vid, outdir)

    print("\nDone.")

if __name__ == '__main__':
    main()