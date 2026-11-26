"""Aspetto di MacBook Manager. Su Omarchy segue il tema attivo, dal vivo: colori da colors.toml, stile dei controlli dai
token [controls] di shell.toml (riempimenti e bordi in trasparenza, nessun arrotondamento, come la shell di Omarchy),
carattere di sistema (`omarchy font current`) e tema di icone (icons.theme). Altrove (KDE) non tocca niente: restano
stile e palette del desktop, e i colori di significato (ok/avviso/errore/grafici) sono quelli di sempre.

    from . import theme as T
    T.c("warn")        -> "#rrggbb" del colore di significato
    T.qc("accent", 80) -> QColor con alfa (0-255)
"""
import os
import subprocess

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "omarchy", "current")
THEME = os.path.join(STATE, "theme")

# Colori di significato fuori da Omarchy (quelli usati finora nella GUI).
DEFAULT = {"ok": "#2ea043", "warn": "#d29922", "err": "#f85149", "info": "#8b949e",
           "accent": "#2a78d6", "accent2": "#eb6834", "series_ok": "#2ea043"}
_sem = dict(DEFAULT)
_active = None   # dict del tema di Omarchy applicato, o None


def c(name):
    return _sem.get(name, DEFAULT.get(name, "#808080"))


def qc(name, alpha=None):
    from PySide6.QtGui import QColor
    col = QColor(c(name))
    if alpha is not None:
        col.setAlpha(alpha)
    return col


def omarchy():
    """True se il tema di Omarchy è disponibile (e non disattivato con MACBOOK_MANAGER_THEME=native)."""
    return os.environ.get("MACBOOK_MANAGER_THEME") != "native" and os.path.isfile(os.path.join(THEME, "colors.toml"))


def name():
    try:
        with open(os.path.join(STATE, "theme.name")) as f:
            return f.readline().strip()
    except OSError:
        return ""


def _toml(path):
    if tomllib is None:
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, ValueError):
        return {}


