# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec — cross-platform freeze for AI Humanizer.
#
# Builds a self-contained onedir bundle that includes:
#   - the FastAPI backend
#   - the pre-built Next.js static frontend (under backend/static/)
#   - pywebview + WebKit/WebView2 bridge
#   - CPU-only PyTorch + transformers + sentence-transformers
#
# Models are NOT bundled — downloaded on first launch to the user's HF cache.
# That keeps the installer ~1.5-2 GB instead of 4+ GB.
#
# Usage:
#   pyinstaller windows/ai-humanizer.spec         # current OS
#   The Windows build orchestrator (windows/build.ps1) runs this then Inno Setup.
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent
BACKEND = ROOT / "backend"
STATIC = BACKEND / "static"

# Make the `app` package importable so collect_all("app") can find it.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# ---- Hidden imports PyInstaller can't discover statically ----
# transformers / sentence-transformers / torch all use dynamic imports.
hidden_imports: list[str] = []
datas: list[tuple[str, str]] = []
binaries: list[tuple[str, str]] = []

for pkg in ("transformers", "torch", "sentence_transformers", "sqlmodel", "pymupdf4llm", "pymupdf"):
    # PyInstaller.utils.hooks.collect_all returns (datas, binaries, hiddenimports)
    d, b, h = collect_all(pkg)
    datas.extend(d)
    binaries.extend(b)
    hidden_imports.extend(h)

# The `app` package (our backend) is imported dynamically at runtime.
# Explicitly include all submodules so PyInstaller bundles them.
app_d, app_b, app_h = collect_all("app")
datas.extend(app_d)
binaries.extend(app_b)
hidden_imports.extend(app_h)

# HuggingFace checks package metadata at runtime via importlib.metadata
metadata_packages = (
    "torch",
    "transformers",
    "sentence_transformers",
    "tqdm",
    "regex",
    "requests",
    "packaging",
    "filelock",
    "numpy",
    "tokenizers",
    "huggingface_hub",
    "pyyaml",
)
for pkg in metadata_packages:
    try:
        datas.extend(copy_metadata(pkg))
    except Exception:
        pass

# Bundle the pre-built frontend — needed so desktop.py's FastAPI
# serves the UI at /.
if STATIC.exists():
    datas.append((str(STATIC), "static"))


a = Analysis(
    [str(BACKEND / "desktop.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Trim weight we don't need.
    excludes=[
        "torchvision",
        "torchaudio",
        "tests",
        "tkinter",
        "matplotlib",
        "PIL.ImageQt",
        "notebook",
        "ipython",
        "jupyter",
        "pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI Humanizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX: DO NOT enable — guaranteed antivirus false positives with ML
    # executables.  See PyInstaller docs on UPX + SmartScreen reputation.
    upx=False,
    console=False,  # no console window on launch (Windows)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "windows" / "app.ico") if (ROOT / "windows" / "app.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AI Humanizer",
)

# On macOS, also emit a .app bundle so the same spec produces a native macOS app.
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="AI Humanizer.app",
        icon=str(ROOT / "dist" / "AI Humanizer.app" / "Contents" / "Resources" / "AppIcon.icns") if (ROOT / "dist" / "AI Humanizer.app" / "Contents" / "Resources" / "AppIcon.icns").exists() else None,
        bundle_identifier="com.aihumanizer.app",
        info_plist={
            "CFBundleName": "AI Humanizer",
            "CFBundleDisplayName": "AI Humanizer",
            "CFBundleVersion": "2.0.0",
            "CFBundleShortVersionString": "2.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
