"""Finestra "Touch Bar in diretta": immagine della barra in tempo reale, cattura PNG e video MP4 (vedi tbcapture.py)."""
import os
import time

from PySide6.QtCore import QProcess, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from . import tbcapture as T

FPS = 30


class BarView(QWidget):
    """Disegna l'ultimo fotogramma adattato alla larghezza, con il punto toccato in rosso."""

    def __init__(self):
        super().__init__()
        self.image = None
        self.touch_x = None
        self.show_touches = True
        self.message = ""
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(40)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return max(40, round(w * T.HEIGHT / T.WIDTH))

    def bar_rect(self):
        w = self.width()
        h = w * T.HEIGHT / T.WIDTH
        if h > self.height():
            h = self.height()
            w = h * T.WIDTH / T.HEIGHT
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#000"))
        r = self.bar_rect()
        if self.image is None:
            p.setPen(QColor("#9a9a9a"))
            p.drawText(self.rect(), Qt.AlignCenter, self.message)
            return
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(r, self.image)
        if self.show_touches and self.touch_x is not None:
            x = r.x() + r.width() * self.touch_x / T.WIDTH
            p.setPen(QPen(QColor("#ff3030"), max(2.0, r.width() / T.WIDTH * 4)))
            p.drawLine(round(x), round(r.top()), round(x), round(r.bottom()))


class LiveWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Touch Bar in diretta")
        self.cap = None
        self.rec = None
        self.rec_path = ""
        self.rec_start = 0.0
        self.rec_written = 0

        lay = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.view = BarView()
        lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.touches = QCheckBox("Mostra i tocchi")
        self.touches.setChecked(True)
        self.touches.toggled.connect(self._toggle_touches)
        self.shot_btn = QPushButton("Cattura PNG")
        self.shot_btn.clicked.connect(self.capture)
        self.rec_btn = QPushButton("● Registra video")
        self.rec_btn.clicked.connect(self.toggle_record)
        self.info = QLabel()
        self.info.setStyleSheet("color: palette(mid);")
        row.addWidget(self.touches)
        row.addStretch(1)
        row.addWidget(self.info)
        row.addWidget(self.shot_btn)
        row.addWidget(self.rec_btn)
        lay.addLayout(row)

        self.timer = QTimer(self)
        self.timer.setInterval(1000 // FPS)
        self.timer.timeout.connect(self._tick)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        w = int(screen.width() * 0.9)
        self.resize(w, round(w * T.HEIGHT / T.WIDTH) + 130)

    # --- ciclo di vita -----------------------------------------------------------------------------
    def showEvent(self, ev):
        super().showEvent(ev)
        if self.cap:
            return
        if not T.renderer_active():
            self._set_buttons(False)
            self.view.image = None
            self.view.message = "La Touch Bar non è in modalità display (renderer fnstrip fermo)."
            self.status.setText("Passa alla modalità display dalla scheda Azioni, poi riapri questa finestra.")
            self.view.update()
            return
        self.cap = T.Capture()
        try:
            self.cap.start()
        except OSError as e:
            self.cap = None
            self.status.setText("Impossibile avviare la cattura: %s" % e)
            return
        self.view.message = "In attesa della barra: toccala (o cambia volume/luminosità)."
        self.status.setText("La barra invia un'immagine solo quando qualcosa cambia: finché è ferma vedi l'ultima. "
                            "La registrazione resta in RAM e si ferma quando chiudi questa finestra.")
        self._set_buttons(False)
        self.timer.start()

    def hideEvent(self, ev):
        super().hideEvent(ev)
        self.shutdown()

    def shutdown(self):
        self.timer.stop()
        if self.rec:
            self._stop_record()
        if self.cap:
            self.cap.stop()
            self.cap = None
        self.view.image = None

    def _set_buttons(self, have_frame):
        self.shot_btn.setEnabled(have_frame)
        self.rec_btn.setEnabled(have_frame or self.rec is not None)

    def _toggle_touches(self, on):
        self.view.show_touches = on
        self.view.update()

    # --- aggiornamento -----------------------------------------------------------------------------
    def _tick(self):
        if not self.cap:
            return
        new = self.cap.poll()
        if new:
            self.view.image = QImage(self.cap.frame, T.WIDTH, T.HEIGHT, T.WIDTH * 4, QImage.Format_RGB32).copy()
            self._set_buttons(True)
        if new or self.view.touch_x != self.cap.touch_x:
            self.view.touch_x = self.cap.touch_x
            self.view.update()
        self.info.setText("%d fotogrammi" % self.cap.frames + ("  ·  ● REC %ds" % (time.monotonic() - self.rec_start)
                                                               if self.rec else ""))
        if self.rec and self.view.image is not None:
            self._feed_record()

    # --- cattura -----------------------------------------------------------------------------------
    def capture(self):
        if self.view.image is None:
            return
        path = T.default_path("PICTURES", "png")
        if self.view.image.save(path, "PNG"):
            self.status.setText("Salvato: %s (%dx%d)" % (path, T.WIDTH, T.HEIGHT))
        else:
            self.status.setText("Salvataggio non riuscito: %s" % path)

    # --- video -------------------------------------------------------------------------------------
    def toggle_record(self):
        if self.rec:
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self):
        self.rec_path = T.default_path("VIDEOS", "mp4")
        self.rec = QProcess(self)
        self.rec.setProcessChannelMode(QProcess.MergedChannels)
        self.rec.finished.connect(self._record_finished)
        self.rec.start("ffmpeg", ["-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr0",
                                  "-s", "%dx%d" % (T.WIDTH, T.HEIGHT), "-r", str(FPS), "-i", "-",
                                  "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
                                  "-movflags", "+faststart", self.rec_path])
        if not self.rec.waitForStarted(3000):
            self.status.setText("ffmpeg non parte: è installato?")
            self.rec = None
            return
        self.rec_start, self.rec_written = time.monotonic(), 0
        self.rec_btn.setText("■ Ferma")
        self.status.setText("Registrazione in corso (%d fotogrammi al secondo)…" % FPS)

    def _frame_for_video(self):
        img = self.view.image
        if self.view.show_touches and self.view.touch_x is not None:
            img = img.copy()
            p = QPainter(img)
            p.setPen(QPen(QColor("#ff3030"), 4))
            p.drawLine(self.view.touch_x, 0, self.view.touch_x, T.HEIGHT)
            p.end()
        return bytes(img.constBits())[:T.FRAME]

    def _feed_record(self):
        due = int((time.monotonic() - self.rec_start) * FPS) + 1
        if due <= self.rec_written:
            return
        data = self._frame_for_video()
        for _ in range(min(due - self.rec_written, FPS)):  # l'immagine resta quella finché la barra non cambia
            self.rec.write(data)
        self.rec_written = due

    def _stop_record(self):
        proc, self.rec = self.rec, None
        self.rec_btn.setText("● Registra video")
        proc.closeWriteChannel()
        self.status.setText("Chiusura del video…")
        if not proc.waitForFinished(15000):
            proc.kill()
        self._set_buttons(self.view.image is not None)

    def _record_finished(self, code, _status):
        out = bytes(self.sender().readAll()).decode(errors="replace").strip() if self.sender() else ""
        if code == 0 and os.path.exists(self.rec_path):
            self.status.setText("Video salvato: %s (%d s)" % (self.rec_path, self.rec_written // FPS))
        else:
            self.status.setText("Video non riuscito (ffmpeg %s): %s" % (code, out[-300:]))
