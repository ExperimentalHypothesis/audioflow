import typer
from . import config
from .soulseek_cronjob import SoulseekCronjob
from .album_cleaner import AlbumCleaner

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


if __name__ == "__main__":
    app()