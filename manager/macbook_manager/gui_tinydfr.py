"""Scheda "Touch Bar" con tiny-dfr come renderer: editor di /etc/tiny-dfr/config.toml (tinydfr.py)."""
import copy

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox, QStackedWidget,
                               QTabWidget, QVBoxLayout, QWidget)

from . import tinydfr as T

CHIP = ("QLabel { background: #111; color: #eee; border: 1px solid #444; border-radius: 4px; padding: 2px 4px; "
        "font-size: 8pt; }")


def _label(b):
    k = T.kind(b)
    what = {"Icon": "🖼 " + str(b.get("Icon", "")), "Text": "“%s”" % b.get("Text", ""),
            "Time": "🕑 ora", "Battery": "🔋 batteria", "": "(spazio)"}[k]
    keys = "+".join(T.actions(b)) or "—"
    s = b.get("Stretch", 1)
    return "%s  →  %s%s" % (what, keys, "  (×%d)" % s if s > 1 else "")


GLYPH = {"brightness_low": "☀−", "brightness_high": "☀+", "mic_off": "🎙✕", "search": "🔍", "backlight_low": "⌨−",
         "backlight_high": "⌨+", "fast_rewind": "⏪", "play_pause": "⏯", "fast_forward": "⏩", "volume_off": "🔇",
         "volume_down": "🔉", "volume_up": "🔊", "bolt": "⚡"}


def _short(b):
    k = T.kind(b)
    if k == "Icon":
        name = str(b["Icon"])
        return GLYPH.get(name, "🔋" if name.startswith("battery") else name.replace("_", " ")[:8])
    if k == "Text":
        return str(b["Text"])[:12]
    return {"Time": "ora", "Battery": "batt", "": " "}[k]


