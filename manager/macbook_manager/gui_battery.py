"""Scheda "Batteria" di MacBook Manager: grafico dal vivo di carica e potenza, sessioni a batteria e report (battery.py).

Il grafico è disegnato con QPainter (niente QtCharts): carica in alto, potenza in basso sulla stessa scala dei tempi, fasce
verdi con l'alimentatore, grigie in sospensione, linee tratteggiate ai riavvii, la Radeon dal registratore se c'è, e un
puntatore che mostra i valori sotto il mouse. Si aggiorna ogni minuto mentre la scheda è aperta.
"""
import statistics as st
import time

from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QSizePolicy, QSplitter, QTableWidget, QTableWidgetItem,
                               QTextBrowser, QVBoxLayout, QWidget)

from . import battery as B

BLUE, ORANGE, GREEN, GRAY = QColor("#2a78d6"), QColor("#eb6834"), QColor(46, 160, 67, 40), QColor(140, 140, 140, 55)
RANGES = [("4 ore", 4 * 3600), ("Oggi", None), ("24 ore", 86400), ("7 giorni", 7 * 86400)]
SMOOTH = [("1 min", 60), ("5 min", 300), ("15 min", 900)]


class _Sig(QObject):
    done = Signal(object)


class _Load(QRunnable):
    def __init__(self, fn, sig):
        super().__init__()
        self.fn, self.sig = fn, sig

    def run(self):
        try:
            val = self.fn()
        except Exception as e:  # noqa: BLE001
            val = e
        try:
            self.sig.done.emit(val)
        except RuntimeError:
            pass


def _smooth(points, window):
    """Medie su finestre di `window` secondi: [(t, v)]."""
    if not points:
        return []
    out, bucket, start = [], [], points[0][0]
    for t, v in points:
        if t - start >= window and bucket:
            out.append((start + window / 2, st.mean(bucket)))
            bucket, start = [], t
        bucket.append(v)
    if bucket:
        out.append((start + min(window, points[-1][0] - start) / 2, st.mean(bucket)))
    return out


