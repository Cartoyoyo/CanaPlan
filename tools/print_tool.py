# -*- coding: utf-8 -*-
import os

from . import i18n
import math
from qgis.PyQt.QtCore import Qt, QDate, QSize
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QDialog,
    QApplication, QFileDialog, QMessageBox,
    QGraphicsTextItem,
)
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.core import (
    Qgis,
    QgsWkbTypes, QgsGeometry, QgsRectangle, QgsPointXY,
    QgsProject, QgsMapSettings, QgsMapRendererParallelJob,
)
from . import errlog

# États de l'outil
_STATE_MOVE   = 0   # rectangle suit la souris (libre ou domino)
_STATE_ROTATE = 1   # ancrage fixé, rectangle pivote autour du centre


# Instrumentation TEMPORAIRE du temps d'export (journal QGIS, onglet CanaPlan).
# Passer à False pour la couper sans rien retirer d'autre.
_CHRONO = True


class _Chrono:
    """Chronomètre d'étapes, déversé dans le journal QGIS.

    Volontairement silencieux si _CHRONO est False, pour qu'aucun appel de
    mesure n'ait à être retiré du code quand on coupe l'instrumentation.
    """

    TAG = "CanaPlan"

    def __init__(self, titre):
        import time
        self._time = time.perf_counter
        self._t0 = self._time()
        self._precedent = self._t0
        if _CHRONO:
            self.log(f"───── {titre} ─────")

    def log(self, message):
        if not _CHRONO:
            return
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(message, self.TAG, Qgis.MessageLevel.Info)

    def etape(self, libelle):
        """Temps écoulé depuis l'étape précédente, et depuis le début."""
        if not _CHRONO:
            return
        maintenant = self._time()
        self.log("%-34s %7.2f s   (cumul %6.2f s)"
                 % (libelle, maintenant - self._precedent, maintenant - self._t0))
        self._precedent = maintenant

    def depuis_debut(self):
        return self._time() - self._t0


# Teintes des emprises sur le plan d'ensemble. Choisies franchement
# distinctes les unes des autres : c'est la couleur, plus que le numéro, qui
# permet de suivre une planche du regard quand les emprises se recouvrent.
_TEINTES_PLANCHES = (210, 0, 135, 32, 280, 175, 55, 320)


def _couleur_planche(index, alpha=255):
    """Couleur d'une planche, cyclique au-delà de la palette."""
    from qgis.PyQt.QtGui import QColor
    teinte = _TEINTES_PLANCHES[index % len(_TEINTES_PLANCHES)]
    couleur = QColor.fromHsv(teinte, 205, 190)
    couleur.setAlpha(alpha)
    return couleur


def _aide_pose(settings):
    """Message de la barre d'état pendant la pose des feuilles."""
    return i18n.tr(
        'pt_aide_pose',
        format=settings["format"],
        orientation=i18n.tr('pd_portrait' if settings["orientation"] == 'portrait'
                            else 'pd_paysage'),
        echelle=f'{settings["echelle"]:,}'.replace(",", " "))


