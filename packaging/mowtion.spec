# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec. Run from the repo root: pyinstaller packaging/mowtion.spec"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"

datas = [
    (str(SRC / "mowtion" / "ui"), "mowtion/ui"),
    (str(SRC / "mowtion" / "assets"), "mowtion/assets"),
]
binaries = []
hiddenimports = [
    "mowtion",
    "mowtion.cli",
    "mowtion.server",
    "mowtion.pipeline",
    "PIL",
    "numpy",
    "scipy",
    "scipy.signal",
    "soundfile",
    "av",
]

for package in (
    "faster_whisper",
    "kokoro_onnx",
    "espeakng_loader",
    "onnxruntime",
    "tokenizers",
    "ctranslate2",
    "phonemizer",
):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    [str(SRC / "mowtion" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mowtion",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="mowtion",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="mowtion.app",
        bundle_identifier="com.mowtion.app",
        info_plist={
            "CFBundleName": "mowtion",
            "CFBundleDisplayName": "mowtion",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
        },
    )
