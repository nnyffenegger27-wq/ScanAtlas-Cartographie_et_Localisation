"""Calculs du TP, indépendants de l'interface. Distances en mètres, angles en degrés.

Un scan = tableau N×3 : angle mathématique antihoraire, distance (m), intensité.
Une pose = (x, y, orientation). Un segment = tableau 2×2 : [premier, dernier point].
"""
from dataclasses import dataclass, field
from pathlib import Path
import csv
import re
from zipfile import ZipFile
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
    intensite_disponible: bool = True
    pose_connue: list | None = None  # Métadonnée MapTool, jamais utilisée par ICP.
    suivi_recalage: dict | None = None  # Résultat de l'option automatique USB.

    def points(self):
        """Polaire -> repère lidar -> rotation et translation dans la carte."""
        theta = np.deg2rad(self.mesures[:, 0] - self.angle_reference)
        rayon = self.mesures[:, 1]
        locaux = np.column_stack((rayon * np.cos(theta), rayon * np.sin(theta)))
        a = np.deg2rad(self.pose[2])
        rotation = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
        return locaux @ rotation.T + np.asarray(self.pose[:2])


def diagnostic_scan(mesures):
    """Contrôle angulaire indicatif ; ni horodatage ni vitesse moteur dans le CSV.

    340..380° : tolérance autour d'un tour. Une grande lacune reste suspecte
    même si les angles de début et de fin sont proches d'un tour complet.
    Aucun point n'est ajouté, supprimé ou réordonné.
    """
    angles = np.asarray(mesures, float)[:, 0]
    deroules = np.rad2deg(np.unwrap(np.deg2rad(angles)))
    etendue = float(np.ptp(deroules)) if len(angles) else 0.
    pas = np.abs(np.diff(deroules))
    lacune = float(pas.max()) if len(pas) else 0.
    if etendue > 380.:
        etat = 'Bloc de plusieurs tours'
    elif etendue < 340.:
        etat = 'Tour incomplet'
    elif lacune > 10.:
        etat = 'Lacune angulaire importante'
    else:
        etat = 'Environ un tour (pertes non exclues)'
    return dict(points=len(angles), etendue=etendue, pas_max=lacune, etat=etat,
                tour_plausible=340. <= etendue <= 380. and lacune <= 10.)


def lire_csv(chemin, contenu=None):
    """Lit ESP32 (6 colonnes), notre export (3), MapTool (4) ou un ZIP de CSV.

    Les indices qui reviennent à zéro et les lignes vides séparent les scans.
    Un fragment importé reste possible : l'utilisateur doit vérifier sa complétude.
    Les lignes non reconnues ne sont jamais ignorées silencieusement.
    """
    if contenu is None and Path(chemin).suffix.lower() == '.zip':
        resultat = []
        with ZipFile(chemin) as archive:
            noms = sorted(n for n in archive.namelist() if n.lower().endswith('.csv') and not n.startswith('__MACOSX/'))
            if not noms:
                raise ValueError('Aucun fichier CSV dans cette archive.')
            for nom in noms:
                try:
                    resultat.extend(lire_csv(nom, archive.read(nom).decode('utf-8-sig')))
                except (ValueError, UnicodeError) as exc:
                    raise ValueError(f'{nom} : {exc}') from exc
        return resultat
    texte = Path(chemin).read_text(encoding='utf-8-sig') if contenu is None else contenu.lstrip('\ufeff')
    maptool = any(l.strip().lower() == 'angle_deg,r_m,x_rel_m,y_rel_m' for l in texte.splitlines())
    pose = [0., 0., 0.]
    pose_connue = None
    if maptool:
        for ligne in texte.splitlines():
            if ligne.strip().lower().startswith('# robot position:'):
                motif = r'#\s*Robot position:\s*x=([^,]+)m,\s*y=([^,]+)m,\s*theta=(.+)deg\s*'
                m = re.fullmatch(motif, ligne.strip(), re.IGNORECASE)
                if not m:
                    raise ValueError('Pose MapTool invalide : x et y en mètres, theta en degrés attendus.')
                try:
                    pose = [float(v) for v in m.groups()]
                except ValueError as exc:
                    raise ValueError('Pose MapTool invalide.') from exc
                if not np.isfinite(pose).all():
                    raise ValueError('Pose MapTool non finie.')
                pose_connue = list(pose)
    groupes, courant, precedent = [], [], None
    def terminer():
        nonlocal courant, precedent
        if courant:
            groupes.append(np.asarray(courant, dtype=float))
        courant, precedent = [], None
    for numero, ligne in enumerate(texte.splitlines(), 1):
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
            if maptool:
                if len(valeurs) != 4:
                    raise ValueError('MapTool : 4 colonnes attendues')
                angle, distance, x, y = valeurs
                # x/y relatifs sont redondants ; vérifier le repère puis
                # recalculer les coordonnées depuis angle et distance.
                attendu = distance*np.array([np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))])
                if not np.allclose(attendu, [x, y], atol=.001, rtol=0):
                    raise ValueError('Coordonnées relatives MapTool incompatibles avec angle et distance')
                intensite = 0.  # Valeur de stockage seulement, flag indisponible.
            elif len(valeurs) == 6:
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
    return [Scan(f'{Path(chemin).stem} / {i+1}', g, list(pose),
                 source='SIMULATION MapTool — intensité non fournie' if maptool else 'CSV réel/importé',
                 angle_reference=0. if maptool else ANGLE_REFERENCE_DEFAUT,
                 intensite_disponible=not maptool,
                 pose_connue=list(pose_connue) if pose_connue is not None else None) for i, g in enumerate(groupes)]


