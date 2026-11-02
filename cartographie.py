"""Calculs du TP, indépendants de l'interface. Distances en mètres, angles en degrés.

Un scan = tableau N×3 : angle mathématique antihoraire, distance (m), intensité.
Une pose = (x, y, orientation). Un segment = tableau 2×2 : [premier, dernier point].
"""
from dataclasses import dataclass, field
from pathlib import Path
import csv
import numpy as np

EPS = 1e-8  # Tolérance géométrique en mètres ; angles comparés en radians.
ANGLE_REFERENCE_DEFAUT = 270.  # Ancien angle 270° = axe x positif du robot.


@dataclass
class Scan:
    nom: str
    mesures: np.ndarray
    pose: list = field(default_factory=lambda: [0., 0., 0.])
    source: str = 'CSV réel/importé'
    angle_reference: float = 0.  # Géométrie neutre ; imports/USB utilisent 270°.

    def points(self):
        """Polaire -> repère lidar -> rotation et translation dans la carte."""
        theta = np.deg2rad(self.mesures[:, 0] - self.angle_reference)
        rayon = self.mesures[:, 1]
        locaux = np.column_stack((rayon * np.cos(theta), rayon * np.sin(theta)))
        a = np.deg2rad(self.pose[2])
        rotation = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        return locaux @ rotation.T + np.asarray(self.pose[:2])


def lire_csv(chemin):
    """Lit le CSV ESP32 (6 colonnes) ou notre export (3 colonnes).

    Les indices qui reviennent à zéro et les lignes vides séparent les scans.
    Un fragment importé reste possible : l'utilisateur doit vérifier sa complétude.
    Les lignes non reconnues ne sont jamais ignorées silencieusement.
    """
    groupes, courant, precedent = [], [], None
    def terminer():
        nonlocal courant, precedent
        if courant:
            groupes.append(np.asarray(courant, dtype=float))
        courant, precedent = [], None
    with open(chemin, encoding='utf-8-sig') as f:
        for numero, ligne in enumerate(f, 1):
            ligne = ligne.strip()
            if not ligne:
                terminer()
                continue
            if ligne.startswith('#') or ligne.lower().startswith(('n,', 'angle_deg,')):
                continue
            try:
                valeurs = [float(v) for v in ligne.split(',')]
                if not np.all(np.isfinite(valeurs)):
                    raise ValueError('valeur non finie')
                if len(valeurs) == 6:
                    indice, angle, distance, intensite, _, _ = valeurs
                    if indice < 0 or indice != int(indice):
                        raise ValueError('indice invalide')
                    if precedent is not None and indice <= precedent:
                        terminer()
                    precedent = indice
                    distance /= 1000.  # Le CSV ESP32 est en mm.
                elif len(valeurs) == 3:
                    angle, distance, intensite = valeurs  # Notre export est en mètres.
                else:
                    raise ValueError('3 ou 6 colonnes attendues')
                if distance < 0 or not 0 <= intensite <= 255:
                    raise ValueError('distance ou intensité invalide')
                courant.append((angle % 360., distance, intensite))
            except ValueError as exc:
                raise ValueError(f'Ligne {numero} : {exc}. CSV attendu, sans sortie Teleplot.') from exc
    terminer()
    if not groupes:
        raise ValueError('Aucune mesure dans ce fichier.')
    return [Scan(f'{Path(chemin).stem} / {i+1}', g,
                 angle_reference=ANGLE_REFERENCE_DEFAUT) for i, g in enumerate(groupes)]


def exporter_scan(scan, chemin):
    with open(chemin, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['angle_deg', 'distance_m', 'intensite'])
        w.writerows(scan.mesures)


def mesures_valides(scan, mini=.05, maxi=12., intensite=0):
    m = scan.mesures
    return np.isfinite(m).all(axis=1) & (m[:, 1] >= mini) & (m[:, 1] < maxi) & (m[:, 2] >= intensite)


def produit_vectoriel(a, b):
    return float(a[0]*b[1] - a[1]*b[0])


def longueur(s):
    return float(np.linalg.norm(s[1]-s[0]))


def angle_segments(a, b):
    """Angle non orienté 0..90° : une droite et son inverse ont le même angle."""
    u, v = a[1]-a[0], b[1]-b[0]
    if min(np.linalg.norm(u), np.linalg.norm(v)) <= EPS:
        raise ValueError('Un segment de longueur nulle ne possède pas de direction.')
    cos = abs(float(np.dot(u, v) / (np.linalg.norm(u)*np.linalg.norm(v))))
    return float(np.rad2deg(np.arccos(np.clip(cos, 0, 1))))


