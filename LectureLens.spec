# LectureLens.spec
# Build a standalone executable with PyInstaller
#
# Usage:
#   pip install pyinstaller
#   pyinstaller LectureLens.spec
#
# Output: dist/LectureLens/LectureLens  (Linux/macOS)
#         dist/LectureLens/LectureLens.exe  (Windows)

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['LectureLens.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'paddleocr', 'paddlepaddle', 'pytesseract',
        'skimage', 'skimage.metrics', 'imagehash',
        'cv2', 'PIL', 'PIL.Image', 'PIL.ImageTk',
        'numpy', 'tqdm', 'yt_dlp',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'pandas', 'jupyter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LectureLens',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no console window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LectureLens',
)
