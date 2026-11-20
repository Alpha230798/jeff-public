# PyInstaller definition for Jeff's local native-app service.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(SPECPATH).resolve().parents[1]
datas = [
    (str(ROOT / "dictionary.json"), "."),
    (str(ROOT / "jeff_system_prompt.md"), "."),
]
binaries = []
hiddenimports = []
for module in ("pypdf", "docx", "selenium", "requests", "certifi"):
    module_datas, module_binaries, module_hiddenimports = collect_all(
        module,
        include_py_files=False,
    )
    datas += module_datas
    binaries += module_binaries
    hiddenimports += module_hiddenimports

analysis = Analysis(
    [str(ROOT / "jarvis" / "native_service.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest", "tests", "streamlit", "altair", "pyarrow"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="JeffService",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="JeffService",
)
