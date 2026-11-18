from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.asf import ASF
from collections import Counter
import os
import re

from src.config import CLEANED_FLAC_PATH, CLEANED_MP3_PATH

AUDIO_EXTENSIONS = (".flac", ".mp3", ".wma")

# Roman numerals pattern (I through XXXIX should cover most albums)
ROMAN_NUMERAL_PATTERN = re.compile(r"\b(X{0,3})(IX|IV|V?I{0,3})\b", re.IGNORECASE)

# Patterns to remove from album titles (order matters - more specific first)
TITLE_CLEANUP_PATTERNS = [
    # Year ranges and years in brackets/parens
    r"[\(\[]\d{4}\s*[-–]\s*\d{4}[\)\]]",  # (1999-2020), [1999-2020]
    r"[\(\[]\d{4}[\)\]]",  # (2020), [2020]
    # Quality/bitrate markers
    r"[\(\[](?:320|256|192|128|V0|V2|FLAC|MP3|AAC|OGG|WEB|CD|VINYL)[\)\]]",
    r"[\(\[](?:16|24)[\-/](?:44|48|96|192)[\)\]]",  # (24/96), [16-44]
    r"[\(\[](?:16|24)\s*bit[\)\]]",  # (24 bit), [16bit]
    # Edition markers
    r"[\(\[](?:Deluxe|Special|Limited|Anniversary|Expanded|Remastered|Bonus|Japanese|Japan|EU|US|UK)\s*(?:Edition|Version|Remaster)?[\)\]]",
    r"[\(\[]Remastered(?:\s+\d{4})?[\)\]]",  # (Remastered), (Remastered 2020)
    r"[\(\[]Remaster[\)\]]",
    # Disc markers
    r"[\(\[](?:Disc|CD|Disk)\s*\d+[\)\]]",  # (Disc 1), [CD2]
    r"[\(\[]Bonus\s*(?:Disc|CD|Disk)?[\)\]]",
    # Source/release markers
    r"[\(\[][A-Z]{2,4}[\)\]]",  # [WEB], [NK], (CDR)
    # Trailing standalone year
    r"\s+\d{4}\s*$",
    # Trailing copy numbers
    r"\s+\d+\s*$",  # "album 1" at the end
]


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
    def __init__(self):
        # Destination paths of albums moved successfully by this instance.
        self.moved_albums: list[Path] = []

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
        status, message = self._move_album(album_path, new_path, album_format)
        if status == CleanResult.SUCCESS:
            self.moved_albums.append(new_path)
        return status, message

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
    def _clean_title(title: str) -> str:
        """
        Cleans album/artist title by removing common metadata cruft
        and applying proper capitalization.
        """
        cleaned = title

        # Apply all cleanup patterns
        for pattern in TITLE_CLEANUP_PATTERNS:
            cleaned = re.sub(str(pattern), "", cleaned, flags=re.IGNORECASE)

        # Clean up whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Remove trailing/leading dashes and dots
        cleaned = cleaned.strip("-–—.").strip()

        # Apply title case
        cleaned = cleaned.title()

        # Fix Roman numerals (restore uppercase)
        def fix_roman(match: re.Match) -> str:
            numeral = match.group(0)
            # Only uppercase if it's a valid Roman numeral (not empty)
            if numeral and re.match(r"^[IVXivx]+$", numeral):
                return numeral.upper()
            return numeral

        cleaned = ROMAN_NUMERAL_PATTERN.sub(fix_roman, cleaned)

        # Fix common small words that should stay lowercase (except at start)
        small_words = [
            "A",
            "An",
            "The",
            "And",
            "Or",
            "Of",
            "In",
            "On",
            "At",
            "To",
            "For",
            "With",
            "By",
        ]
        words = cleaned.split()
        for i, word in enumerate(words):
            if i > 0 and word in small_words:
                words[i] = word.lower()
        cleaned = " ".join(words)

        return cleaned

    @staticmethod
    def _get_audio_files(album_path: Path) -> list[Path]:
        """
        Gets all audio files (FLAC, MP3 and WMA) in the album directory.
        """
        audio_files = []
        for ext in AUDIO_EXTENSIONS:
            audio_files.extend(album_path.glob(f"**/*{ext}"))
        return audio_files

    @staticmethod
    def _get_album_format(album_path: Path) -> str | None:
        """
        Determines the primary format of the album (flac, mp3 or wma).
        WMA is treated as a lossy format alongside MP3 when picking the
        destination library, since both are stored under CLEANED_MP3_PATH.
        Returns the format with the most files, or None if no audio files found.
        """
        flac_count = len(list(album_path.glob("**/*.flac")))
        mp3_count = len(list(album_path.glob("**/*.mp3")))
        wma_count = len(list(album_path.glob("**/*.wma")))

        if flac_count == 0 and mp3_count == 0 and wma_count == 0:
            return None

        if flac_count >= mp3_count + wma_count:
            return "flac"
        return "wma" if wma_count > mp3_count else "mp3"

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
            elif suffix == ".wma":
                audio = ASF(audio_file)

                def _asf_tag(key: str) -> str | None:
                    value = audio.get(key)
                    return str(value[0]) if value else None

                return {
                    "album": _asf_tag("WM/AlbumTitle"),
                    "artist": _asf_tag("Author"),
                    "albumartist": _asf_tag("WM/AlbumArtist"),
                }
        except Exception:
            pass
        return None

    def _get_new_album_path(
        self, album_path: Path
    ) -> tuple[Path, str] | tuple[str, str]:
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

        artist_name = self._clean_title(self._sanitize_filename(artist_name))
        new_title = self._clean_title(self._sanitize_filename(new_title))

        if album_format in ("mp3", "wma"):
            base_path = CLEANED_MP3_PATH
        else:
            base_path = CLEANED_FLAC_PATH

        new_artist_path = base_path / artist_name
        return new_artist_path / new_title, album_format

    @staticmethod
    def _move_album(
        album_path: Path, new_path: Path, album_format: str
    ) -> tuple[str, str]:
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
