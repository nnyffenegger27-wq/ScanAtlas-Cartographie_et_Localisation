"""Suivi lidar et carte vectorielle incrémentale pour le pilotage Wi-Fi.

Premier scan ancré ; références figées pendant chaque recalage ; insertion
uniquement après validation. Aucune odométrie n'est inventée depuis les touches.
"""
from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter
import threading
import numpy as np
from scipy.spatial import cKDTree
from cartographie import (extraire_segments, ajuster_segment, proches, longueur,
                         Scan, Grille, mesures_valides)
from dataclasses import replace
from localisation import points_filtres, transformer, erreur_pose, sous_carte
from localisation_globale import localisation_globale
from localisation_tp import localiser_sur_reference, LOCALE, MULTI
from suivi_lidar import ReferenceSuivi, icp_droites, predire, vitesses, corriger_mouvement


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
    grille: object = None
    enrichissement: bool = True


# Après une récupération (position retrouvée, reprise, trou de liaison), la carte n'est pas enrichie tant que
# ce nombre de scans consécutifs n'ont pas été suivis normalement : une mauvaise position retrouvée ne doit
# jamais déposer de scans clés dans la carte.
PROBATION_SCANS = 3


class CarteDirecte:
    def __init__(self, filtres=None, scans=None, segments=None, resolution=.1):
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
        self.enrichir = True
        self.resolution = resolution
        self.grille = None
        self.localisation_globale_requise = False
        self.prochain_global = 0.
        # Récupération automatique : après 1 s sans suivi, recherche élargie autour de la dernière pose
        # (tous les angles, rayon croissant), puis recherche sur toute la carte après 6 s.
        self.recup_auto = True
        self.perdu_t = None      # heure (horloge du PC) du début de la perte ; l'horloge du lidar repart à zéro si l'ESP32 redémarre
        self.accepte_t = 0.
        self.prochain_auto = 0.
        self._ref_recherche = None
        self._ref_n = -1
        self.probation = 0       # scans restant à suivre normalement avant de réenrichir la carte
        if scans:
            self.charger_reference(scans, segments)

    def charger_reference(self, scans, segments=None):
        """Copie indépendante des scans cochés et de leurs poses, sans réancrage."""
        copies = deepcopy(list(scans))
        if not copies or len(copies)>2000:
            raise ValueError('Choisir de 1 à 2000 scans de référence.')
        points = reduire(np.vstack([points_filtres(s,self.filtres) for s in copies]))
        reference = ReferenceSuivi(points)
        grille = Grille.creer(copies,self.resolution,**self.filtres)
        for scan in copies:
            if self.annuler.is_set():raise ValueError('Chargement annulé.')
            grille.mettre_a_jour(scan,**self.filtres)
        self.points, self.reference_locale, self.grille, self.cles = points, reference, grille, copies
        self.appuis = []
        if segments is not None:
            for segment in segments:
                segment=np.asarray(segment,float)
                if segment.shape!=(2,2) or not np.isfinite(segment).all() or longueur(segment)<1e-8:
                    raise ValueError('Segment de référence invalide.')
                n=max(6,min(160,int(longueur(segment)/.03)+1))
                self.appuis.append((segment.copy(),np.linspace(segment[0],segment[1],n)))
        else:
            for scan in copies:self.appuis = self._ajouter_segments(scan)
        self.localisation_globale_requise=True
        self.reference_globale=sous_carte(copies,self.filtres)

    def relocaliser(self):
        """Recherche sur la carte entière au prochain tour, après déplacement inconnu."""
        if not len(self.points):return
        self.reference_globale=sous_carte(self.cles,self.filtres)
        self.localisation_globale_requise=True
        self.prochain_global=0.
        self.historique_poses=[]
        self.probation=PROBATION_SCANS

    @property
    def segments(self):
        return [s.copy() for s, _ in self.appuis]

    def traiter(self, trame, enrichir=None):
        if enrichir is not None:self.enrichir = bool(enrichir)
        debut = perf_counter()
        scan = trame.scan()
        score = float('nan')
        recuperation = self.perdu or self.reprise
        explicite = self.reprise
        accepte = False
        message = ''
        rmse, methode = float('nan'), 'Ancrage'
        sous_surveillance = False  # ce scan vient d'une récupération ou suit un trou : pas de scan clé
        try:
            if self.localisation_globale_requise and debut < self.prochain_global:
                return self.etat(scan,False,'Position inconnue : nouvel essai global en attente.',score,debut,rmse,'Attente globale')
            if not self.localisation_globale_requise and self.perdu and not explicite and debut-self.dernier_essai < .5:
                return self.etat(scan,False,'Nouvel essai en attente : '+self.dernier_refus,score,debut,rmse,'Attente')
            self.dernier_essai = debut
            pts = points_filtres(scan, self.filtres, locaux=True)
            if len(pts) < 30 or np.linalg.norm(np.ptp(pts, axis=0)) < 1.:
                raise ValueError('Pas assez de géométrie après filtrage ; carte en pause.')
            if self.localisation_globale_requise:
                self.prochain_global=debut+3.
                resultat=localisation_globale(scan,self.reference_globale,annuler=self.annuler,**self.filtres)
                methode,rmse,score=resultat.methode,resultat.rmse,100*resultat.accord_fin
                if not resultat.applicable:
                    raise ValueError('Position inconnue ou ambiguë : '+resultat.message)
                # La référence locale du suivi ne couvre que les 14 m autour du dernier scan clé : après un saut
                # sur la carte (Position 360°), la confirmation et le suivi se font sur le voisinage de la
                # position trouvée, sinon le suivi reperd aussitôt le robot.
                autour=self._reference_autour(resultat.pose)
                affine=icp_droites(pts,autour,resultat.pose,self.annuler)
                if not affine.applicable or affine.accord_fin<.75 or affine.rmse>.10:
                    raise ValueError('Position globale non confirmée par la géométrie locale.')
                self.reference_locale=autour
                sous_surveillance=True
                scan.pose=list(affine.pose)
                rmse,score=affine.rmse,100*affine.accord_fin
                accepte=True
                message=f'Position retrouvée dans la carte : {score:.0f} % à 12 cm.'
                recuperation=True
            elif self.fin_us is None:
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
                omega, vitesse = 0., np.zeros(2)
                if not recuperation and dt<=.6 and len(self.historique_poses)>=2:
                    (t0,p0),(t1,p1) = self.historique_poses[-2:]
                    if t1>t0:
                        initiale=predire(p0,p1,(trame.fin_us-t1)/(t1-t0))
                        omega, vitesse = vitesses(p0,p1,(t1-t0)/1e6)
                duree_tour = trame.duree_us/1e6
                brut = scan.mesures
                def points_corriges(w, v):
                    return points_filtres(replace(scan,mesures=corriger_mouvement(brut,w,v,duree_tour,scan.angle_reference)),
                                          self.filtres, locaux=True)
                # Rotation ou translation rapide : le tour est déformé, on le redresse avec la vitesse estimée
                # (puis une seconde fois avec celle que le recalage vient de mesurer).
                if abs(omega) >= 6. or np.linalg.norm(vitesse) >= .15:
                    pts_corr = points_corriges(omega, vitesse)
                    if len(pts_corr) >= 30:
                        pts = pts_corr
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
                dt_reel = (trame.fin_us-self.fin_us)/1e6
                if resultat.applicable and abs(omega) >= 10. and 0 < dt_reel <= .6 and not self.annuler.is_set():
                    omega2, vitesse2 = vitesses(self.pose,resultat.pose,dt_reel)
                    if abs(omega2-omega) >= 4.:
                        pts2 = points_corriges(omega2, vitesse2)
                        if len(pts2) >= 30:
                            second = icp_droites(pts2,reference_suivi,resultat.pose,self.annuler)
                            if second.applicable and second.accord_fin >= resultat.accord_fin-.01:
                                resultat, pts, omega, vitesse = second, pts2, omega2, vitesse2
                if abs(omega) >= 6. or np.linalg.norm(vitesse) >= .15:
                    # La carte garde le tour redressé (segments et grille construits sur ces mesures).
                    scan.mesures = corriger_mouvement(brut,omega,vitesse,duree_tour,scan.angle_reference)
                methode, rmse = resultat.methode, resultat.rmse
                score = 100*resultat.accord_fin
                ep, ea = erreur_pose(resultat.pose, self.pose)
                # Déplacement physiquement plausible au PWM limité, avec marge de bruit.
                plausible = ep <= .20+1.2*dt and ea <= 10.+150.*dt
                if recuperation:
                    # Fenêtre qui s'élargit avec le temps écoulé depuis la dernière pose validée : un robot
                    # qui continue de rouler ou de tourner pendant la perte ne revient pas dans 8°.
                    ecoule = max(0., debut-self.accepte_t)
                    limites = (1.2, 35.) if explicite else (min(1.5, .25+1.0*ecoule), min(60., 8.+100.*ecoule))
                    plausible = ep <= limites[0] and ea <= limites[1]
                accepte = bool(resultat.applicable and resultat.accord_fin >= .75 and
                               resultat.rmse <= .10 and plausible and not self.annuler.is_set())
                if not accepte:
                    secours = self._recuperer(scan, pts, trame, debut)
                    if secours is None:
                        raison = '' if resultat.applicable else ' '+resultat.message
                        raise ValueError(f'Recalage refusé : {score:.0f} % à 12 cm, RMSE {rmse:.3f} m, déplacement {ep:.2f} m / {ea:.1f}°.{raison} Carte conservée ; nouvel essai automatique.')
                    resultat = secours
                    methode, rmse, score = 'Recherche élargie autour de la dernière pose', resultat.rmse, 100*resultat.accord_fin
                    scan.pose = list(resultat.pose)
                    message = f'Position retrouvée près de la dernière pose : {score:.0f} % à 12 cm.'
                    recuperation = True
                    sous_surveillance = True
                else:
                    scan.pose = list(resultat.pose)
                    message = f'Suivi accepté : {score:.0f} % à 12 cm ; RMSE {resultat.rmse:.3f} m.'
                    # Reprise explicite, ou trou entre deux tours (liaison coupée un instant) : surveillance.
                    sous_surveillance = explicite or dt_reel > .6
            if self.annuler.is_set():
                raise ValueError('Cartographie arrêtée.')
            ep, ea = erreur_pose(scan.pose, self.pose_cle)
            # Carte vide en « Localisation seule » : le premier scan reçu sert de référence (origine fixe)
            # plutôt que de ne rien faire ; les suivants sont ensuite localisés sans enrichir la carte.
            amorce = not self.enrichir and not len(self.points)
            surveille = sous_surveillance or self.probation > 0
            cle = (self.enrichir or amorce) and (self.fin_us is None or (not surveille and (
                ep >= .15 or ea >= 5. or trame.fin_us-self.fin_cle >= 2_000_000)))
            if surveille and self.enrichir and self.fin_us is not None:
                message += ' Carte non enrichie pendant la vérification de la position.'
            if amorce:
                message = 'Localisation seule sans carte : ce scan sert de référence (origine fixe).'
            if cle:
                if len(self.cles) >= 2000:
                    raise ValueError('Limite de 2000 scans clés : enregistrer la carte.')
                nouveaux_points = reduire(np.vstack([self.points, transformer(pts, scan.pose)]))
                nouveaux_appuis = self._ajouter_segments(scan)
                # Seuls les huit derniers scans clés validés servent au suivi local.
                # La référence garde aussi la couverture de la carte importée.
                proches = nouveaux_points[np.linalg.norm(nouveaux_points-np.asarray(scan.pose[:2]),axis=1)<14.]
                local = proches if len(proches)>=30 else nouveaux_points
                nouvelle_reference = ReferenceSuivi(local)
                # Copie à l'insertion seulement : l'UI ne lit jamais une grille en mutation.
                nouvelle_grille = deepcopy(self.grille) if self.grille is not None else Grille.creer([scan],self.resolution,**self.filtres)
                nouvelle_grille.mettre_a_jour(scan,**self.filtres)
                # Publication atomique : aucun état partiellement inséré sur une erreur.
                self.points, self.appuis, self.grille = nouveaux_points, nouveaux_appuis, nouvelle_grille
                self.reference_locale = nouvelle_reference
                self.cles.append(scan)
                self.pose_cle, self.fin_cle = np.array(scan.pose), trame.fin_us
            self.localisation_globale_requise = False
            if sous_surveillance:
                self.probation = PROBATION_SCANS
            elif self.probation > 0:
                self.probation -= 1
            self.pose, self.fin_us = np.array(scan.pose), trame.fin_us
            if recuperation:
                self.historique_poses = []
            self.perdu = False
            self.perdu_t = None
            self.accepte_t = debut
            self.dernier_refus = ""
            self.historique_poses.append((trame.fin_us,self.pose.copy()))
            self.historique_poses = self.historique_poses[-2:]
            self.reprise = False
            self.trajectoire.append(self.pose.copy())
            self.trajectoire = self.trajectoire[-4000:]
        except (ValueError, RuntimeError) as exc:
            accepte = False
            self.perdu = True
            if self.perdu_t is None and self.fin_us is not None:
                self.perdu_t = debut
            self.reprise = False
            message = self.dernier_refus = str(exc)
            if self.perdu_t is not None:
                message = f'Perdu depuis {debut-self.perdu_t:.0f} s, recherche automatique en cours : {message}'
        return self.etat(scan,accepte,message,score,debut,rmse,methode)

    def etat(self,scan,accepte,message,score,debut,rmse,methode):
        return EtatDirect(scan,accepte,message,score,perf_counter()-debut,self.points.copy(),
                          self.segments,np.asarray(self.trajectoire),len(self.cles),tuple(self.cles),
                          rmse,methode,self.grille,self.enrichir)

    def _reference_autour(self, pose, rayon=14.):
        """Référence de suivi construite sur les points de la carte proches de `pose`."""
        p = self.points
        proches = p[np.linalg.norm(p-np.asarray(pose[:2]), axis=1) < rayon]
        return ReferenceSuivi(proches if len(proches) >= 30 else p)

    def _recuperer(self, scan, pts, trame, debut):
        """Recherche élargie autour de la dernière pose, tous angles ; None si rien de sûr.

        Les résultats passent par les mêmes contrôles que la localisation globale : concordance fine
        sur la référence locale (75 % à 12 cm, RMSE 10 cm). Au bout de 6 s, bascule sur la recherche
        sur toute la carte, relancée toutes les 3 s.
        """
        if not (self.recup_auto and len(self.points) and self.perdu_t is not None and self.reference_locale is not None):
            return None
        perdu = debut-self.perdu_t
        if perdu < 1. or debut < self.prochain_auto:
            return None
        self.prochain_auto = debut+1.
        if self._ref_recherche is None or self._ref_n != len(self.cles):
            self._ref_recherche = sous_carte(self.cles, self.filtres)
            self._ref_n = len(self.cles)
        if perdu >= 6.:
            self.reference_globale = self._ref_recherche
            self.localisation_globale_requise = True
            self.prochain_global = 0.
            return None
        try:
            r = localisation_globale(scan, self._ref_recherche, annuler=self.annuler, centre=self.pose[:2],
                                     rayon=min(5., 1.5+perdu), **self.filtres)
            if not r.applicable:
                return None
            affine = icp_droites(pts, self.reference_locale, r.pose, self.annuler)
        except (ValueError, RuntimeError):
            return None
        if not affine.applicable or affine.accord_fin < .75 or affine.rmse > .10:
            return None
        return affine

    def reprendre(self):
        """Autorisation explicite près de la dernière pose validée ; carte conservée."""
        self.perdu = False
        self.reprise = True
        self.historique_poses = []
        self.probation = PROBATION_SCANS

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

