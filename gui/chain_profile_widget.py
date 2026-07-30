# gui/chain_profile_widget.py

from qgis.PyQt.QtWidgets import QWidget, QSizePolicy
from qgis.PyQt.QtGui import QPainter, QPen, QColor, QFontMetrics
from qgis.PyQt.QtCore import Qt, QPointF

_COLOR_TERRAIN = QColor(150, 100, 50)
_COLOR_PIPE = QColor(30, 90, 170)
_COLOR_NODE = QColor(90, 90, 90)
_COLOR_MISSING = QColor(181, 50, 42)


class ChainProfileWidget(QWidget):
    """Schéma simplifié type 'profil en long' d'une chaîne de regards :
    terrain naturel (TN, pointillés bruns), fil d'eau (FE, ligne bleue avec
    la pente de chaque tronçon), et un trait vertical par ouvrage figurant
    sa profondeur. Purement visuel, non éditable."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes = []
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_data(self, nodes):
        """nodes : liste de dicts {nom, cum, tn, profondeur, fe}, triés par
        cum (longueur cumulée) croissante. Les valeurs peuvent être None."""
        self._nodes = nodes or []
        self.update()

    @staticmethod
    def _text_width(fm, text):
        if hasattr(fm, 'horizontalAdvance'):
            return fm.horizontalAdvance(text)
        return fm.width(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), self.palette().base())

        if len(self._nodes) < 1:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(
                self.rect(), Qt.AlignCenter,
                "Aucune chaîne sélectionnée — utilisez « Rechercher la chaîne » ci-dessus.")
            painter.end()
            return

        margin_l, margin_r, margin_t, margin_b = 24, 24, 26, 40
        plot_w = max(w - margin_l - margin_r, 10)
        plot_h = max(h - margin_t - margin_b, 10)

        cums = [n['cum'] for n in self._nodes]
        cum_min, cum_max = min(cums), max(cums)
        if cum_max == cum_min:
            cum_max = cum_min + 1.0

        elevs = [v for n in self._nodes for v in (n['tn'], n['fe']) if v is not None]
        if elevs:
            elev_min, elev_max = min(elevs), max(elevs)
            if elev_max == elev_min:
                elev_max += 1.0
            pad = (elev_max - elev_min) * 0.18
            elev_min -= pad
            elev_max += pad
        else:
            elev_min, elev_max = 0.0, 1.0

        def x_of(cum):
            return margin_l + (cum - cum_min) / (cum_max - cum_min) * plot_w

        def y_of(elev):
            return margin_t + (elev_max - elev) / (elev_max - elev_min) * plot_h

        font = painter.font()
        font.setPointSize(max(font.pointSize() - 2, 7))
        painter.setFont(font)
        fm = QFontMetrics(font)

        # ligne de terrain naturel (TN), pointillés
        pen_tn = QPen(_COLOR_TERRAIN, 2)
        pen_tn.setStyle(Qt.DashLine)
        for i in range(len(self._nodes) - 1):
            n1, n2 = self._nodes[i], self._nodes[i + 1]
            if n1['tn'] is None or n2['tn'] is None:
                continue
            painter.setPen(pen_tn)
            painter.drawLine(QPointF(x_of(n1['cum']), y_of(n1['tn'])),
                              QPointF(x_of(n2['cum']), y_of(n2['tn'])))

        # ligne de fil d'eau (FE / pipe) + libellé de pente par tronçon
        pen_fe = QPen(_COLOR_PIPE, 3)
        pen_fe_missing = QPen(_COLOR_MISSING, 2)
        pen_fe_missing.setStyle(Qt.DotLine)
        for i in range(len(self._nodes) - 1):
            n1, n2 = self._nodes[i], self._nodes[i + 1]
            fe1, fe2 = n1['fe'], n2['fe']
            c1, c2 = n1['cum'], n2['cum']
            y1 = y_of(fe1) if fe1 is not None else margin_t + plot_h
            y2 = y_of(fe2) if fe2 is not None else margin_t + plot_h
            p1, p2 = QPointF(x_of(c1), y1), QPointF(x_of(c2), y2)

            if fe1 is None or fe2 is None:
                painter.setPen(pen_fe_missing)
                painter.drawLine(p1, p2)
                continue

            painter.setPen(pen_fe)
            painter.drawLine(p1, p2)
            longueur = c2 - c1
            if longueur:
                pente = (fe1 - fe2) / longueur * 100
                mid = QPointF((p1.x() + p2.x()) / 2, (p1.y() + p2.y()) / 2 - 6)
                painter.setPen(_COLOR_PIPE)
                painter.drawText(mid, f"{pente:.2f} %")

        # un trait vertical par ouvrage (TN -> FE) + libellés
        for n in self._nodes:
            x = x_of(n['cum'])
            tn, fe = n['tn'], n['fe']
            y_tn = y_of(tn) if tn is not None else margin_t
            y_fe = y_of(fe) if fe is not None else margin_t + plot_h

            ok = tn is not None and fe is not None
            painter.setPen(QPen(_COLOR_NODE if ok else _COLOR_MISSING, 3))
            painter.drawLine(QPointF(x, y_tn), QPointF(x, y_fe))

            painter.setPen(Qt.NoPen)
            painter.setBrush(_COLOR_TERRAIN)
            painter.drawEllipse(QPointF(x, y_tn), 3, 3)
            painter.setBrush(_COLOR_PIPE)
            painter.drawEllipse(QPointF(x, y_fe), 3, 3)

            painter.setPen(self.palette().text().color())
            nom = n['nom']
            painter.drawText(QPointF(x - self._text_width(fm, nom) / 2, margin_t - 10), nom)

            fe_txt = f"{fe:.2f}" if fe is not None else "FE ?"
            painter.setPen(_COLOR_PIPE if fe is not None else _COLOR_MISSING)
            painter.drawText(QPointF(x - self._text_width(fm, fe_txt) / 2, margin_t + plot_h + 16),
                              fe_txt)

        painter.end()
