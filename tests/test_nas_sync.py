from pathlib import Path

import pytest

from nas_sync import Action, NasSync, album_key, find_album_folders, letter_folder


@pytest.mark.parametrize(
    "artist, letter",
    [
        ("Oophoi", "O"),
        ("Øjerum", "O"),
        ("Æthenor", "A"),
        ("_Zoviet_France_", "Z"),
        ("The Orb", "T"),
        ("Ô Paradis", "O"),
        ("65daysofstatic", "0-9"),
    ],
)
def test_letter_folder_matches_nas_layout(artist: str, letter: str):
    assert letter_folder(artist) == letter


@pytest.mark.parametrize(
    "a, b",
    [
        ("2007   Forgotten Rituals [Flac]", "Forgotten Rituals"),
        ("1998 - Behind The Wall Of Sleep", "Behind the Wall of Sleep"),
        ("2018 - Buddha-Bar XX (2CD)", "Buddha-Bar XX"),
        ("Amnios (320)", "Amnios (Remastered 2010)"),
    ],
)
def test_album_key_ignores_year_and_format_noise(a: str, b: str):
    assert album_key(a) == album_key(b)


@pytest.mark.parametrize(
    "a, b",
    [
        ("Time Fragments, Vol. 1_ Lost Memories", "Time Fragments, Vol. 2_ Hidden Visions"),
        ("Amnios", "Amnios (Remixes)"),
    ],
)
def test_album_key_keeps_different_albums_apart(a: str, b: str):
    assert album_key(a) != album_key(b)


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


def test_find_album_folders_treats_disc_subfolders_as_one_album(tmp_path: Path):
    _touch(tmp_path / "Artist" / "Single" / "01.mp3")
    _touch(tmp_path / "Artist" / "Double" / "CD1" / "01.flac")
    _touch(tmp_path / "Artist" / "Double" / "CD2" / "01.flac")
    _touch(tmp_path / "Artist" / "Scans Only" / "cover.jpg")

    albums = find_album_folders(tmp_path)

    assert albums == [tmp_path / "Artist" / "Double", tmp_path / "Artist" / "Single"]


# Source albums below have no tags, so the artist comes from the parent folder name.


def test_new_album_reuses_existing_artist_folder_with_different_case(tmp_path: Path):
    nas = tmp_path / "nas"
    _touch(nas / "O" / "Oophoi" / "Amnios" / "01.flac")
    album = tmp_path / "src" / "OOPHOI" / "New Album"
    _touch(album / "01.mp3")

    plan = NasSync(music_path=nas).plan_album(album)

    assert plan.action == Action.NEW
    assert plan.destination == nas / "O" / "Oophoi" / "New Album"


def test_apple_music_compilation_goes_to_va(tmp_path: Path):
    nas = tmp_path / "nas"
    (nas / "VA").mkdir(parents=True)
    album = tmp_path / "src" / "Compilations" / "Occult Realm"
    _touch(album / "01.m4a")

    plan = NasSync(music_path=nas).plan_album(album)

    assert plan.destination == nas / "VA" / "Occult Realm"


def test_flac_replaces_mp3_in_same_folder_and_keeps_cover(tmp_path: Path):
    nas = tmp_path / "nas"
    nas_album = nas / "O" / "Oophoi" / "Amnios"
    _touch(nas_album / "01.mp3")
    _touch(nas_album / "cover.jpg")
    album = tmp_path / "src" / "Oophoi" / "Amnios"
    _touch(album / "01.flac")
    sync = NasSync(music_path=nas)

    plan = sync.plan_album(album)
    assert plan.action == Action.REPLACE
    assert plan.destination == nas_album
    assert sync.apply(plan)

    assert sorted(p.name for p in nas_album.iterdir()) == ["01.flac", "cover.jpg"]


def test_flac_replaces_mp3_folder_with_different_name(tmp_path: Path):
    nas = tmp_path / "nas"
    old = nas / "O" / "Oophoi" / "1998 - Amnios [MP3]"
    _touch(old / "01.mp3")
    album = tmp_path / "src" / "Oophoi" / "Amnios"
    _touch(album / "01.flac")
    sync = NasSync(music_path=nas)

    plan = sync.plan_album(album)
    assert plan.action == Action.REPLACE
    assert sync.apply(plan)

    assert not old.exists()
    assert (nas / "O" / "Oophoi" / "Amnios" / "01.flac").exists()


def test_failed_copy_deletes_nothing(tmp_path: Path, monkeypatch):
    nas = tmp_path / "nas"
    old = _touch(nas / "O" / "Oophoi" / "Amnios" / "01.mp3")
    album = tmp_path / "src" / "Oophoi" / "Amnios"
    _touch(album / "01.flac")
    sync = NasSync(music_path=nas)
    monkeypatch.setattr(sync, "_rsync", lambda source, target: False)

    assert not sync.apply(sync.plan_album(album))

    assert old.exists()


def test_interrupted_copy_is_not_mistaken_for_an_album_on_nas(tmp_path: Path):
    nas = tmp_path / "nas"
    artist = nas / "O" / "Oophoi"
    _touch(artist / ".Amnios.partial" / "01.flac")  # left behind by an interrupted run
    album = tmp_path / "src" / "Oophoi" / "Amnios"
    _touch(album / "01.flac")
    _touch(album / "02.flac")
    sync = NasSync(music_path=nas)

    plan = sync.plan_album(album)
    assert plan.action == Action.NEW
    assert sync.apply(plan)

    assert sorted(p.name for p in artist.iterdir()) == ["Amnios"]
    assert sorted(p.name for p in (artist / "Amnios").iterdir()) == ["01.flac", "02.flac"]


