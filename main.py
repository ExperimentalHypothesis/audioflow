import typer
from pathlib import Path

import config
from album_cleaner import AlbumCleaner
from flac_to_mp3_converter import FlacToMp3Converter
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


if __name__ == "__main__":
    app()