class LayerEditor(QWidget):
    """Elenco dei pulsanti di una riga, con i campi del pulsante scelto."""

    def __init__(self, changed):
        super().__init__()
        self.changed = changed
        self.buttons = []
        self.loading = False
        lay = QGridLayout(self)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._select)
        lay.addWidget(self.list, 0, 0, 6, 1)
        for i, (txt, icon, fn) in enumerate((("Aggiungi", "list-add", self._add), ("Togli", "list-remove", self._remove),
                                             ("Su", "go-up", lambda: self._move(-1)),
                                             ("Giù", "go-down", lambda: self._move(1)))):
            b = QPushButton(QIcon.fromTheme(icon), txt)
            b.clicked.connect(fn)
            lay.addWidget(b, i, 1)
        box = QGroupBox("Pulsante")
        form = QFormLayout(box)
        self.kind = QComboBox()
        for k, label in T.KINDS:
            self.kind.addItem(label, k)
        self.value = QStackedWidget()
        self.icon = QComboBox()
        self.icon.setEditable(True)
        self.icon.addItems(T.icons())
        self.text = QComboBox()
        self.text.setEditable(True)
        self.time = QComboBox()
        for f, label in T.TIME_FORMATS:
            self.time.addItem(label, f)
        self.battery = QComboBox()
        for m, label in T.BATTERY_MODES:
            self.battery.addItem(label, m)
        for w in (self.icon, self.text, self.time, self.battery, QLabel("")):
            self.value.addWidget(w)
        self.value.setMaximumHeight(self.icon.sizeHint().height())
        self.keys = QComboBox()
        self.keys.setEditable(True)
        self.keys.addItems(T.COMMON_KEYS)
        self.keys.setToolTip("Tasto inviato al tocco. Combinazioni con +, per esempio LeftCtrl+C. I nomi sono quelli "
                             "di input-linux (Esc, VolumeUp, PlayPause, LeftMeta...).")
        self.stretch = QSpinBox()
        self.stretch.setRange(1, 8)
        self.stretch.setSuffix(" spazi")
        form.addRow("Tipo", self.kind)
        form.addRow("Contenuto", self.value)
        form.addRow("Tasto", self.keys)
        form.addRow("Larghezza", self.stretch)
        lay.addWidget(box, 0, 2, 6, 1)
        lay.setColumnStretch(0, 3)
        lay.setColumnStretch(2, 4)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        for w in (self.icon, self.text, self.keys):
            w.currentTextChanged.connect(self._edited)
        for w in (self.time, self.battery):
            w.currentIndexChanged.connect(self._edited)
        self.stretch.valueChanged.connect(self._edited)

    def set_buttons(self, buttons):
        self.buttons = [dict(b) for b in buttons]
        self._fill(0)

    def _fill(self, row):
        self.loading = True
        self.list.clear()
        for b in self.buttons:
            self.list.addItem(_label(b))
        self.loading = False
        self.list.setCurrentRow(min(row, len(self.buttons) - 1))
        self._select(self.list.currentRow())

    def _select(self, row):
        if self.loading:
            return
        ok = 0 <= row < len(self.buttons)
        for w in (self.kind, self.value, self.keys, self.stretch):
            w.setEnabled(ok)
        if not ok:
            return
        b = self.buttons[row]
        self.loading = True
        k = T.kind(b)
        self.kind.setCurrentIndex(max(0, self.kind.findData(k)))
        self.value.setCurrentIndex([x for x, _l in T.KINDS].index(k))
        self.icon.setCurrentText(str(b.get("Icon", "")))
        self.text.setCurrentText(str(b.get("Text", "")))
        self.time.setCurrentIndex(max(0, self.time.findData(b.get("Time", "24hr"))))
        self.battery.setCurrentIndex(max(0, self.battery.findData(b.get("Battery", "both"))))
        self.keys.setCurrentText("+".join(T.actions(b)))
        self.stretch.setValue(int(b.get("Stretch", 1)) if isinstance(b.get("Stretch", 1), int) else 1)
        self.loading = False

    def _kind_changed(self, _i):
        self.value.setCurrentIndex(self.kind.currentIndex())
        self._edited()

    def _edited(self, *_):
        row = self.list.currentRow()
        if self.loading or not 0 <= row < len(self.buttons):
            return
        old = self.buttons[row]
        b = {k: v for k, v in old.items() if k in ("Theme", "Locale", "IconWidth", "IconHeight")}
        k = self.kind.currentData()
        if k == "Icon":
            b["Icon"] = self.icon.currentText().strip()
        elif k == "Text":
            b["Text"] = self.text.currentText()
        elif k == "Time":
            b["Time"] = self.time.currentData()
        elif k == "Battery":
            b["Battery"] = self.battery.currentData()
        if k != "Icon":
            b.pop("Theme", None)
            b.pop("IconWidth", None)
            b.pop("IconHeight", None)
        keys = [x.strip() for x in self.keys.currentText().split("+") if x.strip()]
        if keys:
            b["Action"] = keys
        if self.stretch.value() > 1:
            b["Stretch"] = self.stretch.value()
        self.buttons[row] = b
        self.list.item(row).setText(_label(b))
        self.changed()

    def _add(self):
        row = self.list.currentRow() + 1
        self.buttons.insert(row, {"Text": "Nuovo", "Action": ["F1"]})
        self._fill(row)
        self.changed()

    def _remove(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.buttons):
            del self.buttons[row]
            self._fill(row)
            self.changed()

    def _move(self, d):
        row = self.list.currentRow()
        if 0 <= row < len(self.buttons) and 0 <= row + d < len(self.buttons):
            self.buttons[row], self.buttons[row + d] = self.buttons[row + d], self.buttons[row]
            self._fill(row + d)
            self.changed()


