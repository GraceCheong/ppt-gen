from __future__ import annotations

import argparse
import re
import subprocess
import sys
import zipfile
from pathlib import Path

APP_DIR_NAME = "PORR_atempo"
RELEASE_DIR_NAME = "Release"
VERSION_RE = re.compile(r"^v1\.0\.(\d+)$")
SPEC_FILE_NAME = "LyricsToPPT.spec"

ASSET_FILES = (
    "assets/sequences_sample.txt",
    "assets/atempo.ico",
    "assets/atempo.png",
    "assets/logo.png",
    "assets/background.png",
    "README.md",
    "requirements.txt",
)

if sys.platform == "win32":
    PLATFORM_LABEL = "Windows"
    ARTIFACT_SUBPATH = "dist/PORR_atempo.exe"
    IS_APP_BUNDLE = False
elif sys.platform == "darwin":
    PLATFORM_LABEL = "macOS"
    ARTIFACT_SUBPATH = "dist/PORR_atempo.app"
    IS_APP_BUNDLE = True
else:
    raise SystemExit(f"Unsupported platform: {sys.platform}")


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_release_dirs(release_dir: Path) -> list[tuple[int, Path]]:
    if not release_dir.exists():
        return []
    result = []
    for path in release_dir.iterdir():
        if not path.is_dir():
            continue
        match = VERSION_RE.match(path.name)
        if match:
            result.append((int(match.group(1)), path))
    return sorted(result, key=lambda item: item[0])


def has_zip_file(path: Path) -> bool:
    return any(child.is_file() and child.suffix.lower() == ".zip" for child in path.iterdir())


def next_release_version(release_dir: Path) -> str:
    release_dirs = find_release_dirs(release_dir)
    dirs_with_zip = [(p, d) for p, d in release_dirs if has_zip_file(d)]
    if dirs_with_zip:
        next_patch = dirs_with_zip[-1][0] + 1
    elif release_dirs:
        next_patch = release_dirs[-1][0]
    else:
        next_patch = 0
    return f"v1.0.{next_patch}"


def build_artifact(root: Path) -> Path:
    spec_file = Path(__file__).resolve().parent / SPEC_FILE_NAME
    if not spec_file.is_file():
        raise FileNotFoundError(f"Missing spec file: {SPEC_FILE_NAME}")

    print(f"Building for {PLATFORM_LABEL}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(spec_file)],
            cwd=root,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"PyInstaller failed: exit code {exc.returncode}") from exc

    artifact = root / ARTIFACT_SUBPATH
    if not artifact.exists():
        raise FileNotFoundError(f"Built artifact not found: {artifact}")
    return artifact


def collect_asset_files(root: Path) -> list[Path]:
    missing = [name for name in ASSET_FILES if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing required file(s): " + ", ".join(missing))
    return [root / name for name in ASSET_FILES]


def _add_dir_to_zip(zf: zipfile.ZipFile, dir_path: Path, archive_base: Path) -> None:
    for file_path in dir_path.rglob("*"):
        if file_path.is_file():
            rel = file_path.relative_to(dir_path.parent)
            zf.write(file_path, (archive_base / rel).as_posix())


def create_release_zip(version: str, artifact: Path, asset_files: list[Path], force: bool) -> Path:
    root = project_root()
    version_dir = root / RELEASE_DIR_NAME / version
    zip_path = version_dir / f"{APP_DIR_NAME}-{PLATFORM_LABEL}-{version}.zip"

    version_dir.mkdir(parents=True, exist_ok=True)

    if zip_path.exists() and not force:
        raise FileExistsError(f"{zip_path} already exists. Use --force to overwrite.")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        base = Path(APP_DIR_NAME)

        if IS_APP_BUNDLE:
            _add_dir_to_zip(zf, artifact, base)
        else:
            zf.write(artifact, (base / artifact.name).as_posix())

        for file_path in asset_files:
            rel = file_path.relative_to(root)
            zf.write(file_path, (base / rel).as_posix())

    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"Build and package LyricsToPPT for {PLATFORM_LABEL}."
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing zip.")
    parser.add_argument("--version", help="Override release version (e.g. v1.0.3).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()

    if args.version and not VERSION_RE.match(args.version):
        print(f"Invalid version format: {args.version!r}. Expected v1.0.X", file=sys.stderr)
        return 1

    try:
        artifact = build_artifact(root)
        asset_files = collect_asset_files(root)
        version = args.version or next_release_version(root / RELEASE_DIR_NAME)
        zip_path = create_release_zip(version, artifact, asset_files, args.force)
    except Exception as exc:
        print(f"Release build failed: {exc}", file=sys.stderr)
        return 1

    print(f"Created {zip_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
