from pathlib import Path, PurePosixPath
import socket
import urllib.parse
import urllib.request

from album_cleaner import Colors
from config import (
    NAS_MUSIC_PATH,
    PLEX_MUSIC_PATH,
    PLEX_MUSIC_SECTION,
    PLEX_TOKEN,
    PLEX_URL,
)

# Past this many folders one full library scan is quicker than many partial ones.
MAX_PARTIAL_SCANS = 20


def refresh_plex_library() -> bool:
    return _refresh([None])


def refresh_plex(folders: list[Path]) -> bool:
    """
    Asks Plex to rescan the given NAS folders (paths under NAS_MUSIC_PATH). Returns True on success.
    """
    outside = [f for f in folders if not f.is_relative_to(NAS_MUSIC_PATH)]
    if outside:
        print(f"  {Colors.RED}✗{Colors.RESET} Not in the NAS music folder: {outside[0]}")
        return False
    plex_paths: list[str | None] = sorted(
        {
            str(PurePosixPath(PLEX_MUSIC_PATH, *folder.relative_to(NAS_MUSIC_PATH).parts))
            for folder in folders
        }
    )
    if len(plex_paths) > MAX_PARTIAL_SCANS:
        plex_paths = [None]
    return _refresh(plex_paths)


def _refresh(plex_paths: list[str | None]) -> bool:
    """
    One refresh request per path; None means the whole library.
    """
    c = Colors
    if not PLEX_TOKEN:
        print(f"  {c.DIM}Plex scan skipped: no PLEX_TOKEN in .env{c.RESET}")
        return False

    base_url = _ipv4_url(PLEX_URL)
    try:
        for path in plex_paths:
            query = {"X-Plex-Token": PLEX_TOKEN}
            if path:
                query["path"] = path
            url = (
                f"{base_url}/library/sections/{PLEX_MUSIC_SECTION}/refresh?"
                f"{urllib.parse.urlencode(query)}"
            )
            urllib.request.urlopen(url, timeout=30).close()
    except OSError as error:
        print(f"  {c.YELLOW}⚠{c.RESET} Plex scan failed: {error}")
        return False

    scope = "the whole library" if plex_paths == [None] else f"{len(plex_paths)} folder(s)"
    print(f"  {c.GREEN}✓{c.RESET} Plex is rescanning {scope}")
    return True


def _ipv4_url(url: str) -> str:
    """
    Resolves the host to IPv4 once: ".local" names otherwise wait ~5 s on IPv6 per request.
    """
    parts = urllib.parse.urlsplit(url)
    try:
        address = socket.getaddrinfo(
            parts.hostname, parts.port, socket.AF_INET, socket.SOCK_STREAM
        )[0][4][0]
    except OSError:
        return url
    netloc = f"{address}:{parts.port}" if parts.port else address
    return urllib.parse.urlunsplit(parts._replace(netloc=netloc))
