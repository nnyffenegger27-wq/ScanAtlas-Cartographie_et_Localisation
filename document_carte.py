"""La carte : un seul document partagé par le direct et l'atelier, sans aucune dépendance à une interface.

Les scans clés produits en direct et les scans importés vivent dans la même liste. Chaque scan a deux
drapeaux : visible (affichage) et inclus (participation aux calculs et à la carte de départ du direct).
`version` augmente à chaque modification : l'interface sait ainsi quand redemander la carte.
"""
import base64
import json
import tempfile
import threading
from copy import deepcopy
from pathlib import Path
import numpy as np
from cartographie import (Scan, Grille, lire_csv, exporter_scan, demonstration, mesures_valides,
                          carte_vectorielle, diagnostic_scan, ANGLE_REFERENCE_DEFAUT)
from localisation import sous_carte, points_filtres
from localisation_globale import localisation_globale
from assemblage_global import assembler_scans
from cartographie_direct import CarteDirecte

FILTRES_DEFAUT = dict(mini=.05, maxi=12., intensite=0)
RESOLUTIONS = (.02, .05, .10, .20)
SEUIL_SESSION_FUSIONNEE = 30      # au-delà, une session ouverte s'affiche comme la carte du direct (fusionnée) tant qu'on n'y touche pas


def _entier_mm(tableau):
    return np.rint(np.asarray(tableau, float)*1000).astype(int).ravel().tolist()


def valider_session(data):
    """Scans d'un fichier de session JSON (versions 1 et 2) ; lève ValueError au premier défaut."""
    if not isinstance(data, dict) or data.get('version') not in (1, 2) or not isinstance(data.get('scans'), list):
        raise ValueError('Fichier de session inconnu (version 1 ou 2 attendue).')
    scans, drapeaux = [], []
    for d in data['scans']:
        mesures, pose = np.asarray(d['mesures'], float), np.asarray(d['pose'], float)
        if (mesures.ndim != 2 or mesures.shape[1] != 3 or len(mesures) == 0 or pose.shape != (3,)
                or not np.isfinite(mesures).all() or not np.isfinite(pose).all()):
            raise ValueError('Mesures ou pose invalides dans la session.')
        if (mesures[:, 1] < 0).any() or ((mesures[:, 2] < 0) | (mesures[:, 2] > 255)).any():
            raise ValueError('Distance ou intensité invalide dans la session.')
        source = str(d.get('source', 'Session'))
        # Les relevés réels utilisent ANGLE_REFERENCE_DEFAUT ; les exemples synthétiques un repère neutre.
        reference = 0. if 'SIMULATION' in source or 'SIMULÉ' in str(d.get('nom', '')) else ANGLE_REFERENCE_DEFAUT
        connue = d.get('pose_connue')
        if connue is not None:
            connue = np.asarray(connue, float)
            if connue.shape != (3,) or not np.isfinite(connue).all():
                raise ValueError('Pose connue invalide dans la session.')
            connue = connue.tolist()
        scan = Scan(str(d['nom']), mesures, pose.tolist(), source, reference,
                    bool(d.get('intensite_disponible', 'MapTool' not in source)), connue)
        suivi = d.get('suivi_recalage')
        if suivi is not None and not isinstance(suivi, dict):
            raise ValueError('Suivi de recalage invalide dans la session.')
        scan.suivi_recalage = suivi
        scans.append(scan)
        drapeaux.append((bool(d.get('inclus', True)), bool(d.get('visible', d.get('inclus', True)))))
    return scans, drapeaux, dict(data.get('parametres', {}))


def grille_vers_json(grille):
    """Grille d'occupation pour le navigateur : 0 = inconnu, 1 à 255 = probabilité d'occupation (octets en base64)."""
    valeurs = np.where(grille.observe, 1+np.rint(grille.probabilites()*254), 0).astype(np.uint8)
    hauteur, largeur = valeurs.shape
    return dict(origine=[float(grille.origine[0]), float(grille.origine[1])], resolution=grille.resolution,
                largeur=int(largeur), hauteur=int(hauteur), donnees=base64.b64encode(valeurs.tobytes()).decode('ascii'))


