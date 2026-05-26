#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║              LectureLens  🔍                             ║
║        Any Video  →  Searchable PDF Slides               ║
║                                                          ║
║  Author  : Shivam Aggarwal                               ║
║  GitHub  : https://github.com/aggarwal-shiv              ║
║  License : MIT                                           ║
╚══════════════════════════════════════════════════════════╝

Extracts unique presentation slides from YouTube URLs or local
video files and saves them directly as a searchable PDF —
no PowerPoint step in between. Supports multiple videos per run.

Usage:
    python LectureLens.py            # launch GUI
    python LectureLens.py --install  # install all dependencies first
"""

# ── Standard library ─────────────────────────────────────────────
import os, re, cv2, json, time, shutil, difflib, threading
import subprocess, sys, webbrowser
from pathlib import Path
from typing import Optional
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# ── Optional third-party ─────────────────────────────────────────
import numpy as np

try:
    from PIL import Image as PILImage, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    from skimage.metrics import structural_similarity as ssim
    SSIM_OK = True
except ImportError:
    SSIM_OK = False

try:
    import imagehash
    PHASH_OK = True
except ImportError:
    PHASH_OK = False

try:
    from paddleocr import PaddleOCR
    PADDLE_OK = True
except ImportError:
    PADDLE_OK = False

try:
    import pytesseract
    pytesseract.get_tesseract_version()
    TESS_OK = True
except Exception:
    TESS_OK = False

# ─────────────────────────────────────────────────────────────────
# Theme definitions
# ─────────────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg":          "#1e1e2e",
        "panel":       "#181825",
        "surface":     "#24273a",
        "accent":      "#89b4fa",
        "accent2":     "#cba6f7",
        "accent_dark": "#1e1e2e",
        "success":     "#a6e3a1",
        "warning":     "#fab387",
        "error":       "#f38ba8",
        "text":        "#cdd6f4",
        "subtext":     "#6c7086",
        "border":      "#313244",
        "entry":       "#2a2a3e",
        "btn":         "#313244",
        "btn_active":  "#45475a",
        "tree_odd":    "#1e1e2e",
        "tree_even":   "#24273a",
        "scrollbar":   "#45475a",
    },
    "light": {
        "bg":          "#eff1f5",
        "panel":       "#e6e9ef",
        "surface":     "#dce0e8",
        "accent":      "#1e66f5",
        "accent2":     "#8839ef",
        "accent_dark": "#ffffff",
        "success":     "#40a02b",
        "warning":     "#df8e1d",
        "error":       "#d20f39",
        "text":        "#4c4f69",
        "subtext":     "#8c8fa1",
        "border":      "#ccd0da",
        "entry":       "#dce0e8",
        "btn":         "#ccd0da",
        "btn_active":  "#bcc0cc",
        "tree_odd":    "#eff1f5",
        "tree_even":   "#e6e9ef",
        "scrollbar":   "#bcc0cc",
    },
}

PRESETS = {
    "⚡ Fast": {
        "frame_interval": 2.0, "similarity_thresh": 0.85,
        "hash_threshold": 12,  "confirm_frames": 2,
        "ocr_engine": "none",  "ocr_confidence": 0.6,
        "image_quality": 82,
    },
    "⚖ Balanced": {
        "frame_interval": 1.0, "similarity_thresh": 0.92,
        "hash_threshold": 8,   "confirm_frames": 3,
        "ocr_engine": "auto",  "ocr_confidence": 0.6,
        "image_quality": 95,
    },
    "🎯 Quality": {
        "frame_interval": 0.5, "similarity_thresh": 0.96,
        "hash_threshold": 5,   "confirm_frames": 4,
        "ocr_engine": "auto",  "ocr_confidence": 0.5,
        "image_quality": 100,
    },
}

VERSION = "2.0.0"

# ─────────────────────────────────────────────────────────────────
# Core utilities
# ─────────────────────────────────────────────────────────────────

def sanitize(name: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:200] or "untitled"

def ensure(*dirs):
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)

def format_time(s: float) -> str:
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def probe_duration(path: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(path)],
            capture_output=True, text=True, timeout=15
        )
        return float(json.loads(r.stdout).get("format", {}).get("duration", 0))
    except Exception:
        return 0.0

def compute_phash(img_bgr: np.ndarray) -> Optional[str]:
    if not PHASH_OK:
        return None
    try:
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return str(imagehash.phash(PILImage.fromarray(rgb)))
    except Exception:
        return None

def phash_distance(h1, h2) -> int:
    if not PHASH_OK or h1 is None or h2 is None:
        return 999
    try:
        return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)
    except Exception:
        return 999

def compute_histogram(frame_bgr: np.ndarray) -> np.ndarray:
    hsv  = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist

# ─────────────────────────────────────────────────────────────────
# OCR
# ─────────────────────────────────────────────────────────────────

_paddle_instance = None

def get_paddle():
    global _paddle_instance
    if _paddle_instance is None and PADDLE_OK:
        _paddle_instance = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _paddle_instance

def run_ocr(image_path: Path, engine: str, min_conf: float) -> str:
    effective = engine
    if engine == "auto":
        effective = "paddleocr" if PADDLE_OK else ("tesseract" if TESS_OK else "none")
    if effective == "paddleocr" and PADDLE_OK:
        try:
            result = get_paddle().ocr(str(image_path), cls=True)
            lines  = []
            for block in (result or []):
                for item in (block or []):
                    text, conf = item[1]
                    if conf >= min_conf:
                        lines.append(text)
            return " ".join(lines)
        except Exception:
            pass
    if effective in ("tesseract", "paddleocr") and TESS_OK:
        try:
            return pytesseract.image_to_string(PILImage.open(image_path))
        except Exception:
            pass
    return ""

# ─────────────────────────────────────────────────────────────────
# Slide detector
# ─────────────────────────────────────────────────────────────────

class SlideDetector:
    def __init__(self, slides_dir: Path, cfg: dict):
        self.slides_dir = slides_dir
        self.cfg        = cfg
        ensure(slides_dir)
        self._accepted_gray  = None
        self._accepted_hist  = None
        self._accepted_phash = None
        self._prev_gray      = None
        self._stable_frames  = 0
        self._slide_count    = 0
        self.slides          = []

    def process(self, frame_idx: int, ts: float, frame: np.ndarray):
        small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (320, 240))
        if self._accepted_gray is None:
            self._prev_gray = small
            return self._accept(frame_idx, ts, frame, small)
        moving = self._is_different(self._prev_gray, None, None,
                                    small, None, None, check_all=False)
        self._prev_gray = small
        self._stable_frames = 0 if moving else self._stable_frames + 1
        if self._stable_frames == self.cfg["confirm_frames"]:
            h = compute_histogram(frame)
            p = compute_phash(frame)
            if self._is_different(self._accepted_gray, self._accepted_hist,
                                   self._accepted_phash, small, h, p, check_all=True):
                return self._accept(frame_idx, ts, frame, small)
        return None

    def _is_different(self, g1, h1, p1, g2, h2, p2, check_all=True) -> bool:
        thr   = self.cfg["similarity_thresh"]
        votes = total = 0
        if g1 is not None and SSIM_OK:
            total += 1
            if ssim(g1, g2, data_range=255) < thr:
                votes += 1
        if check_all:
            if h1 is not None and h2 is not None:
                total += 1
                if cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL) < thr:
                    votes += 1
            if p1 and p2:
                total += 1
                if phash_distance(p1, p2) > self.cfg["hash_threshold"]:
                    votes += 1
        return total == 0 or votes >= max(1, (total + 1) // 2)

    def _accept(self, frame_idx, ts, frame, small):
        self._slide_count += 1
        img = self.slides_dir / f"slide_{self._slide_count:04d}_{ts:.2f}s.jpg"
        cv2.imwrite(str(img), frame,
                    [cv2.IMWRITE_JPEG_QUALITY, self.cfg["image_quality"]])
        ph   = compute_phash(frame)
        hist = compute_histogram(frame)
        slide = {"slide_number": self._slide_count, "frame_index": frame_idx,
                  "timestamp": ts, "image_path": img, "ocr_text": "",
                  "phash": ph}
        self.slides.append(slide)
        self._accepted_gray  = small
        self._accepted_hist  = hist
        self._accepted_phash = ph
        return slide

# ─────────────────────────────────────────────────────────────────
# Deduplication
# ─────────────────────────────────────────────────────────────────

def _ssim_files(a: Path, b: Path, thr: float) -> bool:
    if not SSIM_OK:
        return False
    try:
        ga = cv2.imread(str(a), cv2.IMREAD_GRAYSCALE)
        gb = cv2.imread(str(b), cv2.IMREAD_GRAYSCALE)
        if ga is None or gb is None:
            return False
        h, w = min(ga.shape[0], gb.shape[0]), min(ga.shape[1], gb.shape[1])
        return float(ssim(cv2.resize(ga, (w, h)), cv2.resize(gb, (w, h)),
                          data_range=255)) >= thr
    except Exception:
        return False

def deduplicate(slides: list, cfg: dict) -> list:
    unique = []
    for slide in slides:
        dup = -1
        start = max(0, len(unique) - 10)
        for i in range(len(unique) - 1, start - 1, -1):
            ref  = unique[i]
            dist = phash_distance(slide["phash"], ref["phash"])
            if dist <= cfg["hash_threshold"]:
                dup = i; break
            if dist > cfg["hash_threshold"] * 3:
                continue
            if _ssim_files(slide["image_path"], ref["image_path"],
                            cfg["similarity_thresh"]):
                dup = i; break
            if slide["ocr_text"] and ref["ocr_text"]:
                if (difflib.SequenceMatcher(None, slide["ocr_text"],
                                            ref["ocr_text"]).ratio()
                        >= cfg["text_similarity_thresh"]):
                    dup = i; break
        if dup != -1:
            unique[dup] = slide
        else:
            unique.append(slide)
    for i, s in enumerate(unique, 1):
        s["slide_number"] = i
    return unique

# ─────────────────────────────────────────────────────────────────
# PDF export  (direct — Pillow image PDF)
# ─────────────────────────────────────────────────────────────────

def export_pdf_direct(slides: list, pdf_path: Path, log) -> bool:
    images = []
    for s in slides:
        if s["image_path"].exists():
            try:
                images.append(PILImage.open(s["image_path"]).convert("RGB"))
            except Exception as e:
                log(f"  ⚠ Skipping {s['image_path'].name}: {e}")
    if not images:
        return False
    try:
        images[0].save(str(pdf_path), save_all=True,
                        append_images=images[1:], resolution=150)
        return True
    except Exception as e:
        log(f"  ❌ PDF error: {e}")
        return False

# ─────────────────────────────────────────────────────────────────
# Download / validate
# ─────────────────────────────────────────────────────────────────

def download_youtube(url: str, out_dir: Path, log) -> tuple:
    ensure(out_dir)
    base = [sys.executable, "-m", "yt_dlp"]
    try:
        r     = subprocess.run(base + ["--dump-json", "--no-playlist", url],
                               capture_output=True, text=True, timeout=30)
        meta  = json.loads(r.stdout)
        title = meta.get("title", "video")
        dur   = float(meta.get("duration") or 0)
    except Exception:
        title, dur = "video", 0.0
    safe = sanitize(title)
    log(f"📥 Downloading: {title}")
    cmd = base + ["--no-playlist",
                  "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                  "--merge-output-format", "mp4",
                  "--output", str(out_dir / f"{safe}.%(ext)s"),
                  "--newline", "--progress", url]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    last = 0
    for line in proc.stdout:
        m = re.search(r"(\d+\.?\d*)%", line)
        if m:
            pct = float(m.group(1))
            if pct - last >= 10:
                log(f"   Download: {pct:.0f}%")
                last = pct
    proc.wait()
    valid_ext = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}
    cands = sorted(out_dir.glob(f"{safe}.*"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    valid = [p for p in cands if p.suffix.lower() in valid_ext]
    if not valid:
        raise FileNotFoundError("Download finished but video file not found.")
    path = valid[0]
    if not dur:
        dur = probe_duration(path)
    log(f"✅ Downloaded → {path.name}  ({format_time(dur)})")
    return path, title, dur

def validate_local(path_str: str, log) -> tuple:
    path      = Path(path_str)
    valid_ext = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if path.suffix.lower() not in valid_ext:
        raise ValueError(f"Unsupported format: {path.suffix}")
    dur = probe_duration(path)
    log(f"✅ File validated: {path.name}  ({format_time(dur)})")
    return path, path.stem, dur

# ─────────────────────────────────────────────────────────────────
# Full pipeline (one video)
# ─────────────────────────────────────────────────────────────────

def process_video(source: str, output_dir: Path, cfg: dict,
                  log, progress_cb, stop_event: threading.Event) -> Optional[Path]:
    is_url = source.startswith(("http://", "https://"))
    tmp    = output_dir / "temp"
    ensure(tmp)
    try:
        if is_url:
            vpath, title, _ = download_youtube(source, tmp, log)
        else:
            vpath, title, _ = validate_local(source, log)
    except Exception as e:
        log(f"❌ Acquisition failed: {e}")
        return None

    safe       = sanitize(title)
    slides_dir = output_dir / safe / "slides"
    ensure(slides_dir)

    cap = cv2.VideoCapture(str(vpath))
    if not cap.isOpened():
        log(f"❌ Cannot open video: {vpath}")
        return None

    fps    = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step   = max(1, int(fps * cfg["frame_interval"]))
    steps  = max(1, total // step)
    log(f"📹 {total} frames @ {fps:.1f} fps | {format_time(total/fps)}")
    log(f"   Sampling every {cfg['frame_interval']}s")

    detector = SlideDetector(slides_dir, cfg)
    fi = si = 0
    while True:
        if stop_event.is_set():
            cap.release(); log("⛔ Stopped."); return None
        ret, frame = cap.read()
        if not ret: break
        if fi % step == 0:
            ts = fi / fps
            s  = detector.process(fi, ts, frame)
            if s:
                log(f"  🖼  Slide {s['slide_number']} @ {format_time(ts)}")
            si += 1
            progress_cb(si / steps * 60)
        fi += 1
    cap.release()
    log(f"✅ Detection: {len(detector.slides)} candidates")

    if cfg["ocr_engine"] != "none":
        log(f"🔤 OCR ({cfg['ocr_engine']})…")
        for i, sl in enumerate(detector.slides):
            if stop_event.is_set(): return None
            sl["ocr_text"] = run_ocr(sl["image_path"], cfg["ocr_engine"],
                                      cfg["ocr_confidence"])
            progress_cb(60 + (i + 1) / max(len(detector.slides), 1) * 20)

    log("♻  Deduplicating…")
    unique  = deduplicate(detector.slides, cfg)
    removed = len(detector.slides) - len(unique)
    log(f"✅ {len(unique)} unique slides ({removed} duplicates removed)")
    progress_cb(85)

    pdf_path = output_dir / f"{safe}.pdf"
    log(f"📄 Saving PDF → {pdf_path.name}")
    if export_pdf_direct(unique, pdf_path, log):
        size = pdf_path.stat().st_size / 1e6
        log(f"✅ PDF saved: {pdf_path}  ({size:.1f} MB, {len(unique)} slides)")
        progress_cb(100)
        return pdf_path
    log("❌ PDF export failed.")
    return None

# ─────────────────────────────────────────────────────────────────
# Tooltip helper
# ─────────────────────────────────────────────────────────────────

class Tooltip:
    def __init__(self, widget, text: str):
        self._w = widget
        self._t = text
        self._tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _=None):
        x, y, *_ = self._w.bbox("insert") if hasattr(self._w, "bbox") else (0, 0, 0, 0)
        x += self._w.winfo_rootx() + 20
        y += self._w.winfo_rooty() + 20
        self._tip = tk.Toplevel(self._w)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(self._tip, text=self._t, justify="left",
                       bg="#313244", fg="#cdd6f4",
                       font=("Segoe UI", 8), relief="flat",
                       padx=6, pady=3)
        lbl.pack()

    def _hide(self, _=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None

# ─────────────────────────────────────────────────────────────────
# Main GUI Application
# ─────────────────────────────────────────────────────────────────

class LectureLens(tk.Tk):
    """
    LectureLens — Video → Searchable PDF
    Author : Shivam Aggarwal  |  github.com/aggarwal-shiv
    """

    def __init__(self):
        super().__init__()
        self._current_theme = "dark"
        self._themed_tk: list = []   # (widget, {config_key: theme_key})
        self._stop_event      = threading.Event()
        self._running         = False
        self._start_time      = 0.0
        self._queue_items     = {}   # iid -> source string

        self.title("LectureLens — Video → PDF")
        self.geometry("1020x780")
        self.minsize(860, 640)
        self.resizable(True, True)

        self._build_styles()
        self._build_ui()
        self._set_icon()
        self.configure(bg=self.T["bg"])

    # ── Theme ─────────────────────────────────────────────────────

    @property
    def T(self):
        return THEMES[self._current_theme]

    def _reg(self, widget, **mapping):
        """Register a tk.* widget for theme updates."""
        self._themed_tk.append((widget, mapping))
        return widget

    def _apply_theme(self, name: str):
        self._current_theme = name
        self.configure(bg=self.T["bg"])
        self._build_styles()
        for widget, mapping in self._themed_tk:
            try:
                widget.configure(**{k: self.T[v] for k, v in mapping.items()})
            except tk.TclError:
                pass
        # Treeview tag colors
        try:
            self._tree.tag_configure("odd",  background=self.T["tree_odd"])
            self._tree.tag_configure("even", background=self.T["tree_even"])
            self._tree.tag_configure("running",
                                      background=self.T["accent"],
                                      foreground=self.T["accent_dark"])
            self._tree.tag_configure("done",
                                      foreground=self.T["success"])
            self._tree.tag_configure("failed",
                                      foreground=self.T["error"])
        except Exception:
            pass
        # Toggle button label
        icon = "☀" if name == "dark" else "🌙"
        self._theme_btn.configure(text=f" {icon} ", bg=self.T["btn"],
                                   fg=self.T["text"],
                                   activebackground=self.T["btn_active"],
                                   activeforeground=self.T["text"])

    def _build_styles(self):
        T = self.T
        s = ttk.Style(self)
        s.theme_use("clam")

        # Base frames / labels
        for name, bg in [("TFrame", T["bg"]), ("Panel.TFrame", T["panel"]),
                           ("Surface.TFrame", T["surface"])]:
            s.configure(name, background=bg)
        s.configure("TLabel",        background=T["bg"],    foreground=T["text"],
                     font=("Segoe UI", 10))
        s.configure("Panel.TLabel",  background=T["panel"], foreground=T["text"],
                     font=("Segoe UI", 10))
        s.configure("Sub.TLabel",    background=T["panel"], foreground=T["subtext"],
                     font=("Segoe UI", 9))
        s.configure("Header.TLabel", background=T["bg"],    foreground=T["accent"],
                     font=("Segoe UI", 14, "bold"))
        s.configure("Section.TLabel",background=T["panel"], foreground=T["accent2"],
                     font=("Segoe UI", 10, "bold"))
        s.configure("Status.TLabel", background=T["bg"],    foreground=T["subtext"],
                     font=("Segoe UI", 9))
        s.configure("Footer.TLabel", background=T["panel"], foreground=T["subtext"],
                     font=("Segoe UI", 8))
        s.configure("FooterLink.TLabel", background=T["panel"],
                     foreground=T["accent"],
                     font=("Segoe UI", 8, "underline"), cursor="hand2")

        # Buttons
        s.configure("TButton",
                     background=T["btn"], foreground=T["text"],
                     font=("Segoe UI", 10), borderwidth=0,
                     focusthickness=0, relief="flat", padding=(8, 5))
        s.map("TButton",
              background=[("active", T["btn_active"]), ("pressed", T["btn_active"])])
        s.configure("Accent.TButton",
                     background=T["accent"], foreground=T["accent_dark"],
                     font=("Segoe UI", 11, "bold"), padding=(14, 6))
        s.map("Accent.TButton",
              background=[("active", "#74c7ec"), ("disabled", T["border"])])
        s.configure("Stop.TButton",
                     background=T["error"], foreground="#ffffff",
                     font=("Segoe UI", 11, "bold"), padding=(10, 6))
        s.map("Stop.TButton",
              background=[("active", "#e05c7a"), ("disabled", T["border"])])
        s.configure("Preset.TButton",
                     background=T["surface"], foreground=T["text"],
                     font=("Segoe UI", 9), padding=(8, 4))
        s.map("Preset.TButton",
              background=[("active", T["btn_active"])])

        # Progressbar
        s.configure("TProgressbar",
                     troughcolor=T["border"], background=T["accent"],
                     thickness=8)
        s.configure("Thin.TProgressbar",
                     troughcolor=T["border"], background=T["success"],
                     thickness=4)

        # Combobox
        s.configure("TCombobox",
                     fieldbackground=T["entry"], background=T["entry"],
                     foreground=T["text"], selectbackground=T["accent"],
                     selectforeground=T["accent_dark"])
        s.map("TCombobox",
              fieldbackground=[("readonly", T["entry"])],
              foreground=[("readonly", T["text"])])

        # Scrollbar
        s.configure("TScrollbar",
                     background=T["scrollbar"], troughcolor=T["panel"],
                     arrowcolor=T["subtext"], borderwidth=0)

        # Treeview (queue)
        s.configure("Queue.Treeview",
                     background=T["entry"], foreground=T["text"],
                     fieldbackground=T["entry"], rowheight=30,
                     font=("Segoe UI", 9))
        s.configure("Queue.Treeview.Heading",
                     background=T["panel"], foreground=T["subtext"],
                     font=("Segoe UI", 9, "bold"), relief="flat")
        s.map("Queue.Treeview",
              background=[("selected", T["btn_active"])],
              foreground=[("selected", T["text"])])
        s.map("Queue.Treeview.Heading",
              background=[("active", T["btn_active"])])

    # ── Window icon ───────────────────────────────────────────────

    def _set_icon(self):
        if not PIL_OK:
            return
        try:
            img  = PILImage.new("RGBA", (64, 64), (0, 0, 0, 0))
            from PIL import ImageDraw
            d = ImageDraw.Draw(img)
            d.ellipse([2, 2, 62, 62],  fill="#89b4fa")
            d.ellipse([12, 12, 52, 52], fill="#1e1e2e")
            d.ellipse([22, 22, 42, 42], fill="#cba6f7")
            d.rectangle([44, 44, 62, 62], fill="#1e1e2e")
            d.rectangle([50, 48, 64, 52], fill="#89b4fa")
            d.rectangle([48, 50, 52, 64], fill="#89b4fa")
            photo = ImageTk.PhotoImage(img)
            self.iconphoto(True, photo)
            self._icon_ref = photo
        except Exception:
            pass

    # ── Main UI ───────────────────────────────────────────────────

    def _build_ui(self):
        T = self.T
        # ── Header bar ────────────────────────────────────────────
        hdr = tk.Frame(self, bg=T["panel"], pady=10)
        hdr.pack(fill="x")
        self._reg(hdr, bg="panel")

        lbl_title = tk.Label(hdr, text="🔍 LectureLens",
                  bg=T["panel"], fg=T["accent"],
                  font=("Segoe UI", 16, "bold"))
        lbl_title.pack(side="left", padx=(18, 6))
        self._reg(lbl_title, bg="panel", fg="accent")

        tk.Label(hdr, text="Any Video  →  Searchable PDF",
                  bg=T["panel"], fg=T["subtext"],
                  font=("Segoe UI", 10)).pack(side="left")

        # Theme toggle
        self._theme_btn = tk.Button(
            hdr, text=" ☀ ", command=self._toggle_theme,
            bg=T["btn"], fg=T["text"], relief="flat",
            font=("Segoe UI", 12), cursor="hand2",
            activebackground=T["btn_active"], activeforeground=T["text"],
            bd=0, padx=6, pady=2
        )
        self._theme_btn.pack(side="right", padx=(0, 18))
        Tooltip(self._theme_btn, "Toggle dark / light mode")

        tk.Button(hdr, text=" ℹ About ", command=self._show_about,
                   bg=T["btn"], fg=T["text"], relief="flat",
                   font=("Segoe UI", 10), cursor="hand2",
                   activebackground=T["btn_active"],
                   activeforeground=T["text"], bd=0,
                   padx=6, pady=4).pack(side="right", padx=(0, 6))

        # Separator
        tk.Frame(self, height=1, bg=T["border"]).pack(fill="x")

        # ── Body ──────────────────────────────────────────────────
        body = tk.Frame(self, bg=T["bg"])
        body.pack(fill="both", expand=True, padx=14, pady=10)
        body.columnconfigure(0, weight=6)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(0, weight=3)
        body.rowconfigure(1, weight=0)
        body.rowconfigure(2, weight=2)

        # use grid
        self._build_queue(body)
        self._build_output(body)
        self._build_settings(body)
        self._build_log(body)
        self._build_statusbar()
        self._build_footer()

    def _card(self, parent, title: str, row: int, col: int,
               rowspan=1, colspan=1, **grid_kw):
        T = self.T
        card = tk.Frame(parent, bg=T["panel"], bd=0)
        card.grid(row=row, column=col, rowspan=rowspan, columnspan=colspan,
                   sticky="nsew",
                   padx=(0, 7) if col == 0 else (7, 0),
                   pady=(0, 7), **grid_kw)
        self._reg(card, bg="panel")
        inner = tk.Frame(card, bg=T["panel"], padx=12, pady=10)
        inner.pack(fill="both", expand=True)
        self._reg(inner, bg="panel")
        tk.Label(inner, text=title, bg=T["panel"], fg=T["accent2"],
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))
        return inner

    # ── Queue (Treeview) ──────────────────────────────────────────

    def _build_queue(self, parent):
        T = self.T
        sec = self._card(parent, "📹  Video Queue", row=0, col=0)

        # Input row
        inp = tk.Frame(sec, bg=T["panel"])
        inp.pack(fill="x", pady=(0, 8))
        self._reg(inp, bg="panel")

        self._entry_var = tk.StringVar()
        entry = tk.Entry(inp, textvariable=self._entry_var,
                          bg=T["entry"], fg=T["text"],
                          insertbackground=T["text"],
                          relief="flat", font=("Segoe UI", 10),
                          highlightthickness=1,
                          highlightbackground=T["border"],
                          highlightcolor=T["accent"])
        entry.pack(side="left", fill="x", expand=True, ipady=6)
        entry.bind("<Return>", lambda _: self._add_source())
        self._reg(entry, bg="entry", fg="text", insertbackground="text",
                   highlightbackground="border", highlightcolor="accent")
        Tooltip(entry, "Paste a YouTube URL or local file path, then press Enter")

        btn_frame = tk.Frame(inp, bg=T["panel"])
        btn_frame.pack(side="left", padx=(6, 0))
        self._reg(btn_frame, bg="panel")
        ttk.Button(btn_frame, text="Add", command=self._add_source,
                    style="TButton").pack(side="left", padx=(0, 4))
        ttk.Button(btn_frame, text="Browse…", command=self._browse_video,
                    style="TButton").pack(side="left")

        # Treeview
        tv_frame = tk.Frame(sec, bg=T["panel"])
        tv_frame.pack(fill="both", expand=True)
        self._reg(tv_frame, bg="panel")

        cols = ("#", "Source", "Status", "Slides")
        self._tree = ttk.Treeview(tv_frame, columns=cols, show="headings",
                                    style="Queue.Treeview", selectmode="extended",
                                    height=7)
        self._tree.heading("#",      text="#",       anchor="center")
        self._tree.heading("Source", text="Source",  anchor="w")
        self._tree.heading("Status", text="Status",  anchor="center")
        self._tree.heading("Slides", text="Slides",  anchor="center")
        self._tree.column("#",      width=36,  minwidth=30,  anchor="center", stretch=False)
        self._tree.column("Source", width=320, minwidth=200, anchor="w",      stretch=True)
        self._tree.column("Status", width=120, minwidth=100, anchor="center", stretch=False)
        self._tree.column("Slides", width=56,  minwidth=50,  anchor="center", stretch=False)

        self._tree.tag_configure("odd",     background=T["tree_odd"])
        self._tree.tag_configure("even",    background=T["tree_even"])
        self._tree.tag_configure("running", background=T["accent"],
                                  foreground=T["accent_dark"])
        self._tree.tag_configure("done",    foreground=T["success"])
        self._tree.tag_configure("failed",  foreground=T["error"])

        tv_sb = ttk.Scrollbar(tv_frame, orient="vertical",
                               command=self._tree.yview)
        self._tree.configure(yscrollcommand=tv_sb.set)
        tv_sb.pack(side="right", fill="y")
        self._tree.pack(side="left", fill="both", expand=True)
        self._tree.bind("<Delete>", lambda _: self._remove_selected())
        self._tree.bind("<Double-1>", self._on_tree_double_click)

        # Controls
        ctrl = tk.Frame(sec, bg=T["panel"])
        ctrl.pack(fill="x", pady=(8, 0))
        self._reg(ctrl, bg="panel")
        ttk.Button(ctrl, text="↑ Move Up",   command=self._move_up,   style="TButton").pack(side="left", padx=(0, 4))
        ttk.Button(ctrl, text="↓ Move Down", command=self._move_down, style="TButton").pack(side="left", padx=(0, 4))
        ttk.Button(ctrl, text="Remove",      command=self._remove_selected, style="TButton").pack(side="left", padx=(0, 4))
        ttk.Button(ctrl, text="Clear All",   command=self._clear_all, style="TButton").pack(side="left")
        self._count_lbl = tk.Label(ctrl, text="0 videos", bg=T["panel"],
                                    fg=T["subtext"], font=("Segoe UI", 9))
        self._count_lbl.pack(side="right")
        self._reg(self._count_lbl, bg="panel", fg="subtext")

    def _add_source(self):
        val = self._entry_var.get().strip()
        if not val:
            return
        n   = len(self._queue_items) + 1
        src = val if len(val) <= 70 else "…" + val[-67:]
        iid = self._tree.insert("", "end", values=(n, src, "🕐 Pending", "—"),
                                  tags=("odd" if n % 2 else "even",))
        self._queue_items[iid] = val
        self._entry_var.set("")
        self._update_count()

    def _browse_video(self):
        paths = filedialog.askopenfilenames(
            title="Select video file(s)",
            filetypes=[("Video files", "*.mp4 *.mkv *.avi *.mov *.webm *.flv"),
                        ("All files", "*.*")]
        )
        for p in paths:
            self._entry_var.set(p)
            self._add_source()

    def _remove_selected(self):
        for iid in self._tree.selection():
            self._queue_items.pop(iid, None)
            self._tree.delete(iid)
        self._renumber()
        self._update_count()

    def _clear_all(self):
        for iid in list(self._queue_items):
            self._tree.delete(iid)
        self._queue_items.clear()
        self._update_count()

    def _move_up(self):
        sel = self._tree.selection()
        for iid in sel:
            idx = self._tree.index(iid)
            if idx > 0:
                self._tree.move(iid, "", idx - 1)
        self._renumber()

    def _move_down(self):
        sel = list(reversed(self._tree.selection()))
        for iid in sel:
            idx = self._tree.index(iid)
            if idx < len(self._tree.get_children()) - 1:
                self._tree.move(iid, "", idx + 1)
        self._renumber()

    def _renumber(self):
        for i, iid in enumerate(self._tree.get_children(), 1):
            vals = list(self._tree.item(iid, "values"))
            vals[0] = i
            tag = "odd" if i % 2 else "even"
            existing_tags = [t for t in self._tree.item(iid, "tags")
                              if t not in ("odd", "even")]
            self._tree.item(iid, values=vals, tags=[tag] + existing_tags)

    def _update_count(self):
        n = len(self._queue_items)
        self._count_lbl.config(text=f"{n} video{'s' if n != 1 else ''}")

    def _on_tree_double_click(self, event):
        iid = self._tree.identify_row(event.y)
        if iid and iid in self._queue_items:
            src = self._queue_items[iid]
            self._entry_var.set(src)

    def _set_item_status(self, iid: str, status: str, slides: str = "—"):
        if iid not in self._queue_items:
            return
        vals = list(self._tree.item(iid, "values"))
        vals[2] = status
        vals[3] = slides
        row_tag = "odd" if int(vals[0]) % 2 else "even"
        extra   = ("running" if "Processing" in status else
                    "done"    if "Done"        in status else
                    "failed"  if "Failed"      in status else "")
        tags    = [row_tag] + ([extra] if extra else [])
        self._tree.item(iid, values=vals, tags=tags)

    # ── Output directory ──────────────────────────────────────────

    def _build_output(self, parent):
        T   = self.T
        sec = self._card(parent, "📁  Output Directory", row=1, col=0)

        row = tk.Frame(sec, bg=T["panel"])
        row.pack(fill="x")
        self._reg(row, bg="panel")

        self._out_var = tk.StringVar(value=str(Path.home() / "LectureLens"))
        e = tk.Entry(row, textvariable=self._out_var,
                      bg=T["entry"], fg=T["text"],
                      insertbackground=T["text"], relief="flat",
                      font=("Segoe UI", 10), highlightthickness=1,
                      highlightbackground=T["border"], highlightcolor=T["accent"])
        e.pack(side="left", fill="x", expand=True, ipady=6)
        self._reg(e, bg="entry", fg="text", insertbackground="text",
                   highlightbackground="border", highlightcolor="accent")
        ttk.Button(row, text="Browse…", command=self._browse_output,
                    style="TButton").pack(side="left", padx=(6, 0))

        lbl_pdf = tk.Label(sec, text="PDFs are saved here, one file per video.",
                  bg=T["panel"], fg=T["subtext"],
                  font=("Segoe UI", 9))
        lbl_pdf.pack(anchor="w", pady=(6, 0))
        self._reg(lbl_pdf, bg="panel", fg="subtext")

    def _browse_output(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if d:
            self._out_var.set(d)

    # ── Settings ──────────────────────────────────────────────────

    def _build_settings(self, parent):
        T   = self.T
        sec = self._card(parent, "⚙  Settings", row=2, col=0)

        # Presets
        preset_row = tk.Frame(sec, bg=T["panel"])
        preset_row.pack(fill="x", pady=(0, 10))
        self._reg(preset_row, bg="panel")
        tk.Label(preset_row, text="Preset:",
                  bg=T["panel"], fg=T["subtext"],
                  font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        for name in PRESETS:
            ttk.Button(preset_row, text=name, style="Preset.TButton",
                        command=lambda n=name: self._apply_preset(n)
                        ).pack(side="left", padx=(0, 4))
        Tooltip(preset_row,
                "Fast: quick scan, no OCR\nBalanced: recommended\nQuality: thorough scan + OCR")

        # Grid of settings
        grid = tk.Frame(sec, bg=T["panel"])
        grid.pack(fill="x")
        self._reg(grid, bg="panel")

        SETTINGS_DEFS = [
            ("Frame Interval",  "frame_interval", 0.5, 5.0, 0.5,  "%.1f",
             "Sample 1 frame every N seconds"),
            ("Similarity",      "ssim",           0.70, 0.99, 0.01, "%.2f",
             "SSIM cutoff — lower captures more slides"),
            ("Hash Distance",   "hash",           2,   20,  1,    "%.0f",
             "pHash hamming distance threshold"),
            ("Confirm Frames",  "confirm",        1,   10,  1,    "%.0f",
             "Stable frames before accepting a new slide"),
            ("OCR Confidence",  "ocr_conf",       0.1, 1.0, 0.05, "%.2f",
             "Minimum OCR confidence to accept text"),
            ("JPEG Quality",    "quality",        60,  100, 5,    "%.0f",
             "Slide image quality inside PDF (95 recommended)"),
        ]

        self._interval_var = tk.DoubleVar(value=1.0)
        self._ssim_var     = tk.DoubleVar(value=0.92)
        self._hash_var     = tk.IntVar(value=8)
        self._confirm_var  = tk.IntVar(value=3)
        self._conf_var     = tk.DoubleVar(value=0.6)
        self._quality_var  = tk.IntVar(value=95)

        var_map = {
            "frame_interval": self._interval_var,
            "ssim":           self._ssim_var,
            "hash":           self._hash_var,
            "confirm":        self._confirm_var,
            "ocr_conf":       self._conf_var,
            "quality":        self._quality_var,
        }

        for i, (label, key, lo, hi, inc, fmt, tip) in enumerate(SETTINGS_DEFS):
            col_off = (i % 2) * 3
            row_off = i // 2
            lbl = tk.Label(grid, text=label, bg=T["panel"], fg=T["text"],
                            font=("Segoe UI", 9), anchor="w")
            lbl.grid(row=row_off, column=col_off, sticky="w", padx=(0, 4), pady=3)
            self._reg(lbl, bg="panel", fg="text")

            sp = tk.Spinbox(grid, from_=lo, to=hi, increment=inc, format=fmt,
                             textvariable=var_map[key], width=7,
                             bg=T["entry"], fg=T["text"],
                             buttonbackground=T["border"], relief="flat",
                             font=("Segoe UI", 9))
            sp.grid(row=row_off, column=col_off + 1, sticky="w", padx=(0, 20), pady=3)
            self._reg(sp, bg="entry", fg="text", buttonbackground="border")
            Tooltip(sp, tip)

        # OCR engine
        ocr_row = tk.Frame(sec, bg=T["panel"])
        ocr_row.pack(fill="x", pady=(8, 0))
        self._reg(ocr_row, bg="panel")

        lbl_ocr = tk.Label(ocr_row, text="OCR Engine", bg=T["panel"], fg=T["text"],
                  font=("Segoe UI", 9))
        lbl_ocr.pack(side="left", padx=(0, 8))
        self._reg(lbl_ocr, bg="panel", fg="text")

        choices = []
        if PADDLE_OK: choices.append("paddleocr")
        if TESS_OK:   choices.append("tesseract")
        choices += ["auto", "none"]
        self._ocr_var = tk.StringVar(value="auto" if (PADDLE_OK or TESS_OK) else "none")
        cb = ttk.Combobox(ocr_row, textvariable=self._ocr_var,
                           values=choices, width=14, state="readonly")
        cb.pack(side="left")
        Tooltip(cb, "paddleocr = best quality\ntesseract = fallback\nauto = pick best available\nnone = skip OCR")

        avail = []
        if PADDLE_OK: avail.append("PaddleOCR ✓")
        if TESS_OK:   avail.append("Tesseract ✓")
        if not avail: avail = ["No OCR engine found"]
        tk.Label(ocr_row, text=f"  ({', '.join(avail)})", bg=T["panel"],
                  fg=T["subtext"], font=("Segoe UI", 8)
                  ).pack(side="left", padx=(6, 0))

    def _apply_preset(self, name: str):
        p = PRESETS[name]
        self._interval_var.set(p["frame_interval"])
        self._ssim_var.set(p["similarity_thresh"])
        self._hash_var.set(p["hash_threshold"])
        self._confirm_var.set(p["confirm_frames"])
        self._conf_var.set(p["ocr_confidence"])
        self._quality_var.set(p["image_quality"])
        ocr = p["ocr_engine"]
        if ocr == "auto" and not (PADDLE_OK or TESS_OK):
            ocr = "none"
        self._ocr_var.set(ocr)

    # ── Log panel ─────────────────────────────────────────────────

    def _build_log(self, parent):
        T   = self.T
        sec = self._card(parent, "📋  Live Log", row=0, col=1, rowspan=3)

        # Stats strip
        stats = tk.Frame(sec, bg=T["surface"], pady=6, padx=8)
        stats.pack(fill="x", pady=(0, 8))
        self._reg(stats, bg="surface")

        self._stat_slides = self._stat_label(stats, "Slides", "—")
        self._stat_videos = self._stat_label(stats, "Videos", "—")
        self._stat_time   = self._stat_label(stats, "Elapsed", "—")

        # Log text
        log_frame = tk.Frame(sec, bg=T["panel"])
        log_frame.pack(fill="both", expand=True)
        self._reg(log_frame, bg="panel")

        self._log_text = tk.Text(
            log_frame, bg=T["panel"], fg=T["text"],
            insertbackground=T["text"], relief="flat",
            font=("Consolas", 9), wrap="word",
            state="disabled", borderwidth=0, highlightthickness=0
        )
        self._reg(self._log_text, bg="panel", fg="text", insertbackground="text")
        self._log_text.tag_config("ok",   foreground=T["success"])
        self._log_text.tag_config("warn", foreground=T["warning"])
        self._log_text.tag_config("err",  foreground=T["error"])
        self._log_text.tag_config("hi",   foreground=T["accent"])
        self._log_text.tag_config("dim",  foreground=T["subtext"])
        self._log_text.tag_config("bold", foreground=T["text"],
                                   font=("Consolas", 9, "bold"))

        lsb = ttk.Scrollbar(log_frame, orient="vertical",
                              command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        self._log_text.pack(side="left", fill="both", expand=True)

        # Log controls
        lctrl = tk.Frame(sec, bg=T["panel"])
        lctrl.pack(fill="x", pady=(6, 0))
        self._reg(lctrl, bg="panel")
        ttk.Button(lctrl, text="Clear Log", command=self._clear_log,
                    style="TButton").pack(side="left")
        self._open_btn = ttk.Button(lctrl, text="📂 Open Output",
                                     command=self._open_output,
                                     style="TButton")
        self._open_btn.pack(side="right")
        Tooltip(self._open_btn, "Open the output folder in file manager")

    def _stat_label(self, parent, title: str, val: str):
        T   = self.T
        col = tk.Frame(parent, bg=T["surface"])
        col.pack(side="left", padx=(0, 20))
        self._reg(col, bg="surface")
        tk.Label(col, text=title, bg=T["surface"], fg=T["subtext"],
                  font=("Segoe UI", 8)).pack(anchor="w")
        lbl = tk.Label(col, text=val, bg=T["surface"], fg=T["accent"],
                        font=("Segoe UI", 12, "bold"))
        lbl.pack(anchor="w")
        self._reg(lbl, bg="surface", fg="accent")
        return lbl

    def log(self, msg: str):
        tag = ("ok"   if msg.startswith("✅") else
                "err"  if msg.startswith("❌") else
                "warn" if msg.startswith(("⚠", "⛔")) else
                "hi"   if msg.startswith(("📹", "📥", "📄", "🖼", "♻", "🔤", "▶", "═", "─")) else
                "bold" if msg.startswith("🎉") else
                "dim"  if msg.startswith("  ") else "")
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _clear_log(self):
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    def _open_output(self):
        d = self._out_var.get().strip()
        if d and Path(d).exists():
            if sys.platform == "win32":
                os.startfile(d)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])
        else:
            messagebox.showinfo("Output Folder",
                                 "Output folder does not exist yet. Run an extraction first.")

    # ── Status bar ────────────────────────────────────────────────

    def _build_statusbar(self):
        T   = self.T
        bar = tk.Frame(self, bg=T["bg"], pady=8, padx=14)
        bar.pack(fill="x")
        self._reg(bar, bg="bg")

        self._progress_var = tk.DoubleVar(value=0)
        self._progress = ttk.Progressbar(bar, variable=self._progress_var,
                                          maximum=100, style="TProgressbar")
        self._progress.pack(side="left", fill="x", expand=True)

        self._status_lbl = tk.Label(bar, text="Ready", bg=T["bg"],
                                     fg=T["subtext"], font=("Segoe UI", 9),
                                     width=24, anchor="w")
        self._status_lbl.pack(side="left", padx=(12, 0))
        self._reg(self._status_lbl, bg="bg", fg="subtext")

        self._stop_btn = ttk.Button(bar, text="⏹  Stop", command=self._stop,
                                     style="Stop.TButton", state="disabled")
        self._stop_btn.pack(side="right", padx=(8, 0))

        self._start_btn = ttk.Button(bar, text="▶  Extract Slides",
                                      command=self._start,
                                      style="Accent.TButton")
        self._start_btn.pack(side="right")

    # ── Footer ────────────────────────────────────────────────────

    def _build_footer(self):
        T = self.T
        tk.Frame(self, height=1, bg=T["border"]).pack(fill="x")
        foot = tk.Frame(self, bg=T["panel"], pady=5)
        foot.pack(fill="x")
        self._reg(foot, bg="panel")

        tk.Label(foot, text="LectureLens",
                  bg=T["panel"], fg=T["subtext"],
                  font=("Segoe UI", 8, "bold")).pack(side="left", padx=(14, 4))
        tk.Label(foot, text=f"v{VERSION}  ·  by Shivam Aggarwal  ·",
                  bg=T["panel"], fg=T["subtext"],
                  font=("Segoe UI", 8)).pack(side="left")

        link = tk.Label(foot, text="github.com/aggarwal-shiv",
                         bg=T["panel"], fg=T["accent"],
                         font=("Segoe UI", 8, "underline"), cursor="hand2")
        link.pack(side="left", padx=(2, 0))
        link.bind("<Button-1>",
                   lambda _: webbrowser.open("https://github.com/aggarwal-shiv"))
        self._reg(link, bg="panel", fg="accent")

        tk.Label(foot, text="MIT License",
                  bg=T["panel"], fg=T["subtext"],
                  font=("Segoe UI", 8)).pack(side="right", padx=(0, 14))

    # ── Theme toggle ──────────────────────────────────────────────

    def _toggle_theme(self):
        new = "light" if self._current_theme == "dark" else "dark"
        self._apply_theme(new)
        # Re-apply log text tags with new theme colors
        T = self.T
        self._log_text.tag_config("ok",   foreground=T["success"])
        self._log_text.tag_config("warn", foreground=T["warning"])
        self._log_text.tag_config("err",  foreground=T["error"])
        self._log_text.tag_config("hi",   foreground=T["accent"])
        self._log_text.tag_config("dim",  foreground=T["subtext"])
        self._log_text.tag_config("bold", foreground=T["text"],
                                   font=("Consolas", 9, "bold"))

    # ── About dialog ──────────────────────────────────────────────

    def _show_about(self):
        T    = self.T
        win  = tk.Toplevel(self)
        win.title("About LectureLens")
        win.geometry("420x320")
        win.resizable(False, False)
        win.configure(bg=T["panel"])
        win.grab_set()

        tk.Label(win, text="🔍 LectureLens", bg=T["panel"], fg=T["accent"],
                  font=("Segoe UI", 18, "bold")).pack(pady=(24, 4))
        tk.Label(win, text="Any Video  →  Searchable PDF Slides",
                  bg=T["panel"], fg=T["subtext"],
                  font=("Segoe UI", 10)).pack()
        tk.Label(win, text=f"Version {VERSION}", bg=T["panel"],
                  fg=T["subtext"], font=("Segoe UI", 9)).pack(pady=(2, 16))

        tk.Frame(win, height=1, bg=T["border"]).pack(fill="x", padx=30)

        tk.Label(win, text="Author: Shivam Aggarwal",
                  bg=T["panel"], fg=T["text"],
                  font=("Segoe UI", 10)).pack(pady=(16, 4))

        link = tk.Label(win, text="github.com/aggarwal-shiv",
                         bg=T["panel"], fg=T["accent"],
                         font=("Segoe UI", 10, "underline"), cursor="hand2")
        link.pack()
        link.bind("<Button-1>",
                   lambda _: webbrowser.open("https://github.com/aggarwal-shiv"))

        tk.Label(win, text="MIT License — free to use, modify, and share.",
                  bg=T["panel"], fg=T["subtext"],
                  font=("Segoe UI", 9)).pack(pady=(12, 0))

        feat = ("Multi-video queue  ·  YouTube + local files\n"
                "Direct PDF (no PowerPoint)  ·  PaddleOCR + Tesseract\n"
                "Dark & Light themes  ·  Fast / Balanced / Quality presets")
        tk.Label(win, text=feat, bg=T["panel"], fg=T["subtext"],
                  font=("Segoe UI", 8), justify="center").pack(pady=(10, 0))

        ttk.Button(win, text="Close", command=win.destroy,
                    style="TButton").pack(pady=(16, 20))

    # ── Actions ───────────────────────────────────────────────────

    def _get_cfg(self) -> dict:
        return {
            "frame_interval":       self._interval_var.get(),
            "similarity_thresh":    self._ssim_var.get(),
            "hash_threshold":       self._hash_var.get(),
            "confirm_frames":       self._confirm_var.get(),
            "ocr_engine":           self._ocr_var.get(),
            "ocr_confidence":       self._conf_var.get(),
            "image_quality":        self._quality_var.get(),
            "text_similarity_thresh": 0.85,
        }

    def _start(self):
        iids = list(self._tree.get_children())
        if not iids:
            messagebox.showwarning("No Sources",
                                    "Add at least one YouTube URL or video file.")
            return
        out = self._out_var.get().strip()
        if not out:
            messagebox.showwarning("No Output", "Choose an output directory first.")
            return
        self._running = True
        self._stop_event.clear()
        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._progress_var.set(0)
        self._start_time = time.time()
        # Reset statuses
        for iid in iids:
            self._set_item_status(iid, "🕐 Pending", "—")
        cfg = self._get_cfg()
        t   = threading.Thread(target=self._run_all,
                                args=(iids, Path(out), cfg), daemon=True)
        t.start()
        self._tick_clock()

    def _tick_clock(self):
        if self._running:
            elapsed = int(time.time() - self._start_time)
            self._stat_time.configure(text=format_time(elapsed))
            self.after(1000, self._tick_clock)

    def _stop(self):
        self._stop_event.set()
        self._status("Stopping…")

    def _run_all(self, iids: list, out_dir: Path, cfg: dict):
        ensure(out_dir)
        n    = len(iids)
        pdfs = []
        done_slides = 0

        for idx, iid in enumerate(iids):
            if self._stop_event.is_set():
                self._set_item_status(iid, "⛔ Cancelled")
                break
            src = self._queue_items.get(iid, "")
            lbl = src if len(src) <= 48 else "…" + src[-45:]
            self._status(f"[{idx+1}/{n}] {lbl}")
            self._set_item_status(iid, "⚙ Processing…")
            self._stat_videos.configure(text=f"{idx+1}/{n}")

            self.log(f"\n{'─'*52}")
            self.log(f"▶  Video {idx+1}/{n}:  {src}")
            self.log(f"{'─'*52}")

            def cb(pct, _i=idx):
                overall = (_i / n + pct / 100 / n) * 100
                self._progress_var.set(overall)

            pdf = process_video(src, out_dir, cfg,
                                  self.log, cb, self._stop_event)

            if pdf:
                n_slides = len(list((out_dir / sanitize(
                    pdf.stem)).glob("slides/*.jpg")))
                done_slides += n_slides
                self._set_item_status(iid, "✅ Done", str(n_slides) if n_slides else "—")
                self._stat_slides.configure(text=str(done_slides))
                pdfs.append(pdf)
            else:
                self._set_item_status(iid, "❌ Failed", "—")

        # Final summary
        self.log(f"\n{'═'*52}")
        if pdfs:
            self.log(f"🎉 Done!  {len(pdfs)}/{n} PDF(s) saved:")
            for p in pdfs:
                self.log(f"   📄 {p}")
        else:
            self.log("⚠ No PDFs were produced.")

        self._progress_var.set(100 if not self._stop_event.is_set() else
                                self._progress_var.get())
        self._status("Complete ✓" if not self._stop_event.is_set() else "Stopped")
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._running = False

    def _status(self, msg: str):
        self._status_lbl.configure(text=msg)

    def on_close(self):
        if self._running:
            if messagebox.askyesno("Quit",
                                    "Extraction is running. Stop and quit?"):
                self._stop_event.set()
                self.destroy()
        else:
            self.destroy()


# ─────────────────────────────────────────────────────────────────
# Dependency installer
# ─────────────────────────────────────────────────────────────────

def install_deps():
    pkgs = ["yt-dlp", "opencv-python", "scikit-image", "imagehash",
             "Pillow", "paddlepaddle", "paddleocr", "pytesseract", "numpy", "tqdm"]
    print("Installing LectureLens dependencies…\n")
    for pkg in pkgs:
        print(f"  Installing {pkg}…")
        subprocess.run([sys.executable, "-m", "pip", "install", pkg, "-q"],
                        check=False)
    print("\n✅ Done. Run  python LectureLens.py  to launch the app.")


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--install" in sys.argv:
        install_deps()
        sys.exit(0)
    app = LectureLens()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()