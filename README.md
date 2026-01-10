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

## Development

### Running Tests

To run the tests for the project:

```bash
uv run pytest tests/
```
