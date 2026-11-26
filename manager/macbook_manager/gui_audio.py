"""Scheda "Audio" di MacBook Manager: preset e personalizzazioni sicure del DSP degli altoparlanti (audio.py).

Ogni modifica si sente subito (pw-cli sul filtro attivo) e viene salvata; lo script di WirePlumber la riapplica quando il
filtro rinasce. Crossover, EQ di Apple, BuzzKill, limitatori e protezione termica restano sempre attivi.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QSlider, QVBoxLayout, QWidget)

from . import theme as T
from . import audio as A


class _Slider:
    """QSlider intero con etichetta del valore: value() e set() nell'unità reale (scala = divisore)."""

    def __init__(self, lo, hi, scale, fmt, step=1):
        self.scale, self.fmt = scale, fmt
        self.w = QSlider(Qt.Horizontal)
        self.w.setRange(int(round(lo * scale)), int(round(hi * scale)))
        self.w.setSingleStep(step)
        self.w.setPageStep(step * 5)
        self.label = QLabel()
        self.label.setMinimumWidth(110)
        self.w.valueChanged.connect(lambda _v: self.label.setText(self.fmt(self.value())))

    def value(self):
        return self.w.value() / self.scale

    def set(self, v):
        self.w.blockSignals(True)
        self.w.setValue(int(round(v * self.scale)))
        self.w.blockSignals(False)
        self.label.setText(self.fmt(self.value()))


def _balance_text(v):
    v = int(v)
    if v == 0:
        return "al centro"
    return ("sinistra %d %%" if v < 0 else "destra %d %%") % abs(v)


