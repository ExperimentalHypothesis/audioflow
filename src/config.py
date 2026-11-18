from pathlib import Path
import os


def _load_env(path: Path) -> None:
    """
    Loads KEY=value lines from the git-ignored .env; real environment variables win.
    """
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env(Path(__file__).resolve().parent.parent / ".env")


MUSIC_ROOT_PATH = Path("/Users/lukas.kotatko/Music/")
SOULSEEK_ROOT_PATH = Path("/Users/lukas.kotatko/Music/Soulseek")
SOULSEEK_COMPLETE_PATH = SOULSEEK_ROOT_PATH / "complete"
SOULSEEK_DOWNLOADING_PATH = SOULSEEK_ROOT_PATH / "downloading"
CLEANED_FLAC_PATH = MUSIC_ROOT_PATH / "Cleaned FLAC"
CLEANED_MP3_PATH = MUSIC_ROOT_PATH / "Cleaned MP3"

LOCAL_MUSIC_PATH = Path("/Users/lukas.kotatko/Music/Music/Media.localized/Music")
# NAS (WD My Cloud, SMB share). The share is mounted at NAS_MOUNT_PATH (Finder ⌘K or automatically).
# Music on the NAS is sorted as "<Letter>/<Artist>/<Album>", compilations as "VA/<Album>".
NAS_SMB_URL = "smb://MyCloudEX2Ultra.local/Public"
NAS_MOUNT_PATH = Path("/Volumes/Public")
NAS_MUSIC_PATH = NAS_MOUNT_PATH / "Music"
NAS_VARIOUS_ARTISTS_FOLDER = "VA"
# Artists that don't start with a letter (e.g. "65daysofstatic").
NAS_NON_LETTER_FOLDER = "0-9"

# Plex runs on the NAS. After `sync-to-nas` it rescans the folders that changed.
# The token lives in .env (PLEX_TOKEN=...), scanning is skipped without it.
PLEX_URL = os.environ.get("PLEX_URL", "http://MyCloudEX2Ultra.local:32400")
PLEX_TOKEN = os.environ.get("PLEX_TOKEN")
PLEX_MUSIC_SECTION = "15"  # library "Music", see /library/sections
PLEX_MUSIC_PATH = "/shares/Public/Music"  # NAS_MUSIC_PATH as Plex sees it on the NAS


MP3_BITRATE = "V0"
