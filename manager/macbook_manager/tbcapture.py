"""Immagine della Touch Bar (modalità display, renderer fnstrip), senza Qt e senza root.

Usa la registrazione di debug di fnstrip (src/record.rs, commit fissato in config/sources.conf): finché esiste
$XDG_RUNTIME_DIR/fnstrip-record, fnstrip aggiunge ogni fotogramma inviato alla barra a ~/.cache/fnstrip-record/frames.raw
(XRGB8888, 2170x60, un fotogramma intero ciascuno) e scrive tocchi e invii in events.log. fnstrip invia un fotogramma solo
quando qualcosa cambia: l'ultimo fotogramma è quello sullo schermo.

Per non consumare l'SSD (~0,5 MB a fotogramma, fino a 60 al secondo nelle animazioni) ~/.cache/fnstrip-record diventa un
collegamento a una cartella in /run/user (RAM) finché la cattura è attiva, e i file ripartono da zero oltre RECYCLE byte.
"""
import os
import re
import shutil
import struct
import time
import zlib

WIDTH, HEIGHT = 2170, 60
FRAME = WIDTH * HEIGHT * 4
RECYCLE = 64 * 1024 * 1024
RUNTIME = os.environ.get("XDG_RUNTIME_DIR") or "/run/user/%d" % os.getuid()
FLAG = os.path.join(RUNTIME, "fnstrip-record")
RAM_DIR = os.path.join(RUNTIME, "fnstrip-record-data")
CACHE_DIR = os.path.expanduser("~/.cache/fnstrip-record")
TOUCHES = re.compile(r"touches=\[([^\]]*)\]")


class Capture:
    """Una sessione di cattura: start(), poi poll() periodico, infine stop()."""

    def __init__(self):
        self.frame = None        # bytes dell'ultimo fotogramma (XRGB8888)
        self.frames = 0          # fotogrammi ricevuti in questa sessione
        self.touch_x = None      # posizione orizzontale del dito (0..WIDTH) o None
        self._size = 0
        self._events_off = 0
        self._partial = b""
        self._recycle_at = None
        self.active = False

    # --- avvio e arresto ---------------------------------------------------------------------------
    def start(self):
        os.makedirs(RAM_DIR, mode=0o700, exist_ok=True)
        if os.path.islink(CACHE_DIR):
            if os.path.realpath(CACHE_DIR) != os.path.realpath(RAM_DIR):
                os.unlink(CACHE_DIR)
        elif os.path.isdir(CACHE_DIR):  # una registrazione di debug precedente: la metto da parte
            os.rename(CACHE_DIR, CACHE_DIR + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
        if not os.path.islink(CACHE_DIR):
            os.makedirs(os.path.dirname(CACHE_DIR), exist_ok=True)
            os.symlink(RAM_DIR, CACHE_DIR)
        open(FLAG, "a").close()
        self.active = True

    def stop(self):
        """Ferma la registrazione e libera la RAM (fnstrip chiude i file entro mezzo secondo)."""
        self.active = False
        try:
            os.unlink(FLAG)
        except FileNotFoundError:
            pass
        time.sleep(0.6)
        shutil.rmtree(RAM_DIR, ignore_errors=True)
        if os.path.islink(CACHE_DIR):
            os.unlink(CACHE_DIR)

    # --- lettura -----------------------------------------------------------------------------------
    def poll(self):
        """Legge le novità. Ritorna True se è arrivato un fotogramma nuovo."""
        if not self.active:
            return False
        if self._recycle_at is not None:  # riavvio dei file in corso
            if time.monotonic() < self._recycle_at:
                return False
            self._recycle_at = None
            self._size = self._events_off = 0
            self._partial = b""
            open(FLAG, "a").close()
        self._read_events()
        path = os.path.join(RAM_DIR, "frames.raw")
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size < self._size:  # file ripartito da zero
            self._size = 0
        complete = size // FRAME
        new = complete > self._size // FRAME
        if new:
            with open(path, "rb") as f:
                f.seek((complete - 1) * FRAME)
                data = f.read(FRAME)
            if len(data) == FRAME:
                self.frames += complete - self._size // FRAME
                self.frame = data
            self._size = complete * FRAME
        if size > RECYCLE:  # libera la RAM: fnstrip richiude e tronca i file quando il flag torna
            try:
                os.unlink(FLAG)
            except FileNotFoundError:
                pass
            self._recycle_at = time.monotonic() + 0.8
        return new

    def _read_events(self):
        path = os.path.join(RAM_DIR, "events.log")
        try:
            size = os.path.getsize(path)
            if size < self._events_off:
                self._events_off, self._partial = 0, b""
            with open(path, "rb") as f:
                f.seek(self._events_off)
                chunk = f.read()
        except OSError:
            return
        self._events_off += len(chunk)
        lines = (self._partial + chunk).split(b"\n")
        self._partial = lines.pop()
        for line in lines:
            if b" input " not in line:
                continue
            m = TOUCHES.search(line.decode(errors="replace"))
            pts = m.group(1).split() if m else []
            try:
                self.touch_x = int(pts[0].split(",")[0]) if pts else None
            except ValueError:
                self.touch_x = None

    def wait_frame(self, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.poll():
                return True
            time.sleep(0.05)
        return False


def renderer_active():
    import subprocess
    return subprocess.run(["systemctl", "--user", "-q", "is-active", "macbookpro14-3-touchbar-renderer.service"]).returncode == 0


def png_bytes(frame):
    """PNG (RGB) da un fotogramma XRGB8888, solo libreria standard."""
    rows = bytearray()
    for y in range(HEIGHT):
        row = frame[y * WIDTH * 4:(y + 1) * WIDTH * 4]
        rgb = bytearray(WIDTH * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
        rows += b"\x00" + rgb

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


def user_dir(kind, fallback):
    import subprocess
    try:
        d = subprocess.run(["xdg-user-dir", kind], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        d = ""
    d = d if d and d != os.path.expanduser("~") else os.path.expanduser(fallback)
    os.makedirs(d, exist_ok=True)
    return d


def default_path(kind="PICTURES", ext="png"):
    base = user_dir(kind, "~/Immagini" if kind == "PICTURES" else "~/Video")
    return os.path.join(base, "touchbar-%s.%s" % (time.strftime("%Y%m%d-%H%M%S"), ext))
