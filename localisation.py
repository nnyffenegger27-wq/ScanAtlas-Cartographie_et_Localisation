"""Recalage ICP point à point 2D, NumPy uniquement, poses en mètres/degrés.

La référence reste dans son repère global. On estime la pose ABSOLUE du
scan mobile à partir de ses mesures locales et d'une pose initiale proche.
Le score décrit l'accord des points, jamais une erreur de localisation vraie.
"""
from dataclasses import dataclass
from time import perf_counter
import numpy as np
from scipy.spatial import cKDTree
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
    methode: str = 'ICP local'
    candidats: int = 1
    accord_fin: float = 0.
    marge_ambiguite: float = float("inf")
    contradictions: float = 0.


def score_pose(points, reference, pose, distance_max):
    """Coût sur TOUS les points, avec pénalité bornée pour les non-appariés."""
    _, d = plus_proches(transformer(points, pose), reference)
    return float(np.mean(np.minimum(d, distance_max)**2))


def champ_distances(reference, limite, resolution=.05):
    """Distances bornées aux impacts, raster 5 cm ; utilisé seulement pour chercher.

    Chaque impact met à jour son voisinage. Une cellule hors champ vaut limite.
    La validation finale revient aux distances exactes et aux points complets.
    """
    origine = np.floor((reference.min(axis=0)-limite)/resolution)*resolution
    dimensions = np.ceil((reference.max(axis=0)+limite-origine)/resolution).astype(int)+1
    if np.prod(dimensions.astype(float)) > 4_000_000:
        raise ValueError('Zone de recherche trop étendue pour le champ de distances.')
    nx, ny = dimensions
    champ = np.full((ny, nx), limite**2)
    rayon = int(np.ceil(limite/resolution))+1
    for p in reference:
        ix, iy = np.floor((p-origine)/resolution).astype(int)
        x0, x1 = max(0, ix-rayon), min(nx, ix+rayon+1)
        y0, y1 = max(0, iy-rayon), min(ny, iy+rayon+1)
        x = origine[0]+np.arange(x0, x1)*resolution
        y = origine[1]+np.arange(y0, y1)*resolution
        np.minimum(champ[y0:y1, x0:x1], (x[None]-p[0])**2+(y[:, None]-p[1])**2,
                   out=champ[y0:y1, x0:x1])
    return origine, resolution, champ