class TinyDfrEditor(QScrollArea):
    def __init__(self, log):
        super().__init__()
        self.log = log
        self.setWidgetResizable(True)
        self.cfg = None
        self.loading = False
        body = QWidget()
        lay = QVBoxLayout(body)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        # --- luminosità (dal vivo)
        lum = QGroupBox("Luminosità della Touch Bar")
        ll = QGridLayout(lum)
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(5, 100)
        self.bright.setPageStep(10)
        self.bright_lbl = QLabel()
        self.bright_lbl.setMinimumWidth(48)
        self.adaptive = QCheckBox("Segue la luminosità dello schermo (lo slider diventa il massimo)")
        note = QLabel("Si applica subito. Dopo un po' di inattività la barra si attenua e poi si spegne; il primo "
                      "tocco la riaccende. Sul T1 tiny-dfr la regola in software (patches/tiny-dfr).")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(placeholder-text);")
        ll.addWidget(QLabel("Luminosità"), 0, 0)
        ll.addWidget(self.bright, 0, 1)
        ll.addWidget(self.bright_lbl, 0, 2)
        ll.addWidget(self.adaptive, 1, 0, 1, 3)
        ll.addWidget(note, 2, 0, 1, 3)
        self.bright_timer = QTimer(self)
        self.bright_timer.setSingleShot(True)
        self.bright_timer.setInterval(350)
        self.bright_timer.timeout.connect(self._save_brightness)
        self.bright.valueChanged.connect(self._bright_moved)
        self.adaptive.toggled.connect(self._bright_moved)
        lay.addWidget(lum)

        # --- comportamento
        look = QGroupBox("Comportamento e aspetto")
        form = QFormLayout(look)
        self.primary = QComboBox()
        self.primary.addItem("Tasti multimediali (F1-F12 tenendo Fn)", True)
        self.primary.addItem("F1-F12 (tasti multimediali tenendo Fn)", False)
        self.swap = QSpinBox()
        self.swap.setRange(0, 2000)
        self.swap.setSingleStep(50)
        self.swap.setSpecialValueText("disattivato")
        self.swap.setSuffix(" ms")
        self.swap.setToolTip("Doppio tocco veloce su Fn per scambiare le due righe (prova 200 ms)")
        self.outlines = QCheckBox("Bordi dei pulsanti")
        self.shift = QCheckBox("Sposta il disegno di qualche pixel ogni tanto (contro il segno sull'OLED)")
        self.font = QComboBox()
        self.font.setEditable(True)
        for f, label in T.FONTS:
            self.font.addItem(label, f)
        self.font.setToolTip("Modello fontconfig (per esempio :bold, monospace:bold)")
        form.addRow("Riga principale", self.primary)
        form.addRow("Scambio con doppio Fn", self.swap)
        form.addRow("Carattere", self.font)
        form.addRow("", self.outlines)
        form.addRow("", self.shift)
        for w in (self.primary, self.font):
            w.currentIndexChanged.connect(self._changed)
        self.font.currentTextChanged.connect(self._changed)
        self.swap.valueChanged.connect(self._changed)
        for w in (self.outlines, self.shift):
            w.toggled.connect(self._changed)
        lay.addWidget(look)

        # --- tasti
        keys = QGroupBox("Tasti (Esc a sinistra lo aggiunge tiny-dfr da solo)")
        kl = QVBoxLayout(keys)
        self.layer_tabs = QTabWidget()
        self.layers = {}
        for key, label in T.LAYERS:
            ed = LayerEditor(self._changed)
            self.layers[key] = ed
            self.layer_tabs.addTab(ed, label)
        kl.addWidget(self.layer_tabs)
        self.preview = QHBoxLayout()
        self.preview.setSpacing(3)
        pw = QWidget()
        pw.setLayout(self.preview)
        kl.addWidget(QLabel("Anteprima della riga mostrata:"))
        kl.addWidget(pw)
        self.layer_tabs.currentChanged.connect(lambda _i: self._preview())
        lay.addWidget(keys)

        bar = QHBoxLayout()
        self.reset_btn = QPushButton(QIcon.fromTheme("edit-undo"), "Tasti predefiniti")
        self.reset_btn.setToolTip("Rimette i tasti di /usr/share/tiny-dfr/config.toml (da salvare)")
        self.reload_btn = QPushButton(QIcon.fromTheme("view-refresh"), "Ricarica")
        self.save_btn = QPushButton(QIcon.fromTheme("document-save"), "Salva e applica")
        self.save_btn.setDefault(True)
        self.reset_btn.clicked.connect(self._reset_keys)
        self.reload_btn.clicked.connect(self.load)
        self.save_btn.clicked.connect(self.save)
        bar.addWidget(self.reset_btn)
        bar.addWidget(self.reload_btn)
        bar.addStretch(1)
        bar.addWidget(self.save_btn)
        lay.addLayout(bar)
        lay.addStretch(1)
        self.setWidget(body)
        self.dirty = False

    # --- caricamento ---------------------------------------------------------------------------------
    def load(self):
        try:
            self.cfg, _over = T.load()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "tiny-dfr", "Non riesco a leggere %s:\n%s" % (T.USER_CFG, e))
            self.cfg = T.defaults()
        self.loading = True
        c = self.cfg
        self.bright.setValue(max(5, round(c["ActiveBrightness"] * 100 / 255)))
        self.adaptive.setChecked(bool(c["AdaptiveBrightness"]))
        self.primary.setCurrentIndex(0 if c["MediaLayerDefault"] else 1)
        self.swap.setValue(int(c["DoublePressSwitchLayers"]))
        i = self.font.findData(c["FontTemplate"])
        if i >= 0:
            self.font.setCurrentIndex(i)
        else:
            self.font.setEditText(c["FontTemplate"])
        self.outlines.setChecked(bool(c["ShowButtonOutlines"]))
        self.shift.setChecked(bool(c["EnablePixelShift"]))
        for key, ed in self.layers.items():
            ed.set_buttons(c[key])
        self.loading = False
        self._bright_label()
        self._set_dirty(False)
        self._preview()
        self._update_info()

    def _update_info(self):
        if not T.installed():
            self.info.setText("⚠ tiny-dfr non è installato: sudo scripts/install-tiny-dfr.sh")
        elif not T.writable():
            self.info.setText("⚠ %s non è scrivibile dal tuo utente: rilancia sudo scripts/install-tiny-dfr.sh "
                              "(lo rende scrivibile). Intanto puoi solo guardare." % T.USER_CFG)
        else:
            self.info.setText("Configurazione di <b>tiny-dfr</b> (%s). tiny-dfr la rilegge appena salvi: niente "
                              "riavvio. La luminosità si applica subito." % T.USER_CFG)
        for w in (self.save_btn, self.bright, self.adaptive):
            w.setEnabled(T.installed() and T.writable())

    def showEvent(self, ev):
        super().showEvent(ev)
        if self.cfg is None:
            self.load()
        else:
            self._update_info()

    # --- modifiche -----------------------------------------------------------------------------------
    def _collect(self):
        c = copy.deepcopy(self.cfg)
        c["ActiveBrightness"] = round(self.bright.value() * 255 / 100)
        c["AdaptiveBrightness"] = self.adaptive.isChecked()
        c["MediaLayerDefault"] = bool(self.primary.currentData())
        c["DoublePressSwitchLayers"] = self.swap.value()
        txt = self.font.currentText()
        c["FontTemplate"] = self.font.currentData() if self.font.findText(txt) >= 0 else txt
        c["ShowButtonOutlines"] = self.outlines.isChecked()
        c["EnablePixelShift"] = self.shift.isChecked()
        for key, ed in self.layers.items():
            c[key] = [dict(b) for b in ed.buttons]
        return c

    def _set_dirty(self, d):
        self.dirty = d
        self.save_btn.setText("Salva e applica" + (" •" if d else ""))

    def _changed(self, *_):
        if self.loading:
            return
        self._set_dirty(True)
        self._preview()

    def _preview(self):
        while self.preview.count():
            w = self.preview.takeAt(0).widget()
            if w:
                w.deleteLater()
        key = T.LAYERS[self.layer_tabs.currentIndex()][0]
        btns = [{"Text": "esc"}] + self.layers[key].buttons
        for b in btns:
            chip = QLabel(_short(b))
            chip.setStyleSheet(CHIP)
            chip.setAlignment(Qt.AlignCenter)
            self.preview.addWidget(chip, int(b.get("Stretch", 1)) if isinstance(b.get("Stretch", 1), int) else 1)

    def _reset_keys(self):
        base = T.defaults()
        for key, ed in self.layers.items():
            ed.set_buttons(base[key])
        self._changed()

    # --- luminosità dal vivo -------------------------------------------------------------------------
    def _bright_label(self):
        self.bright_lbl.setText("%d %%" % self.bright.value())

    def _bright_moved(self, *_):
        self._bright_label()
        if not self.loading:
            self.bright_timer.start()

    def _save_brightness(self):
        """Scrive solo luminosità e modo sul file attuale: le altre modifiche non salvate restano da salvare."""
        try:
            disk, _over = T.load()
            disk["ActiveBrightness"] = round(self.bright.value() * 255 / 100)
            disk["AdaptiveBrightness"] = self.adaptive.isChecked()
            T.save(disk)
            self.cfg["ActiveBrightness"] = disk["ActiveBrightness"]
            self.cfg["AdaptiveBrightness"] = disk["AdaptiveBrightness"]
        except (OSError, ValueError) as e:
            self.log("tiny-dfr: luminosità non salvata: %s" % e)

    # --- salvataggio ---------------------------------------------------------------------------------
    def save(self):
        c = self._collect()
        errs = T.validate(c)
        if errs:
            QMessageBox.warning(self, "tiny-dfr", "Da correggere prima di salvare:\n\n• " + "\n• ".join(errs))
            return
        try:
            T.save(c)
        except OSError as e:
            QMessageBox.warning(self, "tiny-dfr", "Salvataggio non riuscito:\n%s" % e)
            return
        self.cfg = c
        self._set_dirty(False)
        self.log("tiny-dfr: configurazione salvata in %s (copia precedente in %s)" % (T.USER_CFG, T.BACKUP))
