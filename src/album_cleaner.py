from pathlib import Path
import mutagen
from collections import Counter

class AlbumCleaner:
    def get_consensus_album_title(self, album_path: Path) -> str | None:
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

    def clean_album_folder(self, album_path: Path):
        """
        Cleans the album folder name based on the consensus album title.
        """
        if not album_path.is_dir():
            print(f"Error: {album_path} is not a directory.")
            return

        new_title = self.get_consensus_album_title(album_path)

        if not new_title:
            print(f"Could not determine a consensus album title for {album_path.name}")
            return

        if album_path.name == new_title:
            print(f"'{album_path.name}' is already named correctly.")
            return

        new_path = album_path.parent / new_title
        if new_path.exists():
            print(f"Error: A directory named {new_title} already exists.")
            return

        album_path.rename(new_path)
        print(f"Renamed '{album_path.name}' to '{new_path.name}'")