def _font():
    try:
        out = subprocess.run(["omarchy-font-current"], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    return out or "monospace"


def load():
    """Tema attivo di Omarchy: colori, token dei controlli, carattere, dimensione, icone. None se non c'è."""
    if not omarchy():
        return None
    col = _toml(os.path.join(THEME, "colors.toml"))
    if "background" not in col or "foreground" not in col:
        return None
    shell = _toml(os.path.join(THEME, "shell.toml"))
    try:
        with open(os.path.join(THEME, "icons.theme")) as f:
            icons = f.readline().strip()
    except OSError:
        icons = ""
    return {"colors": col, "controls": shell.get("controls", {}), "font": _font(),
            "size": float(shell.get("font", {}).get("base-size", 12) or 12), "icons": icons,
            "dark": col.get("mode", "dark") != "light", "name": name()}


def _rgba(hexcol, alpha):
    h = hexcol.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return "rgba(%d, %d, %d, %d)" % (r, g, b, round(255 * max(0.0, min(1.0, float(alpha)))))


def stylesheet(t):
    """QSS che imita i controlli della shell di Omarchy (token [controls] di shell.toml)."""
    k, ctl = t["colors"], t["controls"]
    fg, bg = k["foreground"], k["background"]
    accent = k.get("accent", fg)
    dark_bg = k.get("dark_background", bg)
    light_bg = k.get("lighter_background", bg)
    muted_fg = k.get("dark_foreground", fg)
    sel = k.get("selection", accent)

    def tok(state, what, default):
        return ctl.get("%s-%s" % (state, what), default)

    def fill(state, default):
        return _rgba(tok(state, "color", fg), tok(state, "fill-alpha", default))

    def border(state, default_alpha, default_width=1):
        w = int(tok(state, "border-width", default_width))
        return "none" if w == 0 else "%dpx solid %s" % (w, _rgba(tok(state, "border", fg), tok(state, "border-alpha", default_alpha)))

    normal, hover, focus = fill("normal", 0.04), fill("hover-cursor", 0.08), fill("focus", 0.08)
    selected, pressed = fill("selected", 0.18), _rgba(fg, ctl.get("pressed-fill-alpha", 0.22))
    b_normal, b_hover, b_focus = border("normal", 0.4), border("hover-cursor", 0.25), border("focus", 0.25)
    b_sel = border("selected", 1.0, 0)
    sel_fill = _rgba(accent, ctl.get("selection-fill-alpha", 0.35))
    return """
* { outline: none; }
QWidget { background: %(bg)s; color: %(fg)s; selection-background-color: %(sel_fill)s; selection-color: %(fg)s;
          font-family: "%(font)s"; }
QMainWindow, QDialog { background: %(bg)s; }
QToolTip { background: %(bg)s; color: %(fg)s; border: 1px solid %(accent)s; padding: 4px 6px; }
QLabel { background: transparent; }
QPushButton, QToolButton, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit, QTextBrowser {
    background: %(normal)s; border: %(b_normal)s; border-radius: 0; padding: 5px 10px; }
QPlainTextEdit, QTextEdit, QTextBrowser { padding: 4px; background: %(dark_bg)s; }
QPushButton:hover, QToolButton:hover, QComboBox:hover { background: %(hover)s; border: %(b_hover)s; }
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QSpinBox:focus { background: %(focus)s; border: %(b_focus)s; }
QPushButton:pressed, QToolButton:pressed { background: %(pressed)s; }
QPushButton:checked, QToolButton:checked { background: %(selected)s; border: %(b_sel)s; color: %(fg)s; }
QPushButton:checked { border-left: 2px solid %(accent)s; }
QPushButton:disabled, QComboBox:disabled, QLineEdit:disabled { color: %(muted_fg)s; border-color: %(muted)s; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView { background: %(bg)s; border: 1px solid %(accent)s; selection-background-color: %(sel_fill)s; }
QCheckBox, QRadioButton { background: transparent; spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator { width: 14px; height: 14px; border: %(b_normal)s; background: %(normal)s; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background: %(accent)s; border: 1px solid %(accent)s; }
QGroupBox { border: 1px solid %(muted)s; margin-top: 14px; padding: 10px 8px 8px 8px; background: transparent; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: %(muted_fg)s; }
QTabWidget::pane { border: none; border-top: 1px solid %(muted)s; top: -1px; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: %(muted_fg)s; padding: 7px 14px; border: none;
               border-bottom: 2px solid transparent; }
QTabBar::tab:hover { color: %(fg)s; background: %(hover)s; }
QTabBar::tab:selected { color: %(fg)s; border-bottom: 2px solid %(accent)s; background: %(selected)s; }
QHeaderView::section { background: %(light_bg)s; color: %(fg)s; border: none; border-right: 1px solid %(bg)s; padding: 4px 6px; }
QTableWidget, QTableView, QListWidget, QTreeWidget { background: %(dark_bg)s; alternate-background-color: %(light_bg)s;
    gridline-color: %(muted)s; border: 1px solid %(muted)s; }
QTableWidget::item:selected, QTableView::item:selected, QListWidget::item:selected { background: %(sel_fill)s; color: %(fg)s; }
QListWidget#nav { background: %(dark_bg)s; border: none; border-right: 1px solid %(muted)s; padding: 6px 0; }
QListWidget#nav::item { padding: 9px 10px; border: none; border-left: 2px solid transparent; color: %(muted_fg)s; }
QListWidget#nav::item:hover { background: %(hover)s; color: %(fg)s; }
QListWidget#nav::item:selected { background: %(selected)s; border-left: 2px solid %(accent)s; color: %(fg)s; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0; }
QScrollBar::handle { background: %(muted)s; min-height: 24px; min-width: 24px; }
QScrollBar::handle:hover { background: %(muted_fg)s; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page { background: none; border: none; }
QSlider::groove:horizontal { height: 4px; background: %(muted)s; }
QSlider::sub-page:horizontal { background: %(accent)s; }
QSlider::handle:horizontal { width: 12px; margin: -5px 0; background: %(fg)s; }
QProgressBar { border: 1px solid %(muted)s; background: %(dark_bg)s; text-align: center; }
QProgressBar::chunk { background: %(accent)s; }
QMenu { background: %(bg)s; border: 1px solid %(accent)s; }
QMenu::item { padding: 5px 18px; }
QMenu::item:selected { background: %(sel_fill)s; }
""" % dict(bg=bg, fg=fg, accent=accent, dark_bg=dark_bg, light_bg=light_bg, muted=k.get("muted", muted_fg),
           muted_fg=muted_fg, sel=sel, sel_fill=sel_fill, normal=normal, hover=hover, focus=focus, selected=selected,
           pressed=pressed, b_normal=b_normal, b_hover=b_hover, b_focus=b_focus, b_sel=b_sel,
           font=t["font"].replace('"', ''))


def apply(app):
    """Applica il tema di Omarchy all'applicazione (se c'è). True se applicato. Si può richiamare a ogni cambio."""
    global _active
    t = load()
    if t is None:
        return False
    from PySide6.QtGui import QColor, QFont, QIcon, QPalette
    from PySide6.QtWidgets import QStyleFactory
    k = t["colors"]
    if _active is None:
        app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    fg, bg = QColor(k["foreground"]), QColor(k["background"])
    accent = QColor(k.get("accent", k["foreground"]))
    light, dark = QColor(k.get("lighter_background", k["background"])), QColor(k.get("dark_background", k["background"]))
    muted_fg = QColor(k.get("dark_foreground", k["foreground"]))
    for role, col in [(QPalette.Window, bg), (QPalette.WindowText, fg), (QPalette.Base, dark), (QPalette.AlternateBase, light),
                      (QPalette.Text, fg), (QPalette.Button, light), (QPalette.ButtonText, fg),
                      (QPalette.BrightText, QColor(k.get("bright_foreground", k["foreground"]))),
                      (QPalette.Highlight, QColor(k.get("selection", k.get("accent")))), (QPalette.HighlightedText, fg),
                      (QPalette.ToolTipBase, bg), (QPalette.ToolTipText, fg), (QPalette.Link, accent),
                      (QPalette.PlaceholderText, muted_fg), (QPalette.Mid, QColor(k.get("muted", k["foreground"])))]:
        pal.setColor(role, col)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, muted_fg)
    app.setPalette(pal)
    f = QFont(t["font"])
    f.setPointSizeF(t["size"] * 0.85)   # base-size della shell è in pixel a 12; in punti Qt rende uguale a ~10
    app.setFont(f)
    if t["icons"]:
        QIcon.setThemeName(t["icons"])
    app.setStyleSheet(stylesheet(t))
    _sem.update({"ok": k.get("green", DEFAULT["ok"]), "warn": k.get("yellow", DEFAULT["warn"]),
                 "err": k.get("red", DEFAULT["err"]), "info": k.get("dark_foreground", DEFAULT["info"]),
                 "accent": k.get("accent", DEFAULT["accent"]), "accent2": k.get("orange", DEFAULT["accent2"]),
                 "series_ok": k.get("green", DEFAULT["ok"])})
    _active = t
    return True


def watch(app, on_change):
    """Segue `omarchy theme set`: Omarchy scrive theme.name per ultimo. Riapplica il tema e chiama on_change()."""
    from PySide6.QtCore import QFileSystemWatcher, QTimer
    if not omarchy():
        return None
    w = QFileSystemWatcher(app)
    paths = [STATE, os.path.join(STATE, "theme.name")]

    def rearm():
        for p in paths:
            if os.path.exists(p) and p not in w.files() + w.directories():
                w.addPath(p)

    timer = QTimer(app)
    timer.setSingleShot(True)
    timer.setInterval(400)   # il cambio di tema scrive più file: uno solo aggiornamento alla fine

    def fire():
        rearm()
        if apply(app):
            on_change()
    timer.timeout.connect(fire)
    w.fileChanged.connect(lambda _p: timer.start())
    w.directoryChanged.connect(lambda _p: timer.start())
    rearm()
    return w
