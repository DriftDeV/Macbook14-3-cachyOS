"""Scheda "Touch Bar" con OmaBar come renderer: editor di /etc/omabar/config.toml (omabar.py), con l'anteprima disegnata
dal binario di OmaBar stesso (`omabar preview --config`) e i colori del tema di Omarchy in uso."""
import copy
import os
import tempfile

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QScrollArea,
                               QSlider, QSpinBox, QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from . import omabar as O

KIND_LABEL = dict(O.KINDS)


def _label(b):
    k = O.kind(b)
    what = {"label": "“%s”" % b.get("label", ""), "icon": "🖼 %s" % str(b.get("icon", "")).removesuffix("-symbolic"),
            "clock": "🕑 %s" % b.get("clock", ""), "battery": "🔋 batteria", "media": "♫ brano",
            "gap": "│ separatore", "": "(spazio)"}[k]
    keys = "+".join(O.keys(b))
    w = b.get("width")
    return "%s%s%s" % (what, "  →  " + keys if keys else "", "  (×%g)" % w if w else "")


class LayerEditor(QWidget):
    """Nome del livello, elenco dei tasti e campi del tasto scelto."""

    def __init__(self, changed, lock=False):
        super().__init__()
        self.changed = changed
        self.lock = lock
        self.buttons = []
        self.loading = False
        lay = QGridLayout(self)
        self.name = QLineEdit()
        self.name.textEdited.connect(lambda _t: self.changed())
        lay.addWidget(QLabel("Nome"), 0, 0)
        lay.addWidget(self.name, 0, 1)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._select)
        lay.addWidget(self.list, 1, 0, 6, 2)
        for i, (txt, icon, fn) in enumerate((("Aggiungi", "list-add", self._add), ("Togli", "list-remove", self._remove),
                                             ("Su", "go-up", lambda: self._move(-1)),
                                             ("Giù", "go-down", lambda: self._move(1)))):
            b = QPushButton(QIcon.fromTheme(icon), txt)
            b.clicked.connect(fn)
            lay.addWidget(b, i + 1, 2)
        box = QGroupBox("Tasto")
        form = QFormLayout(box)
        self.kind = QComboBox()
        for k, label in O.KINDS:
            self.kind.addItem(label, k)
        self.value = QStackedWidget()
        self.text = QLineEdit()
        self.icon = QComboBox()
        self.icon.setEditable(True)
        self.icon.addItems(O.icons())
        self.icon.setToolTip("Nome di un'icona simbolica (Adwaita, /etc/omabar/icons) o percorso di un SVG")
        self.clock = QComboBox()
        self.clock.setEditable(True)
        self.clock.addItems(O.CLOCKS)
        self.clock.setToolTip("Formato strftime: %H ore, %M minuti, %a giorno, %-d numero del giorno, %b mese")
        self.pages = {"label": self.text, "icon": self.icon, "clock": self.clock}
        for w in (self.text, self.icon, self.clock):
            self.value.addWidget(w)
        self.none = QLabel("—")
        self.value.addWidget(self.none)
        self.value.setMaximumHeight(self.icon.sizeHint().height())
        self.icon_size = QSpinBox()
        self.icon_size.setRange(0, 60)
        self.icon_size.setSpecialValueText("predefinita")
        self.icon_size.setSuffix(" px")
        self.playing = QComboBox()
        self.playing.setEditable(True)
        self.playing.addItems([""] + O.icons())
        self.playing.setToolTip("Icona mostrata al posto dell'altra mentre un lettore suona (per esempio la pausa)")
        self.keys = QComboBox()
        self.keys.setEditable(True)
        self.keys.addItems([""] + O.COMMON_KEYS)
        self.keys.setToolTip("Tasto inviato al tocco. Combinazioni con +, per esempio LeftCtrl+C. Nomi di "
                             "input-linux (Esc, VolumeUp, PlayPause, LeftMeta...).")
        self.width = QDoubleSpinBox()
        self.width.setRange(0, 20)
        self.width.setSingleStep(0.25)
        self.width.setDecimals(2)
        self.width.setSpecialValueText("1 posto")
        self.width.setSuffix(" posti")
        form.addRow("Tipo", self.kind)
        form.addRow("Contenuto", self.value)
        form.addRow("Dimensione icona", self.icon_size)
        form.addRow("Icona mentre suona", self.playing)
        form.addRow("Tasto", self.keys)
        form.addRow("Larghezza", self.width)
        if lock:
            form.addRow(QLabel("A sessione bloccata la barra non invia tasti."))
        lay.addWidget(box, 0, 3, 7, 1)
        lay.setColumnStretch(0, 3)
        lay.setColumnStretch(3, 4)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.text.textEdited.connect(self._edited)
        for w in (self.icon, self.clock, self.playing, self.keys):
            w.currentTextChanged.connect(self._edited)
        self.icon_size.valueChanged.connect(self._edited)
        self.width.valueChanged.connect(self._edited)

    def set_layer(self, layer):
        self.name.setText(layer.get("name", ""))
        self.buttons = [dict(b) for b in layer.get("buttons", [])]
        self._fill(0)

    def layer(self):
        return {"name": self.name.text(), "buttons": [dict(b) for b in self.buttons]}

    def _fill(self, row):
        self.loading = True
        self.list.clear()
        for b in self.buttons:
            self.list.addItem(_label(b))
        self.loading = False
        self.list.setCurrentRow(min(row, len(self.buttons) - 1))
        self._select(self.list.currentRow())

    def _enable(self, k, ok=True):
        self.value.setEnabled(ok and k in self.pages)
        self.icon_size.setEnabled(ok and k == "icon")
        self.playing.setEnabled(ok and k == "icon")
        self.keys.setEnabled(ok and k != "gap" and not self.lock)
        self.width.setEnabled(ok and k != "gap")
        self.kind.setEnabled(ok)

    def _select(self, row):
        if self.loading:
            return
        ok = 0 <= row < len(self.buttons)
        if not ok:
            self._enable("", False)
            return
        b = self.buttons[row]
        k = O.kind(b)
        self.loading = True
        self.kind.setCurrentIndex(max(0, self.kind.findData(k)))
        self.value.setCurrentWidget(self.pages.get(k, self.none))
        self.text.setText(str(b.get("label", "")))
        self.icon.setCurrentText(str(b.get("icon", "")))
        self.clock.setCurrentText(str(b.get("clock", "%H:%M")))
        self.icon_size.setValue(int(b.get("icon_size", 0)))
        self.playing.setCurrentText(str(b.get("icon_playing", "")))
        self.keys.setCurrentText("+".join(O.keys(b)))
        self.width.setValue(float(b.get("width", 0)))
        self.loading = False
        self._enable(k)

    def _kind_changed(self, _i):
        k = self.kind.currentData()
        self.value.setCurrentWidget(self.pages.get(k, self.none))
        self._enable(k)
        self._edited()

    def _edited(self, *_):
        row = self.list.currentRow()
        if self.loading or not 0 <= row < len(self.buttons):
            return
        k = self.kind.currentData()
        b = {}
        if k == "label":
            b["label"] = self.text.text()
        elif k == "icon":
            b["icon"] = self.icon.currentText().strip()
            if self.icon_size.value():
                b["icon_size"] = self.icon_size.value()
            if self.playing.currentText().strip():
                b["icon_playing"] = self.playing.currentText().strip()
        elif k == "clock":
            b["clock"] = self.clock.currentText() or "%H:%M"
        elif k in ("battery", "media", "gap"):
            b[k] = True
        if k != "gap":
            ks = [x.strip() for x in self.keys.currentText().split("+") if x.strip()]
            if ks and not self.lock:
                b["keys"] = ks
            if self.width.value():
                b["width"] = round(self.width.value(), 2)
        self.buttons[row] = b
        self.list.item(row).setText(_label(b))
        self.changed()

    def _add(self):
        row = self.list.currentRow() + 1
        self.buttons.insert(row, {"label": "nuovo"})
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


