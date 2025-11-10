# import pytest
# from pathlib import Path
# from src.album_cleaner import AlbumCleaner
#
# class MockAudio:
#     def __init__(self, album_title):
#         self.tags = {"album": [album_title]}
#
#     def __getitem__(self, key):
#         return self.tags[key]
#
#     def __contains__(self, key):
#         return key in self.tags
#
# @pytest.fixture
# def mock_mutagen_file(monkeypatch):
#     def mock_file(path):
#         if "Slightly" in str(path):
#             return MockAudio("Slightly Different Title")
#         else:
#             return MockAudio("Correct Album Title")
#
#     monkeypatch.setattr("mutagen.File", mock_file)
#
# @pytest.fixture
# def temp_album(tmp_path: Path) -> Path:
#     """
#     Creates a temporary album directory with dummy files.
#     """
#     album_dir = tmp_path / "Original Album Name"
#     album_dir.mkdir()
#
#     (album_dir / "track1.flac").touch()
#     (album_dir / "track2.flac").touch()
#     (album_dir / "track3_Slightly_Different.flac").touch()
#
#     return album_dir
#
# def test_clean_album_folder(temp_album: Path, mock_mutagen_file, monkeypatch):
#     """
#     Tests that the album folder is renamed correctly based on metadata consensus.
#     """
#     # Mock the CLEANED_FLAC_PATH to use the temporary directory
#     monkeypatch.setattr("src.album_cleaner.CLEANED_FLAC_PATH", temp_album.parent)
#
#     cleaner = AlbumCleaner()
#     cleaner.clean_album_folder(temp_album)
#
#     # The new path should be within the temp_album's parent directory,
#     # which is now the mocked CLEANED_FLAC_PATH.
#     # The artist is the name of the temp_album's parent's name, which is the pytest-generated name
#     artist_name = temp_album.parent.name
#     new_album_path = temp_album.parent / artist_name / "Correct Album Title"
#
#     assert new_album_path.exists()
#     assert not temp_album.exists()
#
# def test_clean_album_folder_no_consensus(tmp_path: Path, monkeypatch):
#     """
#     Tests that the album folder is not renamed if no consensus can be reached.
#     """
#     album_dir = tmp_path / "Another Album"
#     album_dir.mkdir()
#     (album_dir / "track1.flac").touch()
#     (album_dir / "track2.flac").touch()
#
#     def mock_file_none(path):
#         return None
#
#     monkeypatch.setattr("mutagen.File", mock_file_none)
#
#     cleaner = AlbumCleaner()
#     cleaner.clean_album_folder(album_dir)
#
#     assert album_dir.exists()