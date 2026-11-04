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
    """Un point par cellule de `pas` (le premier rencontré), dans l'ordre d'origine."""
    if not len(points):
        return np.empty((0, 2))
    cellules = np.floor(points/pas).astype(np.int64)
    cellules -= cellules.min(axis=0)
    cle = cellules[:, 0]*(int(cellules[:, 1].max())+1)+cellules[:, 1]      # clé entière : np.unique 1-D, bien plus rapide que axis=0
    _, idx = np.unique(cle, return_index=True)
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

# Un scan devient « clé » (il entre dans la carte) quand le robot a bougé de 15 cm ou tourné de 5° : la carte est donc
# construite en roulant, pas seulement à l'arrêt. Le coût d'un scan clé ne dépend plus de la taille de la carte
# (≈ 40 ms), donc ce n'est plus un risque de gel ; le suivi, lui, tourne à chaque tour de lidar.
CLE_DISTANCE = .15
CLE_ANGLE = 5.
CLE_DELAI_US = 3_000_000        # robot qui bouge très lentement : au plus un scan clé toutes les 3 s…
IMMOBILE_DISTANCE, IMMOBILE_ANGLE = .04, 1.5      # …mais jamais pendant qu'il est à l'arrêt (pas de scan clé inutile)

# Un point de la carte est périmé quand les rayons d'un nouveau scan l'ont traversé assez souvent : son
# log-odds de la grille d'occupation est repassé sous ce seuil (impact +0,85, rayon traversant -0,4).
SEUIL_PERIME = -.8


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
        self.indice = None       # position et cap approximatifs donnés par l'utilisateur (voir replacer)
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

    def replacer(self, x, y, cap, rayon=1., tolerance=50.):
        """L'utilisateur indique où le robot est sur la carte (point + direction approximatifs).

        Au prochain tour, recherche limitée à `rayon` mètres autour du point et `tolerance` degrés autour du
        cap, puis confirmation par la géométrie locale (mêmes seuils que la localisation globale). Si rien de
        sûr n'est trouvé après quelques essais, l'indice est abandonné et la récupération habituelle reprend.
        """
        valeurs = np.array([x, y, cap, rayon, tolerance], float)
        if not np.isfinite(valeurs).all() or not .2 <= rayon <= 6. or not 5. <= tolerance <= 180.:
            raise ValueError('Indice de position invalide.')
        if not len(self.points):
            raise ValueError('Pas de carte où replacer le robot.')
        if self._ref_recherche is None or self._ref_n != len(self.cles):
            self._ref_recherche = sous_carte(self.cles, self.filtres)
            self._ref_n = len(self.cles)
        self.reference_globale = self._ref_recherche
        self.indice = dict(pose=(float(x), float(y), float(cap)), rayon=float(rayon), tolerance=float(tolerance),
                           debut=perf_counter(), essais=0)
        self.historique_poses = []
        self.probation = PROBATION_SCANS

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
        guide = self.indice
        accepte = False
        message = ''
        rmse, methode = float('nan'), 'Ancrage'
        sous_surveillance = False  # ce scan vient d'une récupération ou suit un trou : pas de scan clé
        try:
            if guide is None and self.localisation_globale_requise and debut < self.prochain_global:
                return self.etat(scan,False,'Position inconnue : nouvel essai global en attente.',score,debut,rmse,'Attente globale')
            if guide is None and not self.localisation_globale_requise and self.perdu and not explicite and debut-self.dernier_essai < .5:
                return self.etat(scan,False,'Nouvel essai en attente : '+self.dernier_refus,score,debut,rmse,'Attente')
            self.dernier_essai = debut
            pts = points_filtres(scan, self.filtres, locaux=True)
            if len(pts) < 30 or np.linalg.norm(np.ptp(pts, axis=0)) < 1.:
                raise ValueError('Pas assez de géométrie après filtrage ; carte en pause.')
            if self.localisation_globale_requise or guide is not None:
                options = {}
                if guide is None:
                    self.prochain_global=debut+3.
                else:
                    options = dict(centre=guide['pose'][:2], rayon=guide['rayon'], cap=guide['pose'][2],
                                   tolerance_cap=guide['tolerance'])
                resultat=localisation_globale(scan,self.reference_globale,annuler=self.annuler,**options,**self.filtres)
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
                if guide is not None:
                    message=f'Position confirmée à partir de ton indice : {score:.0f} % à 12 cm.'
                    self.indice=None
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
            immobile = ep < IMMOBILE_DISTANCE and ea < IMMOBILE_ANGLE
            cle = (self.enrichir or amorce) and (self.fin_us is None or (not surveille and not immobile and (
                ep >= CLE_DISTANCE or ea >= CLE_ANGLE or trame.fin_us-self.fin_cle >= CLE_DELAI_US)))
            if surveille and self.enrichir and self.fin_us is not None:
                message += ' Carte non enrichie pendant la vérification de la position.'
            if amorce:
                message = 'Localisation seule sans carte : ce scan sert de référence (origine fixe).'
            if cle:
                if len(self.cles) >= 2000:
                    raise ValueError('Limite de 2000 scans clés : enregistrer la carte.')
                # Copie à l'insertion seulement : l'UI ne lit jamais une grille en mutation.
                nouvelle_grille = deepcopy(self.grille) if self.grille is not None else Grille.creer([scan],self.resolution,**self.filtres)
                nouvelle_grille.mettre_a_jour(scan,**self.filtres)
                # Ce que ce scan a vu traverser disparaît de la carte (objet déplacé, porte refermée, personne passée).
                anciens = self.points[self._log_odds(nouvelle_grille, self.points) > SEUIL_PERIME]
                nouveaux_points = reduire(np.vstack([anciens, transformer(pts, scan.pose)]))
                nouveaux_appuis = self._ajouter_segments(scan, self._appuis_valides(nouvelle_grille))
                # Seuls les huit derniers scans clés validés servent au suivi local.
                # La référence garde aussi la couverture de la carte importée.
                proches = nouveaux_points[np.linalg.norm(nouveaux_points-np.asarray(scan.pose[:2]),axis=1)<14.]
                local = proches if len(proches)>=30 else nouveaux_points
                nouvelle_reference = ReferenceSuivi(local)
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
            if guide is not None:
                guide['essais'] += 1
                if guide['essais'] >= 5 or perf_counter()-guide['debut'] > 12.:
                    self.indice = None
                    guide = None
                    self.dernier_refus = 'Indice abandonné.'
                else:
                    exc = ValueError('Indice de position non confirmé (essai %d/5) : %s' % (guide['essais'], exc))
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

    @staticmethod
    def _log_odds(grille, points):
        """Log-odds de la cellule de chaque point ; +∞ (jamais périmé) hors de la grille ou jamais observé."""
        if not len(points):
            return np.empty(0)
        ij = np.floor((points-grille.origine)/grille.resolution).astype(int)
        ny, nx = grille.log_odds.shape
        dedans = (ij[:, 0] >= 0) & (ij[:, 0] < nx) & (ij[:, 1] >= 0) & (ij[:, 1] < ny)
        lo = np.full(len(points), np.inf)
        ij = ij[dedans]
        lo[dedans] = np.where(grille.observe[ij[:, 1], ij[:, 0]], grille.log_odds[ij[:, 1], ij[:, 0]], np.inf)
        return lo

    def _appuis_valides(self, grille):
        """Segments de la carte sans ceux dont la majorité des mesures sources a été traversée par de nouveaux rayons."""
        gardes = []
        for segment, supports in self.appuis:
            if np.mean(self._log_odds(grille, supports) <= SEUIL_PERIME) < .5:
                gardes.append((segment, supports))
        return gardes

    def _ajouter_segments(self, scan, appuis=None):
        """Fusionne les segments du scan dans la carte : un mur vu plusieurs fois reste un seul segment."""
        carte = list(self.appuis if appuis is None else appuis)      # les entrées ne sont jamais modifiées sur place
        tableau = np.array([s for s, _ in carte]).reshape(-1, 2, 2)
        for nouveau, pts in extraire_segments(scan, retour_supports=True, saut=.25, erreur=.05, **self.filtres):
            fusionne = True
            while fusionne:
                fusionne = False
                # Préfiltre vectorisé (angle et écart latéral des extrémités) : seuls les voisins plausibles passent
                # par le test exact `proches`.
                for i in self._voisins(tableau, nouveau, 6., .10)[::-1]:
                    ancien, appuis_i = carte[i]
                    if not proches(ancien, nouveau, angle_max=6., distance_max=.10):
                        continue
                    supports = reduire(np.vstack([appuis_i, pts]), pas=.025, maximum=10000)
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
                        tableau = np.delete(tableau, i, axis=0)
                        fusionne = True
                        break
            carte.append((nouveau, pts))
            tableau = np.concatenate([tableau, nouveau[None]])
        if len(carte) > 2000:
            raise ValueError('Limite de 2000 segments : enregistrer la carte.')
        return carte

    @staticmethod
    def _voisins(tableau, nouveau, angle_max, distance_max):
        """Indices des segments de `tableau` (n, 2, 2) à peu près parallèles à `nouveau` et à moins de distance_max de sa droite,
        et inversement. Superset de ce que `proches` accepte ; l'ordre croissant est conservé."""
        if not len(tableau):
            return []
        a0, v = tableau[:, 0], tableau[:, 1]-tableau[:, 0]
        lv = np.linalg.norm(v, axis=1)
        u = nouveau[1]-nouveau[0]
        lu = np.linalg.norm(u)
        ok = (lv > 1e-9) & (lu > 1e-9)
        with np.errstate(divide='ignore', invalid='ignore'):
            cos = np.abs(v@u)/(lv*lu)
            ok &= cos >= np.cos(np.deg2rad(angle_max))-1e-9
            marge = distance_max+1e-6
            # extrémités du nouveau par rapport à la droite de chaque ancien
            n = np.column_stack([-v[:, 1], v[:, 0]])/lv[:, None]
            ok &= np.maximum(np.abs(np.einsum('ij,ij->i', nouveau[0]-a0, n)), np.abs(np.einsum('ij,ij->i', nouveau[1]-a0, n))) <= marge
            # extrémités de chaque ancien par rapport à la droite du nouveau
            nn = np.array([-u[1], u[0]])/lu
            ok &= np.maximum(np.abs((a0-nouveau[0])@nn), np.abs((tableau[:, 1]-nouveau[0])@nn)) <= marge
        # recouvrement des boîtes englobantes élargies
        bas = np.minimum(tableau[:, 0], tableau[:, 1])-marge
        haut = np.maximum(tableau[:, 0], tableau[:, 1])+marge
        ok &= np.all((bas <= np.maximum(nouveau[0], nouveau[1])) & (haut >= np.minimum(nouveau[0], nouveau[1])), axis=1)
        return np.flatnonzero(ok).tolist()
