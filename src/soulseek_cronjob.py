from pathlib import Path
from .album_cleaner import AlbumCleaner

class SoulseekCronjob:
    def __init__(self, complete_folder: Path, downloading_folder: Path, cleaner: AlbumCleaner):
        self.complete_folder = complete_folder
        self.downloading_folder = downloading_folder
        self.cleaner = cleaner

    def is_album_complete(self, album_name: str) -> bool:
        """
        Checks if an album is complete by checking if a folder with the same name
        exists in the downloading folder.
        """
        return not (self.downloading_folder / album_name).exists()

    def process_completed_downloads(self):
        """
        Processes the completed downloads.
        """
        print(f"Processing completed downloads from {self.complete_folder}")
        for album_path in self.complete_folder.iterdir():
            if album_path.is_dir():
                if self.is_album_complete(album_path.name):
                    print(f"'{album_path.name}' is complete. Cleaning...")
                    self.cleaner.clean_album_folder(album_path)
                else:
                    print(f"'{album_path.name}' is still being downloaded.")