# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for 24GB and a Dream.

Anaconda/Miniconda keeps the native dependencies of several stdlib extension
modules in ``<sys.prefix>\\Library\\bin`` instead of ``DLLs``. PyInstaller does
not search that directory, so the frozen app is built without them and dies
during interpreter bootstrap with errors such as::

    ImportError: DLL load failed while importing pyexpat

That happens long before app.py installs any logging, which is why the failure
shows up only as a bootloader dialog. Collect those DLLs explicitly.

Build with:  python -m PyInstaller --noconfirm --clean "24GB and a Dream.spec"
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

# Native dependencies of stdlib extension modules that conda relocates.
# Globs, because conda encodes ABI versions in the names (libmpdec-4.dll).
CONDA_DLL_PATTERNS = (
    "ffi*.dll",        # _ctypes
    "libexpat*.dll",   # pyexpat  -> xml.parsers.expat -> plistlib -> pkg_resources
    "liblzma*.dll",    # _lzma
    "libbz2*.dll",     # _bz2
    "libmpdec*.dll",   # _decimal
    "libcrypto*.dll",  # _hashlib / _ssl
    "libssl*.dll",     # _ssl
    "sqlite3*.dll",    # _sqlite3
    "zlib*.dll",       # zlib
)


def conda_binaries() -> list[tuple[str, str]]:
    """DLLs to bundle from a conda prefix; empty on a standard CPython install."""
    library_bin = Path(sys.prefix) / "Library" / "bin"
    if not library_bin.is_dir():
        return []
    collected: dict[str, tuple[str, str]] = {}
    for pattern in CONDA_DLL_PATTERNS:
        for dll in library_bin.glob(pattern):
            collected[dll.name.lower()] = (str(dll), ".")
    for name, (source, _) in sorted(collected.items()):
        print(f"[spec] bundling conda DLL: {source}")
    return list(collected.values())


# Package metadata, so the startup diagnostics in utils.crash can still report
# real versions from a frozen build instead of "not installed".
DIAGNOSTIC_PACKAGES = ("PySide6", "pydantic", "requests", "PyYAML", "Pillow")


def metadata_datas() -> list[tuple[str, str]]:
    collected: list[tuple[str, str]] = []
    for package in DIAGNOSTIC_PACKAGES:
        try:
            collected.extend(copy_metadata(package))
        except Exception as exc:  # package genuinely absent: keep building
            print(f"[spec] no metadata for {package}: {exc}")
    return collected


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=conda_binaries(),
    datas=metadata_datas(),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # torch is only reached through utils.gpu's optional import and would add
    # gigabytes; ComfyUI runs it in its own virtual environment.
    excludes=['torch'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='24GB and a Dream',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='24GB and a Dream',
)
