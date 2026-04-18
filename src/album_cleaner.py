from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from collections import Counter
import os

from src.config import CLEANED_FLAC_PATH, CLEANED_MP3_PATH

AUDIO_EXTENSIONS = (".flac", ".mp3")


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


class CleanResult:
    SUCCESS = "success"
    SKIPPED = "skipped"
    ERROR = "error"


class AlbumCleaner:
    def clean_album_folder(self, album_path: Path) -> tuple[str, str]:
        """
        Cleans the album folder name based on the consensus album title and moves it.
        Returns (status, message) tuple.
        """
        if not album_path.is_dir():
            return CleanResult.ERROR, "Not a directory"

        result = self._get_new_album_path(album_path)

        # Check if result is an error (first element is a status string)
        if isinstance(result[0], str):
            return result  # type: ignore

        new_path, album_format = result
        return self._move_album(album_path, new_path, album_format)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """
        Removes characters that are invalid for file or directory names.
        """
        replacements = {
            "/": "&",
            "feat.": "&",
            "featuring": "&",
            ":": " -",
        }
        for old, new in replacements.items():
            name = name.replace(old, new)
        return name

    @staticmethod
    def _get_audio_files(album_path: Path) -> list[Path]:
        """
        Gets all audio files (FLAC and MP3) in the album directory.
        """
        audio_files = []
        for ext in AUDIO_EXTENSIONS:
            audio_files.extend(album_path.glob(f"**/*{ext}"))
        return audio_files

    @staticmethod
    def _get_album_format(album_path: Path) -> str | None:
        """
        Determines the primary format of the album (flac or mp3).
        Returns the format with the most files, or None if no audio files found.
        """
        flac_count = len(list(album_path.glob("**/*.flac")))
        mp3_count = len(list(album_path.glob("**/*.mp3")))

        if flac_count == 0 and mp3_count == 0:
            return None
        return "flac" if flac_count >= mp3_count else "mp3"

    @staticmethod
    def _get_audio_metadata(audio_file: Path) -> dict | None:
        """
        Gets metadata from an audio file, normalizing tag names across formats.
        Returns a dict with 'album', 'artist', 'albumartist' keys (if available).
        """
        try:
            suffix = audio_file.suffix.lower()
            if suffix == ".flac":
                audio = FLAC(audio_file)
                return {
                    "album": audio.get("album", [None])[0],
                    "artist": audio.get("artist", [None])[0],
                    "albumartist": audio.get("albumartist", [None])[0],
                }
            elif suffix == ".mp3":
                audio = EasyID3(audio_file)
                return {
                    "album": audio.get("album", [None])[0],
                    "artist": audio.get("artist", [None])[0],
                    "albumartist": audio.get("albumartist", [None])[0],
                }
        except Exception:
            pass
        return None

    def _get_new_album_path(self, album_path: Path) -> tuple[Path, str] | tuple[str, str]:
        """
        Determines the new path for the cleaned album.
        Returns (new_path, format) on success, or (status, message) on failure.
        """
        album_format = self._get_album_format(album_path)
        if not album_format:
            all_files = list(album_path.glob("**/*"))
            extensions = set(f.suffix.lower() for f in all_files if f.is_file())
            ext_list = ", ".join(extensions) if extensions else "none"
            return CleanResult.ERROR, f"No audio files (found: {ext_list})"

        new_title = self._get_consensus_album_title(album_path)
        if not new_title:
            return CleanResult.ERROR, "No album metadata found"

        artist_name = self._get_consensus_artist_name(album_path)
        if not artist_name:
            return CleanResult.ERROR, "No artist metadata found"

        artist_name = self._sanitize_filename(artist_name).title()
        new_title = self._sanitize_filename(new_title).title()

        if album_format == "mp3":
            base_path = CLEANED_MP3_PATH
        else:
            base_path = CLEANED_FLAC_PATH

        new_artist_path = base_path / artist_name
        return new_artist_path / new_title, album_format

    @staticmethod
    def _move_album(album_path: Path, new_path: Path, album_format: str) -> tuple[str, str]:
        """
        Moves the album to the new path.
        Returns (status, message) tuple.
        """
        new_artist_path = new_path.parent
        artist_name = new_artist_path.name
        album_name = new_path.name

        if new_path.exists():
            return CleanResult.SKIPPED, f"Already exists: {artist_name} / {album_name}"

        os.makedirs(new_artist_path, exist_ok=True)

        if not album_path.exists():
            return CleanResult.ERROR, "Source no longer exists"

        album_path.rename(new_path)
        format_label = album_format.upper()
        return CleanResult.SUCCESS, f"{artist_name} / {album_name} ({format_label})"

    def _get_consensus_album_title(self, album_path: Path) -> str | None:
        """
        Gets the most common album title from the metadata of the audio files.
        """
        audio_files = self._get_audio_files(album_path)
        if not audio_files:
            return None

        album_titles = []
        for audio_file in audio_files:
            metadata = self._get_audio_metadata(audio_file)
            if metadata and metadata.get("album"):
                album_titles.append(metadata["album"])

        if not album_titles:
            return None

        most_common_title = Counter(album_titles).most_common(1)[0][0]
        return most_common_title

    def _get_consensus_artist_name(self, album_path: Path) -> str | None:
        """
        Gets the artist name from album metadata.
        First checks for 'albumartist' tag (used for compilations/Various Artists),
        then falls back to most common 'artist' tag.
        """
        album_artists = []
        artist_names = []

        for audio_file in self._get_audio_files(album_path):
            metadata = self._get_audio_metadata(audio_file)
            if metadata:
                if metadata.get("albumartist"):
                    album_artists.append(metadata["albumartist"])
                if metadata.get("artist"):
                    artist_names.append(metadata["artist"])

        # Prefer albumartist if available (handles Various Artists compilations)
        if album_artists:
            most_common_album_artist = Counter(album_artists).most_common(1)[0][0]
            return most_common_album_artist

        # Fall back to most common track artist
        if not artist_names:
            return None

        most_common_artist = Counter(artist_names).most_common(1)[0][0]
        return most_common_artist