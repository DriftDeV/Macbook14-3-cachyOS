"""Interfaccia che si adatta alla finestra: niente larghezza minima imposta dal contenuto, niente scorrimento
orizzontale. Un passaggio unico (`responsify`) sistema le schede già costruite:
  - righe di pulsanti (e di etichette, caselle, pulsanti) -> FlowLayout: vanno a capo;
  - griglie di soli pulsanti e righe di riquadri (QGroupBox/QFrame) -> ReflowLayout: tante colonne quante ne entrano,
    una sola nelle finestre strette;
  - etichette che vanno a capo, menu a tendina che si accorciano, aree scorrevoli solo in verticale.
"""
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import (QAbstractButton, QBoxLayout, QComboBox, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLayout, QLineEdit, QProgressBar, QScrollArea, QSizePolicy, QSlider, QWidget,
                               QWidgetItem, QAbstractScrollArea)


class FlowLayout(QLayout):
    """Elementi in fila alla loro larghezza naturale; a capo quando non ci stanno."""

    def __init__(self, parent=None, spacing=8):
        super().__init__(parent)
        self._items = []
        self._sp = spacing

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, rect, test):
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line = r.x(), r.y(), 0
        for it in self._items:
            if it.widget() is not None and not it.widget().isVisibleTo(it.widget().parentWidget()):
                continue
            hint = it.sizeHint()
            w = min(hint.width(), r.width())
            if x > r.x() and x + w > r.right() + 1:
                x, y, line = r.x(), y + line + self._sp, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), QSize(w, hint.height())))
            x += w + self._sp
            line = max(line, hint.height())
        return y + line - rect.y() + m.bottom()


