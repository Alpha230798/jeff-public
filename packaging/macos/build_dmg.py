from __future__ import annotations

import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
DEFAULT_DMG_PATH = DIST / "Jeff-macos-arm64.dmg"
ICON_SOURCE = ROOT / "browser_extension" / "icons" / "icon-512.png"
MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}


def run(command: list[str], **kwargs) -> None:
    subprocess.run(command, check=True, **kwargs)


def _resolve_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _is_macho_file(path: Path) -> bool:
    with path.open("rb") as file:
        return file.read(4) in MACHO_MAGICS


def _sign_app(app: Path) -> None:
    main_executable = app / "Contents" / "MacOS" / "Jeff"
    mach_o_files = [
        path
        for path in app.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path != main_executable
        and _is_macho_file(path)
    ]
    for path in mach_o_files:
        run(["codesign", "--force", "--sign", "-", "--timestamp=none", str(path)])
    run(["codesign", "--force", "--sign", "-", "--timestamp=none", str(app)])
    for path in mach_o_files:
        run(["codesign", "--verify", "--strict", str(path)])
    run(["codesign", "--verify", "--strict", str(app)])


def _create_native_app(helper_source: Path, output: Path, staging: Path) -> None:
    app = staging / "Jeff.app"
    contents = app / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir()

    service_bundle = resources / "JeffService"
    shutil.copytree(helper_source, service_bundle, symlinks=True)
    selenium_common = service_bundle / "_internal" / "selenium" / "webdriver" / "common"
    platform_helpers = [*selenium_common.glob("linux-*"), selenium_common / "windows"]
    for platform_helper in platform_helpers:
        if platform_helper.is_dir():
            shutil.rmtree(platform_helper)
    for path in service_bundle.rglob("*"):
        if path.is_file() and not path.is_symlink() and not _is_macho_file(path):
            path.chmod(path.stat().st_mode & ~0o111)
    for metadata in service_bundle.rglob("*.dist-info"):
        if metadata.is_dir():
            shutil.rmtree(metadata)
    executable = macos / "Jeff"
    run(
        [
            "swiftc",
            "-parse-as-library",
            "-O",
            "-target",
            "arm64-apple-macosx13.0",
            "-framework",
            "SwiftUI",
            "-framework",
            "AppKit",
            "-framework",
            "UniformTypeIdentifiers",
            "-o",
            str(executable),
            str(ROOT / "packaging" / "macos" / "JeffApp.swift"),
        ]
    )

    iconset = resources / "Jeff.iconset"
    iconset.mkdir()
    for size, names in (
        (16, ("icon_16x16.png",)),
        (32, ("icon_16x16@2x.png", "icon_32x32.png")),
        (64, ("icon_32x32@2x.png",)),
        (128, ("icon_128x128.png",)),
        (256, ("icon_128x128@2x.png", "icon_256x256.png")),
        (512, ("icon_256x256@2x.png", "icon_512x512.png")),
        (1024, ("icon_512x512@2x.png",)),
    ):
        for name in names:
            run(
                [
                    "sips",
                    "-s",
                    "format",
                    "png",
                    "-z",
                    str(size),
                    str(size),
                    str(ICON_SOURCE),
                    "--out",
                    str(iconset / name),
                ],
                stdout=subprocess.DEVNULL,
            )
    run(["iconutil", "-c", "icns", str(iconset), "-o", str(resources / "Jeff.icns")])
    shutil.rmtree(iconset)

    info = {
        "CFBundleDisplayName": "Jeff",
        "CFBundleExecutable": "Jeff",
        "CFBundleIconFile": "Jeff.icns",
        "CFBundleIdentifier": "com.jeff.localassistant",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "Jeff",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1",
        "LSApplicationCategoryType": "public.app-category.productivity",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
    }
    with (contents / "Info.plist").open("wb") as file:
        plistlib.dump(info, file)
    (contents / "PkgInfo").write_text("APPL????", encoding="ascii")

    run(["xattr", "-cr", str(app)])
    _sign_app(app)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise SystemExit(f"Refusing to replace symbolic-link app bundle: {output}")
    if output.is_dir():
        shutil.rmtree(output)
    elif output.exists():
        output.unlink()
    shutil.copytree(app, output, symlinks=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Jeff's native macOS app and DMG.")
    parser.add_argument(
        "--package-only",
        action="store_true",
        help="Create the DMG from an existing native Jeff.app without rebuilding it.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_DMG_PATH),
        help="Destination for the packaged DMG; defaults to dist/Jeff-macos-arm64.dmg.",
    )
    parser.add_argument(
        "--app-bundle",
        type=str,
        default=str(DIST / "Jeff.app"),
        help="Path to the app bundle to package; defaults to dist/Jeff.app.",
    )
    arguments = parser.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("Build Jeff's DMG on macOS.")
    if platform.machine() != "arm64":
        raise SystemExit("This build script currently targets Apple Silicon (arm64).")
    if not ICON_SOURCE.is_file():
        raise SystemExit(f"Missing app icon at {ICON_SOURCE}.")
    BUILD.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    dmg_path = _resolve_path(arguments.output)
    dmg_path.parent.mkdir(parents=True, exist_ok=True)
    app_bundle = _resolve_path(arguments.app_bundle)
    if not arguments.package_only:
        environment = os.environ.copy()
        environment["PYINSTALLER_CONFIG_DIR"] = str(BUILD / "pyinstaller-config")
        python_executables = []
        virtual_env = os.environ.get("VIRTUAL_ENV")
        if virtual_env:
            python_executables.append(Path(virtual_env) / "bin" / "python")
        python_executables.extend(
            [ROOT / ".venv312" / "bin" / "python", Path(sys.executable)]
        )
        python_executable = next(
            (candidate for candidate in python_executables if candidate.is_file()),
            Path(sys.executable),
        )
        with tempfile.TemporaryDirectory(prefix="jeff-build-") as temporary:
            build_root = Path(temporary)
            run(
                [
                    str(python_executable),
                    "-m",
                    "PyInstaller",
                    "--clean",
                    "--noconfirm",
                    "--distpath",
                    str(build_root / "dist"),
                    "--workpath",
                    str(build_root / "work"),
                    str(ROOT / "packaging" / "macos" / "Jeff.spec"),
                ],
                env=environment,
            )
            helper = build_root / "dist" / "JeffService"
            if not helper.is_dir():
                raise SystemExit(f"PyInstaller did not create {helper}.")
            with tempfile.TemporaryDirectory(prefix="jeff-native-app-") as app_temp:
                _create_native_app(helper, app_bundle, Path(app_temp))

    helper_executable = (
        app_bundle / "Contents" / "Resources" / "JeffService" / "JeffService"
    )
    native_executable = app_bundle / "Contents" / "MacOS" / "Jeff"
    if not native_executable.is_file() or not helper_executable.is_file():
        raise SystemExit(
            f"{app_bundle} is not a native Jeff app bundle with its local service."
        )
    with tempfile.TemporaryDirectory(prefix="jeff-dmg-") as temporary:
        staging = Path(temporary)
        staged_app = staging / "Jeff.app"
        run(["ditto", "--noextattr", "--noqtn", str(app_bundle), str(staged_app)])
        run(["xattr", "-cr", str(staged_app)])
        _sign_app(staged_app)
        (staging / "INSTALL.txt").write_text(
            "Jeff for macOS (Apple Silicon)\n\n"
            "Drag Jeff.app to Applications, eject the mounted disk image, and open "
            "Jeff from Applications. It uses its own native SwiftUI window.\n\n"
            "This development build is ad-hoc signed and is not notarized with an "
            "Apple Developer ID. If macOS says it cannot verify the developer or "
            "cannot check the app for malicious software, and you trust this DMG "
            "came from the Jeff repository, Control-click Jeff.app in Applications, "
            "choose Open, and confirm the per-app prompt. If needed, try opening it "
            "once, then use Open Anyway in System Settings > Privacy & Security. "
            "Do not approve an alert that says the app contains malware or will "
            "damage your computer.\n\n"
            "Ollama and Jeff's chat and embedding models are needed for chat; "
            "Ollama does not need to be running just to open Jeff. Firefox "
            "Developer Edition and OpenVPN "
            "Connect are needed only for the optional Browser and VPN features. Jeff "
            "does not bundle Ollama, model weights, accounts, credentials, browser "
            "profiles, or personal data.\n\n"
            "Jeff writes service launch logs to "
            "~/Library/Logs/Jeff/native-service-launch.log.\n",
            encoding="utf-8",
        )
        run([
            "hdiutil",
            "create",
            "-ov",
            "-volname",
            "Jeff",
            "-srcfolder",
            str(staging),
            "-format",
            "UDZO",
            "-imagekey",
            "zlib-level=9",
            str(dmg_path),
        ])
    run(["hdiutil", "verify", str(dmg_path)])
    print(f"Created {dmg_path}")


if __name__ == "__main__":
    main()