def intersection(a, b, eps=EPS):
    """Intersection unique sur les DEUX segments, extrémités comprises.

    Retourne None pour les parallèles, colinéaires et segments dégénérés.
    Les tolérances sur les paramètres sont ramenées à des distances en mètres.
    """
    p, q = a[0], b[0]
    u, v = a[1]-p, b[1]-q
    lu, lv = np.linalg.norm(u), np.linalg.norm(v)
    if min(lu, lv) <= eps:
        return None
    den = produit_vectoriel(u, v)
    if abs(den) <= eps*lu*lv:  # Seuil angulaire de parallélisme.
        return None
    t = produit_vectoriel(q-p, v)/den
    s = produit_vectoriel(q-p, u)/den
    if -eps/lu <= t <= 1+eps/lu and -eps/lv <= s <= 1+eps/lv:
        return p + np.clip(t, 0, 1)*u
    return None


def decouper(a, b, eps=EPS):
    """Garde le plus long côté de a ; égalité -> côté contenant a[0]."""
    point = intersection(a, b, eps)
    if point is None:
        return a.copy()
    gauche, droite = np.linalg.norm(point-a[0]), np.linalg.norm(a[1]-point)
    if min(gauche, droite) <= eps:  # Pas de coupe à une extrémité.
        return a.copy()
    if gauche >= droite-eps:
        return np.array([a[0], point])
    return np.array([point, a[1]])


def distance_point_segment(p, s):
    u = s[1]-s[0]
    denom = np.dot(u, u)
    if denom <= EPS**2:
        return float(np.linalg.norm(p-s[0]))
    t = np.clip(np.dot(p-s[0], u)/denom, 0, 1)
    return float(np.linalg.norm(p-(s[0]+t*u)))


def proches(a, b, angle_max=8., distance_max=.12):
    if min(longueur(a), longueur(b)) <= EPS:
        return False
    if angle_segments(a, b) > angle_max:
        return False
    distance = 0. if intersection(a, b) is not None else min(
        *(distance_point_segment(p, b) for p in a),
        *(distance_point_segment(p, a) for p in b))
    return distance <= distance_max


def ajuster_segment(points):
    """Ajustement orthogonal (PCA/SVD), puis projection des extrémités."""
    centre = np.mean(points, axis=0)
    _, _, axes = np.linalg.svd(points-centre, full_matrices=False)
    direction = axes[0]
    proj = (points-centre) @ direction
    return np.array([centre + proj.min()*direction, centre + proj.max()*direction])


def fusionner(a, b, angle_max=8., distance_max=.12):
    if not proches(a, b, angle_max, distance_max):
        raise ValueError('Ces segments ne sont pas assez proches pour fusionner.')
    return ajuster_segment(np.vstack([a, b]))


def extraire_segments(scan, mini=.05, maxi=12., intensite=0,
                     saut=.20, erreur=.04, nb_min=6, longueur_min=.15):
    """Coupe aux discontinuités, puis split-and-fit par erreur orthogonale.

    On respecte l'ordre temporel des points, sans relier le dernier au premier.
    Les mesures rejetées créent aussi une coupure (pas de pont sur un trou).
    """
    points, valide = scan.points(), mesures_valides(scan, mini, maxi, intensite)
    groupes, groupe = [], []
    for p, ok in zip(points, valide):
        if not ok or (groupe and np.linalg.norm(p-groupe[-1]) > saut):
            if len(groupe) >= nb_min:
                groupes.append(np.array(groupe))
            groupe = []
        if ok:
            groupe.append(p)
    if len(groupe) >= nb_min:
        groupes.append(np.array(groupe))
    resultat = []
    while groupes:
        pts = groupes.pop()
        seg = ajuster_segment(pts)
        if longueur(seg) <= EPS:
            continue
        # Le découpage utilise la droite des extrémités : contrairement à la
        # PCA, son erreur est nulle aux extrémités et révèle les coins internes.
        corde = pts[-1]-pts[0]
        if np.linalg.norm(corde) <= EPS:
            k = len(pts)//2
            groupes.extend(s for s in (pts[:k+1], pts[k:]) if nb_min <= len(s) < len(pts))
            continue
        direction = corde/np.linalg.norm(corde)
        ecarts = np.abs((pts-pts[0]) @ np.array([-direction[1], direction[0]]))
        k = int(np.argmax(ecarts))
        if ecarts[k] > erreur:
            # Un sous-groupe trop petit est rejeté, pas remplacé par une fausse droite.
            for sous in (pts[:k+1], pts[k:]):
                if nb_min <= len(sous) < len(pts):
                    groupes.append(sous)
        elif longueur(seg) >= longueur_min:
            resultat.append(seg)
    return resultat


