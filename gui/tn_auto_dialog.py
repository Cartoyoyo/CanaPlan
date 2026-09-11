# -*- coding: utf-8 -*-
"""Remplissage automatique du TN des regards et tabourets depuis les MNT IGN.

Rien n'est écrit sans validation : le dialogue échantillonne, montre ce qu'il
propose ouvrage par ouvrage (avec l'écart au TN déjà saisi), et ne rend que les
lignes cochées. Par défaut seules les valeurs manquantes sont cochées — un TN
levé ne doit pas être remplacé par une estimation sans geste explicite.
"""

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QCheckBox, QHeaderView, QComboBox,
)

from ..tools import i18n
from ..tools import altimetrie
from ..tools import altimetrie_qgis as aq

_COLOR_MISSING = QColor(181, 50, 42)
_COLOR_DERIVED = QColor(128, 128, 128)
_COLOR_ALERTE = QColor(176, 106, 0)

# Au-delà de cet écart avec le TN déjà saisi, la ligne est signalée : soit le
# levé est faux, soit le MNT ne décrit pas le terrain du projet (remblai récent,
# terrassement postérieur au vol).
SEUIL_ALERTE = 0.50   # m

# Valeur recalculee apres ecriture du TN (cf. TableauSaisieDialog).
DERIVE_FE = 'fe'
DERIVE_PROFONDEUR = 'profondeur'

COL_NOM, COL_TYPE, COL_TN, COL_MNT, COL_ECART, COL_SOURCE = range(6)


class _Worker(QThread):
    """Échantillonnage réseau hors thread UI."""

    avance = pyqtSignal(str)
    fini = pyqtSignal(object, object, str)

    def __init__(self, couches, parent=None):
        super().__init__(parent)
        self._couches = couches

    def run(self):
        try:
            infos, resultats = aq.echantillonner_reseau(
                self._couches, log=self.avance.emit)
            self.fini.emit(infos, resultats, '')
        except Exception as exc:                      # noqa: BLE001
            # Réseau coupé, service en vrac : on remonte le message, pas une
            # trace de pile dans la figure de l'utilisateur.
            self.fini.emit({}, {}, str(exc))


