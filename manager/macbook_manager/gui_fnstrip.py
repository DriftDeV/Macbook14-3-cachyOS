"""Scheda "Touch Bar" di MacBook Manager: editor della configurazione di fnstrip."""
import copy
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from . import fnstrip as F

CHIP = ("QLabel { background: %s; color: %s; border: 1px solid #333; border-radius: 4px; padding: 2px 5px; "
        "font-size: 8pt; }")
SHORT = {"mic": "mic", "camera": "cam", "vpn": "vpn", "cpu": "cpu", "mem": "mem", "disk": "disco", "net": "rete",
         "battery": "batt", "temp": "temp", "fan": "fan"}  # anteprima compatta: deve stare nella finestra


class FnstripEditor(QScrollArea):
    def __init__(self, log, open_live=None):
        super().__init__()
        self.log = log  # funzione(testo) per il registro della finestra
        self.setWidgetResizable(True)
        self.cfg = None
        self.loading = False
        body = QWidget()
        lay = QVBoxLayout(body)

        self.info = QLabel()
        self.info.setWordWrap(True)
        top = QHBoxLayout()
        top.addWidget(self.info, 1)
        if open_live:
            live = QPushButton(QIcon.fromTheme("camera-video"), "Touch Bar in diretta…")
            live.setToolTip("Immagine della barra in tempo reale, cattura PNG e video")
            live.clicked.connect(open_live)
            top.addWidget(live)
        lay.addLayout(top)

        # --- aspetto
        look = QGroupBox("Aspetto")
        form = QFormLayout(look)
        self.theme = self._combo(F.THEMES + [(pid, p[0]) for pid, p in F.PRESETS.items()])
        self.row = self._combo(F.ROWS)
        self.unit = self._combo(F.UNITS)
        self.anim = QCheckBox("Animazione con il logo all'avvio del renderer")
        form.addRow("Tema", self.theme)
        form.addRow("Riga principale", self.row)
        form.addRow("Temperatura in", self.unit)
        form.addRow("", self.anim)
        for w in (self.theme, self.row, self.unit):
            w.currentIndexChanged.connect(self._changed)
        self.anim.toggled.connect(self._changed)
        lay.addWidget(look)

        # --- colori
        self.colors_box = QGroupBox("Colori personalizzati (sopra il tema)")
        self.colors_box.setCheckable(True)
        self.colors_box.toggled.connect(self._changed)
        grid = QGridLayout(self.colors_box)
        self.color_btn = {}
        for i, (key, label) in enumerate(F.COLORS):
            b = QPushButton("—")
            b.setToolTip("Clic: scegli il colore · clic destro: torna a quello del tema")
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            b.setContextMenuPolicy(Qt.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda _p, k=key: self._set_color(k, None))
            b.setMinimumWidth(90)
            grid.addWidget(QLabel(label), i // 2, (i % 2) * 2)   # due colonne: con lo schermo a 1,75x tre non entrano
            grid.addWidget(b, i // 2, (i % 2) * 2 + 1)
            self.color_btn[key] = b
        lay.addWidget(self.colors_box)

        # --- riga extra
        extras = QGroupBox("Riga extra (doppio tocco su Fn, al massimo %d pulsanti)" % F.MAX_EXTRAS)
        el = QGridLayout(extras)
        self.list = QListWidget()
        self.list.setMaximumHeight(220)
        self.list.currentRowChanged.connect(self._select)
        el.addWidget(self.list, 0, 0, 5, 1)
        self.add_btn = QPushButton(QIcon.fromTheme("list-add"), "Aggiungi")
        menu = QMenu(self)
        for icon, (kind, name, _d, _v) in F.ICONS.items():
            act = menu.addAction(("Interruttore: " if kind == "toggle" else "Indicatore: ") + name)
            act.triggered.connect(lambda _=False, i=icon: self._add(i))
        self.add_btn.setMenu(menu)
        self.del_btn = QPushButton(QIcon.fromTheme("list-remove"), "Rimuovi")
        self.up_btn = QPushButton(QIcon.fromTheme("go-up"), "Su")
        self.down_btn = QPushButton(QIcon.fromTheme("go-down"), "Giù")
        self.del_btn.clicked.connect(self._remove)
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn.clicked.connect(lambda: self._move(1))
        for i, b in enumerate((self.add_btn, self.del_btn, self.up_btn, self.down_btn)):
            el.addWidget(b, i, 1)
        note = QLabel("Sulla barra gli interruttori stanno a sinistra dopo Esc (webcam, microfono, VPN) e gli "
                      "indicatori a destra, nell'ordine dell'elenco.")
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        el.addWidget(note, 5, 0, 1, 2)

        self.detail = QGroupBox("Pulsante selezionato")
        dl = QFormLayout(self.detail)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.cmd = QLineEdit()
        self.cmd.setPlaceholderText("comando eseguito al tocco (sh -c)")
        self.stat = QLineEdit()
        self.stat.setPlaceholderText("uscita 0 = pulsante acceso (controllato ogni secondo)")
        self.iface = QLineEdit()
        self.iface.setPlaceholderText("es. wg0, wlan0")
        dl.addRow(self.desc)
        dl.addRow("Comando", self.cmd)
        dl.addRow("Stato", self.stat)
        dl.addRow("Interfaccia", self.iface)
        for w, key in ((self.cmd, "command"), (self.stat, "status"), (self.iface, "interface")):
            w.textEdited.connect(lambda t, k=key: self._edit_field(k, t))
        el.addWidget(self.detail, 6, 0, 1, 2)
        lay.addWidget(extras)

        # --- anteprima
        prev = QGroupBox("Anteprima della riga extra (schematica)")
        self.preview = QHBoxLayout(prev)
        self.preview.setSpacing(3)
        lay.addWidget(prev)

        # --- pulsanti
        bar = QHBoxLayout()
        self.reload_btn = QPushButton(QIcon.fromTheme("document-revert"), "Annulla modifiche")
        self.default_btn = QPushButton(QIcon.fromTheme("edit-undo"), "Configurazione consigliata")
        self.save_btn = QPushButton(QIcon.fromTheme("document-save"), "Salva e applica")
        self.save_btn.setDefault(True)
        self.reload_btn.clicked.connect(self.reload)
        self.default_btn.clicked.connect(self._defaults)
        self.save_btn.clicked.connect(self.save)
        bar.addWidget(self.reload_btn)
        bar.addWidget(self.default_btn)
        bar.addStretch(1)
        bar.addWidget(self.save_btn)
        lay.addLayout(bar)
        lay.addStretch(1)
        self.setWidget(body)
        self.reload()

    # --- utilità -------------------------------------------------------------------------------------
    @staticmethod
    def _combo(pairs):
        c = QComboBox()
        for value, label in pairs:
            c.addItem(label, value)
        return c

    @staticmethod
    def _set_combo(combo, value):
        i = combo.findData(value)
        combo.setCurrentIndex(i if i >= 0 else 0)

    def _dirty(self, on=True):
        self.save_btn.setText("Salva e applica" + (" •" if on else ""))
        self.reload_btn.setEnabled(on)

    # --- caricamento ---------------------------------------------------------------------------------
    def reload(self):
        try:
            self.cfg = F.load()
        except Exception as e:  # noqa: BLE001 (file scritto a mano e non valido)
            QMessageBox.warning(self, "fnstrip", "Non riesco a leggere %s:\n%s\n\nUso la configurazione consigliata; "
                                "salvando, il file attuale resta in config.toml.bak." % (F.CONFIG, e))
            self.cfg = F.defaults()
        self._fill()
        self._dirty(False)

    def _defaults(self):
        self.cfg = F.defaults()
        self._fill()
        self._dirty()

    def _fill(self):
        self.loading = True
        c = self.cfg
        self._set_combo(self.theme, F.preset_of(c) or c.get("theme", "default"))
        self._set_combo(self.row, c.get("default_row", "controls"))
        self._set_combo(self.unit, c.get("temperature_unit", "c"))
        self.anim.setChecked(str(c.get("startup_animation", "on")).lower() not in ("off", "false"))
        colors = c.get("colors") or {}
        self.colors_box.setChecked(bool(colors))
        for k in self.color_btn:
            self._paint_color(k, colors.get(k))
        self._fill_list()
        self.loading = False
        self._update_info()

    def _fill_list(self, select=0):
        self.list.clear()
        for e in self.cfg.get("extras") or []:
            icon = e.get("icon", "?")
            kind, name, _d, _v = F.ICONS.get(icon, ("?", "sconosciuto: " + icon, "", {}))
            it = QListWidgetItem(("⏻  " if kind == "toggle" else "▁▃▆  ") + name)
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(max(0, min(select, self.list.count() - 1)))
        else:
            self._select(-1)
        self.add_btn.setEnabled(self.list.count() < F.MAX_EXTRAS)
        self._preview()

    def _update_info(self):
        from .status import touchbar_renderer
        if touchbar_renderer() == "tiny-dfr":
            self.info.setText("La Touch Bar usa tiny-dfr (Azioni → Renderer): questa configurazione vale per fnstrip. "
                              "tiny-dfr si configura in /etc/tiny-dfr/config.toml (si ricarica da solo).")
        elif not F.installed():
            self.info.setText("⚠ fnstrip non è installato (~/.local/bin/fnstrip): installalo con scripts/install-fnstrip.sh. "
                              "Puoi comunque preparare la configurazione.")
        elif F.renderer_active():
            self.info.setText("Il renderer della Touch Bar è attivo: \"Salva e applica\" lo riavvia e la barra si "
                              "aggiorna in pochi secondi.")
        else:
            self.info.setText("La Touch Bar non è in modalità display: la configurazione si salva e vale quando torni "
                              "alla grafica.")

    # --- modifiche -----------------------------------------------------------------------------------
    def _changed(self, *_):
        if self.loading:
            return
        c = self.cfg
        choice = self.theme.currentData()
        if choice in F.PRESETS:
            if self.sender() is self.theme:  # scelto ora: colori del preset
                F.apply_preset(c, choice)
                self.loading = True
                self.colors_box.setChecked(True)
                for k in self.color_btn:
                    self._paint_color(k, c["colors"].get(k))
                self.loading = False
        else:
            c["theme"] = choice
        c["default_row"] = self.row.currentData()
        c["temperature_unit"] = self.unit.currentData()
        c["startup_animation"] = "on" if self.anim.isChecked() else "off"
        if not self.colors_box.isChecked():
            self._leave_preset()
            c["colors"] = {}
            for k in self.color_btn:
                self._paint_color(k, None)
        self._preview()
        self._dirty()

    def _pick(self, key):
        cur = (self.cfg.get("colors") or {}).get(key) or "#808080"
        col = QColorDialog.getColor(QColor(cur), self, "Colore: " + dict(F.COLORS)[key])
        if col.isValid():
            self._set_color(key, col.name())

    def _leave_preset(self):
        """Un colore cambiato a mano: non è più il preset, il menu mostra il tema di base."""
        pid = self.theme.currentData()
        if pid in F.PRESETS:
            self.loading = True
            self._set_combo(self.theme, F.PRESETS[pid][1])
            self.loading = False

    def _set_color(self, key, value):
        self._leave_preset()
        colors = self.cfg.setdefault("colors", {})
        if value:
            colors[key] = value
        else:
            colors.pop(key, None)
        self._paint_color(key, value)
        self._dirty()

    def _paint_color(self, key, value):
        b = self.color_btn[key]
        if value:
            b.setText(value)
            fg = "#000" if QColor(value).lightness() > 128 else "#fff"
            b.setStyleSheet("background: %s; color: %s;" % (value, fg))
        else:
            b.setText("dal tema")
            b.setStyleSheet("")

    def _add(self, icon):
        ex = self.cfg.setdefault("extras", [])
        if len(ex) >= F.MAX_EXTRAS:
            return
        if icon == "camera" and not os.path.exists("/usr/local/bin/t1-webcam"):
            QMessageBox.information(self, "fnstrip", "t1-webcam non è installato: il pulsante non farà nulla.")
        ex.append(F.new_extra(icon))
        self._fill_list(len(ex) - 1)
        self._dirty()

    def _remove(self):
        r = self.list.currentRow()
        if r >= 0:
            del self.cfg["extras"][r]
            self._fill_list(r)
            self._dirty()

    def _move(self, d):
        r = self.list.currentRow()
        ex = self.cfg.get("extras") or []
        if 0 <= r < len(ex) and 0 <= r + d < len(ex):
            ex[r], ex[r + d] = ex[r + d], ex[r]
            self._fill_list(r + d)
            self._dirty()

    def _select(self, r):
        ex = (self.cfg.get("extras") or []) if self.cfg else []
        ok = 0 <= r < len(ex)
        self.detail.setEnabled(ok)
        self.del_btn.setEnabled(ok)
        self.up_btn.setEnabled(ok and r > 0)
        self.down_btn.setEnabled(ok and r < len(ex) - 1)
        e = ex[r] if ok else {}
        kind, name, desc, defaults = F.ICONS.get(e.get("icon"), ("meter", e.get("icon", ""), "", {}))
        self.desc.setText("<b>%s</b> — %s" % (name, desc) if ok else "Seleziona un pulsante.")
        toggle = kind == "toggle"
        self.cmd.setEnabled(toggle)
        self.stat.setEnabled(toggle)
        self.iface.setEnabled(e.get("icon") in ("vpn", "net"))
        self.cmd.setText(e.get("command", ""))
        self.stat.setText(e.get("status", ""))
        self.iface.setText(e.get("interface", ""))

    def _edit_field(self, key, text):
        r = self.list.currentRow()
        ex = self.cfg.get("extras") or []
        if 0 <= r < len(ex):
            if text.strip():
                ex[r][key] = text
            else:
                ex[r].pop(key, None)
            self._dirty()

    def _preview(self):
        while self.preview.count():
            w = self.preview.takeAt(0).widget()
            if w:
                w.deleteLater()
        mono = (self.cfg or {}).get("theme") == "mono"
        colors = (self.cfg or {}).get("colors") or {}
        plate = colors.get("plate") or ("#3a3a3a" if mono else "#2f3b4c")
        label = colors.get("label") or ("#d0d0d0" if mono else "#ffffff")
        ex = (self.cfg or {}).get("extras") or []
        toggles = sorted((e for e in ex if F.ICONS.get(e.get("icon"), ("",))[0] == "toggle"),
                         key=lambda e: ["camera", "mic", "vpn"].index(e["icon"]) if e["icon"] in ("camera", "mic", "vpn") else 9)
        meters = [e for e in ex if F.ICONS.get(e.get("icon"), ("",))[0] != "toggle"]
        texts = ["esc"] + ["⏻ " + SHORT.get(e["icon"], e["icon"]) for e in toggles] + [None] + \
                ["▁▃▆ " + SHORT.get(e.get("icon"), str(e.get("icon"))) for e in meters]
        for text in texts:
            if text is None:
                self.preview.addStretch(1)
                continue
            lab = QLabel(text)
            lab.setStyleSheet(CHIP % (plate, label))
            self.preview.addWidget(lab)

    # --- salvataggio ---------------------------------------------------------------------------------
    def save(self):
        cfg = copy.deepcopy(self.cfg)
        if not self.colors_box.isChecked():
            cfg["colors"] = {}
        errs = F.validate(cfg)
        if errs:
            QMessageBox.warning(self, "fnstrip", "Da correggere prima di salvare:\n\n" + "\n".join(errs))
            return
        try:
            path = F.save(cfg)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "fnstrip", "Salvataggio non riuscito: %s" % e)
            return
        self.log("fnstrip: salvato %s (precedente in config.toml.bak)" % path)
        restarted, problems = F.restart_renderer()
        if restarted:
            self.log("fnstrip: renderer riavviato")
        else:
            self.log("fnstrip: renderer non attivo, la configurazione vale alla prossima modalità display")
        for p in problems:
            self.log("fnstrip: " + p)
        if problems:
            QMessageBox.warning(self, "fnstrip", "Il renderer segnala problemi nella configurazione:\n\n" +
                                "\n".join(problems[:8]))
        self._dirty(False)
        self._update_info()
