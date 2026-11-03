"""Suivi lidar et carte vectorielle incrémentale pour le pilotage Wi-Fi.

Premier scan ancré ; références figées pendant chaque recalage ; insertion
uniquement après validation. Aucune odométrie n'est inventée depuis les touches.
"""
from dataclasses import dataclass
from time import perf_counter
import threading
import numpy as np
from scipy.spatial import cKDTree
from cartographie import (extraire_segments, ajuster_segment, proches, longueur,
                         Scan, mesures_valides)
from localisation import points_filtres, transformer, erreur_pose
from localisation_tp import localiser_sur_reference, LOCALE, MULTI


def reduire(points, pas=.05, maximum=40000):
    if not len(points):
        return np.empty((0, 2))
    _, idx = np.unique(np.floor(points/pas).astype(np.int64), axis=0, return_index=True)
    pts = points[np.sort(idx)]
    if len(pts) > maximum:
        raise ValueError('Carte pleine : enregistrer et commencer une nouvelle carte.')
    return pts


class ReferenceDirect:
    type = 'Sous-carte Wi-Fi'

    def __init__(self, points):
        self.fond = points.copy()
        self.arbre = cKDTree(self.fond)

    def distance(self, points):
        return self.arbre.query(points)[0]

    def residus(self, points):
        _, idx = self.arbre.query(points)
        return np.clip(points-self.fond[idx], -.5, .5).ravel()

    def contradictions(self, points):
        return 0.


@dataclass
class EtatDirect:
    scan: Scan
    accepte: bool
    message: str
    concordance: float
    duree: float
    points: np.ndarray
    segments: list
    trajectoire: np.ndarray
    cles: int
    scans_cles: tuple


class CarteDirecte:
    def __init__(self, filtres=None):
        self.filtres = dict(filtres or dict(mini=.05, maxi=12., intensite=0))
        self.points = np.empty((0, 2))
        self.appuis = []
        self.trajectoire = []
        self.cles = []
        self.pose = np.zeros(3)
        self.pose_cle = np.zeros(3)
        self.fin_us = None
        self.fin_cle = 0
        self.perdu = False
        self.reprise = False
        self.annuler = threading.Event()

    @property
    def segments(self):
        return [s.copy() for s, _ in self.appuis]

    def traiter(self, trame):
        debut = perf_counter()
        scan = trame.scan()
        score = 0.
        accepte = False
        message = ''
        try:
            pts = points_filtres(scan, self.filtres, locaux=True)
            if len(pts) < 30 or np.linalg.norm(np.ptp(pts, axis=0)) < 1.:
                raise ValueError('Pas assez de géométrie après filtrage ; robot arrêté.')
            if self.fin_us is None:
                scan.pose = [0., 0., 0.]
                message = 'Premier scan : origine fixe de la carte.'
                accepte = True
                score = 100.
            elif self.perdu:
                raise ValueError('Suivi perdu : arrêter, replacer près de la dernière pose puis Reprendre ici.')
            else:
                dt = .1 if self.reprise else (trame.fin_us-self.fin_us)/1e6
                if not 0 < dt <= 1.5:
                    raise ValueError('Scans trop espacés : suivi suspendu, robot arrêté.')
                local = self.points[np.linalg.norm(self.points-self.pose[:2], axis=1) < 15.]
                reference = ReferenceDirect(local)
                resultat = localiser_sur_reference(scan, reference, methode=MULTI if self.reprise else LOCALE,
                    pose_initiale=self.pose, annuler=self.annuler, **self.filtres)
                # Secours borné au voisinage du suivi, jamais recherche globale à chaque tour.
                if not resultat.applicable and not self.annuler.is_set():
                    resultat = localiser_sur_reference(scan, reference, methode=MULTI,
                        pose_initiale=self.pose, annuler=self.annuler, **self.filtres)
                score = 100*resultat.accord_fin
                ep, ea = erreur_pose(resultat.pose, self.pose)
                # Déplacement physiquement plausible au PWM limité, avec marge de bruit.
                plausible = ep <= .20+1.2*dt and ea <= 10.+150.*dt
                accepte = bool(resultat.applicable and resultat.accord_fin >= .75 and
                               resultat.rmse <= .10 and plausible and not self.annuler.is_set())
                if not accepte:
                    raise ValueError(f'Recalage refusé ({score:.0f} % à 12 cm) ; arrêter et reprendre le suivi.')
                scan.pose = list(resultat.pose)
                message = f'Suivi accepté : {score:.0f} % à 12 cm ; RMSE {resultat.rmse:.3f} m.'
            if self.annuler.is_set():
                raise ValueError('Cartographie arrêtée.')
            ep, ea = erreur_pose(scan.pose, self.pose_cle)
            cle = self.fin_us is None or ep >= .15 or ea >= 5. or trame.fin_us-self.fin_cle >= 2_000_000
            if cle:
                if len(self.cles) >= 2000:
                    raise ValueError('Limite de 2000 scans clés : enregistrer la carte.')
                nouveaux_points = reduire(np.vstack([self.points, transformer(pts, scan.pose)]))
                nouveaux_appuis = self._ajouter_segments(scan)
                # Publication atomique : aucun état partiellement inséré sur une erreur.
                self.points, self.appuis = nouveaux_points, nouveaux_appuis
                self.cles.append(scan)
                self.pose_cle, self.fin_cle = np.array(scan.pose), trame.fin_us
            self.pose, self.fin_us = np.array(scan.pose), trame.fin_us
            self.reprise = False
            self.trajectoire.append(self.pose.copy())
            self.trajectoire = self.trajectoire[-4000:]
        except (ValueError, RuntimeError) as exc:
            accepte = False
            self.perdu = True
            message = str(exc)
        return EtatDirect(scan, accepte, message, score, perf_counter()-debut,
                          self.points.copy(), self.segments, np.asarray(self.trajectoire), len(self.cles), tuple(self.cles))

    def reprendre(self):
        """Autorisation explicite près de la dernière pose validée ; carte conservée."""
        self.perdu = False
        self.reprise = True

    def _ajouter_segments(self, scan):
        carte = [(s.copy(), p.copy()) for s, p in self.appuis]
        for nouveau, pts in extraire_segments(scan, retour_supports=True, saut=.25, erreur=.05, **self.filtres):
            for i in range(len(carte)-1, -1, -1):
                ancien, appuis = carte[i]
                if not proches(ancien, nouveau, angle_max=6., distance_max=.10):
                    continue
                supports = reduire(np.vstack([appuis, pts]), pas=.025, maximum=10000)
                # Appuis bornés par segment, régulièrement répartis dans l'ordre projeté.
                if len(supports) > 160:
                    u = (nouveau[1]-nouveau[0])/longueur(nouveau)
                    supports = supports[np.argsort(supports@u)][np.linspace(0,len(supports)-1,160).astype(int)]
                fusion = ajuster_segment(supports)
                if longueur(fusion) <= 1e-8:
                    continue
                u = (fusion[1]-fusion[0])/longueur(fusion)
                if np.max(np.abs((supports-fusion[0])@np.array([-u[1],u[0]]))) <= .05:
                    nouveau, pts = fusion, supports
                    carte.pop(i)
            carte.append((nouveau, pts))
        if len(carte) > 2000:
            raise ValueError('Limite de 2000 segments : enregistrer la carte.')
        return carte
