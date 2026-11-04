"""Exploration autonome : le robot choisit seul où aller pour terminer la carte.

Principe (exploration par frontières) : une frontière est une cellule libre voisine d'une zone encore inconnue.
Le robot va vers la plus proche frontière atteignable, le lidar révèle la zone, la carte grandit, on recommence.
Quand il ne reste aucune frontière atteignable, la pièce est terminée.

Ce module ne contient ni fil, ni réseau, ni horloge propre : `planifier` (lourd, ~1 fois par seconde) et
`commande` (léger, 20 fois par seconde) reçoivent l'heure en argument, donc il se teste en simulation accélérée.
Le robot est holonome (mecanum) : il se déplace dans la direction voulue sans tourner. Pas de rotation =
pas de tour de lidar déformé = suivi plus sûr.
"""
import functools
import threading
import numpy as np
from scipy import ndimage
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

RAYON_ROBOT = .26          # m : distance minimale du centre du robot aux obstacles, pour planifier
DISTANCE_ARRET = .20       # m : obstacle mesuré par le lidar devant le robot, dans sa largeur → arrêt
DEMI_LARGEUR = .19         # m : demi-largeur du couloir balayé par le robot (rayon 17 cm + marge)
DISTANCE_RALENTI = .55     # m : début du ralentissement
DISTANCE_REPOUSSE = .32    # m : au plus près, le robot est repoussé (glisse le long des murs)
TROU_INCONNU_MIN = 12      # cellules : un « inconnu » plus petit est un défaut d'échantillonnage, pas une zone à explorer
FRONTIERE_MIN = 3          # cellules : frontière trop petite pour que le robot y passe
RAYON_ECARTE = .6          # m : une cible déjà atteinte ou impossible n'est pas reprise dans ce rayon


def _verrouille(methode):
    @functools.wraps(methode)
    def enveloppe(self, *a, **k):
        with self.verrou:
            return methode(self, *a, **k)
    return enveloppe