def exporter_scan(scan, chemin):
    with open(chemin, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if not scan.intensite_disponible:
            f.write(f'# Robot position: x={scan.pose[0]}m, y={scan.pose[1]}m, theta={scan.pose[2]}deg\n')
            w.writerow(['angle_deg', 'r_m', 'x_rel_m', 'y_rel_m'])
            a = np.deg2rad(scan.mesures[:, 0]-scan.angle_reference)
            for (angle, distance, _), theta in zip(scan.mesures, a):
                w.writerow([angle-scan.angle_reference, distance, distance*np.cos(theta), distance*np.sin(theta)])
            return
        w.writerow(['angle_deg', 'distance_m', 'intensite'])
        w.writerows(scan.mesures)


def mesures_valides(scan, mini=.05, maxi=12., intensite=0):
    m = scan.mesures
    return np.isfinite(m).all(axis=1) & (m[:, 1] >= mini) & (m[:, 1] < maxi) & ((m[:, 2] >= intensite) if scan.intensite_disponible else True)


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
    """Proximité en angle, distance ET compatibilité des droites supports.

    Une intersection seule ne suffit pas : les extrémités doivent rester
    proches de la droite de l'autre segment pour éviter de fusionner un éventail.
    """
    if min(longueur(a), longueur(b)) <= EPS:
        return False
    if angle_segments(a, b) > angle_max:
        return False
    for support, points in ((a, b), (b, a)):
        u = (support[1]-support[0])/longueur(support)
        normale = np.array([-u[1], u[0]])
        if np.max(np.abs((points-support[0]) @ normale)) > distance_max + EPS:
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
                     saut=.20, erreur=.04, nb_min=6, longueur_min=.15, retour_supports=False):
    """Coupe aux discontinuités, puis split-and-fit par erreur orthogonale.

    On respecte l'ordre temporel des points, sans relier le dernier au premier.
    Les mesures rejetées créent aussi une coupure (pas de pont sur un trou).
    """
    points, valide = scan.points(), mesures_valides(scan, mini, maxi, intensite)
    groupes, groupe = [], []
    precedent = None
    for p, ok, angle in zip(points, valide, scan.mesures[:,0]):
        nouveau_tour = precedent is not None and abs(angle-precedent) > 180.
        if not ok or nouveau_tour or (groupe and np.linalg.norm(p-groupe[-1]) > saut):
            if len(groupe) >= nb_min:
                groupes.append(np.array(groupe))
            groupe = []
        if ok:
            groupe.append(p)
        precedent = angle
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
            u = (seg[1]-seg[0])/longueur(seg)
            erreurs_fit = np.abs((pts-seg[0]) @ np.array([-u[1],u[0]]))
            if erreurs_fit.max() > erreur:
                k = int(np.argmax(erreurs_fit))
                if k in (0, len(pts)-1):
                    k = len(pts)//2
                groupes.extend(s for s in (pts[:k+1],pts[k:]) if nb_min <= len(s) < len(pts))
            else:
                resultat.append((seg, pts.copy()) if retour_supports else seg)
    return resultat


