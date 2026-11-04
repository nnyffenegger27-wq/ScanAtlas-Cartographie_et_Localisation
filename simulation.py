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
    d = np.inf
    for a, b in murs:
        v = b-a
        t = np.clip(np.dot(p-a, v)/np.dot(v, v), 0, 1)
        d = min(d, float(np.linalg.norm(p-(a+t*v))))
    return d


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
    def __init__(self, murs=SALLE_DEUX_PIECES, pose=(0., -1., 0.), graine=1, derive=0.):
        self.murs = murs
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
        return TrameScan(self.sequence, fin, 100000, mesures_simulees(self.pose, self.rng, self.murs))