def carte_vectorielle(scans, angle_max=8., distance_max=.12, **options):
    """Accumule les segments ; fusionne les voisins jusqu'à stabilisation."""
    carte = []
    for scan in scans:
        for nouveau in extraire_segments(scan, **options):
            i = 0
            while i < len(carte):
                if proches(carte[i], nouveau, angle_max, distance_max):
                    nouveau = fusionner(carte.pop(i), nouveau, angle_max, distance_max)
                    i = 0
                else:
                    i += 1
            carte.append(nouveau)
    return carte


def cellules_ligne(x0, y0, x1, y1):
    """Bresenham : indices des cellules traversées du capteur à l'impact."""
    dx, dy = abs(x1-x0), -abs(y1-y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    erreur = dx+dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            return
        double = 2*erreur
        if double >= dy:
            erreur += dy
            x0 += sx
        if double <= dx:
            erreur += dx
            y0 += sy


@dataclass
class Grille:
    origine: np.ndarray
    resolution: float
    log_odds: np.ndarray
    observe: np.ndarray

    @classmethod
    def creer(cls, scans, resolution=.05, mini=.05, maxi=12., intensite=0):
        if not scans or not np.isfinite(resolution) or resolution <= 0:
            raise ValueError('Scans et résolution positive nécessaires.')
        tous = [np.array([s.pose[:2]]) for s in scans]
        tous += [s.points()[mesures_valides(s, mini, maxi, intensite)] for s in scans]
        points = np.vstack(tous)
        origine = np.floor((points.min(axis=0)-.5)/resolution)*resolution
        taille = np.ceil((points.max(axis=0)+.5-origine)/resolution).astype(int)+1
        if np.prod(taille) > 4_000_000:
            raise ValueError('Grille trop grande : augmente la résolution (m/cellule).')
        nx, ny = taille
        return cls(origine, resolution, np.zeros((ny, nx)), np.zeros((ny, nx), bool))

    def mettre_a_jour(self, scan, mini=.05, maxi=12., intensite=0):
        """Log-odds : libre -0.4, impact +0.85 ; au plus une preuve/cellule/scan.

        L'impact gagne sur le libre au sein d'un scan. Un rayon hors grille
        est ignoré ; l'interface reconstruit les bornes pour tous les scans.
        Les retours invalides/à portée max ne libèrent aucune cellule.
        """
        depart = np.floor((np.array(scan.pose[:2])-self.origine)/self.resolution).astype(int)
        ny, nx = self.log_odds.shape
        libre, occupe = set(), set()
        for point in scan.points()[mesures_valides(scan, mini, maxi, intensite)]:
            fin = np.floor((point-self.origine)/self.resolution).astype(int)
            if not (0 <= depart[0] < nx and 0 <= depart[1] < ny and 0 <= fin[0] < nx and 0 <= fin[1] < ny):
                continue
            rayon = list(cellules_ligne(*depart, *fin))
            libre.update(rayon[:-1])
            occupe.add(rayon[-1])
        for cellules, increment in ((libre-occupe, -.4), (occupe, .85)):
            if cellules:
                xx, yy = np.array(list(cellules)).T
                self.log_odds[yy, xx] = np.clip(self.log_odds[yy, xx]+increment, -4, 4)
                self.observe[yy, xx] = True

    def probabilites(self):
        return 1/(1+np.exp(-self.log_odds))


def demonstration():
    """Deux scans SIMULÉS d'une salle rectangulaire avec un obstacle."""
    murs = [np.array(s, float) for s in [
        [[-3,-2],[3,-2]], [[3,-2],[3,2]], [[3,2],[-3,2]], [[-3,2],[-3,-2]],
        [[1,-.6],[1,.6]], [[1,.6],[1.5,.6]], [[1.5,.6],[1.5,-.6]], [[1.5,-.6],[1,-.6]]]]
    resultat = []
    for i, pose in enumerate(([0.,0.,0.], [-.8,.4,15.])):
        mesures = []
        for angle in np.arange(359., -1., -1.):
            a = np.deg2rad(angle+pose[2])
            origine = np.array(pose[:2])
            rayon = np.array([origine, origine+20*np.array([np.cos(a), np.sin(a)])])
            impacts = [p for m in murs if (p := intersection(rayon, m)) is not None]
            distance = min(np.linalg.norm(p-origine) for p in impacts)
            mesures.append([angle, distance, 220])
        resultat.append(Scan(f'SIMULÉ {i+1}', np.array(mesures), list(pose), 'SIMULATION — pas un relevé réel'))
    return resultat