def recherche_icp(mobile, reference, pose_initiale=None, mini=.05, maxi=12., intensite=0,
                  distance_max=.5, iterations_max=80, fenetre_xy=1., fenetre_angle=30.,
                  annuler=None, progression=None):
    """Recherche bornée grossière/fine, puis ICP sur plusieurs départs distincts.

    Fenêtres autour de la pose initiale, axes globaux et angle autour du lidar.
    Pas initial 25 cm et 5° (translation élargie sur grandes fenêtres pour borner
    le travail), deux affinements /2, huit départs ICP plus le départ initial.
    Score borné incluant les non-appariés ; aucun usage d'une pose vraie.
    """
    debut = perf_counter()
    valeurs = np.asarray([mini, maxi, intensite, distance_max, iterations_max, fenetre_xy, fenetre_angle], float)
    initiale = np.asarray(mobile.pose if pose_initiale is None else pose_initiale, float)
    if (mobile is reference or initiale.shape != (3,) or not np.isfinite(initiale).all() or
            not np.isfinite(valeurs).all() or not 0 <= mini < maxi or not 0 <= intensite <= 255 or
            distance_max <= 0 or iterations_max != int(iterations_max) or not 1 <= iterations_max <= 300 or
            not 0 < fenetre_xy <= 3 or not 0 < fenetre_angle <= 90):
        raise ValueError('Recherche : deux scans, pose finie, filtres valides, fenêtre >0 jusqu’à 3 m et 90°, et 1 à 300 itérations.')
    filtres = dict(mini=mini, maxi=maxi, intensite=intensite)
    source = points_filtres(mobile, filtres, locaux=True)
    cible = points_filtres(reference, filtres)
    if min(len(source), len(cible)) < 6 or not np.isfinite(cible).all():
        raise ValueError('Au moins six points distincts par scan et une pose de référence finie sont nécessaires.')
    # 300 points couvrant le mobile pour la recherche, cible jusqu'à 1200.
    petits = source[np.linspace(0, len(source)-1, min(300, len(source)), dtype=int)]
    limite = min(distance_max, 1.)
    origine, resolution, champ = champ_distances(cible, limite)
    bas, haut = initiale-[fenetre_xy, fenetre_xy, fenetre_angle], initiale+[fenetre_xy, fenetre_xy, fenetre_angle]
    nxy, na = int(np.ceil(2*fenetre_xy/.25)), int(np.ceil(2*fenetre_angle/5))
    # Borne le travail grossier sur les fenêtres maximales.
    while (nxy+1)**2*(na+1) > 6000:
        nxy = max(2, nxy-2)
    pas = np.array([2*fenetre_xy/nxy, 2*fenetre_xy/nxy, 2*fenetre_angle/na])
    candidats, total = [], 0

    def evaluer(pose):
        nonlocal total
        if annuler is not None and annuler.is_set():
            raise InterruptedError('Recherche annulée.')
        p = transformer(petits, pose)
        ij = np.rint((p-origine)/resolution).astype(int)
        ok = (ij[:, 0] >= 0) & (ij[:, 0] < champ.shape[1]) & (ij[:, 1] >= 0) & (ij[:, 1] < champ.shape[0])
        d = np.full(len(p), limite**2)
        d[ok] = champ[ij[ok, 1], ij[ok, 0]]
        total += 1
        return float(d.mean()), np.asarray(pose).copy()

    def diversifier(liste, distance, angle, nombre=8):
        retenus = []
        for score, pose in sorted(liste, key=lambda c: c[0]):
            if all(np.linalg.norm(pose[:2]-p[:2]) >= distance or abs(pose[2]-p[2]) >= angle for _, p in retenus):
                retenus.append((score, pose))
                if len(retenus) >= nombre: break
        return retenus

    try:
        if progression: progression('Recherche large en translation et rotation…')
        candidats.append(evaluer(initiale))
        for a in np.linspace(bas[2], haut[2], na+1):
            for x in np.linspace(bas[0], haut[0], nxy+1):
                for y in np.linspace(bas[1], haut[1], nxy+1):
                    candidats.append(evaluer([x, y, a]))
        graines = diversifier(candidats, .3, 8.)
        for _ in range(2):
            candidats = list(graines)
            for _, pose in graines:
                for dx in [-pas[0]/2, 0, pas[0]/2]:
                    for dy in [-pas[1]/2, 0, pas[1]/2]:
                        for da in [-pas[2]/2, 0, pas[2]/2]:
                            p = pose+[dx, dy, da]
                            if np.all(p >= bas-1e-8) and np.all(p <= haut+1e-8):
                                candidats.append(evaluer(p))
            pas /= 2
            graines = diversifier(candidats, max(.12, pas[0]), max(3., pas[2]))
        # Inclure le départ initial afin de conserver les cas déjà faciles.
        graines = graines+[(0., initiale)]
        resultats = []
        for i, (_, pose) in enumerate(graines):
            if annuler is not None and annuler.is_set(): raise InterruptedError('Recherche annulée.')
            if progression: progression(f'Affinement ICP {i+1}/{len(graines)}…')
            r = icp_scan(mobile, reference, pose_initiale=pose, **filtres,
                         distance_max=distance_max, iterations_max=iterations_max, annuler=annuler)
            # L'affinement ne doit pas sortir de la fenêtre annoncée.
            angle = initiale[2]+(r.pose[2]-initiale[2]+180) % 360-180
            p = np.array([r.pose[0], r.pose[1], angle])
            if r.applicable and np.all(p >= bas-1e-8) and np.all(p <= haut+1e-8):
                resultats.append((score_pose(source, cible, r.pose, limite), r))
        if annuler is not None and annuler.is_set(): raise InterruptedError('Recherche annulée.')
        if resultats:
            resultats.sort(key=lambda v: v[0])
            meilleur_score, resultat = resultats[0]
            resultat.message = 'Recherche large puis convergence ICP locale. Vérifie la superposition avant application.'
            valider_solution(resultat, source, cible, distance_max)
            for score, autre in resultats[1:]:
                ep, ea = erreur_pose(autre.pose, resultat.pose)
                if ep > .20 or ea > 5.:
                    resultat.marge_ambiguite = float(score-meilleur_score)
                    if score-meilleur_score < max(.0004, .08*meilleur_score):
                        resultat.applicable = False
                        resultat.message = 'Recalage ambigu : plusieurs poses différentes ont un score voisin. Rapproche la pose initiale ou ajoute une autre vue.'
                    break
        else:
            resultat = ResultatICP(initiale.tolist(), initiale.tolist(), float('inf'), float('inf'), 0., 0, 0, 0., False, False,
                                  'Aucun recalage convergé dans la fenêtre. Vérifie le recouvrement et la pose initiale.')
    except InterruptedError:
        resultat = ResultatICP(initiale.tolist(), initiale.tolist(), float('inf'), float('inf'), 0., 0, 0, 0., False, False, 'Recherche annulée.')
    _, distances = plus_proches(transformer(source, initiale), cible)
    valides = distances <= distance_max
    resultat.rmse_initiale = float(np.sqrt(np.mean(distances[valides]**2))) if valides.any() else float('inf')
    resultat.pose_initiale = initiale.tolist()
    resultat.duree = perf_counter()-debut
    resultat.methode = 'Recherche large + ICP'
    resultat.candidats = total
    return resultat