def test_mp3_is_skipped_when_flac_is_on_nas(tmp_path: Path):
    nas = tmp_path / "nas"
    _touch(nas / "O" / "Oophoi" / "2001 - Mare Imbrium" / "01.flac")
    album = tmp_path / "src" / "Oophoi" / "Mare Imbrium"
    _touch(album / "01.mp3")

    plan = NasSync(music_path=nas).plan_album(album)

    assert plan.action == Action.SKIP
    assert plan.remove == []


def test_mp3_is_skipped_when_album_is_on_nas_in_other_lossy_format(tmp_path: Path):
    nas = tmp_path / "nas"
    _touch(nas / "O" / "Oophoi" / "Amnios" / "01.m4a")
    album = tmp_path / "src" / "Oophoi" / "Amnios"
    _touch(album / "01.mp3")

    plan = NasSync(music_path=nas).plan_album(album)

    assert plan.action == Action.SKIP


def test_album_on_nas_in_same_format_is_never_merged_into(tmp_path: Path):
    nas = tmp_path / "nas"
    _touch(nas / "O" / "Oophoi" / "Amnios" / "01 - Liquos.mp3")
    album = tmp_path / "src" / "Oophoi" / "Amnios"
    _touch(album / "01 Liquos.mp3")
    _touch(album / "02 Aquos.mp3")

    plan = NasSync(music_path=nas).plan_album(album)

    assert plan.action == Action.SKIP
    assert plan.remove == []


def test_flac_album_on_nas_is_never_merged_into(tmp_path: Path):
    nas = tmp_path / "nas"
    _touch(nas / "O" / "Oophoi" / "Amnios" / "01.flac")
    album = tmp_path / "src" / "Oophoi" / "Amnios"
    _touch(album / "01.flac")
    _touch(album / "02.flac")

    plan = NasSync(music_path=nas).plan_album(album)

    assert plan.action == Action.SKIP


def test_loose_files_next_to_album_folders_are_not_an_album(tmp_path: Path):
    _touch(tmp_path / "complete" / "stray.mp3")
    _touch(tmp_path / "complete" / "Artist" / "Album" / "01.mp3")
    loose: list[Path] = []

    albums = find_album_folders(tmp_path / "complete", loose)

    assert albums == [tmp_path / "complete" / "Artist" / "Album"]
    assert loose == [tmp_path / "complete"]


@pytest.fixture
def fake_trash(tmp_path: Path, monkeypatch) -> Path:
    trash = tmp_path / "Trash"
    trash.mkdir()
    script = tmp_path / "fake-trash.sh"
    script.write_text(f'#!/bin/sh\nmv "$1" "{trash}/"\n')
    script.chmod(0o755)
    monkeypatch.setattr("nas_sync.TRASH_COMMAND", str(script))
    return trash


def _library(tmp_path: Path) -> tuple[Path, Path]:
    nas = tmp_path / "nas" / "Music"
    for letter in ("B", "O"):
        (nas / letter).mkdir(parents=True)
    source = tmp_path / "Cleaned FLAC"
    _touch(source / "Biosphere" / "Substrata" / "01.flac")
    _touch(source / "Biosphere" / ".DS_Store")
    _touch(source / "Oophoi" / "Amnios" / "01.mp3")
    _touch(source / "Oophoi" / "Other" / "01.mp3")
    _touch(nas / "O" / "Oophoi" / "Amnios" / "01 - Liquos.mp3")
    return nas, source


def test_move_trashes_copied_and_skipped_albums_and_empty_artist_folders(
    tmp_path: Path, fake_trash: Path, monkeypatch
):
    nas, source = _library(tmp_path)
    monkeypatch.setattr(NasSync, "_ensure_mounted", lambda self: True)

    assert NasSync(assume_yes=True, move=True, music_path=nas).sync([source])

    assert (nas / "B" / "Biosphere" / "Substrata" / "01.flac").exists()
    assert sorted(p.name for p in fake_trash.iterdir()) == ["Amnios", "Other", "Substrata"]
    assert list(source.iterdir()) == []


def test_move_keeps_album_on_mac_when_nas_copy_is_incomplete(
    tmp_path: Path, fake_trash: Path, monkeypatch
):
    nas, source = _library(tmp_path)
    monkeypatch.setattr(NasSync, "_ensure_mounted", lambda self: True)
    monkeypatch.setattr("nas_sync._copied_completely", lambda source, destination: False)

    assert not NasSync(assume_yes=True, move=True, music_path=nas).sync([source])

    assert (source / "Biosphere" / "Substrata" / "01.flac").exists()
    assert sorted(p.name for p in fake_trash.iterdir()) == ["Amnios"]  # skipped, already on NAS


def test_dry_run_with_move_touches_nothing(tmp_path: Path, fake_trash: Path, monkeypatch):
    nas, source = _library(tmp_path)
    monkeypatch.setattr(NasSync, "_ensure_mounted", lambda self: True)

    assert NasSync(dry_run=True, move=True, music_path=nas).sync([source])

    assert list(fake_trash.iterdir()) == []
    assert not (nas / "B" / "Biosphere").exists()
