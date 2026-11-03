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
from suivi_lidar import ReferenceSuivi, icp_droites, predire


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
    rmse: float = float('nan')
    methode: str = 'Ancrage'


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
        self.reference_locale = None
        self.historique_poses = []
        self.dernier_essai = 0.
        self.dernier_refus = ""

    @property
    def segments(self):
        return [s.copy() for s, _ in self.appuis]

    def traiter(self, trame):
        debut = perf_counter()
        scan = trame.scan()
        score = float('nan')
        recuperation = self.perdu or self.reprise
        explicite = self.reprise
        accepte = False
        message = ''
        rmse, methode = float('nan'), 'Ancrage'
        try:
            if self.perdu and not explicite and debut-self.dernier_essai < .5:
                return EtatDirect(scan, False, 'Nouvel essai en attente : '+self.dernier_refus,
                    score, perf_counter()-debut, self.points.copy(), self.segments,
                    np.asarray(self.trajectoire), len(self.cles), tuple(self.cles), rmse, 'Attente')
            self.dernier_essai = debut
            pts = points_filtres(scan, self.filtres, locaux=True)
            if len(pts) < 30 or np.linalg.norm(np.ptp(pts, axis=0)) < 1.:
                raise ValueError('Pas assez de géométrie après filtrage ; carte en pause.')
            if self.fin_us is None:
                scan.pose = [0., 0., 0.]
                message = 'Premier scan : origine fixe de la carte.'
                accepte = True
                score = 100.
            else:
                dt = .1 if recuperation else (trame.fin_us-self.fin_us)/1e6
                if not 0 < dt <= 1.5:
                    raise ValueError('Scans trop espacés : carte en pause, nouvel essai automatique.')
                # Index et normales réutilisés entre scans clés ; aucun recalcul intégral par tour.
                reference_suivi = self.reference_locale
                initiale = self.pose.copy()
                if not recuperation and dt<=.6 and len(self.historique_poses)>=2:
                    (t0,p0),(t1,p1) = self.historique_poses[-2:]
                    if t1>t0:initiale=predire(p0,p1,(trame.fin_us-t1)/(t1-t0))
                resultat = icp_droites(pts,reference_suivi,initiale,self.annuler)
                if not resultat.applicable and not np.allclose(initiale,self.pose) and not self.annuler.is_set():
                    resultat = icp_droites(pts,reference_suivi,self.pose,self.annuler)
                # Secours borné au voisinage du suivi, jamais recherche globale à chaque tour.
                if not resultat.applicable and not self.annuler.is_set():
                    reference = ReferenceDirect(reference_suivi.fond)
                    resultat = localiser_sur_reference(scan, reference, methode=MULTI,
                        pose_initiale=self.pose, annuler=self.annuler, **self.filtres)
                    if resultat.applicable:
                        # La recherche grossière ne doit pas contourner le contrôle
                        # d'observabilité du suivi, notamment devant un mur unique.
                        affine = icp_droites(pts,reference_suivi,resultat.pose,self.annuler)
                        affine.methode = 'Secours multi-résolution + point-vers-droite'
                        resultat = affine
                methode, rmse = resultat.methode, resultat.rmse
                score = 100*resultat.accord_fin
                ep, ea = erreur_pose(resultat.pose, self.pose)
                # Déplacement physiquement plausible au PWM limité, avec marge de bruit.
                plausible = ep <= .20+1.2*dt and ea <= 10.+150.*dt
                if recuperation:
                    plausible = ep <= (1.2 if explicite else .25) and ea <= (35. if explicite else 8.)
                accepte = bool(resultat.applicable and resultat.accord_fin >= .75 and
                               resultat.rmse <= .10 and plausible and not self.annuler.is_set())
                if not accepte:
                    raise ValueError(f'Recalage refusé : {score:.0f} % à 12 cm, RMSE {rmse:.3f} m, déplacement {ep:.2f} m / {ea:.1f}°. Carte conservée ; nouvel essai automatique.')
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
                # Seuls les huit derniers scans clés validés servent au suivi local.
                recents = (self.cles+[scan])[-8:]
                local = reduire(np.vstack([points_filtres(s,self.filtres) for s in recents]))
                nouvelle_reference = ReferenceSuivi(local)
                # Publication atomique : aucun état partiellement inséré sur une erreur.
                self.points, self.appuis = nouveaux_points, nouveaux_appuis
                self.reference_locale = nouvelle_reference
                self.cles.append(scan)
                self.pose_cle, self.fin_cle = np.array(scan.pose), trame.fin_us
            self.pose, self.fin_us = np.array(scan.pose), trame.fin_us
            if recuperation:
                self.historique_poses = []
            self.perdu = False
            self.dernier_refus = ""
            self.historique_poses.append((trame.fin_us,self.pose.copy()))
            self.historique_poses = self.historique_poses[-2:]
            self.reprise = False
            self.trajectoire.append(self.pose.copy())
            self.trajectoire = self.trajectoire[-4000:]
        except (ValueError, RuntimeError) as exc:
            accepte = False
            self.perdu = True
            self.reprise = False
            message = self.dernier_refus = str(exc)
        return EtatDirect(scan, accepte, message, score, perf_counter()-debut,
                          self.points.copy(), self.segments, np.asarray(self.trajectoire), len(self.cles), tuple(self.cles),rmse,methode)

    def reprendre(self):
        """Autorisation explicite près de la dernière pose validée ; carte conservée."""
        self.perdu = False
        self.reprise = True
        self.historique_poses = []

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

