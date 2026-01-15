"""Prints the folder and video structure of a Vimeo account.

Requirements:
	pip install requests

Usage example:
	python vimeo_folder_structure.py --token "your_vimeo_token_here"

The token can be generated at https://developer.vimeo.com/apps with scopes
"public", "private", and "video_files". If the VIMEO_TOKEN environment
variable is defined, the --token argument is optional.

WARNING: NEVER share or commit your token to Git!
Use .env or environment variables to store it securely.

Examples:
	# Using environment variable:
	export VIMEO_TOKEN="your_vimeo_token_here"
	python vimeo_folder_structure.py
	
	# Using --token (for testing only, not recommended):
	python vimeo_folder_structure.py --token "your_vimeo_token_here" --folders-only
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from requests import exceptions as req_exc
from dotenv import load_dotenv

load_dotenv()

API = "https://api.vimeo.com"
PAGE_SIZE = 100


class VimeoError(Exception):
	"""High-level error when communicating with the Vimeo API."""


def bearer_headers(token: str) -> Dict[str, str]:
	return {
		"Authorization": f"bearer {token}",
		"Accept": "application/vnd.vimeo.*+json;version=3.4",
		"User-Agent": "vimeo-folder-structure/1.0",
	}


def api_get(
	url: str,
	headers: Dict[str, str],
	params: Optional[Dict[str, str]] = None,
	max_attempts: int = 5,
) -> Dict:
	for attempt in range(1, max_attempts + 1):
		try:
			response = requests.get(url, headers=headers, params=params, timeout=60)
		except req_exc.RequestException as exc:
			if attempt == max_attempts:
				raise VimeoError(f"Network error calling {url}: {exc}") from exc
			time.sleep(attempt * 2)
			continue

		if response.status_code == 429:
			wait_for = int(response.headers.get("Retry-After", "5"))
			time.sleep(max(wait_for, 1))
			continue

		if response.status_code == 401:
			raise VimeoError("Invalid token or insufficient permissions.")

		if response.status_code >= 400:
			raise VimeoError(
				f"Error {response.status_code} calling {url}: {response.text.strip()}"
			)

		try:
			return response.json()
		except ValueError as exc:
			raise VimeoError("Unexpected API response (invalid JSON).") from exc

	raise VimeoError("Failed to get valid response from Vimeo API.")


def paginate(
	url: str,
	headers: Dict[str, str],
	query: Optional[Dict[str, str]] = None,
) -> Iterable[Dict]:
	params = {"per_page": str(PAGE_SIZE)}
	if query:
		params.update(query)

	next_url: Optional[str] = url
	next_params: Optional[Dict[str, str]] = params

	while next_url:
		data = api_get(next_url, headers, params=next_params)
		for item in data.get("data", []):
			yield item

		paging = data.get("paging") or {}
		next_link = paging.get("next")
		if not next_link:
			break
		if next_link.startswith("http"):
			next_url = next_link
		else:
			next_url = f"{API}{next_link}"
		next_params = None


def build_folder_map(headers: Dict[str, str]) -> Dict[Optional[str], List[Dict]]:
	all_folders = list(
		paginate(
			f"{API}/me/projects",
			headers,
			query={
				"fields": (
					"uri,name,"
					"metadata.connections.parent_folder.uri,"
					"metadata.connections.parent_folder.name"
				)
			},
		)
	)

	folder_map: Dict[Optional[str], List[Dict]] = {}
	for folder in all_folders:
		folder_id = extract_id(folder.get("uri"))
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
		parent_id = extract_id(parent_uri) if parent_uri else None
		folder["_parent_id"] = parent_id

		folder_map.setdefault(parent_id, []).append(folder)

	folder_map.setdefault(None, [])
	return folder_map


def list_folder_videos(folder_uri: str, headers: Dict[str, str]) -> List[Dict]:
	return list(
		paginate(
			f"{API}{folder_uri}/videos",
			headers,
			query={"fields": "uri,name"},
		)
	)


def list_videos_without_folder(headers: Dict[str, str]) -> List[Dict]:
	videos: List[Dict] = []
	for video in paginate(
		f"{API}/me/videos",
		headers,
		query={"fields": "uri,name,metadata.connections.folders.total"},
	):
		folders_meta = (
			video.get("metadata", {})
			.get("connections", {})
			.get("folders", {})
		)
		total = folders_meta.get("total") or folders_meta.get("totalCount")
		if not total:
			videos.append(video)
	return videos


def get_account_name(headers: Dict[str, str]) -> str:
	try:
		profile = api_get(f"{API}/me", headers, params={"fields": "name"})
	except VimeoError:
		return "Vimeo Account"
	name = profile.get("name")
	if name:
		return f"Vimeo Account ({name})"
	return "Vimeo Account"


def clean_name(value: Optional[str], fallback: str) -> str:
	if not value:
		return fallback
	return " ".join(value.split())


def extract_id(uri: Optional[str]) -> str:
	if not uri:
		return "?"
	return uri.rstrip("/").split("/")[-1]


def sort_by_name(items: Sequence[Dict]) -> List[Dict]:
	return sorted(items, key=lambda item: clean_name(item.get("name"), "").lower())


def print_video_group(
	videos: List[Dict],
	prefix: str,
) -> None:
	for index, video in enumerate(videos):
		is_last = index == len(videos) - 1
		connector = "`-- " if is_last else "|-- "
		title = clean_name(video.get("name"), f"video {extract_id(video.get('uri'))}")
		vid = extract_id(video.get("uri"))
		print(f"{prefix}{connector}{title} [video {vid}]")


def print_folder(
	folder: Dict,
	prefix: str,
	folder_map: Dict[Optional[str], List[Dict]],
	headers: Dict[str, str],
	include_videos: bool,
	visited: set[str],
) -> None:
	uri = folder.get("uri")
	if not uri or uri in visited:
		return
	visited.add(uri)

	folder_id = folder.get("_id")
	subfolders = sort_by_name(folder_map.get(folder_id, []))
	items: List[Tuple[str, object]] = [("folder", item) for item in subfolders]

	videos: List[Dict] = []
	if include_videos:
		videos = list_folder_videos(uri, headers)
		for video in videos:
			items.append(("video", video))

	for index, (item_type, content) in enumerate(items):
		is_last = index == len(items) - 1
		connector = "`-- " if is_last else "|-- "
		next_prefix = prefix + ("    " if is_last else "|   ")

		if item_type == "folder":
			name = clean_name(
				content.get("name"),
				f"folder {extract_id(content.get('uri'))}",
			)
			pid = extract_id(content.get("uri"))
			print(f"{prefix}{connector}{name} [folder {pid}]")
			print_folder(
				content,
				next_prefix,
				folder_map,
				headers,
				include_videos,
				visited,
			)
		else:
			title = clean_name(
				content.get("name"),
				f"video {extract_id(content.get('uri'))}",
			)
			vid = extract_id(content.get("uri"))
			print(f"{prefix}{connector}{title} [video {vid}]")


def print_structure(
	headers: Dict[str, str],
	include_videos: bool,
) -> None:
	folder_map = build_folder_map(headers)
	top_level = sort_by_name(folder_map.get(None, []))
	root = get_account_name(headers)
	print(root)

	top_items: List[Tuple[str, object]] = [("folder", folder) for folder in top_level]

	videos_without_folder: List[Dict] = []
	if include_videos:
		videos_without_folder = list_videos_without_folder(headers)
		if videos_without_folder:
			top_items.append(("no_folder", videos_without_folder))

	visited: set[str] = set()

	for index, (item_type, content) in enumerate(top_items):
		is_last = index == len(top_items) - 1
		connector = "`-- " if is_last else "|-- "
		prefix = ""
		next_prefix = "    " if is_last else "|   "

		if item_type == "folder":
			name = clean_name(
				content.get("name"),
				f"folder {extract_id(content.get('uri'))}",
			)
			pid = extract_id(content.get("uri"))
			print(f"{connector}{name} [folder {pid}]")
			print_folder(
				content,
				next_prefix,
				folder_map,
				headers,
				include_videos,
				visited,
			)
		else:
			print(f"{connector}No folder")
			print_video_group(content, next_prefix)


def create_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description="Prints the folder and video tree of a Vimeo account.",
	)
	parser.add_argument(
		"--token",
		type=str,
		default=os.environ.get("VIMEO_TOKEN"),
		help="Vimeo personal access token (scopes: public, private, video_files).",
	)
	parser.add_argument(
		"--folders-only",
		action="store_true",
		help="Don't list videos, only the folder hierarchy.",
	)
	return parser


def main() -> None:
	parser = create_parser()
	args = parser.parse_args()
	if not args.token:
		parser.error("Provide --token or set the VIMEO_TOKEN environment variable.")

	headers = bearer_headers(args.token)
	try:
		print_structure(headers, include_videos=not args.folders_only)
	except VimeoError as exc:
		print(f"Error: {exc}", file=sys.stderr)
		sys.exit(1)


if __name__ == "__main__":
	main()
