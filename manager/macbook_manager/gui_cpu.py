"""Scheda "CPU" di MacBook Manager e riquadro delle regole energetiche (alimentatore / batteria) usato anche dalla
scheda GPU. Le regole sono in power.py; ogni scelta esegue un'azione root fissa (password con polkit)."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QComboBox, QGridLayout, QGroupBox, QLabel, QScrollArea, QVBoxLayout, QWidget)

from . import power as P
from .actions import BY_ID, available


class RulesBox(QGroupBox):
    """Griglia: una riga per regola, una colonna per alimentatore e batteria; la colonna attiva è evidenziata."""

    def __init__(self, title, tab, run_action, note=""):
        super().__init__(title)
        self.run_action = run_action
        g = QGridLayout(self)
        self.heads = {}
        for c, (side, text) in enumerate(P.SIDES, 1):
            h = QLabel("<b>%s</b>" % text)
            g.addWidget(h, 0, c)
            self.heads[side] = h
        self.combos = {}
        row = 1
        for key, t, label, expl, options, _d, sides in P.SETTINGS:
            if t != tab:
                continue
            lab = QLabel(label)
            lab.setToolTip(expl)
            g.addWidget(lab, row, 0)
            for c, (side, _text) in enumerate(P.SIDES, 1):
                if side not in sides:
                    na = QLabel("automatica, profilo giochi" if key == "RADEON_MODE" else "-")
                    na.setStyleSheet("color: palette(placeholder-text);")
                    g.addWidget(na, row, c)
                    continue
                cb = QComboBox()
                cb.setToolTip(expl)
                for value, text in options:
                    cb.addItem(text, value)
                cb.currentIndexChanged.connect(lambda _i, s=side, k=key, w=cb: self._chosen(s, k, w))
                g.addWidget(cb, row, c)
                self.combos[(side, key)] = cb
            row += 1
        g.setColumnStretch(1, 1)
        g.setColumnStretch(2, 1)
        if note:
            n = QLabel(note)
            n.setWordWrap(True)
            n.setStyleSheet("color: palette(placeholder-text);")
            g.addWidget(n, row, 0, 1, 3)
        self.sync()

    def sync(self):
        src = P.source()
        for side, h in self.heads.items():
            h.setText("<b>%s</b>%s" % (dict(P.SIDES)[side], "  ← adesso" if side == src else ""))
        for (side, key), cb in self.combos.items():
            cb.blockSignals(True)
            cb.setCurrentIndex(max(0, cb.findData(P.current(side, key))))
            a = BY_ID.get(P.action_id(side, key, P.current(side, key)))
            cb.setEnabled(bool(a and available(a)))
            cb.blockSignals(False)

    def _chosen(self, side, key, cb):
        aid = P.action_id(side, key, cb.currentData())
        if aid in BY_ID:
            self.run_action(aid)


class CpuTab(QWidget):
    def __init__(self, log, run_action):
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

        sbox = QGroupBox("Intel Core i7-7820HQ, adesso")
        g = QGridLayout(sbox)
        self.vals = {}
        for i, (k, name) in enumerate([("freq", "Frequenza"), ("temp", "Temperatura"), ("power", "Potenza del package"),
                                       ("fans", "Ventole"), ("turbo", "Turbo / frequenza massima"),
                                       ("profile", "Profilo / EPP"), ("limits", "Limite di potenza / tetto"),
                                       ("throttle", "Limitazione termica del firmware")]):
            lab = QLabel(name)
            lab.setStyleSheet("color: palette(placeholder-text);")
            val = QLabel("-")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            g.addWidget(lab, i // 2, (i % 2) * 2)
            g.addWidget(val, i // 2, (i % 2) * 2 + 1)
            self.vals[k] = val
        g.setColumnStretch(1, 1)
        g.setColumnStretch(3, 1)
        lay.addWidget(sbox)

        self.rules = RulesBox("Regole automatiche", "cpu", run_action,
                              "Si applicano da sole quando colleghi o stacchi l'alimentatore (anche dopo il riavvio e la "
                              "sospensione); quelle della colonna \"adesso\" valgono subito. Ogni cambio chiede la "
                              "password di amministratore (ricordata qualche minuto). Passa col mouse sui nomi per la "
                              "spiegazione.")
        lay.addWidget(self.rules)

        tips = QLabel(
            "<b>Combinazioni utili.</b> Prestazioni massime: turbo acceso, 100 %, profilo prestazioni, limite del "
            "firmware. Silenzioso e fresco: tetto a 85 °C oppure limite di 25-35 W. Massima autonomia: turbo spento, "
            "profilo risparmio, limite di 15 W (lento sotto carico).")
        tips.setWordWrap(True)
        tips.setTextFormat(Qt.RichText)
        lay.addWidget(tips)
        lay.addStretch(1)

        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._tick)

    def showEvent(self, e):
        super().showEvent(e)
        self.sync()
        self.timer.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def sync(self):
        self.rules.sync()
        self._tick()

    def _tick(self):
        n, s = P.cpu_now(), P.cpu_state()
        v = self.vals
        v["freq"].setText("%.2f GHz in media, %.2f GHz il core più veloce" % (n["freq_avg"], n["freq_max"])
                          if n["freq_avg"] else "-")
        t = n["temp"]
        v["temp"].setText(("%.0f °C" % t if t is not None else "-") +
                          ("  <span style='color:#d29922'>calda</span>" if t and t >= 90 else ""))
        v["temp"].setTextFormat(Qt.RichText)
        v["power"].setText("%.1f W" % s["package_w"] if s.get("package_w") is not None else
                           "- (servizio macbookpro14-3-cpu-limit non attivo)")
        v["fans"].setText(" / ".join("%d" % f for f in n["fans"]) + " giri/min" if n["fans"] else "-")
        ghz = P.MAX_GHZ * int(n["max_pct"] or 100) / 100
        if n["no_turbo"]:
            ghz = min(ghz, 2.9)
        v["turbo"].setText("%s, massimo %s %% (≈ %.1f GHz)" % ("spento" if n["no_turbo"] else "acceso",
                                                               n["max_pct"] or "-", ghz))
        v["profile"].setText("%s / %s" % (n["profile"] or "-", n["epp"] or "-"))
        lim = "%.0f W" % n["pl1_w"] if n["pl1_w"] else "-"
        if s.get("limit"):
            lim += ", tetto %d °C%s" % (s["limit"], " (sta limitando: %d %%)" % s["target"] if s.get("throttling")
                                        else "")
        else:
            lim += ", nessun tetto"
        v["limits"].setText(lim)
        v["throttle"].setText("%d volte da quando è acceso" % n["throttle_count"])
