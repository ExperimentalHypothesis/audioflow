from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import os
import re
import shutil
import subprocess
import time
import unicodedata

import mutagen
import typer

from album_cleaner import AlbumCleaner, Colors
from plex import refresh_plex
from config import (
    NAS_MOUNT_PATH,
    NAS_MUSIC_PATH,
    NAS_NON_LETTER_FOLDER,
    NAS_SMB_URL,
    NAS_VARIOUS_ARTISTS_FOLDER,
)

LOSSLESS_EXTENSIONS = {".flac", ".wav", ".aiff", ".aif", ".ape", ".wv", ".alac"}
# .m4a counts as lossy: ALAC and AAC share the extension and AAC is far more common.
LOSSY_EXTENSIONS = {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wma"}
AUDIO_EXTENSIONS = LOSSLESS_EXTENSIONS | LOSSY_EXTENSIONS

# Subfolders of a multi-disc album ("CD1", "Disc 2", ...). Their parent is the album.
DISC_FOLDER_PATTERN = re.compile(r"^(cd|disc|disk)\s*\d+\b", re.IGNORECASE)

TRASH_COMMAND = "/usr/bin/trash"  # macOS 15+, moves to the Finder Trash

VARIOUS_ARTISTS_NAMES ={"various artists", "various", "va", "v.a.", "v/a"}

# Apple Music keeps compilations under "Compilations/<Album>".
COMPILATIONS_FOLDER_NAMES = {"compilations"}

# Letters that don't decompose to a base letter with NFKD.
LETTER_OVERRIDES = {"Æ": "A", "Ø": "O", "Œ": "O", "Ð": "D", "Þ": "T", "Ł": "L", "ß": "S"}

# Ignored when comparing album folder names: a leading year ("1998 - ") and bracketed
# year/format/bitrate/disc-count/remaster tags. Anything else (e.g. "Vol. 2") still counts.
YEAR_PREFIX = re.compile(r"^\s*[\(\[]?(?:19|20)\d{2}[\)\]]?\s*[-–_.]*\s+")
NOISE_GROUP = re.compile(
    r"[\(\[]\s*(?:(?:19|20)\d{2}|flac|mp3|aac|m4a|ogg|web|cd|vinyl|lossless|lossy"
    r"|\d{3}\s*(?:k|kbps)?|v[02]|\d+\s*cds?|(?:16|24)\s*-?bit[^\)\]]*"
    r"|remaster(?:ed)?(?:\s*(?:19|20)\d{2})?)\s*[\)\]]",
    re.IGNORECASE,
)


class Action(Enum):
    NEW = "new"
    REPLACE = "replace"
    SKIP = "skip"


def letter_folder(artist: str) -> str:
    """
    The NAS letter folder: first letter or digit without diacritics ("Øjerum" -> "O").
    """
    for char in artist:
        base = unicodedata.normalize("NFKD", char)[0].upper()
        base = LETTER_OVERRIDES.get(base, base)
        if "A" <= base <= "Z":
            return base
        if base.isdigit():
            return NAS_NON_LETTER_FOLDER
    return NAS_NON_LETTER_FOLDER


def album_key(name: str) -> str:
    """
    Comparable album name: "2007 - Forgotten Rituals [Flac]" -> "forgotten rituals".
    """
    name = unicodedata.normalize("NFKD", name)
    name = "".join(char for char in name if not unicodedata.combining(char))
    name = YEAR_PREFIX.sub("", name)
    name = NOISE_GROUP.sub(" ", name)
    return " ".join(re.sub(r"[\W_]+", " ", name.casefold()).split())


def _normalize(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _is_audio(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def _is_lossless(path: Path) -> bool:
    return path.suffix.lower() in LOSSLESS_EXTENSIONS


def _audio_files(folder: Path) -> list[Path]:
    return sorted(f for f in folder.rglob("*") if _is_audio(f))


def _format_label(files: list[Path]) -> str:
    return "/".join(sorted({f.suffix.lower().lstrip(".").upper() for f in files}))


def _folder_size(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())


def _gb(size: int) -> str:
    return f"{size / 1e9:.1f} GB" if size >= 1e8 else f"{size / 1e6:.0f} MB"


def _delete(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _move_into(staging: Path, destination: Path) -> None:
    """
    Renames `staging` to `destination`; an existing destination keeps files staging lacks (covers).
    """
    if not destination.exists():
        staging.rename(destination)
        return
    for child in staging.iterdir():
        target = destination / child.name
        if target.exists():
            _delete(target)
        child.rename(target)
    staging.rmdir()


def _is_junk(path: Path) -> bool:
    return path.name == ".DS_Store" or path.name.startswith("._")


def _copied_completely(source: Path, destination: Path) -> bool:
    for file in source.rglob("*"):
        if not file.is_file() or _is_junk(file):
            continue
        target = destination / file.relative_to(source)
        if not target.is_file() or target.stat().st_size != file.stat().st_size:
            return False
    return True


def _remove_empty_folders(folder: Path, root: Path) -> None:
    """
    Removes `folder` and its parents below `root` while they hold nothing but .DS_Store.
    """
    while folder != root and folder.is_relative_to(root):
        if any(not _is_junk(child) for child in folder.iterdir()):
            return
        for child in folder.iterdir():
            child.unlink()
        folder.rmdir()
        folder = folder.parent


def _has_direct_audio(folder: Path) -> bool:
    return any(_is_audio(child) for child in folder.iterdir())


def _is_album_folder(folder: Path) -> bool:
    if _has_direct_audio(folder):
        return True
    return any(
        child.is_dir()
        and DISC_FOLDER_PATTERN.match(child.name)
        and _has_direct_audio(child)
        for child in folder.iterdir()
    )


def find_album_folders(root: Path, loose: list[Path] | None = None) -> list[Path]:
    """
    Folders under `root` holding audio files directly or in "CD1"/"Disc 2" subfolders.
    Folders with audio files next to other album folders are not albums; they go to `loose`.
    """
    albums = []
    for current, dirs, _ in os.walk(root):
        dirs.sort()
        folder = Path(current)
        if not _is_album_folder(folder):
            continue
        nested_albums = [
            d
            for d in dirs
            if not DISC_FOLDER_PATTERN.match(d)
            and any(_is_audio(f) for f in (folder / d).rglob("*"))
        ]
        if nested_albums:
            if loose is not None and _has_direct_audio(folder):
                loose.append(folder)
            continue
        albums.append(folder)
        dirs[:] = []  # rsync copies the whole album folder, including subfolders
    return albums


def _read_artist_tags(audio_file: Path) -> tuple[str | None, str | None]:
    """
    Returns (albumartist, artist) tags of an audio file.
    """
    if audio_file.suffix.lower() == ".wma":
        metadata = AlbumCleaner._get_audio_metadata(audio_file) or {}
        return metadata.get("albumartist"), metadata.get("artist")
    try:
        audio = mutagen.File(audio_file, easy=True)
    except Exception:
        return None, None
    if audio is None or audio.tags is None:
        return None, None

    def first(key: str) -> str | None:
        try:
            values = audio.tags.get(key)
        except Exception:
            return None
        if not values:
            return None
        return str(values[0]).strip() or None

    return first("albumartist"), first("artist")


@dataclass
class AlbumPlan:
    source: Path
    destination: Path
    artist_source: str  # "tags" | "folder name" | "compilation"
    action: Action
    note: str = ""
    # Lossy files or whole lossy album folders on the NAS, deleted after a successful copy.
    remove: list[Path] = field(default_factory=list)
    # The folder given on the command line; empty folders up to it are cleaned with --move.
    source_root: Path | None = None


class NasSync:
    def __init__(
        self,
        dry_run: bool = False,
        assume_yes: bool = False,
        move: bool = False,
        plex: bool = False,
        music_path: Path = NAS_MUSIC_PATH,
    ):
        self.dry_run = dry_run
        self.assume_yes = assume_yes
        self.move = move
        self.plex = plex
        self.music_path = music_path
        self._folder_cache: dict[Path, list[str]] = {}

    def sync(self, paths: list[Path]) -> bool:
        """
        Copies albums under `paths` into the NAS letter/artist layout; FLAC replaces lossy copies.
        """
        c = Colors

        if shutil.which("rsync") is None:
            print(f"  {c.RED}✗{c.RESET} rsync is not installed")
            return False

        sources = []
        for path in paths:
            source = path.expanduser().resolve()
            if not source.is_dir():
                print(f"  {c.RED}✗{c.RESET} Not a folder: {source}")
                return False
            sources.append(source)

        if not self._ensure_mounted():
            return False

        if self.move and not Path(TRASH_COMMAND).exists():
            print(f"  {c.RED}✗{c.RESET} {TRASH_COMMAND} not found (needs macOS 15+)")
            return False

        plans: list[AlbumPlan] = []
        for source in sources:
            loose: list[Path] = []
            albums = find_album_folders(source, loose)
            for folder in loose:
                print(
                    f"\r\033[K  {c.YELLOW}⚠{c.RESET} Skipping loose audio files next to "
                    f"album folders: {folder}"
                )
            for album in albums:
                print(f"\r\033[K  {c.DIM}Scanning… {len(plans) + 1}: {album.name}{c.RESET}", end="", flush=True)
                plan = self.plan_album(album)
                if plan is None:
                    print(
                        f"\r\033[K  {c.YELLOW}⚠{c.RESET} Skipping, can't tell the artist: {album}"
                    )
                    continue
                plan.source_root = source
                plans.append(plan)
        print("\r\033[K", end="")

        dry_run_label = f" {c.YELLOW}(dry run){c.RESET}" if self.dry_run else ""
        print()
        print(f"{c.BOLD}{'─' * 70}{c.RESET}")
        print(f"{c.BOLD}  Audioflow - Syncing to NAS{c.RESET}{dry_run_label}")
        print(f"{c.DIM}  → {self.music_path}{c.RESET}")
        print(f"{c.BOLD}{'─' * 70}{c.RESET}")
        print()

        if not plans:
            print(f"  {c.DIM}No albums found{c.RESET}")
            print()
            return True

        for plan in plans:
            self._print_plan(plan)
        print()

        to_copy = [plan for plan in plans if plan.action != Action.SKIP]
        sizes = {plan.source: _folder_size(plan.source) for plan in to_copy}
        total = sum(sizes.values())

        counts = Counter(plan.action for plan in plans)
        summary = ", ".join(f"{counts[a]} {a.value}" for a in Action if counts[a])
        print(f"  {c.BOLD}{len(plans)} album(s):{c.RESET} {summary}")
        print(f"  {c.BOLD}To copy:{c.RESET} {_gb(total)}")
        print()

        if self.dry_run:
            print(f"  {c.DIM}Nothing copied or deleted (dry run){c.RESET}")
            print()
            return True

        warnings = []
        if counts[Action.REPLACE]:
            warnings.append(
                f"{counts[Action.REPLACE]} lossy album(s) on the NAS will be deleted "
                f"after their FLAC is copied."
            )
        if self.move:
            warnings.append(
                f"{len(plans)} album(s) on the Mac will be moved to the Trash once they're on the NAS."
            )
        if warnings and not self.assume_yes:
            print("\n".join(f"  {c.YELLOW}{w}{c.RESET}" for w in warnings))
            if not typer.confirm("  Continue?"):
                print(f"  {c.DIM}Aborted{c.RESET}")
                return False

        started = time.monotonic()
        done = 0
        failed = 0
        trashed = 0
        changed_folders: list[Path] = []
        for index, plan in enumerate(to_copy, start=1):
            relative = plan.destination.relative_to(self.music_path)
            percent = done * 100 // total if total else 100
            print()
            print(
                f"{c.CYAN}[{index}/{len(to_copy)}  {_gb(done)} / {_gb(total)}  {percent} %]{c.RESET} "
                f"{c.BOLD}{relative}{c.RESET}",
                flush=True,
            )
            if not self.apply(plan):
                failed += 1
            else:
                changed_folders.append(plan.destination.parent)
                if self.move:
                    trashed += self._trash_source(plan)
            done += sizes[plan.source]

        if self.move:
            for plan in plans:
                if plan.action == Action.SKIP:
                    trashed += self._trash_source(plan)

        minutes, seconds = divmod(int(time.monotonic() - started), 60)
        print()
        if failed:
            print(f"  {c.RED}✗{c.RESET} {failed} of {len(to_copy)} album(s) failed")
        else:
            print(
                f"  {c.GREEN}✓{c.RESET} Synced {len(to_copy)} album(s), {_gb(total)} "
                f"in {minutes} min {seconds} s"
            )
        if self.move:
            kept = len(plans) - trashed
            print(
                f"  {c.GREEN}✓{c.RESET} Moved {trashed} album(s) on the Mac to the Trash"
                + (f", {c.YELLOW}kept {kept}{c.RESET}" if kept else "")
            )
        if self.plex and changed_folders:
            refresh_plex(changed_folders)
        print()
        return failed == 0 and trashed == (len(plans) if self.move else 0)

    def plan_album(self, album: Path) -> AlbumPlan | None:
        """
        Where the album goes ("<Letter>/<Artist>/<Album>" or "VA/<Album>") and what to do there.
        """
        album_artist, artist_source = self._album_artist(album)
        if album_artist is None:
            return None

        if artist_source == "compilation":
            parent = self.music_path / NAS_VARIOUS_ARTISTS_FOLDER
        else:
            artist = AlbumCleaner._clean_title(
                AlbumCleaner._sanitize_filename(album_artist)
            )
            letter = self.music_path / letter_folder(artist)
            parent = letter / self._existing_name(letter, artist)

        matches = self._matching_albums(parent, album.name)
        same_name = next(
            (m for m in matches if _normalize(m.name) == _normalize(album.name)), None
        )
        destination = same_name or parent / album.name
        plan = AlbumPlan(album, destination, artist_source, Action.NEW)

        nas_files = {m: _audio_files(m) for m in matches}
        nas_files = {m: files for m, files in nas_files.items() if files}
        if not nas_files:
            return plan

        source_files = _audio_files(album)
        source_lossless = sum(map(_is_lossless, source_files)) * 2 >= len(source_files)
        lossless_on_nas = [m for m, files in nas_files.items() if any(map(_is_lossless, files))]
        existing = ", ".join(
            f"{m.name} ({_format_label(files)})" for m, files in nas_files.items()
        )

        # The NAS copy is curated, so it's never merged into: only FLAC replacing lossy changes it.
        if lossless_on_nas:
            return self._skip(plan, f"FLAC already on NAS: {existing}")
        if not source_lossless:
            return self._skip(plan, f"already on NAS: {existing}")

        plan.action = Action.REPLACE
        plan.note = f"replaces {existing}"
        for match, files in nas_files.items():
            if match == destination:
                plan.remove += files  # keep covers etc. in the folder the FLAC goes into
            else:
                plan.remove.append(match)
        return plan

    def apply(self, plan: AlbumPlan) -> bool:
        """
        Copies into a hidden staging folder, then deletes replaced lossy copies and moves it in place.
        """
        if plan.action == Action.SKIP:
            return True
        # A half-copied album must not look like an album already on the NAS (it'd be skipped
        # for good); an interrupted copy resumes in the staging folder on the next run instead.
        staging = plan.destination.parent / f".{plan.destination.name}.partial"
        if not self._rsync(plan.source, staging):
            return False
        for path in plan.remove:
            if not path.is_relative_to(self.music_path) or path == self.music_path:
                raise ValueError(f"Refusing to delete outside the NAS music folder: {path}")
            _delete(path)
        if plan.remove:
            print(
                f"  {Colors.DIM}Removed {len(plan.remove)} lossy file(s)/folder(s){Colors.RESET}"
            )
        _move_into(staging, plan.destination)
        return True

    @staticmethod
    def _skip(plan: AlbumPlan, note: str) -> AlbumPlan:
        plan.action = Action.SKIP
        plan.note = note
        return plan

    def _print_plan(self, plan: AlbumPlan) -> None:
        c = Colors
        relative = plan.destination.relative_to(self.music_path)
        color = {
            Action.NEW: c.GREEN,
            Action.REPLACE: c.YELLOW,
            Action.SKIP: c.DIM,
        }[plan.action]
        label = plan.action.value + (f": {plan.note}" if plan.note else "")
        hint = (
            f" {c.YELLOW}(artist from folder name){c.RESET}"
            if plan.artist_source == "folder name"
            else ""
        )
        print(f"  {relative}  [{color}{label}{c.RESET}]{hint}")
        print(f"  {c.DIM}  ← {plan.source}{c.RESET}")
        for path in plan.remove:
            print(f"  {c.RED}    ✗ delete {path.relative_to(self.music_path)}{c.RESET}")
        if self.move:
            when = "" if plan.action == Action.SKIP else " after the copy"
            print(f"  {c.RED}    🗑 Mac: move to Trash{when}{c.RESET}")

    def _trash_source(self, plan: AlbumPlan) -> bool:
        """
        Moves the album on the Mac to the Trash; a copied album only once the NAS has every file.
        """
        c = Colors
        if plan.action != Action.SKIP and not _copied_completely(plan.source, plan.destination):
            print(f"  {c.YELLOW}⚠{c.RESET} Kept on Mac, NAS copy is incomplete: {plan.source}")
            return False
        result = subprocess.run([TRASH_COMMAND, str(plan.source)], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  {c.YELLOW}⚠{c.RESET} Couldn't move to Trash: {plan.source} {result.stderr.strip()}")
            return False
        if plan.source_root:
            _remove_empty_folders(plan.source.parent, plan.source_root)
        return True

    def _album_artist(self, album: Path) -> tuple[str | None, str]:
        if album.parent.name.casefold() in COMPILATIONS_FOLDER_NAMES:
            return NAS_VARIOUS_ARTISTS_FOLDER, "compilation"

        album_artists = Counter()
        artists = Counter()
        for audio_file in _audio_files(album):
            album_artist, artist = _read_artist_tags(audio_file)
            if album_artist:
                album_artists[album_artist] += 1
            if artist:
                artists[artist] += 1

        if album_artists:
            name = album_artists.most_common(1)[0][0]
        elif artists:
            name = artists.most_common(1)[0][0]
        else:
            # No tags: assume an "Artist/Album" folder layout.
            return album.parent.name or None, "folder name"

        if name.strip().casefold() in VARIOUS_ARTISTS_NAMES:
            return NAS_VARIOUS_ARTISTS_FOLDER, "compilation"
        return name, "tags"

    def _children(self, parent: Path) -> list[str]:
        if parent not in self._folder_cache:
            self._folder_cache[parent] = (
                [
                    child.name
                    for child in parent.iterdir()
                    if child.is_dir() and not child.name.startswith(".")
                ]
                if parent.is_dir()
                else []
            )
        return self._folder_cache[parent]

    def _existing_name(self, parent: Path, name: str) -> str:
        wanted = _normalize(name)
        return next((n for n in self._children(parent) if _normalize(n) == wanted), name)

    def _matching_albums(self, parent: Path, album_name: str) -> list[Path]:
        key = album_key(album_name)
        return [parent / n for n in self._children(parent) if album_key(n) == key]

    def _ensure_mounted(self) -> bool:
        """
        Mounts the share if needed; checking the mount stops copies into a local /Volumes folder.
        """
        c = Colors
        if not os.path.ismount(NAS_MOUNT_PATH):
            print(f"  {c.DIM}Mounting {NAS_SMB_URL}…{c.RESET}")
            subprocess.run(
                ["osascript", "-e", f'mount volume "{NAS_SMB_URL}"'],
                capture_output=True,
                timeout=120,
            )
        if not os.path.ismount(NAS_MOUNT_PATH):
            print(
                f"  {c.RED}✗{c.RESET} NAS is not mounted at {NAS_MOUNT_PATH} "
                f"(mount {NAS_SMB_URL} in Finder with ⌘K)"
            )
            return False
        if not self.music_path.is_dir():
            print(f"  {c.RED}✗{c.RESET} Music folder not found on NAS: {self.music_path}")
            return False
        return True

    def _rsync(self, source: Path, target: Path) -> bool:
        target.mkdir(parents=True, exist_ok=True)
        # -rt instead of -a: SMB shares reject owner/permission changes.
        command = [
            "rsync",
            "--recursive",
            "--times",
            "--progress",
            "--partial",
            "--exclude=.DS_Store",
            "--exclude=._*",
            f"{source}/",
            f"{target}/",
        ]
        result = subprocess.run(command)
        if result.returncode != 0:
            print(
                f"  {Colors.RED}✗{Colors.RESET} rsync failed with exit code {result.returncode}"
            )
        return result.returncode == 0