class ReflowLayout(QLayout):
    """Griglia a colonne uguali: tante colonne quante ne entrano (larghezza minima dell'elemento più largo)."""

    def __init__(self, parent=None, spacing=8, min_col=0):
        super().__init__(parent)
        self._items = []
        self._sp = spacing
        self._min_col = min_col

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Horizontal

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def _visible(self):
        return [it for it in self._items if it.widget() is None or not it.widget().isHidden()]

    def _colw(self):
        # Larghezza minima vera del contenuto (minimumSizeHint), non quella esplicita: i riquadri hanno minimo 1 apposta
        # per non bloccare la finestra, ma qui serve sapere quando non stanno più affiancati.
        def w(it):
            wd = it.widget()
            return wd.minimumSizeHint().width() if wd is not None else it.minimumSize().width()
        return max([self._min_col] + [w(it) for it in self._visible()])

    def sizeHint(self):
        items = self._visible()
        m = self.contentsMargins()
        w = sum(it.sizeHint().width() for it in items) + self._sp * max(0, len(items) - 1)
        return QSize(w + m.left() + m.right(), self.heightForWidth(w + m.left() + m.right()))

    def minimumSize(self):
        m = self.contentsMargins()
        return QSize(self._colw() + m.left() + m.right(), 0)

    def _do(self, rect, test):
        items = self._visible()
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        if not items:
            return 0
        cols = max(1, min(len(items), (r.width() + self._sp) // (self._colw() + self._sp)))
        cw = (r.width() - self._sp * (cols - 1)) / cols
        y = r.y()
        for row in range(0, len(items), cols):
            chunk = items[row:row + cols]
            h = max((it.heightForWidth(int(cw)) if it.hasHeightForWidth() else it.sizeHint().height()) for it in chunk)
            if not test:
                for i, it in enumerate(chunk):
                    it.setGeometry(QRect(int(r.x() + i * (cw + self._sp)), y, int(cw), h))
            y += h + self._sp
        return y - self._sp - rect.y() + m.bottom()


# --- passaggio sulle schede -------------------------------------------------------------------------------
_INPUTS = (QSlider, QLineEdit, QProgressBar, QAbstractScrollArea)


def _widgets(layout):
    out = []
    for i in range(layout.count()):
        it = layout.itemAt(i)
        if it.widget() is not None:
            out.append(it.widget())
        elif it.layout() is not None:
            return None   # contiene altri layout: si lascia (ci pensa la ricorsione)
    return out


class _Graveyard:
    """Widget di appoggio (creato alla prima occorrenza: serve una QApplication) per staccare layout dai widget."""
    _w = None

    def __getattr__(self, name):
        if _Graveyard._w is None or _Graveyard._w.layout() is not None:
            _Graveyard._w = QWidget()
        return getattr(_Graveyard._w, name)


_graveyard = _Graveyard()


def _replace(old, new):
    """Mette `new` al posto di `old` (nel layout genitore o come layout del widget) spostando i widget."""
    ws = _widgets(old)
    m = old.contentsMargins()
    new.setContentsMargins(m)
    parent = old.parent()
    for w in ws:
        old.removeWidget(w)
    if isinstance(parent, QBoxLayout):
        idx = parent.indexOf(old)
        stretch = parent.stretch(idx)
        parent.removeItem(old)
        parent.insertLayout(idx, new, stretch)
    elif isinstance(parent, QGridLayout):
        idx = parent.indexOf(old)
        row, col, rs, cs = parent.getItemPosition(idx)
        parent.removeItem(old)
        parent.addLayout(new, row, col, rs, cs)
    elif isinstance(parent, QWidget):
        _graveyard.setLayout(old)  # stacca il vecchio layout dal widget (un widget può averne uno solo)
        _graveyard.layout().deleteLater() if _graveyard.layout() else None
        parent.setLayout(new)
        for w in ws:
            new.addWidget(w)
        return True
    else:
        return False
    for w in ws:
        new.addWidget(w)
    old.deleteLater()
    return True


def _panel(w):
    """Riquadro (gruppo o cornice con contenuto), non un controllo né un'etichetta."""
    return isinstance(w, (QGroupBox, QFrame)) and not isinstance(w, (QLabel, QAbstractScrollArea, QAbstractButton))


def _pairs(grid):
    """Griglia nome/valore a 4 colonne (due coppie per riga) -> coppie in colonne adattive (una sola se stretta)."""
    cells = {}
    for i in range(grid.count()):
        r, c, _rs, _cs = grid.getItemPosition(i)
        w = grid.itemAt(i).widget()
        if w is not None:
            cells[(r, c)] = w
    pairs = []
    for r in range(grid.rowCount()):
        for c in (0, 2):
            if (r, c) in cells and (r, c + 1) in cells:
                pairs.append((cells[(r, c)], cells[(r, c + 1)]))
    if not pairs:
        return
    holder = grid.parentWidget()
    new = ReflowLayout(spacing=6, min_col=300)
    boxes = []
    for name, val in pairs:
        grid.removeWidget(name)
        grid.removeWidget(val)
        box = QWidget()
        g = QGridLayout(box)
        g.setContentsMargins(0, 0, 0, 0)
        name.setMinimumWidth(130)
        name.setWordWrap(True)
        val.setWordWrap(True)
        g.addWidget(name, 0, 0, Qt.AlignTop)
        g.addWidget(val, 0, 1)
        g.setColumnStretch(1, 1)
        boxes.append(box)
    _graveyard.setLayout(grid)
    holder.setLayout(new)
    for b in boxes:
        new.addWidget(b)


def responsify(root):
    """Applica le regole a tutti i layout e i widget sotto `root` (una volta, dopo averli costruiti)."""
    for lay in root.findChildren(QLayout):
        try:
            if isinstance(lay, (FlowLayout, ReflowLayout)):
                continue
            ws = _widgets(lay)
        except RuntimeError:   # layout già sostituito in questo giro
            continue
        if not ws or len(ws) < 2:
            continue
        if isinstance(lay, QGridLayout) and all(isinstance(w, QAbstractButton) for w in ws):
            new = ReflowLayout(spacing=6)
            for w in ws:
                w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            _replace(lay, new)
        elif isinstance(lay, QGridLayout) and all(_panel(w) for w in ws):
            _replace(lay, ReflowLayout(spacing=lay.spacing() if lay.spacing() >= 0 else 8))
        elif isinstance(lay, QGridLayout) and lay.columnCount() == 4 and all(isinstance(w, QLabel) for w in ws):
            _pairs(lay)
        elif isinstance(lay, QHBoxLayout):
            if all(isinstance(w, (QGroupBox, QFrame)) and not isinstance(w, (QLabel, QAbstractScrollArea)) for w in ws):
                _replace(lay, ReflowLayout(spacing=lay.spacing() if lay.spacing() >= 0 else 8))
            elif not any(isinstance(w, _INPUTS) for w in ws) and any(isinstance(w, QAbstractButton) for w in ws):
                _replace(lay, FlowLayout(spacing=6))
    # Riquadri: un QGroupBox non scende sotto la larghezza del titolo. La parte tra parentesi di un titolo lungo
    # diventa una nota che va a capo, e la larghezza minima esplicita (1) vince su quella calcolata dal titolo.
    for gb in root.findChildren(QGroupBox):
        title = gb.title()
        if len(title) > 32 and " (" in title and title.endswith(")") and gb.layout() is not None:
            head, note = title.split(" (", 1)
            gb.setTitle(head)
            lab = QLabel(note[:-1][:1].upper() + note[:-1][1:] + ".")
            lab.setWordWrap(True)
            lab.setStyleSheet("color: palette(placeholder-text);")
            lay = gb.layout()
            if isinstance(lay, QBoxLayout):
                lay.insertWidget(0, lab)
            elif isinstance(lay, QGridLayout):
                lay.addWidget(lab, lay.rowCount(), 0, 1, max(1, lay.columnCount()))   # in fondo al riquadro
            else:
                gb.setTitle(title)
        gb.setMinimumWidth(1)
    for lab in root.findChildren(QLabel):
        if lab.pixmap() is None or lab.pixmap().isNull():
            if len(lab.text()) > 24:
                lab.setWordWrap(True)
            lab.setMinimumWidth(0)
    for cb in root.findChildren(QComboBox):
        cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        cb.setMinimumContentsLength(8)
    for sa in root.findChildren(QScrollArea):
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setWidgetResizable(True)


def scrollable(page):
    """La pagina dentro un'area che scorre solo in verticale (se non lo è già)."""
    if isinstance(page, QScrollArea):
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return page
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sa.setWidget(page)
    sa.page = page
    return sa


def unwrap(w):
    return getattr(w, "page", w)
