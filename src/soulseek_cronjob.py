from pathlib import Path

from album_cleaner import AlbumCleaner, CleanResult, Colors


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
        Processes the completed downloads with formatted output.
        """
        c = Colors

        # Header
        print()
        print(f"{c.BOLD}{'─' * 70}{c.RESET}")
        print(f"{c.BOLD}  Audioflow - Processing Downloads{c.RESET}")
        print(f"{c.DIM}  {self.complete_folder}{c.RESET}")
        print(f"{c.BOLD}{'─' * 70}{c.RESET}")
        print()

        # Counters for summary
        stats = {"success": 0, "skipped": 0, "error": 0, "downloading": 0}

        albums = sorted(
            [p for p in self.complete_folder.iterdir() if p.is_dir()],
            key=lambda x: x.name.lower()
        )

        if not albums:
            print(f"  {c.DIM}No albums found{c.RESET}")
        else:
            for album_path in albums:
                album_name = album_path.name

                if not self.is_album_complete(album_name):
                    # Still downloading
                    print(f"  {c.YELLOW}⏳{c.RESET} {album_name}")
                    print(f"     {c.DIM}Still downloading...{c.RESET}")
                    stats["downloading"] += 1
                else:
                    # Process the album
                    status, message = self.cleaner.clean_album_folder(album_path)

                    if status == CleanResult.SUCCESS:
                        print(f"  {c.GREEN}✓{c.RESET} {album_name}")
                        print(f"     {c.DIM}→ {message}{c.RESET}")
                        stats["success"] += 1
                    elif status == CleanResult.SKIPPED:
                        print(f"  {c.YELLOW}○{c.RESET} {album_name}")
                        print(f"     {c.DIM}{message}{c.RESET}")
                        stats["skipped"] += 1
                    else:  # ERROR
                        print(f"  {c.RED}✗{c.RESET} {album_name}")
                        print(f"     {c.RED}{message}{c.RESET}")
                        stats["error"] += 1

                print()

        # Summary
        print(f"{c.BOLD}{'─' * 70}{c.RESET}")
        summary_parts = []
        if stats["success"]:
            summary_parts.append(f"{c.GREEN}{stats['success']} cleaned{c.RESET}")
        if stats["skipped"]:
            summary_parts.append(f"{c.YELLOW}{stats['skipped']} skipped{c.RESET}")
        if stats["downloading"]:
            summary_parts.append(f"{c.YELLOW}{stats['downloading']} downloading{c.RESET}")
        if stats["error"]:
            summary_parts.append(f"{c.RED}{stats['error']} failed{c.RESET}")

        if summary_parts:
            print(f"  {' · '.join(summary_parts)}")
        else:
            print(f"  {c.DIM}Nothing to process{c.RESET}")
        print(f"{c.BOLD}{'─' * 70}{c.RESET}")
        print()