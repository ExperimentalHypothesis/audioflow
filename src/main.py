import typer
from . import config
from .soulseek_cronjob import SoulseekCronjob

app = typer.Typer()


@app.command()
def process_downloads():
    """
    Process downloaded albums.
    """
    cronjob = SoulseekCronjob(
        complete_folder=config.SOULSEEK_COMPLETE_PATH,
        downloading_folder=config.SOULSEEK_DOWNLOADING_PATH,
    )
    cronjob.process_completed_downloads()


if __name__ == "__main__":
    app()