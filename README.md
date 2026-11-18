# AudioFlow

AudioFlow is a Python-based command-line tool designed to automate the organization and conversion of music files, particularly those downloaded via Soulseek. It streamlines the process of managing your music library by cleaning up album metadata, renaming folders, and converting FLAC files to MP3.

## Features

-   **Soulseek Download Processing**: Monitors Soulseek's completed download directory and processes albums only after they are fully downloaded.
-   **Album Cleaning**: Reads metadata from FLAC files to determine consensus artist and album titles, then renames and moves album folders into a structured FLAC library.
-   **FLAC to MP3 Conversion**: Converts cleaned FLAC albums to MP3 format, preserving the directory structure and allowing for customizable bitrate selection (including V0).

## Requirements

-   Python 3.13 or higher
-   `ffmpeg` installed and available in your system's PATH for FLAC to MP3 conversion.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/audioflow.git
    cd audioflow
    ```

2.  **Install `uv` (if you don't have it):**
    `uv` is a fast Python package installer and resolver.
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
    Make sure `uv` is in your system's PATH.

3.  **Install dependencies:**
    ```bash
    uv sync
    ```

4.  **Configure the application:**
    You will need to set up the configuration variables in `src/config.py`. This includes paths for Soulseek download folders, cleaned FLAC library, and MP3 output.

    ```python
    # src/config.py (Example)
    from pathlib import Path

    # Soulseek Paths
    SOULSEEK_COMPLETE_PATH = Path("/path/to/your/Soulseek/Complete")
    SOULSEEK_DOWNLOADING_PATH = Path("/path/to/your/Soulseek/Downloading")

    # Cleaned Music Library Paths
    CLEANED_FLAC_PATH = Path("/path/to/your/Cleaned/FLAC/Library")
    CLEANED_MP3_PATH = Path("/path/to/your/Cleaned/MP3/Library")

    # Default MP3 Bitrate
    MP3_BITRATE = "320k" # or "V0" for variable bitrate
    ```
    **Note**: Make sure these directories exist and are accessible by the script.

## Usage

The `audioflow` tool provides two main commands:

### 1. Process Soulseek Downloads

This command checks your Soulseek completed downloads, ensures they are fully downloaded, cleans their metadata, and organizes them into your FLAC library.

```bash
uv run python src/main.py process-downloads
# Or, if you have the project installed in your PATH:
# audioflow process-downloads
```

It is recommended to run this command periodically, for example, as a cron job.

### 2. Convert FLAC Album to MP3

This command converts a specified FLAC album (or a directory containing FLAC files) to MP3 format. The output will be placed in your configured MP3 library, mirroring the FLAC library structure.

```bash
uv run python src/main.py convert-to-mp3 --album-path "/path/to/your/Cleaned/FLAC/Library/Artist Name/Album Title" --bitrate "V0"
# Or, if you have the project installed in your PATH:
# audioflow convert-to-mp3 --album-path "/path/to/your/Cleaned/FLAC/Library/Artist Name/Album Title" --bitrate "320k"
```

-   `--album-path`: The path to the FLAC album (or directory) you want to convert. This path should ideally be within your `CLEANED_FLAC_PATH`.
-   `--bitrate`: (Optional) Specify the MP3 bitrate. Defaults to `320k`. You can also use `"V0"` for variable bitrate.

### 5. Copy Albums to the NAS

Copies albums from any folder (a whole library, an artist folder or a single album) to the NAS, sorted the same way as the music already there: `Music/<Letter>/<Artist>/<Album>`, compilations in `Music/VA/<Album>`. The artist comes from the tags (album artist first), or from the parent folder name when there are no tags. Existing NAS folders that differ only in case are reused.

An album is the same as one on the NAS when the folder names match after dropping a leading year and bracketed format/bitrate/disc tags (`2007 - Forgotten Rituals [Flac]` = `Forgotten Rituals`). FLAC always wins, an album never ends up on the NAS twice, and an album already on the NAS is never merged into (track names differ between sources, so merging duplicates tracks):

| Source | On the NAS | Result |
|---|---|---|
| any | not there | Copied. |
| FLAC | MP3 (or another lossy format) | FLAC is copied, then the lossy files (or the whole lossy folder, if it's named differently) are deleted. Nothing is deleted if the copy fails. Asks first, unless `--yes`. |
| any | same or better format | Skipped, the NAS stays as it is. |

The share (`NAS_SMB_URL`) is mounted automatically at `NAS_MOUNT_PATH` if it isn't mounted yet (or mount it in Finder with ⌘K). Configure it in `src/config.py`.

```bash
uv run python main.py sync-to-nas "~/Music/Cleaned FLAC" --dry-run  # show what would be copied/deleted
uv run python main.py sync-to-nas "~/Music/Cleaned FLAC" "~/Music/Cleaned MP3"
uv run python main.py sync-to-nas "~/Music/Cleaned FLAC" --move  # then move them on the Mac to the Trash
```

With `--move`, an album on the Mac goes to the Trash once it's safely on the NAS: after a copy only if every file is on the NAS with the same size, and right away if it was skipped as already on the NAS. Albums that failed or whose artist is unknown stay. Artist folders left empty are removed. Needs macOS 15+ (`/usr/bin/trash`).

After the copy, Plex (running on the NAS) rescans the artist folders that changed, so new albums show up right away. It needs the Plex token in a git-ignored `.env` file in the project root:

```bash
PLEX_TOKEN=...   # Plex Web: any track → ⋯ → Get Info → View XML, the X-Plex-Token in the URL
```

The library section and paths are in `src/config.py` (`PLEX_*`). To rescan by hand: `audioflow plex-scan` (whole library) or `audioflow plex-scan "/Volumes/Public/Music/O/Oophoi"`.

An interrupted copy resumes on the next run: albums are copied into a hidden `.<Album>.partial` folder and renamed when complete. Audio files lying next to album folders (e.g. in the root of a downloads folder) are reported and left alone.

## Development

### Running Tests

To run the tests for the project:

```bash
uv run pytest tests/
```