def extraire_multiscans(scans, **options):
    """Extrait séparément chaque scan dans sa pose, sans relier leurs points."""
    segments, origines = [], []
    for i, scan in enumerate(scans):
        nouveaux = extraire_segments(scan, **options)
        segments.extend(nouveaux)
        origines.extend([i]*len(nouveaux))
    return segments, origines


def nettoyer_segments(carte, scan, marge=.12, minimum_rayons=3, longueur_min=.15):
    """Raccourcit les anciennes formes traversées par plusieurs rayons libres.

    Une pose est appliquée au bloc entier. Les rayons d'angles identiques
    (bins de 0,5°) ne votent qu'une fois, même si le bloc contient plusieurs tours.
    Les impacts proches du segment et les contacts à ses extrémités sont ignorés.
    """
    depart = np.asarray(scan.pose[:2], float)
    impacts = scan.points()
    directions = impacts-depart
    distances = np.linalg.norm(directions, axis=1)
    bins = np.floor((scan.mesures[:,0] % 360.)/.5).astype(int)
    resultat, coupes = [], 0
    for ancien in carte:
        u = ancien[1]-ancien[0]
        taille = longueur(ancien)
        if taille <= EPS:
            continue
        q = depart-ancien[0]
        den = u[0]*directions[:,1]-u[1]*directions[:,0]
        with np.errstate(divide='ignore', invalid='ignore'):
            t = (q[0]*directions[:,1]-q[1]*directions[:,0])/den
            r = (q[0]*u[1]-q[1]*u[0])/den
        # t est la position sur l'ancien segment ; r est la position sur le rayon.
        valides = (np.abs(den)>EPS*taille*distances) & (distances>EPS)
        valides &= (t>EPS/taille) & (t<1-EPS/taille) & (r>=0) & (r<=1)
        valides &= (r*distances>marge) & ((1-r)*distances>marge)
        indices = np.flatnonzero(valides)
        if len(indices):
            _, premiers = np.unique(bins[indices], return_index=True)
            indices = indices[premiers]
        nouveau = ancien.copy()
        if len(indices) >= minimum_rayons:
            # Une seule coupe médiane par ancien segment et nouveau bloc.
            i = indices[np.argsort(t[indices])[len(indices)//2]]
            nouveau = decouper(ancien, np.array([depart, impacts[i]]))
            if not np.allclose(nouveau, ancien, rtol=0, atol=EPS):
                coupes += 1
        if longueur(nouveau) >= longueur_min:
            resultat.append(nouveau)
    return resultat, coupes


def carte_vectorielle(scans, angle_max=8., distance_max=.12, retour_details=False, **options):
    """Carte successive : rayons libres, extraction, fusion sur les points sources.

    Les supports de chaque fusion sont les mesures d'origine, pas les seules
    extrémités d'un segment déjà moyenné. Une fusion doit respecter l'erreur
    d'ajustement sur TOUS ses points, ce qui limite la dérive par fusions en chaîne.
    """
    erreur = options.get('erreur', .04)
    longueur_min = options.get('longueur_min', .15)
    carte = []  # Couples (segment, points sources).
    details = dict(extraits=0, fusions=0, coupes=0, scans=len(scans))
    for scan in scans:
        valide = mesures_valides(scan, options.get('mini', .05), options.get('maxi', 12.), options.get('intensite', 0))
        filtre = Scan(scan.nom, scan.mesures[valide], scan.pose, scan.source, scan.angle_reference, scan.intensite_disponible)
        nettoyee = []
        for segment, supports in carte:
            morceaux, coupes = nettoyer_segments([segment], filtre,
                marge=max(.05, 2*erreur), longueur_min=longueur_min)
            details['coupes'] += coupes
            for morceau in morceaux:
                if coupes:
                    # Conserver uniquement le support observé dans la partie gardée.
                    u = (morceau[1]-morceau[0])/longueur(morceau)
                    projections = (supports-morceau[0]) @ u
                    supports = supports[(projections >= -EPS) & (projections <= longueur(morceau)+EPS)]
                    if len(supports) < 2:
                        supports = morceau.copy()
                nettoyee.append((morceau, supports))
        carte = nettoyee
        for nouveau, supports in extraire_segments(scan, retour_supports=True, **options):
            details['extraits'] += 1
            i = 0
            while i < len(carte):
                ancien, appuis = carte[i]
                if proches(ancien, nouveau, angle_max, distance_max):
                    candidats = np.vstack([appuis, supports])
                    fusion = ajuster_segment(candidats)
                    u = (fusion[1]-fusion[0])/longueur(fusion)
                    residus = np.abs((candidats-fusion[0]) @ np.array([-u[1], u[0]]))
                    if residus.max() <= erreur + EPS:
                        nouveau, supports = fusion, candidats
                        carte.pop(i)
                        details['fusions'] += 1
                        i = 0
                        continue
                i += 1
            carte.append((nouveau, supports))
    segments = [s for s, _ in carte]
    return (segments, details) if retour_details else segments


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

    @classmethod
    def depuis_scan(cls, scan, resolution=.05, **filtres):
        """TP étape 3 : un scan avec sa pose produit une carte d'occupation."""
        grille = cls.creer([scan], resolution, **filtres)
        grille.mettre_a_jour(scan, **filtres)
        return grille

    def agrandir_pour(self, scan, mini=.05, maxi=12., intensite=0):
        """Étend les bornes sans déplacer les anciennes cellules dans le monde.

        La résolution reste fixe. Les nouvelles cases sont inconnues ; les
        probabilités et le masque observé existants sont copiés à l'identique.
        """
        cible = self.creer([scan], self.resolution, mini, maxi, intensite)
        origine = np.minimum(self.origine, cible.origine)
        ancien_debut = np.rint((self.origine-origine)/self.resolution).astype(int)
        cible_debut = np.rint((cible.origine-origine)/self.resolution).astype(int)
        taille = np.maximum(ancien_debut + np.array(self.log_odds.shape[::-1]),
                            cible_debut + np.array(cible.log_odds.shape[::-1]))
        if np.prod(taille) > 4_000_000:
            raise ValueError('Grille trop grande : reconstruis avec une résolution plus grande.')
        nx, ny = taille
        if np.array_equal(ancien_debut, [0, 0]) and (ny, nx) == self.log_odds.shape:
            return
        occupation = np.zeros((ny, nx))
        observe = np.zeros((ny, nx), bool)
        x, y = ancien_debut
        hauteur, largeur = self.log_odds.shape
        occupation[y:y+hauteur, x:x+largeur] = self.log_odds
        observe[y:y+hauteur, x:x+largeur] = self.observe
        self.origine, self.log_odds, self.observe = origine, occupation, observe

    def mettre_a_jour(self, scan, mini=.05, maxi=12., intensite=0):
        """Log-odds : libre -0.4, impact +0.85 ; au plus une preuve/cellule/scan.

        TP étape 3 : met à jour cette même carte avec un nouveau scan + pose.
        L'impact gagne sur le libre au sein d'un scan. Les bornes sont étendues
        au besoin pour ne pas ignorer les rayons situés hors de l'ancienne carte.
        Les retours invalides/à portée max ne libèrent aucune cellule.
        """
        if not 0 <= mini < maxi or not 0 <= intensite <= 255:
            raise ValueError('Filtres invalides : 0 ≤ min < max et intensité entre 0 et 255.')
        if not mesures_valides(scan, mini, maxi, intensite).any():
            return
        self.agrandir_pour(scan, mini, maxi, intensite)
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