def rotation(angle):
    a = np.deg2rad(angle)
    return np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])


def transformer(points, pose):
    return points @ rotation(pose[2]).T + np.asarray(pose[:2])


def erreur_pose(estimee, vraie):
    return (float(np.linalg.norm(np.asarray(estimee[:2])-vraie[:2])),
            float(abs((estimee[2]-vraie[2]+180) % 360-180)))


def points_filtres(scan, filtres, locaux=False, maximum=1200):
    if isinstance(scan, ReferencePoints):
        return scan.points
    neutre = Scan(scan.nom, scan.mesures, [0., 0., 0.], scan.source, scan.angle_reference, scan.intensite_disponible) if locaux else scan
    pts = neutre.points()[mesures_valides(scan, **filtres)]
    # Suppression des doublons exacts : un bloc de plusieurs tours est accepté.
    pts = np.unique(pts, axis=0)
    if len(pts) > maximum:
        pts = pts[np.linspace(0, len(pts)-1, maximum, dtype=int)]
    return pts


@dataclass
class ReferencePoints:
    """Sous-carte déjà filtrée, dans le repère global ; aucune pose vraie utilisée."""
    points: np.ndarray
    nom: str = 'Sous-carte'
    sources: tuple = ()


def sous_carte(scans, filtres, resolution=.05, maximum=2400):
    """Moyenne par cellule : les observations répétées ne dominent pas le score."""
    nuages = [points_filtres(s, filtres, maximum=2400) for s in scans]
    if not nuages or not any(len(p) for p in nuages):
        raise ValueError('Sous-carte vide après filtrage.')
    points = np.concatenate(nuages)
    _, indices = np.unique(np.floor(points/resolution).astype(np.int64), axis=0, return_inverse=True)
    comptes = np.bincount(indices)
    centres = np.column_stack([np.bincount(indices, weights=points[:, k])/comptes for k in range(2)])
    if maximum is not None and len(centres) > maximum:
        centres = centres[np.linspace(0, len(centres)-1, maximum, dtype=int)]
    return ReferencePoints(centres, f'Sous-carte de {len(scans)} scans', tuple(scans))


def valider_solution(resultat, source, cible, distance_max, concordance_min=.65):
    """Accord fin indépendant du rayon large de recherche ; observabilité locale.

    65 % des impacts doivent être à <= 12 cm (ou demi-rayon si plus petit).
    Les normales estimées sur 7 voisins doivent contraindre les deux translations.
    Ce sont des critères numériques, pas une garantie d'erreur absolue.
    """
    p = transformer(source, resultat.pose)
    idx, d = plus_proches(p, cible)
    seuil = min(.12, distance_max*.5)
    bons = d <= seuil
    resultat.accord_fin = float(bons.mean())
    raison = None
    if bons.sum() < 12 or resultat.accord_fin < concordance_min:
        raison = f'Accord fin insuffisant : {resultat.accord_fin:.0%} à moins de {seuil:.2f} m ({concordance_min:.0%} et 12 points requis).'
    else:
        # Normales locales, sans relier des points éloignés par-dessus un trou.
        q = cible[np.unique(idx[bons])]
        normales = []
        for point in q[::max(1, len(q)//240)]:
            distances = np.sum((cible-point)**2, axis=1)
            voisins = np.argsort(distances)[:7]
            voisins = voisins[distances[voisins] <= .35**2]
            if len(voisins) < 4: continue
            v = cible[voisins]; v = v-v.mean(axis=0)
            valeurs, axes = np.linalg.eigh(v.T@v)
            if valeurs[1] > 1e-8 and valeurs[0] < .15*valeurs[1]:
                normales.append(axes[:, 0])
        if len(normales) < 6:
            raison = 'Géométrie insuffisante pour vérifier la pose : trop peu de surfaces linéaires.'
        else:
            n = np.asarray(normales)
            valeurs = np.linalg.eigvalsh(n.T@n/len(n))
            if valeurs[0] < .025:
                raison = 'Géométrie ambiguë : surfaces presque parallèles, glissement possible le long des murs.'
    if raison:
        resultat.applicable = False
        resultat.message = raison
    return resultat


_arbre_en_cache = (None, None)


def plus_proches(points, reference):
    """Plus proche voisin exact (arbre k-d). L'arbre de la dernière référence est gardé : une ICP interroge
    la même référence des dizaines de fois, sa construction n'est payée qu'une fois."""
    global _arbre_en_cache
    points = np.asarray(points, float)
    if not len(points) or not len(reference):
        return np.zeros(len(points), int), np.full(len(points), np.inf)
    cache = _arbre_en_cache                      # lecture unique : sûr entre fils
    if cache[0] is not reference:
        cache = (reference, cKDTree(reference))
        _arbre_en_cache = cache
    distances, indices = cache[1].query(points)
    return indices, distances


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
