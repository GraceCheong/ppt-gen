from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


APP_DIR_NAME = "LyricsToPPT"
RELEASE_DIR_NAME = "Release"
VERSION_RE = re.compile(r"^v1\.0\.(\d+)$")

REQUIRED_FILES = (
    "LyricsToPPT.exe",
    "template.pptx",
    "sequences.txt",
)
SPEC_FILE_NAME = "LyricsToPPT.spec"
EXE_FILE_NAME = "LyricsToPPT.exe"


def project_root() -> Path:
    return Path(__file__).resolve().parent


def read_sequence_titles(sequence_file: Path) -> list[str]:
    lines = [
        line.strip()
        for line in sequence_file.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    return lines[0::2]


def find_release_dirs(release_dir: Path) -> list[tuple[int, Path]]:
    if not release_dir.exists():
        return []

    release_dirs: list[tuple[int, Path]] = []
    for path in release_dir.iterdir():
        if not path.is_dir():
            continue

        match = VERSION_RE.match(path.name)
        if match:
            release_dirs.append((int(match.group(1)), path))

    return sorted(release_dirs, key=lambda item: item[0])


def has_zip_file(path: Path) -> bool:
    return any(child.is_file() and child.suffix.lower() == ".zip" for child in path.iterdir())


def next_release_version(release_dir: Path) -> str:
    release_dirs = find_release_dirs(release_dir)
    dirs_with_zip = [(patch, path) for patch, path in release_dirs if has_zip_file(path)]

    if dirs_with_zip:
        next_patch = dirs_with_zip[-1][0] + 1
    elif release_dirs:
        next_patch = release_dirs[-1][0]
    else:
        next_patch = 0

    return f"v1.0.{next_patch}"


def build_exe(root: Path) -> Path:
    spec_file = root / SPEC_FILE_NAME
    if not spec_file.is_file():
        raise FileNotFoundError(f"Missing PyInstaller spec file: {SPEC_FILE_NAME}")

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file),
    ]

    print("Building exe...")
    try:
        subprocess.run(command, cwd=root, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"PyInstaller failed with exit code {exc.returncode}") from exc

    built_exe = root / "dist" / EXE_FILE_NAME
    if not built_exe.is_file():
        raise FileNotFoundError(f"Built exe was not found: {built_exe}")

    release_exe = root / EXE_FILE_NAME
    shutil.copy2(built_exe, release_exe)
    return release_exe


def collect_release_files(root: Path) -> list[Path]:
    missing = [name for name in REQUIRED_FILES if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing required release file(s): " + ", ".join(missing))

    release_files = [root / name for name in REQUIRED_FILES]

    sequence_titles = read_sequence_titles(root / "sequences.txt")
    missing_lyrics: list[str] = []

    for title in sequence_titles:
        lyric_file = root / f"{title}.txt"
        if lyric_file.is_file():
            release_files.append(lyric_file)
        else:
            missing_lyrics.append(lyric_file.name)

    if missing_lyrics:
        raise FileNotFoundError(
            "Missing lyric file(s) referenced by sequences.txt: "
            + ", ".join(missing_lyrics)
        )

    return release_files


def create_release_zip(version: str, release_files: list[Path], force: bool) -> Path:
    root = project_root()
    version_dir = root / RELEASE_DIR_NAME / version
    zip_path = version_dir / f"{APP_DIR_NAME}-Windows-{version}.zip"

    version_dir.mkdir(parents=True, exist_ok=True)

    if zip_path.exists() and not force:
        raise FileExistsError(f"{zip_path} already exists. Use --force to overwrite it.")

    compression = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(zip_path, "w", compression=compression) as zip_file:
        for file_path in release_files:
            archive_name = Path(APP_DIR_NAME) / file_path.name
            zip_file.write(file_path, archive_name.as_posix())

    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a LyricsToPPT Windows release zip under Release/v1.0.*."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the target zip if it already exists.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()
    release_dir = root / RELEASE_DIR_NAME

    try:
        build_exe(root)
        release_files = collect_release_files(root)
        version = next_release_version(release_dir)
        zip_path = create_release_zip(version, release_files, args.force)
    except Exception as exc:
        print(f"Release build failed: {exc}", file=sys.stderr)
        return 1

    print(f"Created {zip_path.relative_to(root)}")
    print("Included files:")
    for file_path in release_files:
        print(f"  {APP_DIR_NAME}/{file_path.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
