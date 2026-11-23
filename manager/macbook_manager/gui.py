"""Finestra e icona nella barra di sistema di MacBook Manager (PySide6)."""
import os
import sys
import time

from PySide6.QtCore import QObject, QProcess, QRunnable, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
                               QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
                               QSystemTrayIcon, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from . import HELPER, VERSION, status
from .actions import ACTIONS, BY_ID, active_ids, available, expand

DOT = {"ok": "#2ea043", "warn": "#d29922", "err": "#f85149", "info": "#8b949e"}
SOCKET = "macbook-manager-%d" % os.getuid()
TRAY_ACTIONS = ["touchbar-display", "touchbar-keyboard", None, "webcam-on", "webcam-off", None, "sleep-deep",
                None, "wifi-reload", "bt-headset"]


class _Signals(QObject):
    done = Signal(str, object)


class Job(QRunnable):
    """Esegue fn() in un thread e consegna il risultato a done(nome, valore) nel thread della GUI."""

    def __init__(self, name, fn, signals):
        super().__init__()
        self.name, self.fn, self.signals = name, fn, signals

    def run(self):
        try:
            val = self.fn()
        except Exception as e:  # noqa: BLE001
            val = e
        try:
            self.signals.done.emit(self.name, val)
        except RuntimeError:  # finestra già chiusa (uscita durante una lettura)
            pass