class TnAutoDialog(QDialog):
    """Aperçu et validation du remplissage TN. Modal.

    Après exec(), `lignes_retenues` porte les ouvrages à écrire et
    `lignes_rapport` l'intégralité de ce qui a été échantillonné (pour le CSV).
    """

    def __init__(self, couches, reseau, parent=None):
        super().__init__(parent)
        self.couches = couches
        self.reseau = reseau
        self.lignes_retenues = []
        self.lignes_rapport = []
        self._infos = {}
        self._resultats = {}
        self._cases = {}          # cle -> QCheckBox

        self.setWindowTitle(i18n.tr('tn_titre', reseau=reseau))
        self.resize(760, 520)
        self._build_ui()
        self._lancer()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        v = QVBoxLayout(self)

        self.lbl_intro = QLabel(i18n.tr('tn_intro'))
        self.lbl_intro.setWordWrap(True)
        v.addWidget(self.lbl_intro)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            i18n.tr('col_ouvrage'), i18n.tr('col_type'),
            i18n.tr('tn_col_actuel'), i18n.tr('tn_col_propose'),
            i18n.tr('tn_col_ecart'), i18n.tr('tn_col_source')])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            COL_NOM, QHeaderView.ResizeMode.Stretch)
        v.addWidget(self.table)

        self.chk_ecraser = QCheckBox(i18n.tr('tn_ecraser'))
        self.chk_ecraser.setToolTip(i18n.tr('tn_ecraser_tip'))
        self.chk_ecraser.toggled.connect(self._appliquer_ecrasement)
        v.addWidget(self.chk_ecraser)

        # TN = profondeur + FE : changer le TN oblige à recalculer l'une des
        # deux autres valeurs. Par défaut le FE suit, la profondeur de
        # tranchée étant la donnée que l'on impose le plus souvent.
        ligne_derive = QHBoxLayout()
        ligne_derive.addWidget(QLabel(i18n.tr('tn_derive_label')))
        self.combo_derive = QComboBox()
        self.combo_derive.addItem(i18n.tr('tn_derive_fe'), DERIVE_FE)
        self.combo_derive.addItem(i18n.tr('tn_derive_prof'), DERIVE_PROFONDEUR)
        self.combo_derive.setToolTip(i18n.tr('tn_derive_tip'))
        ligne_derive.addWidget(self.combo_derive)
        ligne_derive.addStretch()
        v.addLayout(ligne_derive)

        self.lbl_avert = QLabel(i18n.tr('tn_avertissement'))
        self.lbl_avert.setWordWrap(True)
        self.lbl_avert.setStyleSheet("color: #8a6d00;")
        v.addWidget(self.lbl_avert)

        self.lbl_status = QLabel()
        self.lbl_status.setWordWrap(True)
        v.addWidget(self.lbl_status)

        bas = QHBoxLayout()
        self.btn_tout = QPushButton(i18n.tr('tn_tout_cocher'))
        self.btn_tout.clicked.connect(lambda: self._cocher_tout(True))
        self.btn_rien = QPushButton(i18n.tr('tn_tout_decocher'))
        self.btn_rien.clicked.connect(lambda: self._cocher_tout(False))
        bas.addWidget(self.btn_tout)
        bas.addWidget(self.btn_rien)
        bas.addStretch()
        self.btn_ok = QPushButton(i18n.tr('tn_appliquer'))
        self.btn_ok.clicked.connect(self._valider)
        self.btn_annuler = QPushButton(i18n.tr('annuler'))
        self.btn_annuler.clicked.connect(self.reject)
        bas.addWidget(self.btn_ok)
        bas.addWidget(self.btn_annuler)
        v.addLayout(bas)

        self._activer_actions(False)

    def _activer_actions(self, actif):
        for w in (self.table, self.chk_ecraser, self.combo_derive,
                  self.btn_tout, self.btn_rien, self.btn_ok):
            w.setEnabled(actif)

    # ------------------------------------------------------------------ echantillonnage

    def _lancer(self):
        self.lbl_status.setText(i18n.tr('tn_en_cours'))
        self._worker = _Worker(self.couches, self)
        self._worker.avance.connect(
            lambda m: self.lbl_status.setText(m.strip()))
        self._worker.fini.connect(self._remplir)
        self._worker.start()

    def _remplir(self, infos, resultats, erreur):
        if erreur:
            self.lbl_status.setText(i18n.tr('tn_erreur', message=erreur))
            return
        if not infos:
            self.lbl_status.setText(i18n.tr('tn_aucun_ouvrage'))
            return

        self._infos, self._resultats = infos, resultats
        cles = sorted(infos, key=lambda c: (infos[c]['role'], infos[c]['nom']))

        self.table.setRowCount(len(cles))
        n_ok = n_hors = 0
        for row, cle in enumerate(cles):
            info = infos[cle]
            res = resultats.get(cle, {'z': None, 'source': altimetrie.SRC_AUCUNE})
            z, source = res['z'], res['source']
            tn = info['tn']
            ecart = (z - tn) if (z is not None and tn is not None) else None

            case = QCheckBox()
            case.setEnabled(z is not None)
            # Par défaut : on ne comble que les trous.
            case.setChecked(z is not None and tn is None)
            self._cases[cle] = case
            self.table.setCellWidget(row, COL_NOM, self._cellule_case(case, info['nom']))

            self.table.setItem(row, COL_TYPE, self._item(
                i18n.tr('qc_regards') if info['role'] == 'regard'
                else i18n.tr('qc_tabourets')))
            it_tn = self._item(self._fmt(tn, 3), droite=True)
            if tn is None:
                it_tn.setForeground(_COLOR_MISSING)
            self.table.setItem(row, COL_TN, it_tn)

            it_mnt = self._item(self._fmt(z, 3), droite=True)
            if z is None:
                it_mnt.setForeground(_COLOR_MISSING)
            self.table.setItem(row, COL_MNT, it_mnt)

            it_ec = self._item(self._fmt(ecart, 3, signe=True), droite=True)
            if ecart is not None and abs(ecart) >= SEUIL_ALERTE:
                it_ec.setForeground(_COLOR_ALERTE)
                it_ec.setToolTip(i18n.tr('tn_ecart_tip', seuil="%.2f" % SEUIL_ALERTE))
            self.table.setItem(row, COL_ECART, it_ec)

            it_src = self._item(altimetrie.SOURCE_LABELS.get(source, source))
            if source != altimetrie.SRC_LIDAR_HD:
                it_src.setForeground(_COLOR_DERIVED)
            self.table.setItem(row, COL_SOURCE, it_src)

            self._lignes_ordre = cles
            if z is None:
                n_hors += 1
            else:
                n_ok += 1

        self._lignes_ordre = cles
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(
            COL_NOM, QHeaderView.ResizeMode.Stretch)
        self._activer_actions(True)

        par_source = {}
        for cle in cles:
            s = resultats.get(cle, {}).get('source', altimetrie.SRC_AUCUNE)
            par_source[s] = par_source.get(s, 0) + 1
        detail = ", ".join(
            "{} : {}".format(altimetrie.SOURCE_LABELS.get(s, s), n)
            for s, n in sorted(par_source.items()))
        self.lbl_status.setText(
            i18n.tr('tn_resume', total=len(cles), ok=n_ok, hors=n_hors,
                    detail=detail))

    # ------------------------------------------------------------------ helpers

    def _cellule_case(self, case, texte):
        from qgis.PyQt.QtWidgets import QWidget, QHBoxLayout
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(6)
        h.addWidget(case)
        h.addWidget(QLabel(texte))
        h.addStretch()
        return w

    @staticmethod
    def _item(texte, droite=False):
        it = QTableWidgetItem(texte)
        if droite:
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter)
        return it

    @staticmethod
    def _fmt(val, decimales=2, signe=False):
        if val is None:
            return '—'
        gabarit = "{:+." + str(decimales) + "f}" if signe else "{:." + str(decimales) + "f}"
        return gabarit.format(val)

    def _cocher_tout(self, etat):
        for cle, case in self._cases.items():
            if case.isEnabled():
                if etat and not self.chk_ecraser.isChecked() \
                        and self._infos[cle]['tn'] is not None:
                    continue      # respecte le verrou « ne pas écraser »
                case.setChecked(etat)

    def _appliquer_ecrasement(self, actif):
        """Décoche les ouvrages déjà renseignés quand on repasse en mode
        « ne pas écraser »."""
        if actif:
            return
        for cle, case in self._cases.items():
            if self._infos[cle]['tn'] is not None:
                case.setChecked(False)

    # ------------------------------------------------------------------ sortie

    @property
    def derive(self):
        """Valeur que le TN entraine : DERIVE_FE ou DERIVE_PROFONDEUR."""
        return self.combo_derive.currentData()

    def _valider(self):
        self.lignes_retenues = []
        self.lignes_rapport = []
        for cle in getattr(self, '_lignes_ordre', []):
            info = self._infos[cle]
            res = self._resultats.get(cle, {'z': None, 'source': altimetrie.SRC_AUCUNE})
            z = res['z']
            case = self._cases.get(cle)
            retenu = bool(case and case.isChecked() and z is not None)
            if retenu:
                self.lignes_retenues.append({
                    'role': info['role'], 'fid': info['fid'],
                    'nom': info['nom'], 'z': z, 'source': res['source'],
                })
            self.lignes_rapport.append({
                'type': info['role'], 'nom': info['nom'], 'fid': info['fid'],
                'x': info['x'], 'y': info['y'],
                'tn_avant': info['tn'], 'tn_mnt': z,
                'ecart': (z - info['tn']) if (z is not None and info['tn'] is not None) else None,
                'source': altimetrie.SOURCE_LABELS.get(res['source'], res['source']),
                'applique': retenu,
            })
        self.accept()

    def reject(self):
        worker = getattr(self, '_worker', None)
        if worker is not None and worker.isRunning():
            worker.wait(3000)
        super().reject()
