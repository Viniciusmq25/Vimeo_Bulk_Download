# Vimeo Bulk Downloader

This repository ships two Python utilities that interact with the Vimeo API:

- `vimeo_bulk_download.py`: downloads every video in your account, mirrors the folder hierarchy, picks the best available media file, and stores JSON sidecar metadata.
- `vimeo_folder_structure.py`: prints the full folder/video tree in the terminal so you can inspect the account layout before starting a backup.

Both scripts authenticate with Vimeo personal access tokens and share pagination/auth helpers.

## ✨ Key Features

- Personal access token authentication against Vimeo.
- Automatic API pagination to iterate through the entire library.
- Smart selection of the best available file (progressive MP4 or direct download).
- Folder structure mirrored locally to match Vimeo Projects.
- Automatic resume for interrupted downloads (HTTP range requests).
- Per-video JSON metadata written next to each media file.
- `--overwrite` flag to rebuild existing files when required.
- Companion script for folder exploration (`vimeo_folder_structure.py`).

## 📋 Prerequisites

- Python 3.8 or newer.
- Vimeo Personal Access Token with scopes `public`, `private`, and `video_files`.
- Python dependencies:
  - `requests`
  - `tqdm`
  - `tenacity`

Install them with:

```powershell
python -m pip install --upgrade pip
python -m pip install requests tqdm tenacity
```

> **Tip:** consider creating a virtual environment first (`python -m venv .venv`).

## 🔐 Setting the Vimeo Token

1. Go to [https://developer.vimeo.com/apps](https://developer.vimeo.com/apps) and create a Personal Access Token with scopes `public`, `private`, and `video_files`.
2. Store the token securely; you will need it for API calls.
3. Expose it via the `VIMEO_TOKEN` environment variable so the scripts can read it automatically. In PowerShell:

```powershell
# Session-only
$env:VIMEO_TOKEN = "your_token_here"

# Optional: persist for future sessions
setx VIMEO_TOKEN "your_token_here"
```

## 🚀 Running the Bulk Downloader

Use the built-in help to explore all options:

```powershell
python vimeo_bulk_download.py --help
```

### Basic example

With `VIMEO_TOKEN` already set:

```powershell
python vimeo_bulk_download.py --out "D:\Backup\Vimeo"
```

### Provide the token on the command line

```powershell
python vimeo_bulk_download.py --token "your_token_here" --out "D:\Backup\Vimeo"
```

### Force overwriting existing files

```powershell
python vimeo_bulk_download.py --out "D:\Backup\Vimeo" --overwrite
```

#### Available parameters

- `--out PATH` (optional): output directory. Defaults to the script's configured path.
- `--token TOKEN` (optional): Vimeo token. Falls back to `VIMEO_TOKEN` if omitted.
- `--overwrite`: replace files that already exist.

### Listing the folder tree without downloading

Use the helper script to inspect your projects:

```powershell
python vimeo_folder_structure.py --token "your_token_here"
```

Useful parameters:

- `--token TOKEN`: same behavior as the main script; uses `VIMEO_TOKEN` when missing.
- `--folders-only`: hide videos and print folder names only.

## 🗂️ Output layout

- Each Vimeo Project becomes a subdirectory inside the target folder.
- Videos without a folder land in the root of the output directory.
- Every video produces `video_name.ext` plus `video_name.ext.json` containing the metadata.

## 🧠 Behavior and best practices

- **API pagination:** fetches 50 items per request (safe Vimeo limit) until the end.
- **Automatic retries:** HTTP calls and downloads rely on `tenacity` to recover from transient issues or rate limiting (`HTTP 429`).
- **Download resume:** partially downloaded files continue from where they stopped.
- **Best file selection:** prioritizes progressive MP4 streams with the highest resolution/bitrate; falls back to the best alternative link.

## 🛠️ Troubleshooting

| Symptom | Likely cause | Suggested action |
| --- | --- | --- |
| `Error: provide --token or set VIMEO_TOKEN` | Token missing | Pass `--token` or set `VIMEO_TOKEN`. |
| `401 Unauthorized` | Invalid token or wrong scopes | Generate a fresh token with the correct scopes. |
| `Rate limited; retrying` | Too many requests in a short window | Wait; the script honors `Retry-After` automatically. |
| Downloads stop halfway | Connection drops | Run the script again; it resumes from the last byte. |
| Duplicate files remain | `--overwrite` not provided | Add `--overwrite` to replace existing files. |

## ✅ Quick checklist before running

- [ ] Python 3.8+ installed
- [ ] Dependencies installed (`pip install requests tqdm tenacity`)
- [ ] Vimeo token with `public`, `private`, `video_files`
- [ ] `VIMEO_TOKEN` exported or `--token` ready
- [ ] Destination folder with enough free space

## 📦 Project layout

```text
Vimeo_API/
├── vimeo_bulk_download.py      # Main download script
├── vimeo_folder_structure.py   # Utility that prints the project tree
├── videos/                     # Optional directory for downloads
└── README.md                   # This file
```

## 🧭 Suggested next steps

- Create a `requirements.txt` to simplify dependency installation.
- Add automated tests (e.g., mocked API responses) for better stability.
- Package the script as a CLI (`pipx`/`setuptools`) for easier distribution.