def _dot(level):
    lab = QLabel("●")
    lab.setStyleSheet("color: %s; font-size: 14pt;" % DOT.get(level, DOT["info"]))
    lab.setFixedWidth(22)
    return lab


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("MacBook Manager")
        self.setWindowIcon(QIcon.fromTheme("computer-laptop"))
        self.resize(760, 680)
        self.pool = QThreadPool.globalInstance()
        self.sig = _Signals()
        self.sig.done.connect(self._job_done)
        self.items, self.busy, self.proc, self.queue, self.last = [], False, None, [], 0.0
        self.action_buttons = {}  # id -> pulsante
        self.active = set()

        central = QWidget()
        lay = QVBoxLayout(central)
        head = QHBoxLayout()
        self.summary = QLabel("Lettura dello stato…")
        self.summary.setStyleSheet("font-size: 12pt; font-weight: 600;")
        head.addWidget(self.summary, 1)
        refresh = QPushButton(QIcon.fromTheme("view-refresh"), "Aggiorna")
        refresh.clicked.connect(lambda: self.refresh(force=True))
        head.addWidget(refresh)
        lay.addLayout(head)

        self.tabs = QTabWidget()
        self.status_box = QWidget()
        self.status_lay = QVBoxLayout(self.status_box)
        self.status_lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.status_box)
        self.tabs.addTab(scroll, QIcon.fromTheme("dialog-information"), "Stato")
        self.tabs.addTab(self._actions_tab(), QIcon.fromTheme("system-run"), "Azioni")
        from .gui_fnstrip import FnstripEditor
        self.fnstrip = FnstripEditor(lambda t: self.log.appendPlainText(t))
        self.tabs.addTab(self.fnstrip, QIcon.fromTheme("input-keyboard"), "Touch Bar")
        self.sleep_table = QTableWidget(0, 6)
        self.sleep_table.setHorizontalHeaderLabels(["Inizio", "Durata", "Modo", "Coperchio", "Batteria", "Risveglio"])
        self.sleep_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.sleep_table.horizontalHeader().setStretchLastSection(True)
        self.sleep_table.verticalHeader().setVisible(False)
        self.sleep_table.setEditTriggers(QTableWidget.NoEditTriggers)
        sleep_tab = QWidget()
        sl = QVBoxLayout(sleep_tab)
        self.sleep_note = QLabel()
        self.sleep_note.setWordWrap(True)
        sl.addWidget(self.sleep_note)
        sl.addWidget(self.sleep_table)
        self.tabs.addTab(sleep_tab, QIcon.fromTheme("system-suspend"), "Sospensioni")
        self.tabs.currentChanged.connect(self._tab_changed)
        lay.addWidget(self.tabs, 1)

        lay.addWidget(QLabel("Registro"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        self.log.setPlaceholderText("L'output delle azioni compare qui. Le azioni di sistema chiedono la password "
                                    "(polkit) e la ricordano per qualche minuto.")
        lay.addWidget(self.log)
        self.setCentralWidget(central)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        self.tray = None
        self.refresh(force=True)

    # --- azioni ------------------------------------------------------------------------------------------
    def _actions_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        groups = {}
        for a in ACTIONS:
            if not available(a):
                continue
            if a["group"] not in groups:
                box = QGroupBox(a["group"])
                grid = QGridLayout(box)
                groups[a["group"]] = (box, grid)
                lay.addWidget(box)
            box, grid = groups[a["group"]]
            b = QPushButton(self._btn_text(a, False))
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            b.setToolTip("Chiede la password di amministratore (polkit)" if a["root"] else "")
            b.clicked.connect(lambda _=False, i=a["id"]: self.run_action(i))
            n = grid.count()
            grid.addWidget(b, n // 2, n % 2)
            self.action_buttons[a["id"]] = b
        lay.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(w)
        return scroll

    @staticmethod
    def _btn_text(a, active):
        return ("✓ " if active else "") + a["label"] + ("  🔒" if a["root"] and not active else "")

    def _update_buttons(self):
        """L'opzione già attiva è spuntata e non cliccabile (anche nel menu dell'icona)."""
        for aid, b in self.action_buttons.items():
            on = aid in self.active
            b.setText(self._btn_text(BY_ID[aid], on))
            b.setEnabled(not on and not self.busy)
        if self.tray:
            self.tray.update_actions(self.active, self.busy)

    def run_action(self, action_id, confirmed=False):
        a = BY_ID[action_id]
        if self.busy:
            QMessageBox.information(self, "MacBook Manager", "Un'altra azione è in corso.")
            return
        if a.get("confirm") and not confirmed and QMessageBox.question(self, a["label"], a["confirm"]) != QMessageBox.Yes:
            return
        self.busy = True
        for b in self.action_buttons.values():
            b.setEnabled(False)
        self.log.appendPlainText("\n▶ %s  (%s)" % (a["label"], time.strftime("%H:%M:%S")))
        if a["root"]:
            self.queue = [["pkexec", HELPER, a["id"]]]
        else:
            self.queue = [expand(s) for s in a["steps"]]
        self.current = a
        self._next_step(0)

    def _next_step(self, rc):
        if rc != 0 or not self.queue:
            self._action_done(rc)
            return
        argv = self.queue.pop(0)
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(
            lambda: self.log.insertPlainText(bytes(self.proc.readAllStandardOutput()).decode(errors="replace")))
        self.proc.finished.connect(lambda code, _st: self._next_step(code))
        self.proc.errorOccurred.connect(lambda e: e == QProcess.FailedToStart and self._next_step(127))
        self.proc.start(argv[0], argv[1:])

    def _action_done(self, rc):
        if rc == 126:
            msg = "annullata (password non inserita)"
        else:
            msg = "fatto" if rc == 0 else "non riuscita (codice %d)" % rc
        self.log.appendPlainText("■ " + msg)
        self.log.ensureCursorVisible()
        self.busy = False
        self._update_buttons()
        if self.tray and rc not in (0, 126):
            self.tray.showMessage("MacBook Manager", "Azione non riuscita: guarda il registro.",
                                  QSystemTrayIcon.Warning, 5000)
        status.invalidate()
        self.refresh(force=True)
        then = getattr(self, "current", {}).get("then") if rc == 0 else None
        if then and then[0] in BY_ID:
            nxt = BY_ID[then[0]]
            if QMessageBox.question(self, nxt["label"], then[1]) == QMessageBox.Yes:
                self.run_action(then[0], confirmed=True)

    # --- stato -------------------------------------------------------------------------------------------
    def refresh(self, force=False):
        # Finestra nascosta: solo il tooltip dell'icona, una lettura al minuto (niente consumi inutili).
        if not force and not self.isVisible() and (self.tray is None or time.monotonic() - self.last < 60):
            return
        self.last = time.monotonic()
        self.pool.start(Job("status", lambda: (status.collect(), active_ids()), self.sig))

    def _tab_changed(self, i):
        w = self.tabs.widget(i)
        if w is self.fnstrip:
            self.fnstrip._update_info()
        elif self.tabs.tabText(i) == "Sospensioni":
            self.load_sleep()

    def load_sleep(self):
        self.sleep_note.setText("Lettura del journal…")
        self.pool.start(Job("sleep", status.sleep_history, self.sig))

    def _job_done(self, name, val):
        if isinstance(val, Exception):
            self.log.appendPlainText("errore in %s: %s" % (name, val))
            return
        if name == "status":
            self.active = val[1]
            self._update_buttons()
            self.show_status(val[0])
        elif name == "sleep":
            self.show_sleep(val)

    def show_status(self, items):
        self.items = items
        while self.status_lay.count() > 1:  # l'ultimo elemento è lo spazio elastico
            w = self.status_lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        boxes = {}
        for it in items:
            if it["group"] not in boxes:
                box = QGroupBox(it["group"])
                grid = QGridLayout(box)
                grid.setColumnStretch(2, 1)
                boxes[it["group"]] = grid
                self.status_lay.insertWidget(self.status_lay.count() - 1, box)
            grid = boxes[it["group"]]
            r = grid.rowCount()
            grid.addWidget(_dot(it["level"]), r, 0)
            lab = QLabel(it["label"])
            lab.setStyleSheet("font-weight: 600;")
            grid.addWidget(lab, r, 1)
            val = QLabel(it["value"])
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            if it["hint"]:
                val.setToolTip(it["hint"])
                lab.setToolTip(it["hint"])
            grid.addWidget(val, r, 2)
            fix = it.get("fix")
            if fix and it["level"] != "ok" and fix in BY_ID and available(BY_ID[fix]):
                b = QPushButton("Spegni ora" if fix == "poweroff" else "Correggi")
                b.setToolTip(BY_ID[fix]["label"])
                b.clicked.connect(lambda _=False, i=fix: self.run_action(i))
                grid.addWidget(b, r, 3)
            if it["level"] in ("warn", "err") and it["hint"]:
                h = QLabel(it["hint"])
                h.setWordWrap(True)
                h.setStyleSheet("color: %s;" % DOT[it["level"]])
                grid.addWidget(h, r + 1, 1, 1, 3)
        errs = [i for i in items if i["level"] == "err"]
        warns = [i for i in items if i["level"] == "warn"]
        if errs:
            self.summary.setText("⚠ %d problem%s da sistemare" % (len(errs), "a" if len(errs) == 1 else "i"))
        elif warns:
            self.summary.setText("Tutto funziona, %d avvis%s" % (len(warns), "o" if len(warns) == 1 else "i"))
        else:
            self.summary.setText("✓ Tutto in ordine")
        if self.tray:
            self.tray.update_from(items)

    def show_sleep(self, hist):
        self.sleep_table.setRowCount(0)
        for c in reversed(hist):
            r = self.sleep_table.rowCount()
            self.sleep_table.insertRow(r)
            bat = "-"
            if c.get("mah") is not None:
                bat = "%s%% → %s%%, %d mAh" % (c["b0"][0], c["b1"][0], c["mah"])
            cells = [time.strftime("%d/%m %H:%M", time.localtime(c["start"])),
                     "%.0f min" % c["minutes"] if c["minutes"] is not None else "?",
                     {"deep": "S3", "s2idle": "s2idle"}.get(c["mode"], c["mode"]), c["lid"], bat, c.get("cause", "?")]
            for col, txt in enumerate(cells):
                item = QTableWidgetItem(txt)
                if col == 5 and c["spontaneous"]:
                    item.setForeground(Qt.red)
                self.sleep_table.setItem(r, col, item)
        spont = sum(1 for c in hist if c["spontaneous"])
        self.sleep_note.setText(
            "%d sospensioni in questo avvio, %d risvegli a coperchio chiuso senza aprirlo. "
            "Con S3 il consumo atteso è di pochi mAh all'ora; con s2idle centinaia." % (len(hist), spont))

    def closeEvent(self, ev):
        if self.tray and self.tray.isVisible():
            ev.ignore()
            self.hide()
        else:
            ev.accept()
            self.app.quit()

    def toggle(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.show_front()

    def show_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.refresh(force=True)


class Tray(QSystemTrayIcon):
    def __init__(self, win):
        super().__init__(QIcon.fromTheme("computer-laptop"), win)
        self.win = win
        menu = QMenu()
        menu.addAction(QIcon.fromTheme("computer-laptop"), "Apri MacBook Manager", win.show_front)
        menu.addSeparator()
        self.acts = {}
        for aid in TRAY_ACTIONS:
            if aid is None:
                menu.addSeparator()
            elif aid in BY_ID and available(BY_ID[aid]):
                act = QAction(BY_ID[aid]["label"], menu)
                act.setCheckable(bool(BY_ID[aid].get("active")))
                act.triggered.connect(lambda _=False, i=aid: win.run_action(i))
                menu.addAction(act)
                self.acts[aid] = act
        menu.addSeparator()
        menu.addAction(QIcon.fromTheme("application-exit"), "Esci", win.app.quit)
        self.setContextMenu(menu)
        self.menu = menu
        self.activated.connect(lambda r: r == QSystemTrayIcon.Trigger and win.toggle())
        self.setToolTip("MacBook Manager")

    def update_actions(self, active, busy):
        for aid, act in self.acts.items():
            on = aid in active
            if act.isCheckable():
                act.setChecked(on)
            act.setEnabled(not on and not busy)

    def update_from(self, items):
        get = {i["id"]: i for i in items}
        bits = [get[k]["value"] for k in ("battery", "touchbar", "sleepmode") if k in get]
        errs = [i for i in items if i["level"] == "err"]
        self.setIcon(QIcon.fromTheme("dialog-warning" if errs else "computer-laptop"))
        self.setToolTip("MacBook Manager\n" + "\n".join(bits) + ("\n⚠ " + errs[0]["label"] if errs else ""))


def main(tray=False):
    app = QApplication(sys.argv)
    app.setApplicationName("macbook-manager")
    app.setApplicationVersion(VERSION)
    app.setDesktopFileName("macbook-manager")
    app.setQuitOnLastWindowClosed(False)

    # Una sola istanza: se è già aperta (per esempio nella barra di sistema) le si chiede di mostrarsi.
    sock = QLocalSocket()
    sock.connectToServer(SOCKET)
    if sock.waitForConnected(300):
        if not tray:
            sock.write(b"show")
            sock.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(SOCKET)
    server = QLocalServer()
    server.listen(SOCKET)

    win = MainWindow(app)
    if QSystemTrayIcon.isSystemTrayAvailable():
        win.tray = Tray(win)
        win.tray.show()
        win.tray.update_from(win.items)

    def on_conn():
        c = server.nextPendingConnection()
        c.readyRead.connect(lambda: c.readAll() and win.show_front())
    server.newConnection.connect(on_conn)

    if not tray or win.tray is None:
        win.show()
    return app.exec()