class PrintTool(QgsMapTool):

    def __init__(self, canvas, iface, settings, on_finished=None):
        super().__init__(canvas)
        self.iface = iface
        self.s     = settings

        # Appelé une seule fois quand l'outil rend la main, que l'export ait
        # eu lieu ou que l'utilisateur ait abandonné. L'export tout en un s'en
        # sert pour refermer son archive : lui seul sait quand la pose des
        # feuilles est finie.
        self._on_finished       = on_finished
        self._finished_notified = False

        factor  = settings["echelle"] / 1000.0
        self._w = settings["w_mm"] * factor   # largeur feuille en mètres
        self._h = settings["h_mm"] * factor   # hauteur feuille en mètres

        self._state   = _STATE_MOVE
        self._anchor  = None    # QgsPointXY : centre ancré au 1er clic
        self._cur_rot = 0.0     # rotation courante en radians (horaire depuis N)

        self._sheets = []   # [{'center': QgsPointXY, 'rotation_rad': float}]
        self._bands  = []   # [QgsRubberBand] feuilles définitivement posées

        self._preview = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self._preview.setColor(QColor(255, 140, 0, 70))
        self._preview.setStrokeColor(QColor(220, 100, 0, 230))
        self._preview.setWidth(2)

        # Trait épais rouge sur le bord HAUT pour distinguer le sens
        self._preview_top_edge = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.LineGeometry)
        self._preview_top_edge.setColor(QColor(220, 30, 30, 255))
        self._preview_top_edge.setWidth(5)

        # Bande grise en bas = zone cartouche
        self._preview_carto_band = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
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

        self.setCursor(Qt.CursorShape.CrossCursor)

    # ── Cycle de vie ───────────────────────────────────────────────────────

    def activate(self):
        super().activate()
        self.canvas().setCursor(Qt.CursorShape.CrossCursor)
        if self.s.get('cadrage_auto'):
            return   # rien à poser : l'aide n'aurait aucun sens
        self.iface.messageBar().pushMessage(
            i18n.tr('msg_impression'), _aide_pose(self.s),
            level=Qgis.MessageLevel.Info, duration=0,
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
        self._notify_finished()

    def _notify_finished(self):
        """Prévient l'appelant, une fois au plus.

        Différé d'un tour de boucle : deactivate() est appelé au milieu d'un
        changement d'outil du canevas, où ouvrir une fenêtre modale n'est pas
        sain.
        """
        if self._finished_notified or self._on_finished is None:
            return
        self._finished_notified = True

        from qgis.PyQt.QtCore import QTimer
        callback = self._on_finished
        self._on_finished = None
        QTimer.singleShot(0, callback)

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

        if event.button() == Qt.MouseButton.LeftButton:
            if self._state == _STATE_MOVE:
                # 1er clic : ancrer la position, passer en rotation
                self._anchor  = self._compute_move_center(pt)
                self._cur_rot = 0.0
                self._state   = _STATE_ROTATE
                n = len(self._sheets) + 1
                self.iface.messageBar().pushMessage(
                    i18n.tr('msg_impression'),
                    i18n.tr('pt_orienter', n=n),
                    level=Qgis.MessageLevel.Info, duration=5,
                )

            else:  # _STATE_ROTATE
                # 2ème clic : fixer l'orientation, poser la feuille
                self._place_sheet(self._anchor, self._cur_rot)
                self._state = _STATE_MOVE

        elif event.button() == Qt.MouseButton.RightButton:
            if self._sheets:
                self._ask_and_export()
            else:
                self.canvas().unsetMapTool(self)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            from qgis.PyQt.QtCore import QTimer
            self._reset()
            QTimer.singleShot(0, self._reopen_settings)
            event.accept()

        elif event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if self._state == _STATE_ROTATE:
                # Annule l'ancrage en cours, revient au placement libre
                self._state   = _STATE_MOVE
                self._anchor  = None
                self._cur_rot = 0.0
                self.iface.messageBar().pushMessage(
                    i18n.tr('msg_impression'), i18n.tr('pt_ancrage_annule'),
                    level=Qgis.MessageLevel.Info, duration=3)
            elif self._sheets:
                # Dépile uniquement la dernière feuille posée
                self._sheets.pop()
                band = self._bands.pop()
                band.reset()
                self.canvas().scene().removeItem(band)
                self.iface.messageBar().pushMessage(
                    i18n.tr('msg_impression'),
                    i18n.tr('pt_feuille_supprimee', n=len(self._sheets) + 1),
                    level=Qgis.MessageLevel.Info, duration=3)
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
        index_ori = dlg.orient_combo.findData(self.s["orientation"])
        if index_ori >= 0:
            dlg.orient_combo.setCurrentIndex(index_ori)
        for idx in range(dlg.scale_combo.count()):
            if dlg.scale_combo.itemData(idx) == self.s["echelle"]:
                dlg.scale_combo.setCurrentIndex(idx)
                break
        # On pose des planches à la main : rouvrir les réglages ne doit pas
        # faire repartir en cadrage automatique, qui est pourtant le défaut.
        if self.s.get('cadrage_auto'):
            dlg.rb_auto.setChecked(True)
        else:
            dlg.rb_manuel.setChecked(True)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            self.canvas().unsetMapTool(self)
            return

        # La fenêtre ne rend que les réglages de mise en page : tout ce qui
        # a été décidé ailleurs — formats à produire, dossier de sortie,
        # ouverture après export — doit survivre à sa réouverture.
        conserves = {cle: self.s[cle]
                     for cle in ('do_pdf', 'do_dxf', 'output_dir', 'open_after')
                     if cle in self.s}
        self.s = dlg.get_settings()
        self.s.update(conserves)
        factor   = self.s["echelle"] / 1000.0
        self._w  = self.s["w_mm"] * factor
        self._h  = self.s["h_mm"] * factor

        # Réactiver explicitement l'outil sur le canevas
        self.canvas().setMapTool(self)

        self.iface.messageBar().pushMessage(
            i18n.tr('msg_impression'), _aide_pose(self.s),
            level=Qgis.MessageLevel.Info, duration=0,
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

    def _corners_zone_carte(self, cx, cy, theta_rad):
        """Coins de la zone cartographiée d'une feuille, cartouche exclu.

        _corners() délimite la feuille de papier ; la page imprimée, elle,
        ne montre que la zone au-dessus du cartouche, et son centre est donc
        un demi-cartouche plus haut. Le plan d'ensemble doit délimiter cette
        zone-là, sans quoi ses cadres annoncent une bande de terrain que les
        pages ne montrent pas.
        """
        carto_h_m = self._carto_h_m()
        ct, st = math.cos(theta_rad), math.sin(theta_rad)
        # Même remontée que dans _generate_pdf pour passer du centre de la
        # feuille au centre de la carte.
        ccx = cx + (carto_h_m / 2.0) * st
        ccy = cy + (carto_h_m / 2.0) * ct
        hw = self._w / 2.0
        hh = (self._h - carto_h_m) / 2.0
        local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        return [
            QgsPointXY(ccx + lx * ct + ly * st,
                       ccy - lx * st + ly * ct)
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

    def definir_feuilles(self, planches):
        """Impose la liste des planches, sans passer par les clics.

        Utilisé par le cadrage automatique. Les emprises s'affichent comme
        des feuilles posées à la main : le reste de l'outil, export compris,
        ne fait aucune différence entre les deux origines.
        """
        for centre, rotation in planches:
            self._place_sheet(centre, rotation, annoncer=False)

    def exporter_maintenant(self):
        """Lance l'export sans attendre le clic droit (cadrage automatique)."""
        if not self._sheets:
            return
        self._ask_and_export()

    def _place_sheet(self, center, rotation_rad, annoncer=True):
        corners = self._corners(center.x(), center.y(), rotation_rad)
        band = QgsRubberBand(self.canvas(), QgsWkbTypes.GeometryType.PolygonGeometry)
        band.setColor(QColor(30, 100, 200, 45))
        band.setStrokeColor(QColor(20, 80, 180, 210))
        band.setWidth(2)
        band.setToGeometry(QgsGeometry.fromPolygonXY([corners]), None)

        self._sheets.append({
            'center':       QgsPointXY(center),
            'rotation_rad': rotation_rad,
        })
        self._bands.append(band)

        if annoncer:
            n = len(self._sheets)
            self.iface.messageBar().pushMessage(
                i18n.tr('msg_impression'),
                i18n.tr('pt_feuille_posee', n=n),
                level=Qgis.MessageLevel.Info, duration=4,
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
                self.iface.mainWindow(), i18n.tr('pt_export_dxf'),
                i18n.tr('pt_aucune_planche'))
            return
        xs = [p.x() for p in all_corners]
        ys = [p.y() for p in all_corners]
        extent = QgsRectangle(min(xs), min(ys), max(xs), max(ys))

        default_name = self.s["titre"].replace(" ", "_") + ".dxf"
        out_dir  = self.s.get("output_dir")
        dxf_path = None
        if out_dir and os.path.isdir(out_dir):
            cand = os.path.join(out_dir, default_name)
            # Ne jamais écraser silencieusement un fichier existant
            if not os.path.exists(cand) or QMessageBox.question(
                    self.iface.mainWindow(), i18n.tr('pt_export_dxf'),
                    i18n.tr('pt_fichier_existe', chemin=cand),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                dxf_path = cand
        if not dxf_path:
            start_dir   = project_dir() or os.path.expanduser("~")
            dxf_path, _ = QFileDialog.getSaveFileName(
                self.iface.mainWindow(),
                i18n.tr('msg_export_dxf_titre'),
                os.path.join(start_dir, default_name),
                i18n.tr('fic_dxf'),
            )
            if not dxf_path:
                return

        run_export_dxf_with_ui(
            self.iface, dxf_path, extent, float(self.s["echelle"]),
            with_label_decorations=True, force_2d=True,
            open_after=self.s.get('open_after', True),
        )

    # ── Export PDF ─────────────────────────────────────────────────────────

    def _export_pdf(self):
        # Le plan d'ensemble est un réglage de la fenêtre d'export, plus une
        # question posée au milieu de l'export.
        overview_settings = (self._overview_settings()
                             if self.s.get('plan_ensemble', True) else False)

        from .projet_bet import project_dir
        # Nom du fichier projet (sans extension) comme nom PDF par défaut
        projet_path = QgsProject.instance().fileName()
        if projet_path:
            projet_nom = os.path.splitext(os.path.basename(projet_path))[0]
        else:
            projet_nom = "Plan_de_reseau"
        default_name = projet_nom + ".pdf"
        out_dir  = self.s.get("output_dir")
        pdf_path = None
        if out_dir and os.path.isdir(out_dir):
            cand = os.path.join(out_dir, default_name)
            # Ne jamais écraser silencieusement un fichier existant
            if not os.path.exists(cand) or QMessageBox.question(
                    self.iface.mainWindow(), i18n.tr('msg_impression'),
                    i18n.tr('pt_fichier_existe', chemin=cand),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                pdf_path = cand
        if not pdf_path:
            start_dir = project_dir() or os.path.expanduser("~")
            pdf_path, _ = QFileDialog.getSaveFileName(
                self.iface.mainWindow(),
                i18n.tr('pt_export_pdf_titre'),
                os.path.join(start_dir, default_name),
                i18n.tr('fic_pdf_court'),
            )
            if not pdf_path:
                return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._generate_pdf(pdf_path, overview_settings)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(
                self.iface.mainWindow(), i18n.tr('msg_impression'),
                i18n.tr('pt_erreur_pdf', erreur=exc),
            )
            return
        finally:
            QApplication.restoreOverrideCursor()

    def _overview_settings(self):
        """Réglages du plan d'ensemble, ou False s'il n'y a rien à cadrer.

        L'échelle est calculée automatiquement pour faire tenir la bbox des
        planches + 30 % de marge dans le même format que les détails.
        """
        if not self._sheets:
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
        ech_raw = max(bbox_w_m * 1000 / w_mm, bbox_h_m * 1000 / h_map)
        # Arrondi à l'échelle normalisée supérieure (affichable en cartouche)
        _std = [100, 200, 250, 500, 750, 1000, 1500, 2000, 2500, 5000,
                7500, 10000, 15000, 20000, 25000, 50000]
        ech  = next((v for v in _std if v >= ech_raw),
                    math.ceil(ech_raw / 10000.0) * 10000)

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
        from qgis.PyQt.QtGui import QPainter, QPen, QPolygon, QTransform
        from qgis.PyQt.QtCore import QRect, QRectF, QPoint, QEventLoop
        from qgis.PyQt.QtWidgets import QProgressDialog
        from qgis.core import QgsProject

        chrono = _Chrono("Export PDF")

        w_mm    = self.s["w_mm"]
        h_mm    = self.s["h_mm"]
        echelle = self.s["echelle"]
        dpi     = float(self.s.get("dpi", 150))
        n       = len(self._sheets)

        # Couches cochées, dans l'ordre de rendu réel (custom layer order si
        # défini, sinon ordre de l'arbre). canvas().layers() appliquait le filtre
        # d'échelle du canevas, ce qui excluait les couches hors échelle courante
        # (ex. ortho visible seulement à 1:2000). On reconstruit la liste sans
        # ce filtre : QgsMapSettings applique lui-même la visibilité par échelle.
        _root = QgsProject.instance().layerTreeRoot()
        _visible_ids = {
            node.layer().id()
            for node in _root.findLayers()
            if node.isVisible() and node.layer() is not None
        }
        if _root.hasCustomLayerOrder():
            # customLayerOrder() = [bas→haut] ; setLayers() attend [haut→bas]
            _ordered = list(reversed(_root.customLayerOrder()))
        else:
            # findLayers() = [haut→bas] dans l'arbre, ordre correct pour setLayers()
            _ordered = [node.layer() for node in _root.findLayers()
                        if node.layer() is not None]
        _print_layers = [lyr for lyr in _ordered
                         if lyr is not None and lyr.id() in _visible_ids]

        chrono.etape("preparation des couches")
        if _CHRONO:
            # Le fournisseur distingue les couches locales des flux distants,
            # dont la latence est le premier suspect.
            chrono.log("  %d couches, %d feuilles, %.0f dpi, format %s"
                       % (len(_print_layers), n, dpi, self.s['format']))
            for lyr in _print_layers:
                try:
                    fournisseur = lyr.dataProvider().name()
                except Exception:
                    fournisseur = "?"
                if fournisseur in ('wms', 'wmts', 'xyz', 'arcgismapserver'):
                    detail = "  <-- flux distant"
                    # Le format demande et le mode de tuilage pesent bien plus
                    # lourd que tout le reste : on veut les voir.
                    try:
                        chrono.log("      source: %s" % lyr.source())
                    except Exception as _err:
                        errlog.ignored(_err, "print_tool._generate_pdf:782")
                else:
                    try:
                        detail = "  %d entites" % lyr.featureCount()
                    except Exception:
                        detail = ""
                chrono.log("    [%-8s] %-34s%s"
                           % (fournisseur, lyr.name(), detail))

        pdf_title = os.path.splitext(os.path.basename(pdf_path))[0].replace("_", " ")
        titre     = self._split_two_lines(pdf_title)

        # Conversions utilitaires
        def px(mm_val):
            return int(mm_val * dpi / 25.4)

        w_px = px(w_mm)
        h_px = px(h_mm)

        # Cartouche adaptatif
        carto_h_mm = max(15.0, min(30.0, h_mm * 0.085))
        carto_y_mm = h_mm - carto_h_mm
        carto_y_px = px(carto_y_mm)
        carto_h_px = px(carto_h_mm)

        fmt_ech = f"{self.s['format']}  —  1 : {echelle:,}".replace(",", " ")

        # ── Pré-vérification du verrou fichier ───────────────────────────
        # Détecte un PDF ouvert dans un autre programme AVANT de lancer les
        # rendus (longs), plutôt qu'à l'ouverture du QPrinter après coup.
        if os.path.exists(pdf_path):
            try:
                with open(pdf_path, "ab"):
                    pass
            except OSError:
                raise RuntimeError(
                    i18n.tr('pt_ecriture_impossible', chemin=pdf_path))

        first_page = [True]

        def _new_page():
            if first_page[0]:
                first_page[0] = False
            else:
                writer.newPage()

        def _start_render(cx, cy, rot_rad, w_m, h_m, out_w=None, out_h=None):
            """Démarre un job de rendu (non bloquant) et le retourne."""
            proj = QgsProject.instance()
            ms = QgsMapSettings()
            ms.setDestinationCrs(proj.crs())
            ms.setTransformContext(proj.transformContext())
            ms.setEllipsoid(proj.ellipsoid())
            # QgsMapRendererParallelJob composite les couches selon la
            # convention QgsMapSettings : index 0 = premier plan. _print_layers
            # est déjà en ordre [haut→bas] de l'arbre : pas d'inversion
            # (l'inversion de l'ancien SequentialJob passait l'ortho devant).
            ms.setLayers(_print_layers)
            ms.setOutputSize(QSize(out_w or w_px, out_h or h_px))
            ms.setExtent(QgsRectangle(cx - w_m / 2, cy - h_m / 2,
                                       cx + w_m / 2, cy + h_m / 2))
            # Signe inverse : QgsMapSettings.setRotation() fait tourner le
            # CONTENU, alors que rot_rad oriente la PLANCHE. Vérifié sur
            # l'API : une ligne d'azimut +30° est redressée par
            # setRotation(-30) ; setRotation(+30) la porte à +60°, soit deux
            # fois l'inclinaison — ce que montraient les planches.
            ms.setRotation(-math.degrees(rot_rad))
            ms.setOutputDpi(dpi)
            ms.setBackgroundColor(QColor(255, 255, 255))
            try:
                ms.setFlag(Qgis.MapSettingsFlag.Antialiasing,       True)
                ms.setFlag(Qgis.MapSettingsFlag.DrawLabeling,       True)
                ms.setFlag(Qgis.MapSettingsFlag.UseAdvancedEffects, True)
                # ForceVectorOutput n'a rien à faire ici : la sortie de ce job
                # est une QImage (renderedImage()), recollée ensuite dans le
                # QPrinter. Le drapeau ne préservait donc aucun vectoriel mais
                # privait QGIS de ses raccourcis de rendu.
            except AttributeError as _err:
                errlog.ignored(_err, "print_tool._start_render:860")

            # Vertices tombant dans le même pixel : inutiles à cette
            # résolution, mais coûteux à parcourir sur les fonds cadastraux.
            # Seuil en pixels, donc invisible par construction.
            try:
                from qgis.core import QgsVectorSimplifyMethod
                simplify = QgsVectorSimplifyMethod()
                simplify.setSimplifyHints(
                    Qgis.VectorRenderingSimplificationFlag.GeometrySimplification)
                simplify.setSimplifyAlgorithm(Qgis.VectorSimplificationAlgorithm.Distance)
                simplify.setThreshold(1.0)
                simplify.setForceLocalOptimization(True)
                ms.setSimplifyMethod(simplify)
            except Exception as _err:
                errlog.ignored(_err, "print_tool._start_render:875")
            # ParallelJob : les couches d'une même page sont rendues sur
            # plusieurs threads (SequentialJob n'en utilisait qu'un seul).
            job = QgsMapRendererParallelJob(ms)
            job.start()
            return job

        def _draw_scalebar(ech=None):
            """Barre d'échelle discrète, tracée à même la carte."""
            ech = ech or echelle
            n_seg = 4

            # Largeur visée ~28 % de la page, arrondie à une valeur ronde.
            sb_w_m  = w_mm * 0.28 / 1000.0 * ech
            seg_m   = self._nice_scalebar_step(sb_w_m / n_seg)
            seg_px  = seg_m * 1000.0 / ech * dpi / 25.4
            total_px = int(seg_px * n_seg)

            sb_h_px = max(3, px(1.8))     # barre fine : 1,8 mm

            # La police d'abord : c'est elle qui impose la hauteur de la
            # bande de libellés. Fixer cette hauteur en millimètres coupait
            # le texte par le bas dès que la police dépassait — ce qui était
            # le cas sur tous les formats à partir du A3.
            drapeau = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
            f_sb = QFont("Arial")
            f_sb.setPointSize(max(5, int(carto_h_mm / 25.4 * 72 * 0.16)))
            painter.setFont(f_sb)
            lbl_h = painter.boundingRect(
                QRect(0, 0, w_px, px(30)), drapeau, "0000 m").height()
            lbl_h += max(1, px(0.8))

            sb_x = (w_px - total_px) // 2
            sb_y = carto_y_px - px(3) - sb_h_px

            encre = QColor(0x33, 0x33, 0x33)

            # ── Segments alternés ────────────────────────────────────────
            for k in range(n_seg):
                r = QRect(sb_x + int(k * seg_px), sb_y, int(seg_px), sb_h_px)
                painter.fillRect(r, encre if k % 2 == 0
                                 else QColor(255, 255, 255))

            # Un seul contour pour toute la barre, plus les séparations : les
            # segments encadrés un par un doublaient chaque trait intérieur.
            painter.setPen(QPen(encre, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRect(sb_x, sb_y, total_px, sb_h_px))
            for k in range(1, n_seg):
                x = sb_x + int(k * seg_px)
                painter.drawLine(x, sb_y, x, sb_y + sb_h_px)

            # ── Graduations ──────────────────────────────────────────────
            painter.setPen(encre)
            for k in range(n_seg + 1):
                valeur = seg_m * k
                texte = ("%g" % valeur)
                if k == n_seg:
                    texte += " m"     # l'unité une seule fois, en bout
                lx = sb_x + int(k * seg_px)
                # Largeur mesurée et non calée sur une graduation : le dernier
                # libellé porte l'unité, il est donc plus large qu'un pas de
                # graduation et se faisait tronquer.
                besoin = painter.boundingRect(
                    QRect(0, 0, w_px, lbl_h), drapeau, texte)
                demi = besoin.width() // 2 + max(1, px(0.6))
                painter.drawText(
                    QRect(lx - demi, sb_y - lbl_h, 2 * demi, lbl_h),
                    drapeau, texte)

        def _draw_cartouche(titre_txt, fmt, page_num):
            painter.fillRect(
                QRect(0, carto_y_px, w_px, h_px - carto_y_px),
                QColor(255, 255, 255))
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.drawLine(0, carto_y_px, w_px, carto_y_px)
            pt = max(7, int(carto_h_mm / 25.4 * 72 * 0.30))

            def _police_ajustee(text, max_w, max_h, bold):
                """Plus grande taille <= pt qui fait tenir `text` dans la case.

                La taille de base ne se déduit que de la hauteur du bandeau.
                En portrait, celle-ci est plafonnée à 30 mm sur une page
                étroite : la case de date, qui ne fait que 12 % de la largeur,
                est alors bien trop petite. Le retour à la ligne ne sauve rien,
                une date n'ayant aucune espace où se couper.
                """
                f = QFont("Arial")
                f.setBold(bold)
                flags = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap
                for taille in range(int(pt), 4, -1):
                    f.setPointSize(taille)
                    # boundingRect du painter : métriques du périphérique de
                    # sortie, pas celles de l'écran.
                    painter.setFont(f)
                    besoin = painter.boundingRect(
                        QRect(0, 0, max_w, max_h), flags, text)
                    if besoin.width() <= max_w and besoin.height() <= max_h:
                        break
                return f

            # La date est incompressible (10 caractères sans espace) alors
            # que le titre a toujours de la marge : les 4 % transférés ne
            # coûtent rien au titre et évitent une date en corps 6.
            sections = [
                (titre_txt, 0.00, 0.41, True),
                (fmt,       0.41, 0.32, False),
                (QDate.currentDate().toString("dd/MM/yyyy"), 0.73, 0.16, False),
                (page_num,  0.89, 0.11, False),
            ]
            for text, xf, wf, bold in sections:
                xp = int(xf * w_px)
                wp = int(wf * w_px)
                if xf > 0:
                    painter.drawLine(xp, carto_y_px, xp, h_px)
                painter.setFont(
                    _police_ajustee(text, wp - 8, carto_h_px, bold))
                painter.setPen(QColor(0, 0, 0))
                painter.drawText(
                    QRect(xp + 4, carto_y_px, wp - 8, carto_h_px),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                    text)
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.drawRect(QRect(0, carto_y_px, w_px - 1,
                                   h_px - carto_y_px - 1))

        def _draw_north_arrow(rot_rad):
            """Flèche du nord en haut à droite de la zone carte.

            La carte est rendue avec setRotation(-rot) : le contenu tourne de
            -rot, donc le nord s'écarte du haut de page de rot dans le sens
            anti-horaire. La flèche était déjà dessinée ainsi — c'est le
            rendu qui suivait la mauvaise convention.
            """
            size   = px(14)          # diamètre du médaillon (~14 mm)
            margin = px(5)
            cx_a   = w_px - margin - size // 2
            cy_a   = margin + size // 2
            painter.save()
            # Médaillon opaque (pas d'alpha : transparency group Qt5)
            painter.setBrush(QColor(255, 255, 255))
            painter.setPen(QPen(QColor(0, 0, 0), max(1, int(px(0.3)))))
            painter.drawEllipse(QPoint(cx_a, cy_a), size // 2, size // 2)
            painter.translate(cx_a, cy_a)
            painter.rotate(-math.degrees(rot_rad))
            r = size * 0.30
            arrow = QPolygon([
                QPoint(0, int(-r * 1.15)),
                QPoint(int(-r * 0.55), int(r * 0.45)),
                QPoint(0, int(r * 0.10)),
                QPoint(int(r * 0.55), int(r * 0.45)),
            ])
            painter.setBrush(QColor(0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(arrow)
            f_n = QFont("Arial")
            f_n.setBold(True)
            f_n.setPixelSize(max(8, int(size * 0.26)))
            painter.setFont(f_n)
            painter.setPen(QColor(0, 0, 0))
            painter.drawText(
                QRect(int(-r), int(r * 0.30), int(2 * r), int(size * 0.32)),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, "N")
            painter.restore()

        # ── Rendu de toutes les pages en parallèle ────────────────────────
        # Tous les jobs sont démarrés en même temps (threads QGIS) : les
        # latences des fonds distants (WMS, ortho, PCI) se recouvrent au lieu
        # de s'additionner. L'attente se fait via une boîte de progression
        # annulable au lieu de bloquer l'interface avec waitForFinished().
        # Le rendu reste entièrement effectué AVANT d'ouvrir le QPrinter :
        # sur Qt5/Windows, mélanger writer.newPage() et jobs de rendu dans le
        # même flux provoque des pages blanches sur les premières feuilles.
        h_map_mm = h_mm - carto_h_mm
        h_map_px = px(h_map_mm)

        ov_ctx = {}   # contexte overview pour le dessin des emprises
        jobs   = []
        if overview_settings:
            ov       = overview_settings
            ov_ech   = ov["echelle"]
            ov_w_m   = w_mm * ov_ech / 1000.0
            ov_h_m   = h_map_mm * ov_ech / 1000.0
            ov_ctx   = {
                "ov_w_m": ov_w_m, "ov_h_m": ov_h_m,
                "ov_cx":  ov["cx"], "ov_cy": ov["cy"],
                "ov_ech": ov_ech,
            }
            jobs.append(_start_render(
                ov["cx"], ov["cy"], 0.0, ov_w_m, ov_h_m, w_px, h_map_px))

        # Hauteur de la zone carte seule (même logique que le plan d'ensemble)
        h_map_m_det = h_map_mm * echelle / 1000.0
        carto_h_m   = carto_h_mm * echelle / 1000.0

        for sheet in self._sheets:
            cx  = sheet['center'].x()
            cy  = sheet['center'].y()
            rot = sheet['rotation_rad']
            # Le centre géom. de la feuille est au milieu de la page complète
            # (cartouche inclus). On remonte de la moitié du cartouche dans la
            # direction "haut" du papier pour obtenir le centre de la zone carte.
            cx_c = cx + (carto_h_m / 2) * math.sin(rot)
            cy_c = cy + (carto_h_m / 2) * math.cos(rot)
            jobs.append(_start_render(
                cx_c, cy_c, rot, self._w, h_map_m_det, w_px, h_map_px))

        chrono.etape("lancement des %d jobs" % len(jobs))

        progress = QProgressDialog(
            i18n.tr('pt_rendu_cartes'), i18n.tr('annuler'), 0, len(jobs),
            self.iface.mainWindow())
        progress.setWindowTitle(i18n.tr('msg_impression'))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(400)
        deja_fini = [False] * len(jobs)
        try:
            while True:
                done = 0
                for i, j in enumerate(jobs):
                    if j.isActive():
                        continue
                    done += 1
                    # Premier passage à l'état terminé : on horodate ce job.
                    if not deja_fini[i]:
                        deja_fini[i] = True
                        chrono.log("  job %d/%d rendu           %7.2f s"
                                   % (i + 1, len(jobs), chrono.depuis_debut()))
                progress.setValue(done)
                if progress.wasCanceled():
                    for j in jobs:
                        j.cancel()
                    self.iface.messageBar().pushMessage(
                        i18n.tr('msg_impression'), i18n.tr('pt_export_annule'),
                        level=Qgis.MessageLevel.Warning, duration=5)
                    return
                if done == len(jobs):
                    break
                QApplication.processEvents(
                    QEventLoop.ProcessEventsFlag.AllEvents, 50)
        finally:
            progress.close()

        chrono.etape("attente rendu des cartes")

        img_ov      = jobs[0].renderedImage() if overview_settings else None
        detail_imgs = [j.renderedImage()
                       for j in (jobs[1:] if overview_settings else jobs)]
        jobs.clear()

        # ── Création du PDF via QPrinter (Qt5 et Qt6) ────────────────────
        try:
            from qgis.PyQt.QtPrintSupport import QPrinter
            from qgis.PyQt.QtCore import QSizeF
            from qgis.PyQt.QtGui import QPageSize
            writer = QPrinter()
            writer.setOutputFileName(pdf_path)
            writer.setResolution(int(dpi))
            writer.setFullPage(True)
            writer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            # setPaperSize() a disparu en Qt6. setPageSize(QPageSize) existe
            # depuis Qt 5.3 et donne le même résultat au mm près.
            writer.setPageSize(
                QPageSize(QSizeF(w_mm, h_mm), QPageSize.Unit.Millimeter))
        except Exception as e:
            raise RuntimeError(i18n.tr('pt_pdf_impossible', chemin=e))

        painter = QPainter(writer)
        if not painter.isActive():
            raise RuntimeError(
                i18n.tr('pt_ecriture_impossible', chemin=pdf_path))

        # ── Plan d'ensemble ───────────────────────────────────────────────
        if overview_settings and img_ov is not None:
            _new_page()
            ov_w_m   = ov_ctx["ov_w_m"]
            ov_h_m   = ov_ctx["ov_h_m"]
            ov_cx    = ov_ctx["ov_cx"]
            ov_cy    = ov_ctx["ov_cy"]

            painter.drawImage(QRect(0, 0, w_px, h_map_px), img_ov)
            ext_xmin = ov_cx - ov_w_m / 2
            ext_ymax = ov_cy + ov_h_m / 2

            def _map_to_px(pt):
                fx = (pt.x() - ext_xmin) / ov_w_m
                fy = (ext_ymax - pt.y()) / ov_h_m
                return QPoint(int(fx * w_px), int(fy * h_map_px))

            # save/restore obligatoire : les couleurs semi-transparentes ouvrent
            # un transparency group PDF que Qt5 ne ferme pas sans restore(),
            # ce qui crée un voile blanc sur toutes les pages suivantes.
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            # Chaque planche reçoit sa teinte, et le style de trait alterne
            # au-delà de la palette : deux planches de même couleur ne se
            # ressemblent alors jamais tout à fait.
            polys = []
            for si, sheet in enumerate(self._sheets):
                # Zone cartographiée et non feuille entière : le cadre doit
                # délimiter exactement ce que la page montrera.
                corners = self._corners_zone_carte(
                    sheet['center'].x(), sheet['center'].y(),
                    sheet['rotation_rad'])
                polys.append(QPolygon([_map_to_px(c) for c in corners]))

            # Passe 1 : les fonds, très légers. Un aplat marqué s'additionne
            # dans les recouvrements et noircit justement les zones où il
            # faudrait y voir clair.
            painter.setPen(Qt.PenStyle.NoPen)
            for si, poly in enumerate(polys):
                painter.setBrush(_couleur_planche(si, 30))
                painter.drawPolygon(poly)

            # Passe 2 : tous les contours par-dessus tous les fonds, sinon le
            # fond d'une planche vient masquer le contour de sa voisine.
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for si, poly in enumerate(polys):
                style = (Qt.PenStyle.SolidLine
                         if (si // len(_TEINTES_PLANCHES)) % 2 == 0
                         else Qt.PenStyle.DashLine)
                stylo = QPen(_couleur_planche(si, 245), max(2, px(0.6)))
                stylo.setStyle(style)
                stylo.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
                painter.setPen(stylo)
                painter.drawPolygon(poly)

            # Passe 3 : les numéros. Un chiffre cerné de blanc plutôt
            # qu'une pastille pleine : le liseré suffit à le détacher d'une
            # ortho, sans masquer le fond de plan au centre de la planche,
            # justement là où on veut le lire.
            from qgis.PyQt.QtGui import QPainterPath, QFontMetrics

            sheet_h_px = self._h / ov_h_m * h_map_px
            f_num = QFont("Arial")
            f_num.setBold(True)
            f_num.setPixelSize(max(px(3.2), int(sheet_h_px * 0.20)))
            metrique = QFontMetrics(f_num, painter.device())
            liseré = max(2, px(0.55))

            for si, sheet in enumerate(self._sheets):
                # Centre de la zone carte : le centre de la feuille tombe
                # dans le cartouche, donc à côté de ce que la page montre.
                coins = self._corners_zone_carte(
                    sheet['center'].x(), sheet['center'].y(),
                    sheet['rotation_rad'])
                ctr = _map_to_px(QgsPointXY(
                    sum(c.x() for c in coins) / 4.0,
                    sum(c.y() for c in coins) / 4.0))
                texte = str(si + 1)
                try:
                    largeur = metrique.horizontalAdvance(texte)
                except AttributeError:
                    largeur = metrique.width(texte)   # Qt < 5.11

                chemin = QPainterPath()
                # addText part de la ligne de base : on recentre à la main.
                chemin.addText(
                    ctr.x() - largeur / 2.0,
                    ctr.y() + (metrique.ascent() - metrique.descent()) / 2.0,
                    f_num, texte)

                painter.setPen(QPen(QColor(255, 255, 255, 230), liseré))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(chemin)              # le cerne
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(_couleur_planche(si, 255))
                painter.drawPath(chemin)              # le chiffre
            painter.restore()

            _draw_north_arrow(0.0)
            _draw_scalebar(ov_ctx['ov_ech'])
            ov_fmt = i18n.tr(
                'pt_nb_feuilles', nb=n,
                echelle=f"{int(ov_ctx['ov_ech']):,}".replace(",", " "))
            _draw_cartouche(
                i18n.tr('pt_cartouche_ensemble', titre=titre),
                ov_fmt,
                i18n.tr('pt_ens'))

        # ── Feuilles de détail ────────────────────────────────────────────
        # Même logique que le plan d'ensemble : image limitée à la zone carte
        # (h_map_px), cartouche dessiné par-dessus dans l'espace restant.
        for i in range(len(detail_imgs)):
            _new_page()
            painter.drawImage(QRect(0, 0, w_px, h_map_px), detail_imgs[i])
            detail_imgs[i] = None   # libère l'image (pic mémoire, grands formats)
            _draw_north_arrow(self._sheets[i]['rotation_rad'])
            _draw_scalebar()
            _draw_cartouche(titre, fmt_ech, f"{i + 1} / {n}")

        painter.end()

        chrono.etape("composition et ecriture PDF")
        chrono.log("TOTAL %.2f s" % chrono.depuis_debut())

        self.iface.messageBar().pushMessage(
            i18n.tr('msg_impression'),
            i18n.tr('pt_pdf_exporte', nb=n, chemin=pdf_path),
            level=Qgis.MessageLevel.Info, duration=8,
        )
        if self.s.get('open_after', True):
            try:
                # Ouvre le PDF que le plugin vient d'ecrire, avec le lecteur
                # associe. Chemin choisi par l'utilisateur au QFileDialog.
                os.startfile(pdf_path)  # nosec B606
            except Exception as _err:
                errlog.ignored(_err, "print_tool._generate_pdf:1282")

