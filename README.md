<div align="center">

# 🔍 LectureLens

### Any Video → Searchable PDF Slides

**Extract, deduplicate, and export presentation slides from any video — directly to PDF.**  
YouTube, NPTEL, Coursera, local files. No PowerPoint. No manual work.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()
[![OCR](https://img.shields.io/badge/OCR-PaddleOCR%20%7C%20Tesseract-orange)]()
[![Author](https://img.shields.io/badge/Author-Shivam%20Aggarwal-cba6f7)](https://github.com/aggarwal-shiv)

</div>

---

## ✨ What is LectureLens?

LectureLens watches a video frame-by-frame, detects when the slide changes, removes duplicate and transitional frames, optionally OCR-scans each slide for text searchability, and saves everything as a single PDF — all from a polished desktop GUI with dark and light themes.

---

## 🖥️ GUI Highlights

| Feature | Details |
|---|---|
| **Dark & Light mode** | Toggle with one click — full theme switch, no restart |
| **Multi-video queue** | Treeview with per-video status: Pending / Processing / Done / Failed |
| **YouTube + local** | Paste any URL or Browse for MP4, MKV, AVI, MOV, WebM, FLV |
| **Direct PDF** | Slides saved straight to PDF — no `.pptx` ever created |
| **Presets** | ⚡ Fast / ⚖ Balanced / 🎯 Quality — fill all settings with one click |
| **Live log** | Colour-coded, scrollable, clearable |
| **Stats bar** | Tracks slides found, videos processed, elapsed time |
| **Stop button** | Gracefully interrupts any in-progress extraction |
| **Open output** | One-click to open the PDF folder in your file manager |
| **Tooltips** | Hover any setting for an explanation |
| **Keyboard shortcuts** | Enter to add URL, Delete to remove selected queue item |
| **About dialog** | App info, author, GitHub link |

---

## 🚀 Pipeline

```
Input: YouTube URL  ──── or ────  Local video path (MP4 / MKV / AVI …)
           │
     yt-dlp download
           │
    Frame sampling  ←  configurable interval (default: 1 frame/s)
           │
   ┌───────▼────────────────┐
   │   Slide Change Detector │
   │  SSIM + pHash + HSV     │
   │  Histogram majority vote│
   │  + temporal smoothing   │  ← no animation false-positives
   └───────┬────────────────┘
           │
    OCR (PaddleOCR / Tesseract)  ← text-searchable PDF
           │
   Deduplication (pHash + SSIM + text similarity)
           │
   ┌───────▼──────┐
   │  PDF  export │  ← direct, Pillow image PDF, no PowerPoint
   └──────────────┘
```

---

## 📦 Installation

### Clone

```bash
git clone https://github.com/aggarwal-shiv/LectureLens.git
cd LectureLens
```

### Install Python dependencies

**Option A — auto installer (recommended first time):**
```bash
python LectureLens.py --install
```

**Option B — manual:**
```bash
pip install -r requirements.txt
```

### System tools (optional but recommended)

| Tool | Why | Install |
|---|---|---|
| **FFprobe** | Accurate video duration display | ships with [FFmpeg](https://ffmpeg.org/download.html) |
| **Tesseract** | Fallback OCR engine | [tesseract-ocr.github.io](https://tesseract-ocr.github.io/tessdoc/Installation.html) |
| **tkinter** | GUI (usually bundled) | Linux: `sudo apt install python3-tk` |

---

## ▶️ Running LectureLens

### Windows
```bat
run.bat
```

### Linux / macOS
```bash
chmod +x run.sh LectureLens.py
./run.sh
# or directly:
./LectureLens.py
```

---

## 📦 Build a Standalone Executable (optional)

```bash
pip install pyinstaller
pyinstaller LectureLens.spec
# Output → dist/LectureLens/
```

---

## ⚙️ Settings Reference

| Setting | Default | Effect |
|---|---|---|
| **Frame Interval** | `1.0 s` | Sample one frame every N seconds. Lower = more slides, slower |
| **Similarity** | `0.92` | SSIM cutoff. Lower → more slides captured |
| **Hash Distance** | `8` | pHash Hamming distance for duplicate detection |
| **Confirm Frames** | `3` | Stable frames required before accepting a new slide |
| **OCR Engine** | `auto` | `paddleocr` / `tesseract` / `auto` / `none` |
| **OCR Confidence** | `0.60` | Minimum score to keep an OCR text line |
| **JPEG Quality** | `95` | Slide image quality inside PDF (1–100) |

### Presets

| Preset | Best For |
|---|---|
| ⚡ **Fast** | Quick preview, no OCR, coarse sampling |
| ⚖ **Balanced** | Recommended for most lecture videos |
| 🎯 **Quality** | Dense slides, whiteboards, maximum fidelity + OCR |

---

## 📂 Output Structure

```
LectureLens/                     ← chosen output directory
├── Video_Title_1/
│   └── slides/
│       ├── slide_0001_4.50s.jpg
│       └── …
├── Video_Title_1.pdf            ← final deliverable ✅
└── Video_Title_2.pdf
```

---

## 🧠 How Slide Detection Works

Each sampled frame goes through a **three-signal majority vote**:

1. **SSIM** — structural pixel similarity vs last accepted slide
2. **pHash** — perceptual hash (robust to minor compression artifacts)
3. **HSV Histogram** — catches colour-palette changes SSIM may miss

A new slide is only saved after `confirm_frames` consecutive stable frames, eliminating false positives from animated builds. A+B+C only saves the final full state.

---

## 📋 Requirements

```
Python 3.9+    opencv-python    scikit-image    imagehash
Pillow         yt-dlp           paddlepaddle    paddleocr
pytesseract    numpy            tqdm            tkinter
```

---

## 👤 Author

**Shivam Aggarwal**  
GitHub: [github.com/aggarwal-shiv](https://github.com/aggarwal-shiv)

---

## 📄 License

[MIT](LICENSE) — free to use, modify, and distribute.

---

## 🙏 Acknowledgements

[yt-dlp](https://github.com/yt-dlp/yt-dlp) · [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) · [OpenCV](https://opencv.org/) · [scikit-image](https://scikit-image.org/) · [imagehash](https://github.com/JohannesBuchner/imagehash) · [Pillow](https://python-pillow.org/)

---

<div align="center">
Made with ❤️ by <a href="https://github.com/aggarwal-shiv">Shivam Aggarwal</a><br>
<i>For everyone who ever wished they could get the slides from a lecture video.</i>
</div>
