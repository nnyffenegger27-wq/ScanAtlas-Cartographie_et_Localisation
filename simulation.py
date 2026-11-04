"""Salles simulées : lidar, collisions et cinématique d'un robot mecanum, sans réseau ni matériel.

Sert au robot simulé du mode démonstration (simuler_robot_wifi.py) et aux tests de l'exploration autonome.
Repère : x vers l'avant, y vers la gauche, cap en degrés dans le sens trigonométrique, comme les poses du suivi.
"""
import numpy as np
from robot_wifi import TrameScan

# Salle de démonstration : 7 m × 5 m avec un petit mur intérieur en L.
SALLE_DEMO = np.array([[[-3, -2], [4, -2]], [[4, -2], [4, 3]], [[4, 3], [-3, 3]],
                       [[-3, 3], [-3, -2]], [[.6, .8], [1.4, .8]], [[1.4, .8], [1.4, 1.5]]], float)

# Deux pièces reliées par une porte de 1 m, avec un meuble : de quoi tester les frontières et les détours.
SALLE_DEUX_PIECES = np.array([
    [[-3, -2], [3, -2]], [[3, 3], [-3, 3]], [[-3, 3], [-3, -2]],                                     # pièce principale
    [[3, -2], [8, -2]], [[8, -2], [8, 3]], [[8, 3], [3, 3]],                                         # pièce de droite
    [[3, -2], [3, .2]], [[3, 1.2], [3, 3]],                                                          # cloison avec porte (y 0,2 à 1,2)
    [[-1, 0], [0, 0]], [[0, 0], [0, 1]], [[0, 1], [-1, 1]], [[-1, 1], [-1, 0]],                      # meuble carré
], float)

def rectangle(x0, y0, x1, y1):
    """Les 4 côtés d'un rectangle (un meuble vu par le lidar à hauteur de capteur)."""
    return [[[x0, y0], [x1, y0]], [[x1, y0], [x1, y1]], [[x1, y1], [x0, y1]], [[x0, y1], [x0, y0]]]


def polygone(cx, cy, rayon, n=10, rotation=0.):
    """Un meuble rond (table, pilier) approché par n côtés."""
    a = np.deg2rad(rotation)+np.linspace(0, 2*np.pi, n, endpoint=False)
    p = np.column_stack([cx+rayon*np.cos(a), cy+rayon*np.sin(a)])
    return [[p[i].tolist(), p[(i+1) % n].tolist()] for i in range(n)]


def cloison(p, q, portes=()):
    """Un mur de p à q avec des ouvertures : `portes` = [(début, fin), ...] en mètres le long du mur."""
    p, q = np.asarray(p, float), np.asarray(q, float)
    longueur = float(np.linalg.norm(q-p))
    u = (q-p)/longueur
    bornes, t = [], 0.
    for d, f in sorted(portes):
        if d > t:
            bornes.append((t, d))
        t = f
    if t < longueur:
        bornes.append((t, longueur))
    return [[(p+u*a).tolist(), (p+u*b).tolist()] for a, b in bornes]


def _appartement():
    """Appartement 16 m × 10 m : salon, cuisine, couloir de 16 m, bureau, chambre et salle de réunion.

    Trois portes sur le couloir, une porte entre le bureau et la chambre (donc une boucle), une ouverture
    salon/cuisine, des meubles de toutes tailles (canapé, tables, chaises, armoires, îlot, plantes), deux piliers et
    une table ronde. Les passages les plus étroits font 90 cm, les écarts entre meubles de 40 cm ne sont pas franchissables.
    """
    m = []
    m += rectangle(0, 0, 16, 10)                                                              # enveloppe
    m += cloison((0, 6), (16, 6), portes=[(2.8, 3.7), (13.5, 14.4)])                          # couloir ↔ salon, cuisine
    m += cloison((0, 7.2), (16, 7.2), portes=[(1.0, 1.9), (6.0, 6.9), (11.8, 12.7)])          # couloir ↔ bureau, chambre, réunion
    m += cloison((7, 0), (7, 6), portes=[(2.0, 3.0)])                                         # salon ↔ cuisine
    m += cloison((5, 7.2), (5, 10), portes=[(.4, 1.2)])                                       # bureau ↔ chambre
    m += cloison((10, 7.2), (10, 10))                                                         # chambre | réunion
    # salon
    m += rectangle(0, 1.2, .9, 3.4)                                                           # canapé
    m += rectangle(1.6, 1.9, 2.1, 2.7)                                                        # table basse
    m += rectangle(2.6, 2.4, 4.6, 3.4)                                                        # table à manger
    m += rectangle(3.2, 1.8, 3.6, 2.2) + rectangle(3.2, 3.6, 3.6, 4.0)                        # deux chaises
    m += rectangle(4.2, 0, 6.6, .4)                                                           # bibliothèque
    m += rectangle(4.5, 5.6, 6.5, 6.0)                                                        # meuble TV
    m += rectangle(5.4, 4.2, 5.8, 4.6)                                                        # pilier
    # cuisine
    m += rectangle(10, 2.4, 12.4, 3.3)                                                        # îlot
    m += rectangle(9, 0, 15, .6) + rectangle(15, 0, 16, .7)                                   # plan de travail, frigo
    m += polygone(13.5, 4.6, .55, 10)                                                         # table ronde
    m += rectangle(8.6, 4.4, 9.0, 4.8)                                                        # pilier
    # couloir
    m += rectangle(8.4, 6, 8.8, 6.35)                                                         # plante
    # bureau
    m += rectangle(.4, 9.3, 2.2, 10) + rectangle(1.0, 8.7, 1.4, 9.1)                          # bureau et sa chaise
    m += rectangle(4.3, 8.6, 5, 10)                                                           # armoire
    m += rectangle(0, 7.2, .7, 7.9)                                                           # coffre
    # chambre
    m += rectangle(6.2, 8.2, 8.0, 10) + rectangle(8.0, 9.6, 8.4, 10)                          # lit, table de nuit
    m += rectangle(9.4, 7.8, 10, 10)                                                          # armoire
    # salle de réunion
    m += rectangle(11.5, 8.1, 14.5, 9.3)                                                      # grande table
    m += rectangle(15.6, 8.0, 16, 9.6) + rectangle(10.1, 9.5, 10.6, 10)                       # meuble bas, plante
    return np.array(m, float)

