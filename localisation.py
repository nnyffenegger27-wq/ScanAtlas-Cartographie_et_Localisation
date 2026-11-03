"""Recalage ICP point à point 2D, NumPy uniquement, poses en mètres/degrés.

La référence reste dans son repère global. On estime la pose ABSOLUE du
scan mobile à partir de ses mesures locales et d'une pose initiale proche.
Le score décrit l'accord des points, jamais une erreur de localisation vraie.
"""
from dataclasses import dataclass
from time import perf_counter
import numpy as np
from cartographie import Scan, mesures_valides


@dataclass
class ResultatICP:
    pose: list
    pose_initiale: list
    rmse_initiale: float
    rmse: float
    recouvrement: float
    correspondances: int
    iterations: int
    duree: float
    converge: bool
    applicable: bool
    message: str


def rotation(angle):
    a = np.deg2rad(angle)
    return np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])


def transformer(points, pose):
    return points @ rotation(pose[2]).T + np.asarray(pose[:2])


def erreur_pose(estimee, vraie):
    return (float(np.linalg.norm(np.asarray(estimee[:2])-vraie[:2])),
            float(abs((estimee[2]-vraie[2]+180) % 360-180)))


def points_filtres(scan, filtres, locaux=False, maximum=1200):
    neutre = Scan(scan.nom, scan.mesures, [0., 0., 0.], scan.source, scan.angle_reference) if locaux else scan
    pts = neutre.points()[mesures_valides(scan, **filtres)]
    # Suppression des doublons exacts : un bloc de plusieurs tours est accepté.
    pts = np.unique(pts, axis=0)
    if len(pts) > maximum:
        pts = pts[np.linspace(0, len(pts)-1, maximum, dtype=int)]
    return pts


def plus_proches(points, reference):
    """Recherche exacte par blocs pour borner la mémoire sans dépendance SciPy."""
    indices, distances = [], []
    for debut in range(0, len(points), 128):
        d = np.sum((points[debut:debut+128, None]-reference[None])**2, axis=2)
        idx = np.argmin(d, axis=1)
        indices.extend(idx)
        distances.extend(np.sqrt(d[np.arange(len(idx)), idx]))
    return np.asarray(indices), np.asarray(distances)


def icp_scan(mobile, reference, pose_initiale=None, mini=.05, maxi=12., intensite=0,
             distance_max=.5, iterations_max=80, annuler=None):
    """ICP tronqué : distance limite puis conservation des 80 % meilleurs accords.

    >=6 paires, >=30 % du mobile dans distance_max et géométrie non colinéaire.
    Arrêt à correction <0,1 mm et <0,001 degré ; 1200 points max par nuage.
    Les entrées ne sont jamais modifiées. Une convergence locale peut être fausse.
    """
    debut = perf_counter()
    if mobile is reference:
        raise ValueError('Choisis deux scans différents.')
    valeurs = np.asarray([mini, maxi, intensite, distance_max, iterations_max], float)
    if (not np.isfinite(valeurs).all() or not 0 <= mini < maxi or
            not 0 <= intensite <= 255 or distance_max <= 0 or
            iterations_max != int(iterations_max) or not 1 <= iterations_max <= 300):
        raise ValueError('Filtres invalides, distance positive et 1 à 300 itérations entières requis.')
    pose = np.array(mobile.pose if pose_initiale is None else pose_initiale, dtype=float)
    if pose.shape != (3,) or not np.isfinite(pose).all():
        raise ValueError('La pose initiale doit contenir x, y et orientation finis.')
    initiale = pose.copy()
    filtres = dict(mini=mini, maxi=maxi, intensite=intensite)
    source = points_filtres(mobile, filtres, locaux=True)
    cible = points_filtres(reference, filtres)
    if min(len(source), len(cible)) < 6:
        raise ValueError('Au moins six points distincts par scan après filtrage sont nécessaires. Réduis les filtres si besoin.')
    if not np.isfinite(cible).all():
        raise ValueError('Pose de référence invalide.')

    def associations(p):
        idx, d = plus_proches(p, cible)
        valides = np.flatnonzero(d <= distance_max)
        # Le recouvrement est AVANT troncature ; RMSE sur toutes ces paires.
        rmse = float(np.sqrt(np.mean(d[valides]**2))) if len(valides) else float('inf')
        meilleurs = valides[np.argsort(d[valides])[:max(6, int(np.ceil(.8*len(valides))))]]
        return idx, meilleurs, rmse, len(valides)/len(source), len(valides)

    _, _, rmse_initiale, _, _ = associations(transformer(source, pose))
    converge, message, tours = False, 'Limite d’itérations atteinte : rapproche la pose initiale ou augmente la limite.', 0
    for tours in range(1, int(iterations_max)+1):
        if annuler is not None and annuler.is_set():
            message = 'Recalage annulé.'
            break
        points = transformer(source, pose)
        idx, bons, _, taux, _ = associations(points)
        if len(bons) < 6 or taux < .3:
            message = 'Recouvrement insuffisant : rapproche les scans ou ajuste la distance d’appariement.'
            break
        p, q = points[bons], cible[idx[bons]]
        cp, cq = p.mean(axis=0), q.mean(axis=0)
        u, valeurs_s, vt = np.linalg.svd((p-cp).T @ (q-cq))
        if valeurs_s[0] < 1e-12 or valeurs_s[1] < 1e-6*valeurs_s[0]:
            message = 'Géométrie ambiguë : les correspondances suivent une seule droite.'
            break
        r = vt.T @ u.T
        if np.linalg.det(r) < 0:
            vt[-1] *= -1
            r = vt.T @ u.T
        t = cq-r @ cp
        delta_angle = float(np.rad2deg(np.arctan2(r[1, 0], r[0, 0])))
        ancienne = pose.copy()
        pose[:2] = r @ pose[:2]+t
        pose[2] = (pose[2]+delta_angle+180) % 360-180
        if np.linalg.norm(pose[:2]-ancienne[:2]) < 1e-4 and abs(delta_angle) < .001:
            converge, message = True, 'Convergence locale. Vérifie les murs et ouvertures avant d’appliquer.'
            break
    _, _, rmse, taux, nombre = associations(transformer(source, pose))
    applicable = (converge and taux >= .3 and nombre >= 6 and
                  np.isfinite(rmse) and (not np.isfinite(rmse_initiale) or rmse <= rmse_initiale+1e-6))
    if converge and not applicable:
        message = 'Résultat non validé : accord final insuffisant ou dégradé.'
    return ResultatICP(pose.tolist(), initiale.tolist(), rmse_initiale, rmse,
                       taux, nombre, tours, perf_counter()-debut, converge, applicable, message)
