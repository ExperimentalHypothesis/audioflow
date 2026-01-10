from pathlib import Path
import mutagen
from collections import Counter
import os

from src.config import CLEANED_FLAC_PATH


class AlbumCleaner:
    def clean_album_folder(self, album_path: Path):
        """
        Cleans the album folder name based on the consensus album title and moves it.
        """
        if not album_path.is_dir():
            print(f"Error: {album_path} is not a directory.")
            return

        new_path = self._get_new_album_path(album_path)
        if not new_path:
            return

        self._move_album(album_path, new_path)

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

    def _get_new_album_path(self, album_path: Path) -> Path | None:
        """
        Determines the new path for the cleaned album.
        """
        new_title = self._get_consensus_album_title(album_path)
        if not new_title:
            print(f"Could not determine a consensus album title for {album_path.name}")
            return None

        artist_name = self._get_consensus_artist_name(album_path)
        if not artist_name:
            print(f"Could not determine a consensus artist name for {album_path.name}")
            return None

        artist_name = self._sanitize_filename(artist_name).title()
        new_title = self._sanitize_filename(new_title).title()

        new_artist_path = CLEANED_FLAC_PATH / artist_name
        return new_artist_path / new_title

    @staticmethod
    def _move_album(album_path: Path, new_path: Path):
        """
        Moves the album to the new path.
        """
        new_artist_path = new_path.parent

        if new_path.exists():
            print(f"Error: A directory named {new_path.name} already exists in {new_artist_path}.")
            return

        print(f"Creating directory: {new_artist_path}")
        os.makedirs(new_artist_path, exist_ok=True)

        if not album_path.exists():
            print(f"Error: Source album path '{album_path}' no longer exists. Skipping rename.")
            return

        album_path.rename(new_path)
        print(f"Moved and renamed '{album_path.name}' to '{new_path.name}' in '{new_artist_path}'")

    @staticmethod
    def _get_consensus_album_title(album_path: Path) -> str | None:
        """
        Gets the most common album title from the metadata of the audio files.
        """
        album_titles = []
        for audio_file in album_path.glob("**/*.flac"):
            try:
                audio = mutagen.File(audio_file)
                if audio and "album" in audio:
                    album_titles.append(audio["album"][0])
            except Exception as e:
                print(f"Error reading metadata from {audio_file}: {e}")

        if not album_titles:
            return None

        most_common_title = Counter(album_titles).most_common(1)[0][0]
        return most_common_title

    @staticmethod
    def _get_consensus_artist_name(album_path: Path) -> str | None:
        """
        Gets the most common artist name from the metadata of the audio files.
        """
        artist_names = []
        for audio_file in album_path.glob("**/*.flac"):
            try:
                audio = mutagen.File(audio_file)
                if audio and "artist" in audio:
                    artist_names.append(audio["artist"][0])
            except Exception as e:
                print(f"Error reading metadata from {audio_file}: {e}")

        if not artist_names:
            return None

        most_common_artist = Counter(artist_names).most_common(1)[0][0]
        return most_common_artist

