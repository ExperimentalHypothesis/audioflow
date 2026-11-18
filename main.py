import typer
from pathlib import Path

import config
from album_cleaner import AlbumCleaner
from flac_to_mp3_converter import FlacToMp3Converter
from nas_sync import NasSync
from plex import refresh_plex, refresh_plex_library
from soulseek_cronjob import SoulseekCronjob

app = typer.Typer()


@app.command()
def process_downloads():
    """
    Process downloaded albums.
    """
    cleaner = AlbumCleaner()
    cronjob = SoulseekCronjob(
        complete_folder=config.SOULSEEK_COMPLETE_PATH,
        downloading_folder=config.SOULSEEK_DOWNLOADING_PATH,
        cleaner=cleaner,
    )
    cronjob.process_completed_downloads()


@app.command()
def convert_to_mp3(
    album_path: Path,
    bitrate: str = typer.Option(
        config.MP3_BITRATE,
        "--bitrate",
        "-b",
        help="The bitrate for the MP3 files (e.g., '320k').",
    ),
):
    """
    Converts a FLAC album to MP3.
    """
    converter = FlacToMp3Converter(bitrate=bitrate)
    converter.convert(album_path)


@app.command()
def sync_to_nas(
    paths: list[Path] = typer.Argument(
        ..., help="Folders with albums: a whole library, an artist or a single album."
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Only show what would be copied and deleted.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Don't ask before deleting anything.",
    ),
    move: bool = typer.Option(
        False,
        "--move",
        "-m",
        help="Move albums on the Mac to the Trash once they're on the NAS.",
    ),
):
    """
    Copies albums to the NAS as <Letter>/<Artist>/<Album>; FLAC replaces MP3, never the reverse.
    """
    if not NasSync(dry_run=dry_run, assume_yes=yes, move=move, plex=True).sync(paths):
        raise typer.Exit(code=1)


@app.command()
def plex_scan(
    paths: list[Path] = typer.Argument(
        None, help="Folders on the NAS (under /Volumes/Public/Music); whole library if omitted."
    ),
):
    """
    Makes Plex rescan the music library (or just the given folders).
    """
    folders = [path.expanduser().resolve() for path in paths or []]
    ok = refresh_plex(folders) if folders else refresh_plex_library()
    if not ok:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()