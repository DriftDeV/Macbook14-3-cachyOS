"""Scheda "Ottimizzazione" di MacBook Manager: app Chromium/Electron e web app con la GPU sulla Radeon (optimize.py)."""
from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from . import theme as T
from . import optimize as O



class OptimizeTab(QWidget):
    def __init__(self, log):
        super().__init__()
        self.log = log
        self.proc = None
        lay = QVBoxLayout(self)
        intro = QLabel(
            "<b>App Chromium/Electron e web app</b> (Brave, Discord, Claude Desktop, web app installate dal browser…). "
            "Sotto Wayland il loro processo GPU crolla con i buffer della Radeon e disegnano con la CPU: scatti e "
            "consumi alti. L'ottimizzazione dà <code>AMD_DEBUG=notiling</code> solo a queste app (restano su Wayland e "
            "usano la Radeon), riattiva l'accelerazione di Claude Desktop e attiva un servizio che ottimizza anche le "
            "app che installerai. Verificata il 24/11/2026 su Brave, Discord, Sidra e Claude Desktop.")
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.RichText)
        lay.addWidget(intro)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["App", "Tipo", "Stato", "Dettaglio"])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        lay.addWidget(self.table, 1)

        self.live = QLabel()
        self.live.setWordWrap(True)
        lay.addWidget(self.live)
        self.svc = QLabel()
        self.svc.setWordWrap(True)
        lay.addWidget(self.svc)

        bar = QHBoxLayout()
        self.refresh_btn = QPushButton(QIcon.fromTheme("view-refresh"), "Aggiorna")
        self.undo_btn = QPushButton(QIcon.fromTheme("edit-undo"), "Annulla ottimizzazioni")
        self.go_btn = QPushButton(QIcon.fromTheme("games-solve"), "Ottimizza tutte")
        self.go_btn.setDefault(True)
        self.refresh_btn.clicked.connect(self.refresh)
        self.undo_btn.clicked.connect(self.undo)
        self.go_btn.clicked.connect(self.optimize)
        bar.addWidget(self.refresh_btn)
        bar.addWidget(self.undo_btn)
        bar.addStretch(1)
        bar.addWidget(self.go_btn)
        lay.addLayout(bar)
        self.loaded = False

    # --- stato -------------------------------------------------------------------------------------
    def showEvent(self, ev):
        super().showEvent(ev)
        if not self.loaded:
            self.refresh()

    def refresh(self):
        self.loaded = True
        if not O.script():
            self.table.setRowCount(0)
            self.live.setText("Script di ottimizzazione non trovato: reinstalla il manager (scripts/install-manager.sh).")
            for b in (self.go_btn, self.undo_btn):
                b.setEnabled(False)
            return
        try:
            apps = O.apps()
        except Exception as e:  # noqa: BLE001
            self.log("ottimizzazione: elenco non riuscito: %s" % e)
            apps = []
        self.table.setRowCount(0)
        for a in apps:
            r = self.table.rowCount()
            self.table.insertRow(r)
            state = QTableWidgetItem("✓ ottimizzata" if a["ok"] else "da ottimizzare")
            state.setForeground(T.qc("ok") if a["ok"] else T.qc("warn"))
            for c, item in enumerate((QTableWidgetItem(a["name"]), QTableWidgetItem("web app" if a["web"] else "app"),
                                      state, QTableWidgetItem(a["detail"] or a["file"]))):
                self.table.setItem(r, c, item)
        todo = sum(1 for a in apps if not a["ok"])
        self.go_btn.setEnabled(not self.proc)
        self.go_btn.setText("Ottimizza tutte (%d da fare)" % todo if todo else "Ottimizza tutte")
        self.undo_btn.setEnabled(not self.proc and any(a["ok"] for a in apps))
        run = O.running()
        if run:
            off = [a for a, acc in run if not acc]
            txt = ", ".join("%s %s" % (a, "✓" if acc else "✗ GPU spenta") for a, acc in run)
            self.live.setText("<b>In esecuzione:</b> " + txt + (
                "<br><span style='color:" + T.c("err") + "'>Le app con la GPU spenta vanno chiuse del tutto e riaperte dopo "
                "l'ottimizzazione.</span>" if off else ""))
        else:
            self.live.setText("Nessuna app Chromium/Electron in esecuzione.")
        self.svc.setText("Servizio per le app nuove: <b>%s</b>" % ("attivo" if O.service_active() else "non attivo"))

    # --- azioni ------------------------------------------------------------------------------------
    def _run(self, args, title):
        self.go_btn.setEnabled(False)
        self.undo_btn.setEnabled(False)
        self.log("\n▶ %s" % title)
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(
            lambda: self.log(bytes(self.proc.readAllStandardOutput()).decode(errors="replace").rstrip()))
        self.proc.finished.connect(self._done)
        self.proc.start(O.script(), args)

    def _done(self, code, _st):
        self.proc = None
        self.log("■ %s" % ("fatto" if code == 0 else "non riuscito (codice %d)" % code))
        self.refresh()
        if code == 0:
            QMessageBox.information(self, "Ottimizzazione", "Fatto. Chiudi del tutto le app Chromium/Electron (anche "
                                    "dall'icona nella barra di sistema) e riaprile dal menu.")

    def optimize(self):
        self._run([], "Ottimizza tutte le app Chromium/Electron e web app")

    def undo(self):
        if QMessageBox.question(self, "Annulla ottimizzazioni",
                                "Togliere l'ottimizzazione da tutte le app e fermare il servizio? Sotto Wayland "
                                "torneranno a disegnare con la CPU.") == QMessageBox.Yes:
            self._run(["--undo"], "Annulla le ottimizzazioni")