SALLE_APPARTEMENT = _appartement()

# Salles proposées par la démonstration : identifiant → (titre, murs, pose de départ x, y, cap°).
SALLES = {
    'appartement': dict(titre='Appartement (16 × 10 m, couloir, 5 pièces)', murs=SALLE_APPARTEMENT, depart=(2., 4.6, 0.)),
    'deux_pieces': dict(titre='Deux pièces reliées par une porte', murs=SALLE_DEUX_PIECES, depart=(0., -1., 0.)),
    'salle': dict(titre='Salle simple (7 × 5 m)', murs=SALLE_DEMO, depart=(0., 0., 0.)),
}
SALLE_PAR_DEFAUT = 'appartement'

MURS = SALLE_DEMO   # nom historique

# Vitesse à 65 % de puissance (valeur de référence du robot simulé).
VITESSE_65 = .3          # m/s
ROTATION_65 = 35.        # °/s
RAYON_ROBOT = .17        # m, pour les collisions


def mesures_simulees(pose, rng, murs=SALLE_DEMO, n=450, portee=12., bruit=.003):
    """Un tour de lidar depuis `pose` : tableau (angle °, distance m, intensité)."""
    angles = np.linspace(0, 360, n, endpoint=False)
    a = np.deg2rad(angles+pose[2])
    rayons = np.column_stack([np.cos(a), np.sin(a)])
    dist = np.full(len(angles), float(portee))

    def croix(a, b):
        return a[..., 0]*b[..., 1]-a[..., 1]*b[..., 0]
    for p, q in murs:
        v = q-p
        w = p-np.asarray(pose[:2])
        den = croix(rayons, v)
        with np.errstate(divide='ignore', invalid='ignore'):
            t = croix(w, v)/den
            u = croix(w, rayons)/den
        valide = (np.abs(den) > 1e-9) & (t > .05) & (u >= 0) & (u <= 1)
        dist[valide] = np.minimum(dist[valide], t[valide])
    dist = np.maximum(.05, dist+rng.normal(0, bruit, len(dist)))
    return np.column_stack([angles, dist, np.full(len(dist), 230)])


def distance_aux_murs(point, murs=SALLE_DEMO):
    p = np.asarray(point, float)
    a, v = murs[:, 0], murs[:, 1]-murs[:, 0]
    t = np.clip(((p-a)*v).sum(axis=1)/(v*v).sum(axis=1), 0, 1)
    return float(np.min(np.linalg.norm(p-(a+t[:, None]*v), axis=1)))


def deplacer(pose, avance, gauche, tourne, dt, murs=SALLE_DEMO, rayon=RAYON_ROBOT):
    """Avance la pose de dt secondes. `avance`/`gauche`/`tourne` sont des pourcentages signés (-100..100).

    Un mur arrête la composante qui le heurterait (le robot glisse le long du mur, il ne le traverse pas).
    """
    pose = np.asarray(pose, float).copy()
    a = np.deg2rad(pose[2])
    R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    local = np.array([avance, gauche], float)/65.*VITESSE_65
    monde = R@local*dt
    for essai in (monde, np.array([monde[0], 0.]), np.array([0., monde[1]])):
        if distance_aux_murs(pose[:2]+essai, murs) >= rayon:
            pose[:2] += essai
            break
    pose[2] += ROTATION_65*tourne/65.*dt
    return pose


class SalleVirtuelle:
    """Robot + salle avancés à pas de temps fixe, pour tester sans temps réel."""
    def __init__(self, murs=SALLE_DEUX_PIECES, pose=(0., -1., 0.), graine=1, derive=0., bruit=.003):
        self.murs = murs
        self.bruit = bruit               # écart-type du bruit de mesure en mètres (un LD06 réel : 1 à 2 cm)
        self.pose = np.array(pose, float)
        self.rng = np.random.default_rng(graine)
        self.t = 0.
        self.sequence = 0
        self.derive = derive             # glissement aléatoire (fraction de la vitesse), simule le patinage des roues

    def avancer(self, commande, dt):
        avance, gauche, tourne = commande
        if self.derive:
            gauche = gauche+self.derive*avance*self.rng.normal()
        self.pose = deplacer(self.pose, avance, gauche, tourne, dt, self.murs)
        self.t += dt

    def trame(self):
        self.sequence += 1
        fin = 1_000_000+int(self.t*1e6)
        return TrameScan(self.sequence, fin, 100000, mesures_simulees(self.pose, self.rng, self.murs, bruit=self.bruit))