class Chart(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.data = None
        self.mouse_x = None

    def set_data(self, d):
        self.data = d
        self.update()

    def leaveEvent(self, _e):
        self.mouse_x = None
        self.update()

    def mouseMoveEvent(self, e):
        self.mouse_x = e.position().x()
        self.update()

    def _geom(self):
        w, h = self.width(), self.height()
        left, right = 46, 12
        top_c = QRectF(left, 8, w - left - right, h * 0.50)
        top_p = QRectF(left, h * 0.50 + 30, w - left - right, h * 0.50 - 52)
        return top_c, top_p

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        ink = pal.color(pal.ColorRole.WindowText)
        muted = QColor(ink)
        muted.setAlpha(140)
        grid = QColor(ink)
        grid.setAlpha(30)
        f = QFont(self.font())
        f.setPointSizeF(max(7.5, f.pointSizeF() - 1))
        p.setFont(f)
        d = self.data
        rc, rp = self._geom()
        if not d or not d["charge"]:
            p.setPen(muted)
            p.drawText(self.rect(), Qt.AlignCenter, "Lettura della cronologia della batteria…" if d is None else
                       "Nessun dato nel periodo scelto")
            return
        t0, t1 = d["t0"], d["t1"]
        span = max(t1 - t0, 60)
        X = lambda t: rc.left() + (t - t0) / span * rc.width()  # noqa: E731
        pmax = max(35.0, max((v for _t, v in d["power"]), default=0) * 1.1)
        Yc = lambda v: rc.top() + (100 - v) / 100 * rc.height()  # noqa: E731
        Yp = lambda v: rp.top() + (pmax - v) / pmax * rp.height()  # noqa: E731

        # fasce: alimentatore, sospensioni
        for rect in (rc, rp):
            for (a, b), col in [(x, GREEN) for x in d["ac"]] + [(x, GRAY) for x in d["suspends"]]:
                xa, xb = max(X(a), rect.left()), min(X(b), rect.right())
                if xb > xa:
                    p.fillRect(QRectF(xa, rect.top(), xb - xa, rect.height()), col)
        # griglia e assi
        p.setPen(QPen(grid, 1))
        for v in (0, 25, 50, 75, 100):
            p.drawLine(QPointF(rc.left(), Yc(v)), QPointF(rc.right(), Yc(v)))
        step = 5 if pmax <= 40 else 10
        for v in range(0, int(pmax) + 1, step):
            p.drawLine(QPointF(rp.left(), Yp(v)), QPointF(rp.right(), Yp(v)))
        p.setPen(muted)
        for v in (0, 50, 100):
            p.drawText(QRectF(0, Yc(v) - 8, rc.left() - 6, 16), Qt.AlignRight | Qt.AlignVCenter, "%d%%" % v)
        for v in range(0, int(pmax) + 1, step * 2):
            p.drawText(QRectF(0, Yp(v) - 8, rp.left() - 6, 16), Qt.AlignRight | Qt.AlignVCenter, "%d W" % v)
        p.drawText(QRectF(rc.left() + 4, rc.top(), 200, 16), Qt.AlignLeft, "Carica")
        p.drawText(QRectF(rp.left() + 4, rp.top() - 18, 400, 16), Qt.AlignLeft,
                   "Potenza assorbita (media su %s)%s" % (d["smooth_label"],
                                                          "  ·  arancione: Radeon" if d["radeon"] else ""))
        # tacche orarie
        hours = span / 3600
        tick = 3600 if hours <= 8 else (3 * 3600 if hours <= 30 else 86400)
        lt = time.localtime(t0)
        if tick < 86400:  # prima ora intera dopo t0, multipla di tick
            first = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, 0, 0, 0, 0, -1)) + 3600
            while time.localtime(first).tm_hour % (tick // 3600):
                first += 3600
        else:  # mezzanotte successiva
            first = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) + 86400
        t = first
        while t < t1:
            x = X(t)
            p.setPen(QPen(grid, 1))
            p.drawLine(QPointF(x, rc.top()), QPointF(x, rp.bottom()))
            p.setPen(muted)
            p.drawText(QRectF(x - 40, rp.bottom() + 3, 80, 16), Qt.AlignHCenter,
                       time.strftime("%d/%m" if tick >= 86400 else "%H:%M", time.localtime(t)))
            t += tick
        # riavvii
        p.setPen(QPen(muted, 1, Qt.DashLine))
        for b in d["boots"]:
            if t0 <= b <= t1:
                p.drawLine(QPointF(X(b), rc.top()), QPointF(X(b), rp.bottom()))
        # curve (interrotte dove mancano dati per più di 10 minuti)

        def curve(pts, fy, color, width, fill_rect=None, dash=False):
            segs, cur, last = [], [], None
            for t, v in pts:
                if last is not None and t - last > 600:
                    segs.append(cur)
                    cur = []
                cur.append((X(t), fy(v)))
                last = t
            segs.append(cur)
            for seg in segs:
                if len(seg) < 2:
                    continue
                path = QPainterPath(QPointF(*seg[0]))
                for x, y in seg[1:]:
                    path.lineTo(x, y)
                if fill_rect is not None:
                    area = QPainterPath(path)
                    area.lineTo(seg[-1][0], fill_rect.bottom())
                    area.lineTo(seg[0][0], fill_rect.bottom())
                    area.closeSubpath()
                    c = QColor(color)
                    c.setAlpha(28)
                    p.fillPath(area, c)
                p.setPen(QPen(color, width, Qt.DashLine if dash else Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPath(path)

        curve(d["charge"], Yc, BLUE, 2, fill_rect=rc)
        curve(d["power"], Yp, BLUE, 1.6)
        if d["radeon"]:
            curve(d["radeon"], Yp, ORANGE, 1.4, dash=True)
        # puntatore
        if self.mouse_x is not None and rc.left() <= self.mouse_x <= rc.right():
            tm = t0 + (self.mouse_x - rc.left()) / rc.width() * span
            near = lambda pts: min(pts, key=lambda q: abs(q[0] - tm)) if pts else None  # noqa: E731
            c, w, r = near(d["charge"]), near(d["power"]), near(d["radeon"])
            p.setPen(QPen(ink, 1))
            p.drawLine(QPointF(self.mouse_x, rc.top()), QPointF(self.mouse_x, rp.bottom()))
            lines = [time.strftime("%d/%m %H:%M", time.localtime(tm))]
            if c and abs(c[0] - tm) < 1800:
                lines.append("carica %.0f %%" % c[1])
            if w and abs(w[0] - tm) < 1800:
                lines.append("potenza %.1f W" % w[1])
            if r and abs(r[0] - tm) < 1800:
                lines.append("Radeon %.1f W" % r[1])
            for a, b in d["ac"]:
                if a <= tm <= b:
                    lines.append("alimentatore collegato")
            for a, b in d["suspends"]:
                if a <= tm <= b:
                    lines.append("in sospensione")
            fm = p.fontMetrics()
            bw = max(fm.horizontalAdvance(s) for s in lines) + 14
            bh = fm.height() * len(lines) + 10
            bx = self.mouse_x + 10 if self.mouse_x + 10 + bw < self.width() else self.mouse_x - 10 - bw
            box = QRectF(bx, rc.top() + 6, bw, bh)
            bg = pal.color(pal.ColorRole.Base)
            bg.setAlpha(235)
            p.setPen(QPen(grid, 1))
            p.setBrush(bg)
            p.drawRoundedRect(box, 4, 4)
            p.setPen(ink)
            for i, s in enumerate(lines):
                p.drawText(QPointF(box.left() + 7, box.top() + 5 + fm.ascent() + i * fm.height()), s)


class _Tile(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        t = QLabel(title)
        t.setStyleSheet("color: palette(placeholder-text); font-size: 9pt;")
        self.value = QLabel("-")
        self.value.setStyleSheet("font-size: 15pt; font-weight: 600;")
        self.sub = QLabel("")
        self.sub.setStyleSheet("color: palette(placeholder-text); font-size: 8.5pt;")
        for w in (t, self.value, self.sub):
            lay.addWidget(w)

    def set(self, value, sub=""):
        self.value.setText(value)
        self.sub.setText(sub)


class BatteryTab(QWidget):
    def __init__(self, log):
        super().__init__()
        self.log = log
        self.pool = QThreadPool.globalInstance()
        self.sig = _Sig()
        self.sig.done.connect(self._loaded)
        self.busy = False
        self.reports = []
        self.last = None
        lay = QVBoxLayout(self)

        tiles = QGridLayout()
        self.t_pct, self.t_now, self.t_hour = _Tile("Carica"), _Tile("Potenza ora"), _Tile("Media ultima ora")
        self.t_left, self.t_health, self.t_temp = _Tile("Autonomia stimata"), _Tile("Salute"), _Tile("Temperature")
        for i, t in enumerate([self.t_pct, self.t_now, self.t_hour, self.t_left, self.t_health, self.t_temp]):
            tiles.addWidget(t, 0, i)
        lay.addLayout(tiles)

        bar = QHBoxLayout()
        self.range_group = QButtonGroup(self)
        for i, (name, _s) in enumerate(RANGES):
            b = QPushButton(name)
            b.setCheckable(True)
            b.setChecked(i == 0)
            self.range_group.addButton(b, i)
            bar.addWidget(b)
        self.range_group.idClicked.connect(lambda _i: self.refresh())
        bar.addSpacing(12)
        bar.addWidget(QLabel("Media su"))
        self.smooth = QComboBox()
        for name, sec in SMOOTH:
            self.smooth.addItem(name, sec)
        self.smooth.setCurrentIndex(1)
        self.smooth.currentIndexChanged.connect(lambda _i: self._draw())
        bar.addWidget(self.smooth)
        bar.addStretch(1)
        self.png_btn = QPushButton(QIcon.fromTheme("image-x-generic"), "Salva grafico PNG")
        self.png_btn.clicked.connect(self._save_png)
        bar.addWidget(self.png_btn)
        lay.addLayout(bar)

        split = QSplitter(Qt.Vertical)
        self.chart = Chart()
        split.addWidget(self.chart)
        low = QWidget()
        ll = QVBoxLayout(low)
        ll.setContentsMargins(0, 0, 0, 0)
        logrow = QHBoxLayout()
        self.logger = QLabel()
        self.logger.setWordWrap(True)
        logrow.addWidget(self.logger, 1)
        self.logger_btn = QPushButton(QIcon.fromTheme("media-record"), "Attiva registratore")
        self.logger_btn.clicked.connect(self._enable_logger)
        logrow.addWidget(self.logger_btn)
        ll.addLayout(logrow)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Sessione a batteria", "Durata", "Carica", "Media", "Autonomia", "Fattori"])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._show_report)
        ll.addWidget(self.table, 1)
        self.report = QTextBrowser()
        ll.addWidget(self.report, 1)
        rb = QHBoxLayout()
        rb.addStretch(1)
        self.copy_btn = QPushButton(QIcon.fromTheme("edit-copy"), "Copia report")
        self.copy_btn.clicked.connect(self._copy)
        self.html_btn = QPushButton(QIcon.fromTheme("text-html"), "Esporta HTML")
        self.html_btn.clicked.connect(self._export_html)
        rb.addWidget(self.copy_btn)
        rb.addWidget(self.html_btn)
        ll.addLayout(rb)
        split.addWidget(low)
        split.setSizes([360, 320])
        lay.addWidget(split, 1)

        self.timer = QTimer(self)
        self.timer.setInterval(60000)
        self.timer.timeout.connect(self.refresh)

    # --- caricamento -----------------------------------------------------------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        self.timer.start()
        self.refresh()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.timer.stop()

    def _span(self):
        name, sec = RANGES[max(0, self.range_group.checkedId())]
        if sec is None:
            lt = time.localtime()
            t0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
            return t0, time.time()
        return time.time() - sec, time.time()

    def refresh(self):
        if self.busy:  # un clic durante un caricamento: si ricarica appena finisce
            self.pending = True
            return
        self.busy, self.pending = True, False
        t0, t1 = self._span()
        with_reports = not self.reports or time.time() - getattr(self, "_rep_t", 0) > 300

        def work():
            span = max(t1 - t0, 3600) + 3600
            charge, rate = B.upower_history("charge", span), B.upower_history("rate", span)
            ev = B.events(t0 - 3600)
            res = {"t0": t0, "t1": t1, "charge_all": charge, "rate_all": rate, "ev": ev,
                   "samples": B.load_samples(t0, t1), "now": B.now(), "logger": B.logger_state()}
            if with_reports:
                res["reports"] = B.all_reports(60)
            return res

        self.pool.start(_Load(work, self.sig))

    def _loaded(self, res):
        self.busy = False
        if getattr(self, "pending", False):
            QTimer.singleShot(0, self.refresh)
        if isinstance(res, Exception):
            self.log("Batteria: %s" % res)
            return
        self.last = res
        if "reports" in res:
            self.reports = res["reports"]
            self._rep_t = time.time()
            self._fill_table()
        self._tiles()
        self._draw()
        self._logger_line()

    # --- indicatori --------------------------------------------------------------------------------------
    def _tiles(self):
        n, rate = self.last["now"], self.last["rate_all"]
        state = "in carica" if n["status"] == "Charging" else ("piena" if n["status"] == "Full" else
                                                               ("a batteria" if not n["ac"] else n["status"].lower()))
        self.t_pct.set("%.0f %%" % n["pct"] if n["pct"] is not None else "-",
                       "%s, %.1f Wh" % (state, n["energy_wh"]) if n["energy_wh"] else state)
        self.t_now.set("%.1f W" % n["power_w"] if n["power_w"] is not None else "-",
                       "in ingresso" if n["ac"] and n["status"] == "Charging" else ("" if n["ac"] else "in uscita"))
        hour = B.recent_power(rate, 60)
        self.t_hour.set("%.1f W" % hour if hour else "-", "a batteria" if hour else "nessuna scarica nell'ultima ora")
        if not n["ac"] and n["time_to_empty"]:
            self.t_left.set(B.hm(n["time_to_empty"] / 60), "secondo UPower")
        elif n["ac"] and n["time_to_full"]:
            self.t_left.set(B.hm(n["time_to_full"] / 60), "alla carica completa")
        else:
            ref = hour or (self.reports[0]["avg_w"] if self.reports and self.reports[0].get("avg_w") else None)
            self.t_left.set(B.hm(n["full_wh"] / ref * 60) if ref and n["full_wh"] else "-",
                            "con la batteria piena" if ref else "")
        self.t_health.set("%.0f %%" % n["health"] if n["health"] else "-",
                          "%d cicli, %.0f/%.0f Wh" % (n["cycles"] or 0, n["full_wh"] or 0, n["design_wh"] or 0))
        cpu = B._cpu_temp()
        self.t_temp.set("%.0f °C" % n["temp"] if n["temp"] else "-",
                        "batteria; CPU %s °C" % cpu if cpu != "" else "batteria")

    def _draw(self):
        if not self.last:
            return
        r = self.last
        t0, t1 = r["t0"], r["t1"]
        win = self.smooth.currentData()
        charge = [(t, v) for t, v, _s in r["charge_all"] if t0 - 300 <= t <= t1]
        rate = [(t, v) for t, v, s in r["rate_all"] if t0 - 300 <= t <= t1 and v > 0.3]
        radeon = [(s["ts"], s["radeon_w"]) for s in r["samples"] if s.get("radeon_w") is not None]
        sus = [(a, b) for a, b in r["ev"]["suspends"] if b >= t0 and a <= t1]
        self.chart.set_data({
            "t0": t0, "t1": t1, "charge": charge, "power": _smooth(rate, win),
            "radeon": _smooth(radeon, win) if radeon else [],
            "ac": [(a, b) for a, b in B.ac_bands(r["charge_all"]) if b >= t0 and a <= t1],
            "suspends": sus, "boots": r["ev"]["boots"], "smooth_label": self.smooth.currentText(),
        })

    def _logger_line(self):
        active, last, total = self.last["logger"]
        if active:
            ago = "ultimo campione %s" % (time.strftime("%H:%M", time.localtime(last)) if last else "-")
            self.logger.setText("Registratore attivo: un campione al minuto (%d finora, %s). I report delle sessioni "
                                "includono Radeon, luminosità, audio, Touch Bar e app più pesanti." % (total, ago))
            self.logger_btn.hide()
        else:
            self.logger.setText("Registratore spento: grafico e sessioni vengono da UPower, ma senza i fattori che "
                                "spiegano i consumi.")
            self.logger_btn.show()

    # --- sessioni ------------------------------------------------------------------------------------------
    def _fill_table(self):
        sel = self.table.currentRow()
        self.table.setRowCount(len(self.reports))
        for i, r in enumerate(self.reports):
            when = "%s → %s%s" % (time.strftime("%d/%m %H:%M", time.localtime(r["start"])),
                                  time.strftime("%H:%M", time.localtime(r["end"])), "" if r["closed"] else " (in corso)")
            vals = [when, B.hm(r["duration_min"]), "%.0f → %.0f %%" % (r["start_pct"], r["end_pct"]),
                    "%.1f W" % r["avg_w"] if r["avg_w"] else "-",
                    B.hm(r["projected_h"] * 60) if r["projected_h"] else "-",
                    "sì" if r.get("factors") else "no"]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j in (1, 3, 4):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, j, it)
        if self.reports:
            self.table.selectRow(sel if 0 <= sel < len(self.reports) else 0)

    def _selected(self):
        i = self.table.currentRow()
        return (self.reports[i], self.reports[i + 1:]) if 0 <= i < len(self.reports) else (None, [])

    def _show_report(self):
        r, prev = self._selected()
        if not r:
            self.report.clear()
            return
        lines = B.report_lines(r, prev[:10])
        html = "<b>%s</b><br>" % lines[0] + "<br>".join(ln.strip().replace("  ", "&nbsp;&nbsp;") for ln in lines[1:])
        self.report.setHtml(html)

    def _copy(self):
        r, prev = self._selected()
        if r:
            QGuiApplication.clipboard().setText("\n".join(B.report_lines(r, prev[:10])))
            self.log("Batteria: report copiato negli appunti")

    def _export_html(self):
        r, prev = self._selected()
        if not r or not self.last:
            return
        name = time.strftime("report-batteria-%Y%m%d-%H%M.html", time.localtime(r["start"]))
        path, _ = QFileDialog.getSaveFileName(self, "Esporta report", name, "HTML (*.html)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(B.html_report(r, prev[:10], self.last["charge_all"], self.last["rate_all"]))
        self.log("Batteria: report salvato in %s" % path)

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salva grafico", time.strftime("batteria-%Y%m%d-%H%M.png"),
                                              "PNG (*.png)")
        if path and self.chart.grab().save(path, "PNG"):
            self.log("Batteria: grafico salvato in %s" % path)

    def _enable_logger(self):
        import subprocess
        r = subprocess.run(["systemctl", "--user", "enable", "--now", "macbook-manager-battery-log.timer"],
                           capture_output=True, text=True)
        self.log("Batteria: registratore %s" % ("attivato" if r.returncode == 0 else
                                                "non attivato: %s (serve scripts/install-manager.sh)" %
                                                (r.stderr or r.stdout).strip()))
        self.refresh()