class OmaBarEditor(QScrollArea):
    def __init__(self, log):
        super().__init__()
        self.log = log
        self.cfg = None
        self.loading = False
        self.dirty = False
        self.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        # --- anteprima
        prev = QGroupBox("Anteprima (disegnata da OmaBar con i colori del tema in uso)")
        pl = QVBoxLayout(prev)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumHeight(40)
        pl.addWidget(self.image)
        row = QHBoxLayout()
        self.fake_media = QCheckBox("Simula un brano in riproduzione")
        self.fake_media.setChecked(True)
        self.fake_media.toggled.connect(lambda _c: self._schedule_preview())
        row.addWidget(self.fake_media)
        row.addStretch(1)
        pl.addLayout(row)
        self.prev_timer = QTimer(self)
        self.prev_timer.setSingleShot(True)
        self.prev_timer.setInterval(250)
        self.prev_timer.timeout.connect(self._preview)
        lay.addWidget(prev)

        # --- luminosità (dal vivo)
        lum = QGroupBox("Luminosità della Touch Bar")
        ll = QGridLayout(lum)
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(1, 255)
        self.bright_lbl = QLabel()
        self.min_bright = QSlider(Qt.Horizontal)
        self.min_bright.setRange(1, 255)
        self.min_lbl = QLabel()
        for lbl in (self.bright_lbl, self.min_lbl):
            lbl.setMinimumWidth(48)
        self.follow = QCheckBox("Segue la luminosità dello schermo (dalla minima, schermo al minimo, alla massima)")
        note = QLabel("Si applica subito. Il T1 non ha una retroilluminazione: OmaBar scurisce i colori in software.")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(placeholder-text);")
        ll.addWidget(QLabel("Massima"), 0, 0)
        ll.addWidget(self.bright, 0, 1)
        ll.addWidget(self.bright_lbl, 0, 2)
        ll.addWidget(QLabel("Minima"), 1, 0)
        ll.addWidget(self.min_bright, 1, 1)
        ll.addWidget(self.min_lbl, 1, 2)
        ll.addWidget(self.follow, 2, 0, 1, 3)
        ll.addWidget(note, 3, 0, 1, 3)
        self.bright_timer = QTimer(self)
        self.bright_timer.setSingleShot(True)
        self.bright_timer.setInterval(350)
        self.bright_timer.timeout.connect(self._save_brightness)
        self.bright.valueChanged.connect(self._bright_moved)
        self.min_bright.valueChanged.connect(self._bright_moved)
        self.follow.toggled.connect(self._bright_moved)
        lay.addWidget(lum)

        # --- aspetto
        look = QGroupBox("Aspetto")
        form = QFormLayout(look)
        self.bar = QComboBox()
        self.bar.addItem("Fondo dal tema di Omarchy", "theme")
        self.bar.addItem("Fondo nero (consuma meno, niente segno sull'OLED)", "black")
        self.outlines = QCheckBox("Sfondo dei tasti a riposo (spento: solo icone e testo)")
        self.shift = QCheckBox("Sposta il disegno di qualche pixel ogni 2 minuti (contro il segno sull'OLED)")
        self.font = QComboBox()
        self.font.setEditable(True)
        self.font.addItems(O.FONTS)
        self.font_size = QSpinBox()
        self.font_size.setRange(10, 48)
        self.font_size.setSuffix(" pt")
        self.fade = QSpinBox()
        self.fade.setRange(0, 3000)
        self.fade.setSingleStep(50)
        self.fade.setSpecialValueText("cambio secco")
        self.fade.setSuffix(" ms")
        form.addRow("Fondo", self.bar)
        form.addRow("Carattere", self.font)
        form.addRow("Dimensione", self.font_size)
        form.addRow("Dissolvenza al cambio di tema", self.fade)
        form.addRow("", self.outlines)
        form.addRow("", self.shift)
        self.bar.currentIndexChanged.connect(self._changed)
        self.font.currentTextChanged.connect(self._changed)
        for w in (self.font_size, self.fade):
            w.valueChanged.connect(self._changed)
        for w in (self.outlines, self.shift):
            w.toggled.connect(self._changed)
        lay.addWidget(look)

        # --- tasti
        keys = QGroupBox("Tasti (il primo livello è quello normale, il secondo compare tenendo premuto Fn)")
        kl = QVBoxLayout(keys)
        self.layer_tabs = QTabWidget()
        self.layer_tabs.setMinimumHeight(340)  # le schede si aggiungono dopo: senza minimo resta schiacciata
        self.layer_tabs.currentChanged.connect(lambda _i: self._schedule_preview())
        kl.addWidget(self.layer_tabs)
        lb = QHBoxLayout()
        add = QPushButton(QIcon.fromTheme("list-add"), "Aggiungi livello")
        rem = QPushButton(QIcon.fromTheme("list-remove"), "Togli questo livello")
        add.clicked.connect(self._add_layer)
        rem.clicked.connect(self._remove_layer)
        lb.addWidget(add)
        lb.addWidget(rem)
        lb.addStretch(1)
        kl.addLayout(lb)
        self.layer_eds = []
        self.lock_ed = LayerEditor(self._changed, lock=True)
        lay.addWidget(keys)

        bar = QHBoxLayout()
        self.reset_btn = QPushButton(QIcon.fromTheme("edit-undo"), "Tutto predefinito")
        self.reset_btn.setToolTip("Rimette la configurazione di /usr/share/omabar/config.toml (da salvare)")
        self.reload_btn = QPushButton(QIcon.fromTheme("view-refresh"), "Ricarica")
        self.save_btn = QPushButton(QIcon.fromTheme("document-save"), "Salva e applica")
        self.save_btn.setDefault(True)
        self.reset_btn.clicked.connect(self._reset)
        self.reload_btn.clicked.connect(self.load)
        self.save_btn.clicked.connect(self.save)
        bar.addWidget(self.reset_btn)
        bar.addWidget(self.reload_btn)
        bar.addStretch(1)
        bar.addWidget(self.save_btn)
        lay.addLayout(bar)
        lay.addStretch(1)
        self.setWidget(body)

    # --- caricamento ---------------------------------------------------------------------------------
    def load(self):
        try:
            self.cfg, _over = O.load()
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "OmaBar", "Non riesco a leggere %s:\n%s" % (O.USER_CFG, e))
            self.cfg = O.defaults()
        self._show_cfg(self.cfg)
        self._set_dirty(False)
        self._update_info()

    def _show_cfg(self, c):
        self.loading = True
        d, t = c["display"], c["theme"]
        self.bright.setValue(int(d["brightness"]))
        self.min_bright.setValue(int(d["min_brightness"]))
        self.follow.setChecked(bool(d["follow_screen"]))
        self.shift.setChecked(bool(d["pixel_shift"]))
        self.font.setCurrentText(str(d["font"]))
        self.font_size.setValue(int(round(float(d["font_size"]))))
        self.fade.setValue(int(d["fade_ms"]))
        self.bar.setCurrentIndex(max(0, self.bar.findData(t["bar"])))
        self.outlines.setChecked(bool(t["outlines"]))
        cur = self.layer_tabs.currentIndex()
        self.layer_tabs.blockSignals(True)
        self.layer_tabs.clear()
        self.layer_eds = []
        for layer in c["layer"]:
            ed = LayerEditor(self._changed)
            ed.set_layer(layer)
            self.layer_eds.append(ed)
        self._retitle()
        self.lock_ed.set_layer(c["lock"])
        self.layer_tabs.addTab(self.lock_ed, QIcon.fromTheme("system-lock-screen"), "Sessione bloccata")
        self.layer_tabs.setCurrentIndex(max(0, min(cur, self.layer_tabs.count() - 1)))
        self.layer_tabs.blockSignals(False)
        self.loading = False
        self._bright_label()
        self._schedule_preview()

    def _retitle(self):
        for i, ed in enumerate(self.layer_eds):
            title = "Normale" if i == 0 else ("Con Fn" if i == 1 else "Livello %d" % (i + 1))
            idx = self.layer_tabs.indexOf(ed)
            if idx < 0:
                self.layer_tabs.insertTab(i, ed, title)
            else:
                self.layer_tabs.setTabText(idx, title)

    def _update_info(self):
        if not O.installed():
            self.info.setText("⚠ OmaBar non è installato: sudo omarchy/install-omabar.sh")
        elif not O.writable():
            self.info.setText("⚠ %s non è scrivibile dal tuo utente: rilancia sudo omarchy/install-omabar.sh "
                              "(lo rende scrivibile). Intanto puoi solo guardare." % O.USER_CFG)
        else:
            self.info.setText("Configurazione di <b>OmaBar</b> (%s): i colori seguono da soli il tema di Omarchy. "
                              "OmaBar la rilegge appena salvi, senza riavvio; la luminosità si applica subito."
                              % O.USER_CFG)
        ok = O.installed() and O.writable()
        for w in (self.save_btn, self.bright, self.min_bright, self.follow):
            w.setEnabled(ok)

    def showEvent(self, ev):
        super().showEvent(ev)
        if self.cfg is None:
            self.load()
        else:
            self._update_info()

    # --- modifiche -----------------------------------------------------------------------------------
    def _collect(self):
        c = copy.deepcopy(self.cfg)
        d, t = c["display"], c["theme"]
        d["brightness"] = self.bright.value()
        d["min_brightness"] = self.min_bright.value()
        d["follow_screen"] = self.follow.isChecked()
        d["pixel_shift"] = self.shift.isChecked()
        d["font"] = self.font.currentText().strip() or "sans-serif"
        if int(round(float(d["font_size"]))) != self.font_size.value():
            d["font_size"] = self.font_size.value()
        d["fade_ms"] = self.fade.value()
        t["bar"] = self.bar.currentData()
        t["outlines"] = self.outlines.isChecked()
        c["layer"] = [ed.layer() for ed in self.layer_eds]
        c["lock"] = self.lock_ed.layer()
        return c

    def _set_dirty(self, d):
        self.dirty = d
        self.save_btn.setText("Salva e applica" + (" •" if d else ""))

    def _changed(self, *_):
        if self.loading:
            return
        self._set_dirty(True)
        self._schedule_preview()

    def _add_layer(self):
        ed = LayerEditor(self._changed)
        ed.set_layer({"name": "livello %d" % (len(self.layer_eds) + 1), "buttons": [{"label": "esc", "keys": ["Esc"]}]})
        self.layer_eds.append(ed)
        self._retitle()
        self.layer_tabs.setCurrentWidget(ed)
        self._changed()

    def _remove_layer(self):
        w = self.layer_tabs.currentWidget()
        if w is self.lock_ed or len(self.layer_eds) <= 1:
            QMessageBox.information(self, "OmaBar", "Il livello della sessione bloccata e l'ultimo livello restano.")
            return
        self.layer_eds.remove(w)
        self.layer_tabs.removeTab(self.layer_tabs.indexOf(w))
        w.deleteLater()
        self._retitle()
        self._changed()

    def _reset(self):
        self._show_cfg(O.defaults())
        self._changed()

    # --- anteprima -----------------------------------------------------------------------------------
    def _schedule_preview(self):
        if not self.loading:
            self.prev_timer.start()

    def _preview(self):
        if self.cfg is None:
            return
        c = self._collect()
        errs = O.validate(c)
        if errs:
            self.image.setPixmap(QPixmap())
            self.image.setText("⚠ " + errs[0])
            return
        w = self.layer_tabs.currentWidget()
        locked = w is self.lock_ed
        layer = 0 if locked or w not in self.layer_eds else self.layer_eds.index(w)
        fd, out = tempfile.mkstemp(prefix="omabar-preview-", suffix=".png")
        os.close(fd)
        try:
            err = O.preview(c, out, layer=layer, locked=locked,
                            media="Titolo del brano|Artista" if self.fake_media.isChecked() else None)
            if err:
                self.image.setPixmap(QPixmap())
                self.image.setText("⚠ " + err)
                return
            pm = QPixmap(out)
            width = max(400, self.viewport().width() - 60)
            self.image.setPixmap(pm.scaledToWidth(width, Qt.SmoothTransformation))
        finally:
            os.unlink(out)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._schedule_preview()

    # --- luminosità dal vivo -------------------------------------------------------------------------
    def _bright_label(self):
        self.bright_lbl.setText("%d %%" % round(self.bright.value() * 100 / 255))
        self.min_lbl.setText("%d %%" % round(self.min_bright.value() * 100 / 255))

    def _bright_moved(self, *_):
        if self.min_bright.value() > self.bright.value():
            (self.bright if self.sender() is self.min_bright else self.min_bright).setValue(
                self.min_bright.value() if self.sender() is self.min_bright else self.bright.value())
        self._bright_label()
        if not self.loading:
            self.bright_timer.start()
            self._schedule_preview()

    def _save_brightness(self):
        """Scrive solo la luminosità sul file attuale: le altre modifiche non salvate restano da salvare."""
        try:
            disk, _over = O.load()
            disk["display"].update(brightness=self.bright.value(), min_brightness=self.min_bright.value(),
                                   follow_screen=self.follow.isChecked())
            O.save(disk)
            self.cfg["display"].update(brightness=disk["display"]["brightness"],
                                       min_brightness=disk["display"]["min_brightness"],
                                       follow_screen=disk["display"]["follow_screen"])
        except (OSError, ValueError) as e:
            self.log("OmaBar: luminosità non salvata: %s" % e)

    # --- salvataggio ---------------------------------------------------------------------------------
    def save(self):
        c = self._collect()
        errs = O.validate(c)
        if errs:
            QMessageBox.warning(self, "OmaBar", "Da correggere prima di salvare:\n\n• " + "\n• ".join(errs))
            return
        try:
            O.save(c)
        except ValueError as e:
            QMessageBox.warning(self, "OmaBar", "OmaBar non accetterebbe questa configurazione:\n\n%s" % e)
            return
        except OSError as e:
            QMessageBox.warning(self, "OmaBar", "Salvataggio non riuscito:\n%s" % e)
            return
        self.cfg = c
        self._set_dirty(False)
        self.log("OmaBar: configurazione salvata in %s (copia precedente in %s)" % (O.USER_CFG, O.BACKUP))