class AudioTab(QWidget):
    def __init__(self, log):
        super().__init__()
        self.log = log
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        intro = QLabel(
            "<b>Altoparlanti</b>: 2 tweeter e 2 woofer, con l'elaborazione di Apple (crossover, equalizzazione, "
            "compressori, limitatori, protezione termica) e, se vuoi, i bassi psicoacustici di Asahi Linux. "
            "Le modifiche si sentono subito e restano salvate. Valgono solo per gli altoparlanti: le cuffie non hanno "
            "elaborazione.")
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.RichText)
        lay.addWidget(intro)
        self.state = QLabel()
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.RichText)
        lay.addWidget(self.state)

        # preset
        pbox = QGroupBox("Preset")
        pl = QVBoxLayout(pbox)
        self.preset = QComboBox()
        for pid, name, _d, _v in A.PRESETS:
            self.preset.addItem(name, pid)
        self.preset.addItem("Personalizzato", "custom")
        self.preset.currentIndexChanged.connect(self._preset_chosen)
        pl.addWidget(self.preset)
        self.pdesc = QLabel()
        self.pdesc.setWordWrap(True)
        pl.addWidget(self.pdesc)
        lay.addWidget(pbox)

        # bassi
        self.bbox = QGroupBox("Bassi psicoacustici (bankstown)")
        g = QGridLayout(self.bbox)
        self.bass = QCheckBox("Attivi")
        g.addWidget(self.bass, 0, 0, 1, 3)
        self.amount = _Slider(*A.AMOUNT, 100, lambda v: "%.2f" % v, step=5)
        self.freq = _Slider(*A.FREQ, 1, lambda v: "%d Hz" % v, step=5)
        self.char = _Slider(*A.CHARACTER, 100, lambda v: "%d %%" % round(v * 100), step=5)
        rows = [("Intensità", self.amount, "quanto si sentono le armoniche dei bassi (1,45 = Asahi 14\")"),
                ("Frequenza", self.freq, "fin dove arrivano i bassi da rinforzare: più bassa = basso più profondo"),
                ("Carattere", self.char, "0 % morbido e caldo, 100 % deciso e definito")]
        for i, (name, sl, tip) in enumerate(rows, 1):
            lab = QLabel(name)
            lab.setToolTip(tip)
            sl.w.setToolTip(tip)
            g.addWidget(lab, i, 0)
            g.addWidget(sl.w, i, 1)
            g.addWidget(sl.label, i, 2)
        lay.addWidget(self.bbox)

        # livello e bilanciamento
        lbox = QGroupBox("Livello e bilanciamento")
        g = QGridLayout(lbox)
        self.level = _Slider(*A.LEVEL_DB, 10, lambda v: "%.1f dB" % v if v < 0 else "fabbrica (0 dB)")
        self.balance = _Slider(*A.BALANCE, 1, _balance_text, step=5)
        for i, (name, sl, tip) in enumerate([
                ("Livello massimo", self.level,
                 "abbassa allo stesso modo tutti e quattro gli altoparlanti: utile se distorcono o si interrompono "
                 "ad alto volume. Non si può alzare oltre la fabbrica."),
                ("Bilanciamento", self.balance,
                 "abbassa il lato opposto fino a 12 dB (utile anche se un lato è danneggiato)")]):
            lab = QLabel(name)
            lab.setToolTip(tip)
            sl.w.setToolTip(tip)
            g.addWidget(lab, i, 0)
            g.addWidget(sl.w, i, 1)
            g.addWidget(sl.label, i, 2)
        lay.addWidget(lbox)

        # dinamica
        dbox = QGroupBox("Dinamica")
        dl = QVBoxLayout(dbox)
        self.loud = QCheckBox("Compensazione dei bassi a basso volume (Loudness)")
        self.loud.setToolTip("Sotto metà volume aggiunge bassi e un po' di acuti, che l'orecchio perde per primi.")
        self.comp = QCheckBox("Compressione dinamica (alza i passaggi piano, separa bassi e voce)")
        self.comp.setToolTip("Compressori Mozart e DualBand di Apple. Spenta: dinamica più naturale, parlato meno "
                             "intelligibile a basso volume.")
        dl.addWidget(self.loud)
        dl.addWidget(self.comp)
        lay.addWidget(dbox)

        safe = QLabel("<b>Sempre attivi</b> (non modificabili): crossover tweeter/woofer, equalizzazione di Apple, "
                      "filtro anti-vibrazioni BuzzKill, limitatori e protezione termica degli altoparlanti.")
        safe.setWordWrap(True)
        safe.setTextFormat(Qt.RichText)
        lay.addWidget(safe)
        lay.addStretch(1)

        bar = QHBoxLayout()
        self.reset_btn = QPushButton(QIcon.fromTheme("edit-undo"), "Ripristina consigliato")
        self.reset_btn.clicked.connect(lambda: self._load(A.BY_PRESET["bass"][3], apply=True))
        self.refresh_btn = QPushButton(QIcon.fromTheme("view-refresh"), "Aggiorna stato")
        self.refresh_btn.clicked.connect(self.sync)
        bar.addWidget(self.refresh_btn)
        bar.addStretch(1)
        bar.addWidget(self.reset_btn)
        outer.addLayout(bar)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._apply)
        for sl in (self.amount, self.freq, self.char, self.level, self.balance):
            sl.w.valueChanged.connect(self._changed)
        for cb in (self.bass, self.loud, self.comp):
            cb.toggled.connect(self._changed)
        self.loading = False
        self.settings = None

    # --- stato -------------------------------------------------------------------------------------
    def sync(self):
        """All'apertura della scheda: stato del DSP e impostazioni salvate (o il preset consigliato)."""
        nid, vals = A.node_info()
        bank = A.has_bankstown(vals)
        if not A.installed():
            txt = ("<span style='color:" + T.c("warn") + "'>DSP degli altoparlanti non installato.</span> "
                   "Installalo con <code>sudo scripts/install-audio-dsp.sh</code> (o <code>install.sh</code>).")
        elif nid is None:
            txt = ("<span style='color:" + T.c("warn") + "'>Filtro non attivo</span>: cuffie collegate, oppure l'audio non è "
                   "ancora partito. Le impostazioni si possono preparare e valgono quando torna.")
        else:
            txt = "<span style='color:" + T.c("ok") + "'>Filtro attivo</span> (\"MacBook Pro 14,3 Speakers\")."
        if A.installed() and not bank:
            txt += " Questa versione del DSP non ha bankstown: aggiorna con <code>sudo scripts/install-audio-dsp.sh</code>."
        self.state.setText(txt)
        self.bbox.setEnabled(bank)
        if self.settings is None:
            saved = A.load()
            self._load(saved if saved else A.BY_PRESET["bass" if bank else "factory"][3], apply=False)

    def _load(self, s, apply):
        s = A.sanitize(s)
        self.loading = True
        self.bass.setChecked(s["bass"])
        self.amount.set(s["bass_amount"])
        self.freq.set(s["bass_freq"])
        self.char.set(s["bass_character"])
        self.level.set(s["level_db"])
        self.balance.set(s["balance"])
        self.loud.setChecked(s["loudness"])
        self.comp.setChecked(s["compression"])
        self.loading = False
        self.settings = s
        self._show_preset(A.preset_of(s))
        if apply:
            self._apply()

    def _show_preset(self, pid):
        self.preset.blockSignals(True)
        self.preset.setCurrentIndex(max(0, self.preset.findData(pid)))
        self.preset.blockSignals(False)
        self.pdesc.setText(A.BY_PRESET[pid][2] if pid in A.BY_PRESET else
                           "Impostazioni scelte da te (sempre dentro i limiti sicuri).")
        for w in (self.amount.w, self.freq.w, self.char.w):
            w.setEnabled(self.bass.isChecked())

    def _current(self):
        s = dict(self.settings or A.DEFAULTS)
        s.update(bass=self.bass.isChecked(), bass_amount=self.amount.value(), bass_freq=self.freq.value(),
                 bass_character=self.char.value(), level_db=self.level.value(), balance=self.balance.value(),
                 loudness=self.loud.isChecked(), compression=self.comp.isChecked())
        return A.sanitize(s)

    # --- modifiche ---------------------------------------------------------------------------------
    def _preset_chosen(self, _i):
        pid = self.preset.currentData()
        if pid in A.BY_PRESET:
            self._load(A.BY_PRESET[pid][3], apply=True)
        else:
            self._show_preset("custom")

    def _changed(self, *_a):
        if self.loading:
            return
        self.settings = self._current()
        self._show_preset(A.preset_of(self.settings))
        self.timer.start()

    def _apply(self):
        s = A.save(self._current())
        self.settings = s
        ok, msg = A.apply_live(s)
        name = A.BY_PRESET.get(A.preset_of(s), (None, "personalizzato"))[1]
        self.log("Audio (%s): %s" % (name, msg if ok else "salvato; " + msg))
