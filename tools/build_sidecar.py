"""porr-server 사이드카 바이너리를 빌드하고 Tauri binaries/ 폴더에 배치한다.

사용법:
    cd c:/dev/ppt-gen
    python tools/build_sidecar.py

사전 조건:
    pip install pyinstaller

출력:
    apps/desktop/src-tauri/binaries/porr-server-<target-triple>.exe
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _target_triple() -> str:
    """현재 플랫폼의 Rust target triple을 반환한다."""
    machine = platform.machine().lower()
    system = platform.system().lower()

    if system == "windows":
        arch = "x86_64" if machine in ("amd64", "x86_64") else "aarch64"
        return f"{arch}-pc-windows-msvc"
    if system == "darwin":
        arch = "aarch64" if machine == "arm64" else "x86_64"
        return f"{arch}-apple-darwin"
    # Linux
    arch = "x86_64" if machine in ("amd64", "x86_64") else "aarch64"
    return f"{arch}-unknown-linux-gnu"


def main() -> None:
    root = _project_root()
    spec = os.path.join(root, "tools", "porr_server.spec")
    dist_dir = os.path.join(root, "dist")
    binaries_dir = os.path.join(root, "apps", "desktop", "src-tauri", "binaries")

    print(f"[build-sidecar] PyInstaller 빌드 시작: {spec}")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--distpath", dist_dir, spec],
        cwd=root,
    )
    if result.returncode != 0:
        print("[build-sidecar] 빌드 실패")
        sys.exit(1)

    triple = _target_triple()
    ext = ".exe" if platform.system() == "Windows" else ""
    src_exe = os.path.join(dist_dir, "porr-server", f"porr-server{ext}")
    if not os.path.exists(src_exe):
        # onefile 모드 fallback
        src_exe = os.path.join(dist_dir, f"porr-server{ext}")

    if not os.path.exists(src_exe):
        print(f"[build-sidecar] 빌드 결과물을 찾을 수 없습니다: {src_exe}")
        sys.exit(1)

    os.makedirs(binaries_dir, exist_ok=True)
    dest = os.path.join(binaries_dir, f"porr-server-{triple}{ext}")

    # onedir 모드: 전체 디렉터리를 복사
    src_dir = os.path.join(dist_dir, "porr-server")
    if os.path.isdir(src_dir):
        dest_dir = os.path.join(binaries_dir, f"porr-server-{triple}")
        if os.path.exists(dest_dir):
            shutil.rmtree(dest_dir)
        shutil.copytree(src_dir, dest_dir)
        # 실행 파일 이름도 triple로 변경
        src_inner = os.path.join(dest_dir, f"porr-server{ext}")
        dest_inner = os.path.join(dest_dir, f"porr-server-{triple}{ext}")
        if os.path.exists(src_inner) and not os.path.exists(dest_inner):
            os.rename(src_inner, dest_inner)
        dest = dest_inner
    else:
        shutil.copy2(src_exe, dest)

    print(f"[build-sidecar] 완료: {dest}")
    print(f"[build-sidecar] 이제 `cargo tauri build`를 실행해 데스크톱 앱을 빌드하세요.")


if __name__ == "__main__":
    main()
