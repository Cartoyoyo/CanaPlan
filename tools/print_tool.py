# -*- coding: utf-8 -*-
import os
import math
from qgis.PyQt.QtCore import Qt, QDate
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QApplication, QFileDialog, QMessageBox,
    QGraphicsTextItem,
)
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.core import (
    QgsWkbTypes, QgsGeometry, QgsRectangle, QgsPointXY,
    QgsProject, QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLabel,
    QgsLayoutItemPage, QgsLayoutSize, QgsLayoutPoint, QgsUnitTypes,
    QgsLayoutExporter, QgsLayoutItemScaleBar, QgsVectorLayer,
    QgsSingleSymbolRenderer,
)

# États de l'outil
_STATE_MOVE   = 0   # rectangle suit la souris (libre ou domino)
_STATE_ROTATE = 1   # ancrage fixé, rectangle pivote autour du centre


class PrintTool(QgsMapTool):

    def __init__(self, canvas, iface, settings):
        super().__init__(canvas)
        self.iface = iface
        self.s     = settings

        factor  = settings["echelle"] / 1000.0
        self._w = settings["w_mm"] * factor   # largeur feuille en mètres
        self._h = settings["h_mm"] * factor   # hauteur feuille en mètres

        self._state   = _STATE_MOVE
        self._anchor  = None    # QgsPointXY : centre ancré au 1er clic
        self._cur_rot = 0.0     # rotation courante en radians (horaire depuis N)

        self._sheets = []   # [{'center': QgsPointXY, 'rotation_rad': float}]
        self._bands  = []   # [QgsRubberBand] feuilles définitivement posées

        self._preview = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self._preview.setColor(QColor(255, 140, 0, 70))
        self._preview.setStrokeColor(QColor(220, 100, 0, 230))
        self._preview.setWidth(2)

        # Trait épais rouge sur le bord HAUT pour distinguer le sens
        self._preview_top_edge = QgsRubberBand(canvas, QgsWkbTypes.LineGeometry)
        self._preview_top_edge.setColor(QColor(220, 30, 30, 255))
        self._preview_top_edge.setWidth(5)

        # Bande grise en bas = zone cartouche
        self._preview_carto_band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self._preview_carto_band.setColor(QColor(180, 180, 180, 150))
        self._preview_carto_band.setStrokeColor(QColor(90, 90, 90, 200))
        self._preview_carto_band.setWidth(1)

        # Texte "Cartouche" dans la bande
        self._preview_carto_label = QGraphicsTextItem()
        self._preview_carto_label.setDefaultTextColor(QColor(60, 60, 60, 210))
        self._preview_carto_label.setVisible(False)
        canvas.scene().addItem(self._preview_carto_label)

        # Numéro de feuille en gros dans l'aperçu
        self._preview_label = QGraphicsTextItem()
        self._preview_label.setDefaultTextColor(QColor(220, 30, 30, 200))
        self._preview_label.setVisible(False)
        canvas.scene().addItem(self._preview_label)

        self.setCursor(Qt.CrossCursor)

    # ── Cycle de vie ───────────────────────────────────────────────────────

    def activate(self):
        super().activate()
        self.canvas().setCursor(Qt.CrossCursor)
        fmt, ori, ech = self.s["format"], self.s["orientation"], self.s["echelle"]
        self.iface.messageBar().pushMessage(
            "Impression",
            f"{fmt} {ori}  ·  1:{ech:,}  —  "
            "1er clic : ancrer  ·  orienter  ·  2e clic : fixer  |  Clic droit : exporter  |  Échap : changer l'échelle".replace(",", " "),
            level=0, duration=0,
        )

    def deactivate(self):
        self.iface.messageBar().clearWidgets()
        self._preview.reset()
        self._preview_top_edge.reset()
        self._preview_carto_band.reset()
        self._preview_carto_label.setVisible(False)
        self._preview_label.setVisible(False)
        for b in self._bands:
            b.reset()
        self._bands.clear()
        self._sheets.clear()
        self._anchor  = None
        self._cur_rot = 0.0
        self._state   = _STATE_MOVE
        super().deactivate()

    # ── Événements canvas ──────────────────────────────────────────────────

    def canvasMoveEvent(self, event):
        pt = self.toMapCoordinates(event.pos())

        if self._state == _STATE_MOVE:
            center = self._compute_move_center(pt)
            self._draw_preview(center, 0.0)

        else:  # _STATE_ROTATE
            dx = pt.x() - self._anchor.x()
            dy = pt.y() - self._anchor.y()
            if abs(dx) > 1e-10 or abs(dy) > 1e-10:
                # atan2(dx, dy) : angle horaire depuis le Nord
                self._cur_rot = math.atan2(dx, dy)
            self._draw_preview(self._anchor, self._cur_rot)

    def canvasPressEvent(self, event):
        pt = self.toMapCoordinates(event.pos())

        if event.button() == Qt.LeftButton:
            if self._state == _STATE_MOVE:
                # 1er clic : ancrer la position, passer en rotation
                self._anchor  = self._compute_move_center(pt)
                self._cur_rot = 0.0
                self._state   = _STATE_ROTATE
                n = len(self._sheets) + 1
                self.iface.messageBar().pushMessage(
                    "Impression",
                    f"Feuille {n} — orientez avec la souris · 2ᵉ clic pour fixer",
                    level=0, duration=5,
                )

            else:  # _STATE_ROTATE
                # 2ème clic : fixer l'orientation, poser la feuille
                self._place_sheet(self._anchor, self._cur_rot)
                self._state = _STATE_MOVE

        elif event.button() == Qt.RightButton:
            if self._sheets:
                self._ask_and_export()
            else:
                self.canvas().unsetMapTool(self)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            from qgis.PyQt.QtCore import QTimer
            self._reset()
            QTimer.singleShot(0, self._reopen_settings)
            event.accept()

    def _reset(self):
        """Efface toutes les feuilles posées (garde l'outil actif)."""
        self._preview.reset()
        self._preview_top_edge.reset()
        self._preview_carto_band.reset()
        self._preview_carto_label.setVisible(False)
        self._preview_label.setVisible(False)
        for b in self._bands:
            b.reset()
        self._bands.clear()
        self._sheets.clear()
        self._anchor  = None
        self._cur_rot = 0.0
        self._state   = _STATE_MOVE

    def _reopen_settings(self):
        """Rouvre le dialog de paramètres pré-rempli avec les réglages courants.
        Si l'utilisateur valide, met à jour l'outil et reprend le placement.
        Si l'utilisateur annule, désactive l'outil."""
        from ..gui.print_dialog import PrintDialog

        dlg = PrintDialog(self.iface.mainWindow())
        dlg.titre_edit.setText(self.s["titre"])
        dlg.format_combo.setCurrentText(self.s["format"])
        dlg.orient_combo.setCurrentText(self.s["orientation"])
        for idx in range(dlg.scale_combo.count()):
            if dlg.scale_combo.itemData(idx) == self.s["echelle"]:
                dlg.scale_combo.setCurrentIndex(idx)
                break

        if dlg.exec_() != PrintDialog.Accepted:
            self.canvas().unsetMapTool(self)
            return

        # Préserver les choix PDF/DXF déjà faits
        do_pdf = self.s.get('do_pdf', True)
        do_dxf = self.s.get('do_dxf', False)
        self.s   = dlg.get_settings()
        self.s['do_pdf'] = do_pdf
        self.s['do_dxf'] = do_dxf
        factor   = self.s["echelle"] / 1000.0
        self._w  = self.s["w_mm"] * factor
        self._h  = self.s["h_mm"] * factor

        # Réactiver explicitement l'outil sur le canevas
        self.canvas().setMapTool(self)

        fmt, ori, ech = self.s["format"], self.s["orientation"], self.s["echelle"]
        self.iface.messageBar().pushMessage(
            "Impression",
            f"{fmt} {ori}  ·  1:{ech:,}  —  "
            "1er clic : ancrer  ·  orienter  ·  2e clic : fixer  |  Clic droit : exporter  |  Échap : changer l'échelle".replace(",", " "),
            level=0, duration=0,
        )

    # ── Calcul de position ─────────────────────────────────────────────────

    def _compute_move_center(self, pt):
        """Centre de la prochaine feuille :
        libre pour la 1ère, orbite bord-à-bord pour les suivantes."""
        if not self._sheets:
            return pt
        return self._orbit_center(pt, self._sheets[-1])

    def _orbit_center(self, pt, last):
        """Orbite libre autour de la dernière feuille, toujours bord-à-bord
        (rayon polaire exact). Aux angles ~45° le contact est naturellement
        coin-à-coin. Recouvrement de 10 %."""
        cx    = last['center'].x()
        cy    = last['center'].y()
        theta = last['rotation_rad']
        ct    = math.cos(theta)
        st    = math.sin(theta)

        dx_w = pt.x() - cx
        dy_w = pt.y() - cy
        if math.hypot(dx_w, dy_w) < 1e-10:
            dx_w, dy_w = 1.0, 0.0

        # Direction en repère local
        dlx = dx_w * ct - dy_w * st
        dly = dx_w * st + dy_w * ct

        # Rayon polaire du rectangle dans cette direction
        r = self._polar_radius(dlx, dly)

        # Centre de la nouvelle feuille = 2 × r dans cette direction, −10 %
        d = math.hypot(dlx, dly)
        nlx = (dlx / d) * 2 * r * 0.9
        nly = (dly / d) * 2 * r * 0.9

        return QgsPointXY(
            cx + nlx * ct + nly * st,
            cy - nlx * st + nly * ct,
        )

    def _polar_radius(self, dlx, dly):
        """Distance centre → bord du rectangle dans la direction locale (dlx, dly)."""
        d = math.hypot(dlx, dly)
        if d < 1e-10:
            return self._w / 2
        ndx, ndy = abs(dlx) / d, abs(dly) / d
        hw, hh   = self._w / 2, self._h / 2
        t_x = hw / ndx if ndx > 1e-10 else float('inf')
        t_y = hh / ndy if ndy > 1e-10 else float('inf')
        return min(t_x, t_y)

    # ── Géométrie rubber band ──────────────────────────────────────────────

    def _corners(self, cx, cy, theta_rad):
        """4 coins du rectangle orienté, en coordonnées monde."""
        ct, st = math.cos(theta_rad), math.sin(theta_rad)
        hw, hh = self._w / 2, self._h / 2
        # Coins en repère local (bas-gauche, bas-droit, haut-droit, haut-gauche)
        local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        return [
            QgsPointXY(cx + lx * ct + ly * st,
                       cy - lx * st + ly * ct)
            for lx, ly in local
        ]

    def _carto_h_m(self):
        """Hauteur de la bande cartouche en mètres (même calcul que _generate_pdf)."""
        h_mm   = self.s["h_mm"]
        factor = self.s["echelle"] / 1000.0
        return max(15.0, min(30.0, h_mm * 0.085)) * factor

    def _draw_preview(self, center_pt, theta_rad):
        corners = self._corners(center_pt.x(), center_pt.y(), theta_rad)
        self._preview.setToGeometry(QgsGeometry.fromPolygonXY([corners]), None)

        # Trait rouge épais sur le bord HAUT (entre coin haut-gauche et haut-droit)
        self._preview_top_edge.setToGeometry(
            QgsGeometry.fromPolylineXY([corners[3], corners[2]]), None)

        # Bande cartouche en bas + texte
        self._draw_carto_band(center_pt, theta_rad)

        # Numéro de feuille en gros (90 % de la hauteur)
        self._update_preview_label(center_pt, theta_rad)

    def _draw_carto_band(self, center_pt, theta_rad):
        """Dessine la bande grise cartouche en bas de l'aperçu + texte rotatif."""
        cx, cy = center_pt.x(), center_pt.y()
        ct, st = math.cos(theta_rad), math.sin(theta_rad)
        hw = self._w / 2
        hh = self._h / 2
        ch = self._carto_h_m()

        # Les 4 coins de la bande en repère local
        # (bas-gauche → bas-droit → haut-droit-bande → haut-gauche-bande)
        local_band = [(-hw, -hh), (hw, -hh), (hw, -hh + ch), (-hw, -hh + ch)]
        band_corners = [
            QgsPointXY(cx + lx * ct + ly * st, cy - lx * st + ly * ct)
            for lx, ly in local_band
        ]
        self._preview_carto_band.setToGeometry(
            QgsGeometry.fromPolygonXY([band_corners]), None)

        # Centre de la bande en coordonnées monde (lx=0, ly = -hh + ch/2)
        band_cy_l = -hh + ch / 2
        band_center_map = QgsPointXY(cx + band_cy_l * st, cy + band_cy_l * ct)
        band_center_px  = self.toCanvasCoordinates(band_center_map)

        # Hauteur de la bande en pixels (pour dimensionner la fonte)
        bot_map = QgsPointXY(cx + (-hh) * st,      cy + (-hh) * ct)
        top_map = QgsPointXY(cx + (-hh + ch) * st, cy + (-hh + ch) * ct)
        bot_px  = self.toCanvasCoordinates(bot_map)
        top_px  = self.toCanvasCoordinates(top_map)
        band_px_h = math.hypot(top_px.x() - bot_px.x(), top_px.y() - bot_px.y())

        self._preview_carto_label.setPlainText("Cartouche")
        font = self._preview_carto_label.font()
        font.setPointSizeF(max(6.0, band_px_h * 0.42))
        font.setBold(False)
        self._preview_carto_label.setFont(font)

        rect = self._preview_carto_label.boundingRect()
        self._preview_carto_label.setTransformOriginPoint(
            rect.width() / 2, rect.height() / 2)
        self._preview_carto_label.setPos(
            band_center_px.x() - rect.width()  / 2,
            band_center_px.y() - rect.height() / 2,
        )
        self._preview_carto_label.setRotation(math.degrees(theta_rad))
        self._preview_carto_label.setVisible(True)

    def _update_preview_label(self, center_pt, theta_rad):
        """Affiche le numéro de la prochaine feuille en gros au centre de l'aperçu."""
        n = len(self._sheets) + 1
        self._preview_label.setPlainText(str(n))

        center_px = self.toCanvasCoordinates(center_pt)
        ct, st = math.cos(theta_rad), math.sin(theta_rad)
        hh = self._h / 2
        top_map = QgsPointXY(center_pt.x() + hh * st, center_pt.y() + hh * ct)
        bot_map = QgsPointXY(center_pt.x() - hh * st, center_pt.y() - hh * ct)
        top_px = self.toCanvasCoordinates(top_map)
        bot_px = self.toCanvasCoordinates(bot_map)
        pixel_h = math.hypot(top_px.x() - bot_px.x(), top_px.y() - bot_px.y())

        font = self._preview_label.font()
        font.setPointSizeF(max(10, pixel_h * 0.90))
        font.setBold(True)
        self._preview_label.setFont(font)

        rect = self._preview_label.boundingRect()
        self._preview_label.setTransformOriginPoint(rect.width() / 2, rect.height() / 2)
        self._preview_label.setPos(
            center_px.x() - rect.width() / 2,
            center_px.y() - rect.height() / 2)
        self._preview_label.setRotation(math.degrees(theta_rad))
        self._preview_label.setVisible(True)

    # ── Pose d'une feuille ─────────────────────────────────────────────────

    def _place_sheet(self, center, rotation_rad):
        corners = self._corners(center.x(), center.y(), rotation_rad)
        band = QgsRubberBand(self.canvas(), QgsWkbTypes.PolygonGeometry)
        band.setColor(QColor(30, 100, 200, 45))
        band.setStrokeColor(QColor(20, 80, 180, 210))
        band.setWidth(2)
        band.setToGeometry(QgsGeometry.fromPolygonXY([corners]), None)

        self._sheets.append({
            'center':       QgsPointXY(center),
            'rotation_rad': rotation_rad,
        })
        self._bands.append(band)

        n = len(self._sheets)
        self.iface.messageBar().pushMessage(
            "Impression",
            f"Feuille {n} posée — 1er clic pour la suivante · clic droit pour exporter",
            level=0, duration=4,
        )

    # ── Choix du format d'export ───────────────────────────────────────────

    def _ask_and_export(self):
        do_pdf = self.s.get('do_pdf', True)
        do_dxf = self.s.get('do_dxf', False)
        if do_pdf:
            self._export_pdf()
        if do_dxf:
            self._export_dxf()
        self.canvas().unsetMapTool(self)

    # ── Export DXF 2018 ────────────────────────────────────────────────────

    def _export_dxf(self):
        from .projet_bet import project_dir
        from .dxf_export import run_export_dxf_with_ui

        # Extent = union de toutes les emprises posées (coins, rotation incluse)
        all_corners = []
        for sheet in self._sheets:
            all_corners.extend(self._corners(
                sheet['center'].x(), sheet['center'].y(),
                sheet['rotation_rad']))
        if not all_corners:
            QMessageBox.warning(
                self.iface.mainWindow(), "Export DXF",
                "Aucune planche posée — placez au moins une planche avant d'exporter.")
            return
        xs = [p.x() for p in all_corners]
        ys = [p.y() for p in all_corners]
        extent = QgsRectangle(min(xs), min(ys), max(xs), max(ys))

        default_name = self.s["titre"].replace(" ", "_") + ".dxf"
        out_dir = self.s.get("output_dir")
        if out_dir and os.path.isdir(out_dir):
            dxf_path = os.path.join(out_dir, default_name)
        else:
            start_dir   = project_dir() or os.path.expanduser("~")
            dxf_path, _ = QFileDialog.getSaveFileName(
                self.iface.mainWindow(),
                "Exporter le plan en DXF 2018",
                os.path.join(start_dir, default_name),
                "DXF (*.dxf)",
            )
            if not dxf_path:
                return

        run_export_dxf_with_ui(
            self.iface, dxf_path, extent, float(self.s["echelle"]),
            with_label_decorations=True, force_2d=True, open_after=True,
        )

    # ── Export PDF ─────────────────────────────────────────────────────────

    def _export_pdf(self):
        overview_settings = self._ask_overview_settings()
        # overview_settings est None si l'utilisateur a annulé la fenêtre overview
        # ou un dict si accepté, ou False si refusé

        from .projet_bet import project_dir
        # Nom du fichier projet (sans extension) comme nom PDF par défaut
        projet_path = QgsProject.instance().fileName()
        if projet_path:
            projet_nom = os.path.splitext(os.path.basename(projet_path))[0]
        else:
            projet_nom = "Plan_de_reseau"
        default_name = projet_nom + ".pdf"
        out_dir = self.s.get("output_dir")
        if out_dir and os.path.isdir(out_dir):
            pdf_path = os.path.join(out_dir, default_name)
        else:
            start_dir = project_dir() or os.path.expanduser("~")
            pdf_path, _ = QFileDialog.getSaveFileName(
                self.iface.mainWindow(),
                "Exporter le plan en PDF",
                os.path.join(start_dir, default_name),
                "PDF (*.pdf)",
            )
            if not pdf_path:
                return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._generate_pdf(pdf_path, overview_settings)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(
                self.iface.mainWindow(), "Impression",
                f"Erreur lors de la génération du PDF :\n{exc}",
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

    def _ask_overview_settings(self):
        """Demande simplement si l'utilisateur veut un plan d'ensemble.
        L'échelle est calculée automatiquement pour faire tenir la bbox
        des feuilles + 30 % de marge dans le même format que les détails."""
        from qgis.PyQt.QtWidgets import QMessageBox

        rep = QMessageBox.question(
            self.iface.mainWindow(),
            "Plan d'ensemble",
            "Ajouter un plan d'ensemble en première page ?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
        )
        if rep == QMessageBox.Cancel:
            return None
        if rep == QMessageBox.No:
            return False

        # Bbox de toutes les emprises (coins, rotation incluse)
        all_pts = []
        for sheet in self._sheets:
            all_pts.extend(self._corners(
                sheet['center'].x(), sheet['center'].y(), sheet['rotation_rad']))
        xs = [p.x() for p in all_pts]
        ys = [p.y() for p in all_pts]
        raw_w = max(xs) - min(xs) if len(xs) > 1 else self._w
        raw_h = max(ys) - min(ys) if len(ys) > 1 else self._h

        # Marge 30 % de chaque côté
        bbox_w_m = raw_w * 1.60
        bbox_h_m = raw_h * 1.60
        cx_bbox  = (min(xs) + max(xs)) / 2
        cy_bbox  = (min(ys) + max(ys)) / 2

        # Échelle auto : la bbox doit tenir dans le format HORS cartouche
        w_mm    = self.s["w_mm"]
        h_mm    = self.s["h_mm"]
        carto_h = max(15.0, min(30.0, h_mm * 0.085))
        h_map   = h_mm - carto_h          # hauteur dispo pour la carte
        ech     = max(bbox_w_m * 1000 / w_mm, bbox_h_m * 1000 / h_map)

        return {
            "echelle":  ech,
            "w_mm":     w_mm,
            "h_mm":     h_mm,
            "carto_h":  carto_h,
            "cx":       cx_bbox,
            "cy":       cy_bbox,
            "bbox_w_m": bbox_w_m,
            "bbox_h_m": bbox_h_m,
        }

    @staticmethod
    def _nice_scalebar_step(meters):
        """Arrondit à une valeur lisible pour la barre d'échelle (10, 20, 50, 100…)."""
        nice = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
        for v in nice:
            if v >= meters:
                return v
        return meters

    @staticmethod
    def _split_two_lines(text):
        """Coupe 'text' en 2 lignes à la limite de mot la plus proche du centre."""
        mid = len(text) // 2
        left  = text.rfind(' ', 0, mid + 1)
        right = text.find(' ', mid)
        if left == -1 and right == -1:
            return text
        if left == -1:
            split = right
        elif right == -1:
            split = left
        else:
            split = left if (mid - left) <= (right - mid) else right
        return text[:split] + '\n' + text[split + 1:]

    def _generate_pdf(self, pdf_path, overview_settings=False):
        w_mm    = self.s["w_mm"]
        h_mm    = self.s["h_mm"]
        echelle = self.s["echelle"]
        # Titre du cartouche = nom du fichier PDF (sans extension, _ → espace)
        pdf_title = os.path.splitext(os.path.basename(pdf_path))[0]
        pdf_title = pdf_title.replace("_", " ")
        titre   = self._split_two_lines(pdf_title)
        n       = len(self._sheets)

        # Cartouche adaptatif : ~8,5 % de la hauteur, entre 15 et 30 mm
        carto_h = max(15.0, min(30.0, h_mm * 0.085))
        carto_y = h_mm - carto_h

        layout = QgsPrintLayout(QgsProject.instance())
        layout.initializeDefaults()
        coll = layout.pageCollection()

        # ── Plan d'ensemble en 1ère page (optionnel) ─────────────────────
        temp_layer = None
        page_start = 0
        if overview_settings:
            temp_layer = self._add_overview_page(
                layout, coll, 0, carto_h, titre, overview_settings)
            page_start = 1

        for i, sheet in enumerate(self._sheets):
            cx       = sheet['center'].x()
            cy       = sheet['center'].y()
            rot      = sheet['rotation_rad']
            page_idx = page_start + i

            # ── Page ────────────────────────────────────────────────────
            if page_idx == 0:
                page = coll.pages()[0]
            else:
                page = QgsLayoutItemPage(layout)
                coll.addPage(page)
            page.setPageSize(
                QgsLayoutSize(w_mm, h_mm, QgsUnitTypes.LayoutMillimeters))

            # ── Carte pleine page (échelle exacte) ───────────────────────
            map_item = QgsLayoutItemMap(layout)
            map_item.setFrameEnabled(True)
            layout.addLayoutItem(map_item)
            map_item.attemptResize(
                QgsLayoutSize(w_mm, h_mm, QgsUnitTypes.LayoutMillimeters))
            map_item.attemptMove(
                QgsLayoutPoint(0, 0, QgsUnitTypes.LayoutMillimeters),
                page=page_idx)
            map_item.setExtent(QgsRectangle(
                cx - self._w / 2, cy - self._h / 2,
                cx + self._w / 2, cy + self._h / 2,
            ))
            map_item.setMapRotation(math.degrees(rot))

            # ── Cartouche en bandeau bas (fond blanc, sur la carte) ──────
            fmt_ech = f"{self.s['format']}  —  1 : {echelle:,}".replace(",", " ")
            sections = [
                (titre,                                       0.00, 0.45, 27, True,  Qt.AlignHCenter),
                (fmt_ech,                                     0.45, 0.32, 24, False, Qt.AlignHCenter),
                (QDate.currentDate().toString("dd/MM/yyyy"),  0.77, 0.12, 21, False, Qt.AlignHCenter),
                (f"{i + 1} / {n}",                            0.89, 0.11, 24, False, Qt.AlignHCenter),
            ]
            for text, x_frac, w_frac, pt_size, bold, align in sections:
                lbl = QgsLayoutItemLabel(layout)
                lbl.setText(text)
                f = QFont("Arial", pt_size)
                f.setBold(bold)
                lbl.setFont(f)
                lbl.setHAlign(align)
                lbl.setVAlign(Qt.AlignVCenter)
                lbl.setFrameEnabled(True)
                lbl.setBackgroundEnabled(True)
                lbl.setBackgroundColor(QColor(255, 255, 255))
                layout.addLayoutItem(lbl)
                lbl.attemptResize(
                    QgsLayoutSize(w_mm * w_frac, carto_h,
                                  QgsUnitTypes.LayoutMillimeters))
                lbl.attemptMove(
                    QgsLayoutPoint(w_mm * x_frac, carto_y,
                                   QgsUnitTypes.LayoutMillimeters),
                    page=page_idx)

            # Barre d'échelle centrée juste au-dessus du cartouche
            sb_w_mm = w_mm * 0.40
            sb_h_mm = 8.0
            sb_w_m  = sb_w_mm / 1000.0 * echelle
            seg_m   = self._nice_scalebar_step(sb_w_m / 3.0)
            scalebar = QgsLayoutItemScaleBar(layout)
            scalebar.setLinkedMap(map_item)
            scalebar.setStyle('Single Box')
            scalebar.setUnits(QgsUnitTypes.DistanceMeters)
            scalebar.setUnitLabel('m')
            scalebar.setNumberOfSegments(3)
            scalebar.setNumberOfSegmentsLeft(0)
            scalebar.setUnitsPerSegment(seg_m)
            scalebar.setFrameEnabled(False)
            scalebar.setBackgroundEnabled(False)
            layout.addLayoutItem(scalebar)
            scalebar.attemptResize(
                QgsLayoutSize(sb_w_mm, sb_h_mm, QgsUnitTypes.LayoutMillimeters))
            scalebar.attemptMove(
                QgsLayoutPoint((w_mm - sb_w_mm) / 2, carto_y - sb_h_mm - 3,
                               QgsUnitTypes.LayoutMillimeters),
                page=page_idx)

        # ── Export ───────────────────────────────────────────────────────
        exporter     = QgsLayoutExporter(layout)
        pdf_settings = QgsLayoutExporter.PdfExportSettings()
        pdf_settings.dpi = float(self.s.get("dpi", 150))
        pdf_settings.forceVectorOutput = True
        pdf_settings.simplifyGeometries = False   # fidélité géométrique
        # Compression JPEG des rasters embarqués (QGIS 3.30+)
        try:
            pdf_settings.imageCompression = (
                QgsLayoutExporter.PdfImageCompression.Lossy)
        except AttributeError:
            pass
        result = exporter.exportToPdf(pdf_path, pdf_settings)
        if temp_layer:
            QgsProject.instance().removeMapLayer(temp_layer.id())

        if result != QgsLayoutExporter.Success:
            raise RuntimeError(f"QgsLayoutExporter a retourné le code {result}")

        self.iface.messageBar().pushMessage(
            "Impression",
            f"PDF exporté — {n} feuille{'s' if n > 1 else ''} : {pdf_path}",
            level=0, duration=8,
        )
        try:
            os.startfile(pdf_path)
        except Exception:
            pass

    # ── Plan d'ensemble ────────────────────────────────────────────────────

    def _add_overview_page(self, layout, coll, page_idx,
                           carto_h, titre, ov):
        """Ajoute une page de plan d'ensemble avec les emprises numérotées."""
        from qgis.core import (
            QgsVectorLayer, QgsFeature, QgsGeometry,
            QgsSingleSymbolRenderer, QgsFillSymbol,
        )

        n        = len(self._sheets)
        w_mm     = ov["w_mm"]
        h_mm     = ov["h_mm"]
        carto_h  = ov.get("carto_h", max(15.0, min(30.0, h_mm * 0.085)))
        ech      = ov["echelle"]
        cx_bbox  = ov["cx"]
        cy_bbox  = ov["cy"]
        bbox_w_m = ov["bbox_w_m"]
        bbox_h_m = ov["bbox_h_m"]

        h_map   = h_mm - carto_h   # zone carte sans le cartouche
        carto_y = h_map            # cartouche démarre exactement là où la carte finit

        if page_idx == 0:
            page = coll.pages()[0]
        else:
            page = QgsLayoutItemPage(layout)
            coll.addPage(page)
        page.setPageSize(
            QgsLayoutSize(w_mm, h_mm, QgsUnitTypes.LayoutMillimeters))

        # ── Couche mémoire : emprises (symbologie seule, sans étiquetage PAL)
        crs_id = QgsProject.instance().crs().authid() or "EPSG:2154"
        lyr = QgsVectorLayer(
            f"Polygon?crs={crs_id}&field=numero:integer",
            "_bet_overview_", "memory",
        )
        feats = []
        for i, sheet in enumerate(self._sheets):
            corners = self._corners(
                sheet['center'].x(), sheet['center'].y(), sheet['rotation_rad'])
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPolygonXY([corners]))
            feat.setAttributes([i + 1])
            feats.append(feat)
        lyr.dataProvider().addFeatures(feats)
        lyr.updateExtents()

        sym = QgsFillSymbol.createSimple({
            'color': '30,100,200,50',
            'outline_color': '20,80,180,230',
            'outline_width': '0.8',
        })
        lyr.setRenderer(QgsSingleSymbolRenderer(sym))

        QgsProject.instance().addMapLayer(lyr, False)   # pas dans la légende

        # ── Emprise vue d'ensemble ────────────────────────────────────────
        ext_w_m = w_mm * ech / 1000.0
        ext_h_m = h_map * ech / 1000.0
        overview_ext = QgsRectangle(
            cx_bbox - ext_w_m / 2, cy_bbox - ext_h_m / 2,
            cx_bbox + ext_w_m / 2, cy_bbox + ext_h_m / 2,
        )

        # ── Carte (hauteur hors cartouche) ───────────────────────────────
        map_item = QgsLayoutItemMap(layout)
        map_item.setFrameEnabled(True)
        map_item.setKeepLayerSet(True)
        map_item.setLayers([lyr] + list(self.canvas().layers()))
        layout.addLayoutItem(map_item)
        map_item.attemptResize(
            QgsLayoutSize(w_mm, h_map, QgsUnitTypes.LayoutMillimeters))
        map_item.attemptMove(
            QgsLayoutPoint(0, 0, QgsUnitTypes.LayoutMillimeters),
            page=page_idx)
        map_item.setExtent(overview_ext)

        # ── Numéros de feuilles : QgsLayoutItemLabel centrés précisément ─
        # Le moteur PAL déplace librement les étiquettes ; on calcule ici la
        # position exacte depuis les coordonnées du centre de chaque feuille.
        for i, sheet in enumerate(self._sheets):
            cx_s = sheet['center'].x()
            cy_s = sheet['center'].y()

            # Conversion carte → layout (Y inversé : carte ↑ = layout ↓)
            lx = (cx_s - overview_ext.xMinimum()) / overview_ext.width()  * w_mm
            ly = (overview_ext.yMaximum() - cy_s)  / overview_ext.height() * h_map

            # Taille du label proportionnelle à l'emprise de la feuille
            lbl_w = max(8.0,  min(60.0, self._w / overview_ext.width()  * w_mm  * 0.55))
            lbl_h = max(6.0,  min(40.0, self._h / overview_ext.height() * h_map * 0.45))

            num_lbl = QgsLayoutItemLabel(layout)
            num_lbl.setText(str(i + 1))
            f = QFont("Arial", 36)
            f.setBold(True)
            num_lbl.setFont(f)
            num_lbl.setHAlign(Qt.AlignHCenter)
            num_lbl.setVAlign(Qt.AlignVCenter)
            num_lbl.setFrameEnabled(False)
            num_lbl.setBackgroundEnabled(False)
            layout.addLayoutItem(num_lbl)
            num_lbl.attemptResize(
                QgsLayoutSize(lbl_w, lbl_h, QgsUnitTypes.LayoutMillimeters))
            num_lbl.attemptMove(
                QgsLayoutPoint(lx - lbl_w / 2, ly - lbl_h / 2,
                               QgsUnitTypes.LayoutMillimeters),
                page=page_idx)

        # ── Cartouche en bandeau bas (fond blanc, sur la carte) ──────────
        _ov_titre = f"{titre} — Plan d'ensemble"
        sections = [
            (_ov_titre,                                  0.00, 0.55, 24, True,  Qt.AlignHCenter),
            (f"{n} feuille{'s' if n > 1 else ''}",      0.55, 0.20, 22, False, Qt.AlignHCenter),
            (QDate.currentDate().toString("dd/MM/yyyy"), 0.75, 0.13, 20, False, Qt.AlignHCenter),
            ("Ensemble",                                 0.88, 0.12, 22, False, Qt.AlignHCenter),
        ]
        for text, x_frac, w_frac, pt_size, bold, align in sections:
            lbl = QgsLayoutItemLabel(layout)
            lbl.setText(text)
            f = QFont("Arial", pt_size)
            f.setBold(bold)
            lbl.setFont(f)
            lbl.setHAlign(align)
            lbl.setVAlign(Qt.AlignVCenter)
            lbl.setFrameEnabled(True)
            lbl.setBackgroundEnabled(True)
            lbl.setBackgroundColor(QColor(255, 255, 255))
            layout.addLayoutItem(lbl)
            lbl.attemptResize(
                QgsLayoutSize(w_mm * w_frac, carto_h,
                              QgsUnitTypes.LayoutMillimeters))
            lbl.attemptMove(
                QgsLayoutPoint(w_mm * x_frac, carto_y,
                               QgsUnitTypes.LayoutMillimeters),
                page=page_idx)

        # Barre d'échelle centrée juste au-dessus du cartouche
        sb_w_mm = w_mm * 0.40
        sb_h_mm = 8.0
        sb_w_m  = sb_w_mm / 1000.0 * ech
        seg_m   = self._nice_scalebar_step(sb_w_m / 3.0)
        scalebar = QgsLayoutItemScaleBar(layout)
        scalebar.setLinkedMap(map_item)
        scalebar.setStyle('Single Box')
        scalebar.setUnits(QgsUnitTypes.DistanceMeters)
        scalebar.setUnitLabel('m')
        scalebar.setNumberOfSegments(3)
        scalebar.setNumberOfSegmentsLeft(0)
        scalebar.setUnitsPerSegment(seg_m)
        scalebar.setFrameEnabled(False)
        scalebar.setBackgroundEnabled(False)
        layout.addLayoutItem(scalebar)
        scalebar.attemptResize(
            QgsLayoutSize(sb_w_mm, sb_h_mm, QgsUnitTypes.LayoutMillimeters))
        scalebar.attemptMove(
            QgsLayoutPoint((w_mm - sb_w_mm) / 2, carto_y - sb_h_mm - 3,
                           QgsUnitTypes.LayoutMillimeters),
            page=page_idx)

        return lyr   # à supprimer après export