class DocumentCarte:
    def __init__(self):
        self.verrou = threading.RLock()
        self.scans, self.inclus, self.visibles = [], [], []
        self.filtres = dict(FILTRES_DEFAUT)
        self.resolution = .05
        self.version = 0
        self.nom = 'Sans titre'
        self.vue_directe = None      # carte fusionnée du direct, valable tant que la version n'a pas changé
        self.session_fusionnee = None   # version d'une grosse session ouverte, affichée fusionnée tant qu'on n'y touche pas
        self._cache_vue = None
        self._verrou_vue = threading.Lock()      # un seul calcul de la carte fusionnée à la fois (nuage, plan et grille la demandent ensemble)

    # -- état -----------------------------------------------------------------------------------
    def _change(self):
        self.version += 1

    def vider(self):
        with self.verrou:
            self.scans, self.inclus, self.visibles = [], [], []
            self.nom = 'Sans titre'
            self._change()

    def instantane(self):
        with self.verrou:
            return (list(self.scans), list(self.inclus), list(self.visibles), dict(self.filtres), self.resolution, self.nom)

    def restaurer(self, instantane):
        with self.verrou:
            self.scans, self.inclus, self.visibles, self.filtres, self.resolution, self.nom = (
                list(instantane[0]), list(instantane[1]), list(instantane[2]), dict(instantane[3]), instantane[4], instantane[5])
            self._change()

    def scans_inclus(self):
        with self.verrou:
            return [s for s, oui in zip(self.scans, self.inclus) if oui]

    def ajouter(self, scans):
        with self.verrou:
            self.scans.extend(scans)
            self.inclus.extend([True]*len(scans))
            self.visibles.extend([True]*len(scans))
            self._change()

    def remplacer_par_direct(self, cles, ignores=(), vue=None):
        """Le direct publie ses scans clés : ils remplacent les scans inclus, les scans exclus sont conservés.

        `vue` = dict(points, appuis, grille) : la carte fusionnée du direct (nuage dédoublonné, segments fusionnés,
        grille d'occupation). Tant que le document n'est pas modifié, l'onglet Carte affiche cette même carte au lieu
        de la recalculer depuis chaque scan clé : une seule carte pour tous les onglets, et pas de segments en double."""
        with self.verrou:
            exclus = [(s, v) for s, oui, v in zip(self.scans, self.inclus, self.visibles) if not oui]
            ancien = {id(s): v for s, oui, v in zip(self.scans, self.inclus, self.visibles) if oui}
            self.scans = [s for s, _ in exclus] + list(cles)
            self.inclus = [False]*len(exclus) + [True]*len(cles)
            self.visibles = [v for _, v in exclus] + [ancien.get(id(s), True) for s in cles]
            self._change()
            self.vue_directe = None if vue is None else dict(vue, version=self.version)

    def supprimer(self, indice):
        with self.verrou:
            self._verifier(indice)
            for liste in (self.scans, self.inclus, self.visibles):
                liste.pop(indice)
            self._change()

    def regler(self, indice, visible=None, inclus=None, pose=None, nom=None):
        with self.verrou:
            self._verifier(indice)
            if visible is not None:
                self.visibles[indice] = bool(visible)
            if inclus is not None:
                self.inclus[indice] = bool(inclus)
            if nom is not None:
                if not str(nom).strip():
                    raise ValueError('Nom vide.')
                self.scans[indice].nom = str(nom).strip()[:80]
            if pose is not None:
                pose = [float(v) for v in pose]
                if len(pose) != 3 or not np.isfinite(pose).all():
                    raise ValueError('Pose invalide (x, y, orientation).')
                self.scans[indice].pose = pose
                self.scans[indice].suivi_recalage = None
            self._change()

    def regler_tous(self, visible=None, inclus=None):
        with self.verrou:
            if visible is not None:
                self.visibles = [bool(visible)]*len(self.scans)
            if inclus is not None:
                self.inclus = [bool(inclus)]*len(self.scans)
            self._change()

    def regler_filtres(self, mini=None, maxi=None, intensite=None, resolution=None):
        with self.verrou:
            nouveau = dict(self.filtres)
            for cle, valeur in (('mini', mini), ('maxi', maxi), ('intensite', intensite)):
                if valeur is not None:
                    nouveau[cle] = float(valeur)
            if not (np.isfinite(list(nouveau.values())).all() and 0 <= nouveau['mini'] < nouveau['maxi'] <= 50
                    and 0 <= nouveau['intensite'] <= 255):
                raise ValueError('Filtres hors limites (0 ≤ min < max ≤ 50 m, intensité 0 à 255).')
            if resolution is not None:
                if float(resolution) not in RESOLUTIONS:
                    raise ValueError('Résolution : 2, 5, 10 ou 20 cm.')
                self.resolution = float(resolution)
            self.filtres = nouveau
            self._change()

    def _verifier(self, indice):
        if not isinstance(indice, int) or not 0 <= indice < len(self.scans):
            raise ValueError('Scan inconnu.')

    # -- fichiers -------------------------------------------------------------------------------
    def importer(self, nom_fichier, octets):
        """CSV, ZIP de CSV ou session JSON ; renvoie un message. Une session remplace la carte, le reste s'ajoute."""
        suffixe = Path(nom_fichier).suffix.lower()
        if suffixe == '.json':
            scans, drapeaux, parametres = valider_session(json.loads(octets.decode('utf-8-sig')))
            with self.verrou:
                self.scans = scans
                self.inclus = [i for i, _ in drapeaux]
                self.visibles = [v for _, v in drapeaux]
                self.nom = Path(nom_fichier).stem
                try:
                    self.regler_filtres(**{k: float(str(parametres[k]).replace(',', '.'))
                                           for k in ('mini', 'maxi', 'intensite') if k in parametres})
                except (ValueError, TypeError):
                    pass
                self._change()
                self.session_fusionnee = self.version if sum(self.inclus) > SEUIL_SESSION_FUSIONNEE else None
            return f'Session « {Path(nom_fichier).stem} » ouverte : {len(scans)} scans.'
        if suffixe == '.zip':
            with tempfile.TemporaryDirectory() as dossier:
                chemin = Path(dossier)/'import.zip'
                chemin.write_bytes(octets)
                scans = lire_csv(str(chemin))
        elif suffixe == '.csv':
            scans = lire_csv(nom_fichier, octets.decode('utf-8-sig'))
        else:
            raise ValueError('Formats acceptés : .csv, .zip de CSV ou session .json.')
        self.ajouter(scans)
        return f'{len(scans)} scan(s) importé(s).'

    def demonstration(self):
        self.ajouter(demonstration())
        return 'Deux scans simulés ajoutés.'

    def session_json(self):
        with self.verrou:
            contenu = dict(version=2, parametres={k: str(v) for k, v in self.filtres.items()},
                           scans=[dict(nom=s.nom, mesures=s.mesures.tolist(), pose=list(s.pose), source=s.source,
                                       angle_reference=s.angle_reference, inclus=oui, visible=vis,
                                       intensite_disponible=s.intensite_disponible, pose_connue=s.pose_connue,
                                       suivi_recalage=s.suivi_recalage)
                                  for s, oui, vis in zip(self.scans, self.inclus, self.visibles)])
        return json.dumps(contenu, ensure_ascii=False, allow_nan=False).encode('utf-8')

    def scan_csv(self, indice):
        with self.verrou:
            self._verifier(indice)
            scan = self.scans[indice]
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier)/'scan.csv'
            exporter_scan(scan, str(chemin))
            return chemin.read_bytes()

    # -- vues calculées -------------------------------------------------------------------------
    def liste(self):
        with self.verrou:
            sortie = []
            for i, (s, oui, vis) in enumerate(zip(self.scans, self.inclus, self.visibles)):
                d = diagnostic_scan(s.mesures)
                sortie.append(dict(id=i, nom=s.nom, source=s.source, inclus=oui, visible=vis, pose=[round(v, 4) for v in s.pose],
                                   points=len(s.mesures), etendue=round(float(d['etendue']), 1), etat=d['etat'],
                                   recalage=(s.suivi_recalage or {}).get('message')))
            return dict(version=self.version, nom=self.nom, scans=sortie, filtres=dict(self.filtres),
                        resolution=self.resolution, fusion=self.fusion_active())

    def _vue(self):
        """Carte fusionnée déjà prête (celle du direct), sinon None. Ne calcule rien."""
        v = self.vue_directe
        return v if v is not None and v['version'] == self.version else None

    def fusion_active(self):
        with self.verrou:
            return self._vue() is not None or self.session_fusionnee == self.version

    def vue_courante(self):
        """La carte fusionnée affichée (points, segments, grille) ou None : celle du direct, ou, pour une grosse session
        ouverte et pas encore modifiée, celle que le direct aurait construite avec ces scans (mise en cache, calculée
        hors du verrou du document : quelques secondes pour des centaines de scans)."""
        with self._verrou_vue:
            with self.verrou:
                v = self._vue()
                if v is not None:
                    return v
                if self.session_fusionnee != self.version:
                    return None
                if self._cache_vue is not None and self._cache_vue['version'] == self.version:
                    return self._cache_vue
                version, filtres, resolution = self.version, dict(self.filtres), self.resolution
                scans = [s for s, oui in zip(self.scans, self.inclus) if oui]
            points, appuis, grille = CarteDirecte.construire(scans, filtres, resolution)
            vue = dict(points=points, appuis=appuis, grille=grille, version=version)
            with self.verrou:
                if self.version == version:
                    self._cache_vue = vue
            return vue

    def nuage(self):
        """Points locaux (mm) de chaque scan et sa pose : le navigateur place, déplace et dessine."""
        vue = self.vue_courante()
        if vue is not None:            # carte fusionnée : un seul nuage, déjà dans le repère de la carte
            return dict(version=vue['version'], fusion=True, scans=[dict(id=-1, pose=[0., 0., 0.], pts=_entier_mm(vue['points']))])
        with self.verrou:
            sortie = []
            for i, (s, vis) in enumerate(zip(self.scans, self.visibles)):
                if not vis:
                    continue
                valides = mesures_valides(s, **self.filtres)
                theta = np.deg2rad(s.mesures[valides, 0]-s.angle_reference)
                rayon = s.mesures[valides, 1]
                local = np.column_stack((rayon*np.cos(theta), rayon*np.sin(theta)))
                sortie.append(dict(id=i, pose=list(s.pose), pts=_entier_mm(local)))
            return dict(version=self.version, scans=sortie)

    def grille(self):
        """Carte d'occupation des scans inclus : 0 = inconnu, 1 à 255 = probabilité d'occupation."""
        vue = self.vue_courante()
        if vue is not None and vue['grille'] is not None:
            return grille_vers_json(vue['grille'])
        scans = self.scans_inclus()
        if not scans:
            raise ValueError('Aucun scan inclus.')
        grille = Grille.creer(scans, self.resolution, **self.filtres)
        for scan in scans:
            grille.mettre_a_jour(scan, **self.filtres)
        return grille_vers_json(grille)

    def plan(self):
        """Carte vectorielle : segments fusionnés des scans inclus."""
        vue = self.vue_courante()
        if vue is not None:
            return dict(segments=[[round(float(v), 3) for v in np.asarray(seg).ravel()] for seg, _ in vue['appuis']])
        scans = self.scans_inclus()
        if not scans:
            raise ValueError('Aucun scan inclus.')
        segments = carte_vectorielle(scans, **self.filtres)
        return dict(segments=[[round(float(v), 3) for v in np.asarray(s).ravel()] for s in segments])

    # -- calculs lents --------------------------------------------------------------------------
    def recaler(self, indice, annuler=None):
        """Cherche la pose du scan sur le reste de la carte ; ne modifie rien (l'aperçu se valide à part)."""
        with self.verrou:
            self._verifier(indice)
            mobile = deepcopy(self.scans[indice])
            autres = [s for i, (s, oui) in enumerate(zip(self.scans, self.inclus)) if oui and i != indice]
            filtres = dict(self.filtres)
        if not autres:
            raise ValueError('Il faut au moins un autre scan inclus comme référence.')
        reference = sous_carte(autres, filtres, maximum=None)
        r = localisation_globale(mobile, reference, annuler=annuler, **filtres)
        return dict(id=indice, applicable=bool(r.applicable), pose=[float(v) for v in r.pose],
                    pose_initiale=[float(v) for v in r.pose_initiale], concordance=float(r.accord_fin),
                    rmse=float(r.rmse), recouvrement=float(r.recouvrement), duree=float(r.duree), message=r.message)

    def assembler(self, annuler=None, progression=None):
        """Replace tous les scans inclus dans un même repère (le premier est fixe)."""
        with self.verrou:
            indices = [i for i, oui in enumerate(self.inclus) if oui]
            scans = [self.scans[i] for i in indices]
            filtres = dict(self.filtres)
        resultat = assembler_scans(scans, annuler=annuler, progression=progression, **filtres)
        with self.verrou:
            for i, nouveau in zip(indices, resultat):
                self.scans[i] = nouveau
            self._change()
        groupes = {(s.suivi_recalage or {}).get('groupe', 0) for s in resultat}
        return f'{len(resultat)} scans assemblés' + (f' en {len(groupes)} groupes distincts.' if len(groupes) > 1 else '.')