class Explorateur:
    def __init__(self, rayon=RAYON_ROBOT, vitesse=1., duree_max=1800.):
        self.verrou = threading.RLock()       # la planification et la boucle de sécurité tournent dans deux fils
        self.rayon = float(rayon)
        self.vitesse = float(vitesse)     # fraction de la puissance réglée (0..1) : le curseur Puissance est la vitesse maximale
        self.duree_max = duree_max
        self.remettre_a_zero()

    # -- état -------------------------------------------------------------------------------------
    def remettre_a_zero(self):
        self.etat = 'inactif'             # inactif | exploration | termine | bloque | erreur
        self.message = ''
        self.cible = None
        self.chemin = []                  # points de passage restants (x, y), le premier est le prochain
        self.frontieres = []              # centres des frontières atteignables (pour l'affichage)
        self.ecartees = []                # cibles déjà atteintes ou impossibles
        self.debut = None
        self.replanifier = False
        self.historique = []              # (t, x, y, vx_commande, vy_commande)
        self.blocages = 0
        self._navigation = None
        self.dernier_plan = None

    @_verrouille
    def demarrer(self, maintenant):
        self.remettre_a_zero()
        self.etat, self.debut = 'exploration', float(maintenant)
        self.message = 'Exploration : analyse de la carte…'

    @_verrouille
    def arreter(self, etat='inactif', message=''):
        self.etat, self.message = etat, message
        self.chemin, self.cible, self.frontieres = [], None, []

    @property
    def actif(self):
        return self.etat == 'exploration'

    @_verrouille
    def diagnostic(self):
        return dict(etat=self.etat, message=self.message, cible=None if self.cible is None else [round(float(v), 2) for v in self.cible],
                    chemin=[[round(float(x), 2), round(float(y), 2)] for x, y in self.chemin[:40]],
                    frontieres=[[round(float(x), 2), round(float(y), 2)] for x, y in self.frontieres[:40]])

    # -- planification (lourd) --------------------------------------------------------------------
    def _navigation_depuis(self, grille, pose):
        """Grilles de navigation : traversable, distance aux obstacles, frontières. Repère : cellule (ligne, colonne)."""
        r = float(grille.resolution)
        marge = 3
        lo = np.pad(grille.log_odds, marge)
        obs = np.pad(grille.observe, marge)
        origine = np.asarray(grille.origine, float)-marge*r
        occupe = obs & (lo > 0.)
        libre = obs & (lo <= 0.)
        inconnu = ~obs
        etiquettes, n = ndimage.label(inconnu)
        if n:
            tailles = np.bincount(etiquettes.ravel())
            petit = tailles < TROU_INCONNU_MIN
            petit[0] = False
            vrai_inconnu = inconnu & ~petit[etiquettes]
        else:
            vrai_inconnu = inconnu
        distance = ndimage.distance_transform_edt(~occupe)*r if occupe.any() else np.full(occupe.shape, 99.)
        traversable = libre & (distance >= self.rayon)
        # Autour du robot : cellules libres accessibles même trop proches d'un mur (il doit pouvoir s'en écarter).
        iy, ix = self._cellule(origine, r, pose[:2])
        iy0, ix0 = np.clip(iy, 0, lo.shape[0]-1), np.clip(ix, 0, lo.shape[1]-1)
        rayon_cellules = int(np.ceil(.4/r))
        masque = np.zeros(lo.shape, bool)
        masque[max(0, iy0-rayon_cellules):iy0+rayon_cellules+1, max(0, ix0-rayon_cellules):ix0+rayon_cellules+1] = True
        traversable |= libre & masque & (distance >= .12)
        # Frontière : cellule traversable voisine (4 voisins) d'un vrai inconnu.
        voisin_inconnu = np.zeros_like(vrai_inconnu)
        voisin_inconnu[1:, :] |= vrai_inconnu[:-1, :]
        voisin_inconnu[:-1, :] |= vrai_inconnu[1:, :]
        voisin_inconnu[:, 1:] |= vrai_inconnu[:, :-1]
        voisin_inconnu[:, :-1] |= vrai_inconnu[:, 1:]
        frontiere = traversable & voisin_inconnu
        return dict(r=r, origine=origine, traversable=traversable, distance=distance, frontiere=frontiere,
                    cellule_robot=(int(iy), int(ix)))

    @staticmethod
    def _cellule(origine, r, point):
        return (int(np.floor((point[1]-origine[1])/r)), int(np.floor((point[0]-origine[0])/r)))

    @staticmethod
    def _monde(nav, cellule):
        return (nav['origine'][0]+(cellule[1]+.5)*nav['r'], nav['origine'][1]+(cellule[0]+.5)*nav['r'])

    def _graphe(self, nav):
        trav, dist = nav['traversable'], nav['distance']
        ny, nx = trav.shape
        index = np.arange(ny*nx).reshape(ny, nx)
        penalite = 1.+4.*np.clip((.6-dist)/.6, 0., 1.)**2           # préfère le milieu des passages
        sources, cibles, poids = [], [], []
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            for signe in (1, -1):
                oy, ox = dy*signe, dx*signe
                ys = slice(max(0, -oy), ny-max(0, oy)); xs = slice(max(0, -ox), nx-max(0, ox))
                yd = slice(max(0, oy), ny-max(0, -oy)); xd = slice(max(0, ox), nx-max(0, -ox))
                ok = trav[ys, xs] & trav[yd, xd]
                if dy and dx:                                         # diagonale : pas de coupe de coin
                    ok &= trav[ys, xd] & trav[yd, xs]
                longueur = np.hypot(dy, dx)*nav['r']
                sources.append(index[ys, xs][ok]); cibles.append(index[yd, xd][ok])
                poids.append(longueur*penalite[yd, xd][ok])
        s, c, w = np.concatenate(sources), np.concatenate(cibles), np.concatenate(poids)
        return csr_matrix((w, (s, c)), shape=(ny*nx, ny*nx))

    def _ligne_libre(self, nav, a, b):
        pas = max(1, int(np.ceil(np.hypot(b[0]-a[0], b[1]-a[1])/(.5*nav['r']))))
        ys = np.rint(np.linspace(a[0], b[0], pas+1)).astype(int)
        xs = np.rint(np.linspace(a[1], b[1], pas+1)).astype(int)
        return bool(nav['traversable'][ys, xs].all())

    @_verrouille
    def planifier(self, grille, pose, maintenant):
        """Choisit la prochaine frontière et le chemin pour y aller. Appelé environ une fois par seconde."""
        if self.etat != 'exploration':
            return
        if self.debut is not None and maintenant-self.debut > self.duree_max:
            return self.arreter('termine', 'Durée maximale d’exploration atteinte ; carte conservée.')
        self.replanifier = False
        nav = self._navigation_depuis(grille, pose)
        self._navigation = nav
        trav = nav['traversable']
        depart = nav['cellule_robot']
        ny, nx = trav.shape
        if not (0 <= depart[0] < ny and 0 <= depart[1] < nx) or not trav[depart]:
            self.chemin, self.cible = [], None
            self.message = 'Exploration : le robot n’est pas sur une zone libre connue ; attente du prochain tour.'
            return
        graphe = self._graphe(nav)
        source = depart[0]*nx+depart[1]
        couts, predecesseurs = dijkstra(graphe, directed=True, indices=source, return_predecessors=True)
        couts = couts.reshape(ny, nx)
        etiquettes, n = ndimage.label(nav['frontiere'], structure=np.ones((3, 3)))
        candidats = []
        for k in range(1, n+1):
            cellules = np.argwhere(etiquettes == k)
            if len(cellules) < FRONTIERE_MIN:
                continue
            c = couts[cellules[:, 0], cellules[:, 1]]
            if not np.isfinite(c).any():
                continue
            i = int(np.argmin(c))
            cellule = (int(cellules[i, 0]), int(cellules[i, 1]))
            monde = self._monde(nav, cellule)
            if any(np.hypot(monde[0]-e[0], monde[1]-e[1]) < RAYON_ECARTE for e in self.ecartees):
                continue
            cout = float(c[i])*(1.-min(.3, .01*len(cellules)))
            if self.cible is not None and np.hypot(monde[0]-self.cible[0], monde[1]-self.cible[1]) < .5:
                cout *= .7                                            # garde la cible actuelle : évite de zigzaguer
            candidats.append((cout, cellule, monde, len(cellules)))
        self.frontieres = [m for _, _, m, _ in candidats]
        if not candidats:
            self.chemin, self.cible = [], None
            return self.arreter('termine', 'Exploration terminée : plus aucune zone inconnue atteignable.')
        _, cellule, monde, _ = min(candidats, key=lambda v: v[0])
        chaine = [cellule]
        while chaine[-1] != depart and len(chaine) < ny*nx:
            p = predecesseurs[chaine[-1][0]*nx+chaine[-1][1]]
            if p < 0:
                break
            chaine.append((int(p//nx), int(p % nx)))
        chaine.reverse()
        # Raccourcis : du point courant, on saute au plus lointain point visible en ligne droite libre.
        simplifie, i = [], 0
        while i < len(chaine)-1:
            j = len(chaine)-1
            while j > i+1 and not self._ligne_libre(nav, chaine[i], chaine[j]):
                j -= 1
            simplifie.append(chaine[j])
            i = j
        self.chemin = [self._monde(nav, c) for c in simplifie]
        self.cible = monde
        self.message = f'Exploration : vers ({monde[0]:.1f} ; {monde[1]:.1f}) · {len(candidats)} zone(s) à voir.'
        self.dernier_plan = maintenant

    # -- commande (léger) -------------------------------------------------------------------------
    @_verrouille
    def commande(self, pose, points_locaux, maintenant, puissance_max=1.):
        """(surge, sway, yaw) dans [-1, 1], repère du robot. Toujours (0, 0, 0) hors exploration."""
        nul = (0., 0., 0.)
        if self.etat != 'exploration':
            return nul
        pos = np.asarray(pose[:2], float)
        while self.chemin and np.hypot(*(np.asarray(self.chemin[0])-pos)) < .18:
            reached = self.chemin.pop(0)
            if not self.chemin:
                self.ecartees.append(reached)
                self.replanifier = True
        if not self.chemin:
            return nul
        suivant = np.asarray(self.chemin[0])
        if self._navigation is not None:
            nav = self._navigation
            a, b = self._cellule(nav['origine'], nav['r'], pos), self._cellule(nav['origine'], nav['r'], suivant)
            ny, nx = nav['traversable'].shape
            if all(0 <= v < m for (v, m) in ((a[0], ny), (a[1], nx), (b[0], ny), (b[1], nx))) and not self._ligne_libre(nav, a, b):
                self.replanifier = True
        vers = suivant-pos
        distance_finale = np.hypot(*(np.asarray(self.chemin[-1])-pos))
        theta = np.deg2rad(pose[2])
        c, s = np.cos(theta), np.sin(theta)
        local = np.array([c*vers[0]+s*vers[1], -s*vers[0]+c*vers[1]])
        norme = float(np.hypot(*local))
        if norme < 1e-6:
            return nul
        u = local/norme
        vitesse = self.vitesse*(1. if distance_finale > .6 else max(.45, distance_finale/.6))
        v = u*vitesse
        pts = np.asarray(points_locaux, float).reshape(-1, 2)
        if len(pts):
            d = np.hypot(pts[:, 0], pts[:, 1])
            proches = d > .12                                    # ignore le châssis lui-même
            pts, d = pts[proches], d[proches]
            if len(pts):
                # Couloir balayé par le robot : seuls les points devant lui, dans sa largeur, comptent.
                devant = pts@u
                lateral = np.abs(pts@np.array([-u[1], u[0]]))
                dans_le_couloir = (devant > 0.) & (lateral < DEMI_LARGEUR)
                d_sens = float(devant[dans_le_couloir].min()) if dans_le_couloir.any() else np.inf
                echelle = float(np.clip((d_sens-DISTANCE_ARRET)/(DISTANCE_RALENTI-DISTANCE_ARRET), 0., 1.))
                v = v*echelle
                pres = d < DISTANCE_REPOUSSE                      # repousse : le robot glisse le long des obstacles
                if pres.any():
                    poussee = -((DISTANCE_REPOUSSE-d[pres])/DISTANCE_REPOUSSE)[:, None]*(pts[pres]/d[pres, None])
                    v = v+.9*poussee.sum(axis=0)*self.vitesse
                if echelle == 0. and self.vitesse > 0:
                    self.replanifier = True
        v = np.clip(v, -1., 1.)*puissance_max
        self._surveiller(maintenant, pos, pose[2], v)
        if self.etat != 'exploration':
            return nul
        return (float(v[0]), float(v[1]), 0.)

    # -- surveillance : bloqué ? sens des axes inversé ? ------------------------------------------
    def _surveiller(self, t, pos, cap, v):
        theta = np.deg2rad(cap)
        monde = np.array([np.cos(theta)*v[0]-np.sin(theta)*v[1], np.sin(theta)*v[0]+np.cos(theta)*v[1]])
        self.historique.append((t, float(pos[0]), float(pos[1]), float(monde[0]), float(monde[1])))
        self.historique = [h for h in self.historique if t-h[0] <= 3.]
        premier = self.historique[0]
        fenetre = t-premier[0]
        if fenetre < 2.4:
            return
        moyenne = np.mean([[h[3], h[4]] for h in self.historique], axis=0)
        ordonne = float(np.hypot(*moyenne))
        if ordonne < .25:
            return                                               # on n'a pas vraiment demandé de bouger
        deplacement = np.array([pos[0]-premier[1], pos[1]-premier[2]])
        d = float(np.hypot(*deplacement))
        if d < .04:
            self.blocages += 1
            self.ecartees.append(tuple(self.cible) if self.cible is not None else tuple(pos))
            self.historique = []
            self.replanifier = True
            if self.blocages >= 3:
                self.arreter('bloque', 'Le robot n’avance pas (obstacle ou roues bloquées). Exploration arrêtée.')
            else:
                self.message = f'Exploration : robot immobilisé, autre destination (essai {self.blocages}/3).'
            return
        self.blocages = 0
        cosinus = float(deplacement@moyenne/(d*ordonne))
        if d >= .12 and cosinus < .2:
            angle = np.degrees(np.arccos(np.clip(cosinus, -1, 1)))
            self.arreter('erreur', f'Le robot ne va pas dans la direction commandée (écart de {angle:.0f}°). '
                                   'Vérifie le sens des moteurs et l’orientation du lidar avant d’explorer seul.')
