"""Charge de la carte directe : coût borné, journal hors du chemin critique, points périmés, carte unique."""
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import journal_direct
from cartographie import demonstration, proches
from cartographie_direct import CarteDirecte, reduire
from document_carte import DocumentCarte, grille_vers_json, valider_session
from journal_direct import JournalDirect
from simulation import SalleVirtuelle, SALLE_DEMO, rectangle


class Reduire(unittest.TestCase):
    def test_identique_a_np_unique_par_ligne(self):
        rng = np.random.default_rng(3)
        pts = rng.uniform(-7, 9, (5000, 2))
        attendu = pts[np.sort(np.unique(np.floor(pts/.05).astype(np.int64), axis=0, return_index=True)[1])]
        self.assertTrue(np.array_equal(reduire(pts), attendu))

    def test_vide_et_limite(self):
        self.assertEqual(reduire(np.empty((0, 2))).shape, (0, 2))
        with self.assertRaises(ValueError):
            reduire(np.random.default_rng(1).uniform(0, 100, (5000, 2)), maximum=100)


class Voisins(unittest.TestCase):
    def test_le_prefiltre_garde_tout_ce_que_proches_accepte(self):
        rng = np.random.default_rng(5)
        tableau, vus = [], 0
        for _ in range(400):
            centre = rng.uniform(-1, 1, 2)
            a = rng.uniform(0, np.pi)
            u = np.array([np.cos(a), np.sin(a)])
            tableau.append([centre-u*rng.uniform(.2, 1.5), centre+u*rng.uniform(.2, 1.5)])
        tableau = np.array(tableau)
        for nouveau in tableau[:150]:
            nouveau = nouveau+rng.normal(0, .02, (2, 2))
            voisins = set(CarteDirecte._voisins(tableau, nouveau, 6., .10))
            for i, s in enumerate(tableau):
                if proches(s, nouveau, angle_max=6., distance_max=.10):
                    vus += 1
                    self.assertIn(i, voisins)
        self.assertGreater(vus, 30)                                  # le test n'est pas vide


def rouler(carte, salle, commande, secondes, dt=.1):
    for _ in range(int(secondes/dt)):
        salle.avancer(commande, dt)
        carte.traiter(salle.trame())


class ScansCles(unittest.TestCase):
    def test_robot_a_l_arret_n_ajoute_aucun_scan_cle(self):
        salle, carte = SalleVirtuelle(SALLE_DEMO, pose=(0., 0., 0.)), CarteDirecte()
        rouler(carte, salle, (0, 0, 0), 20.)
        self.assertEqual(len(carte.cles), 1)                       # que le premier scan, pas un toutes les 2 s

    def test_un_scan_cle_tous_les_15_cm_environ(self):
        salle, carte = SalleVirtuelle(SALLE_DEMO, pose=(-2., 0., 0.)), CarteDirecte()
        rouler(carte, salle, (30, 0, 0), 20.)                      # ~ 2,8 m à 30 %
        parcouru = salle.pose[0]+2.
        self.assertGreater(parcouru, 2.)
        self.assertLessEqual(len(carte.cles), parcouru/.15+3)
        self.assertGreaterEqual(len(carte.cles), parcouru/.3)


class PointsPerimes(unittest.TestCase):
    BOITE = (1.8, -1.2, 2.3, -.7)

    def test_un_objet_retire_disparait_et_les_murs_restent(self):
        avec = np.vstack([SALLE_DEMO, np.array(rectangle(*self.BOITE), float)])
        salle, carte = SalleVirtuelle(avec, pose=(0., 0., 0.), bruit=.004), CarteDirecte()
        va_et_vient = [((30, 0, 0), 5.), ((-30, 0, 0), 5.), ((0, 30, 0), 3.), ((0, -30, 0), 3.)]
        for commande, duree in va_et_vient*2:
            rouler(carte, salle, commande, duree)

        def dans(pts, boite, marge=.12):
            x0, y0, x1, y1 = boite
            return int(np.sum((pts[:, 0] > x0-marge) & (pts[:, 0] < x1+marge) & (pts[:, 1] > y0-marge) & (pts[:, 1] < y1+marge)))
        avant = dans(carte.points, self.BOITE)
        murs_avant = len(carte.points)-avant
        self.assertGreater(avant, 8)                               # l'objet est bien dans la carte
        salle.murs = SALLE_DEMO                                    # on l'enlève
        for commande, duree in va_et_vient*3:
            rouler(carte, salle, commande, duree)
        self.assertLessEqual(dans(carte.points, self.BOITE), 2)    # plus de trace de l'objet
        segments_boite = [s for s, _ in carte.appuis if self.BOITE[0]-.2 < s[:, 0].mean() < self.BOITE[2]+.2
                          and self.BOITE[1]-.2 < s[:, 1].mean() < self.BOITE[3]+.2]
        self.assertEqual(segments_boite, [])
        # les murs, eux, n'ont pas été grignotés
        self.assertGreater(len(carte.points)-dans(carte.points, self.BOITE), .8*murs_avant)


class JournalHorsChemin(unittest.TestCase):
    def faux_etat(self, scans, n):
        return SimpleNamespace(accepte=True, message='ok', concordance=100., enrichissement=True, cles=n,
                               scans_cles=tuple(scans[:n]), scan=scans[0])

    def test_resultat_ne_bloque_pas_et_tout_est_ecrit_a_la_fermeture(self):
        modele = demonstration()[0]
        scans = [copy.deepcopy(modele) for _ in range(300)]
        with tempfile.TemporaryDirectory() as tmp:
            j = JournalDirect(tmp)
            pire = 0.
            for n in range(1, 301):
                t = time.perf_counter()
                j.resultat(SimpleNamespace(sequence=n), self.faux_etat(scans, n), dict(mini=.05, maxi=12., intensite=0))
                pire = max(pire, time.perf_counter()-t)
            j.evenement('Suivi perdu')
            j.fermer()
            self.assertLess(pire, .02)                              # un appel ne sérialise jamais la carte
            dossier = Path(j.dossier)
            self.assertIn('Suivi perdu', (dossier/'evenements.log').read_text(encoding='utf-8'))
            self.assertEqual(len((dossier/'tours.jsonl').read_text(encoding='utf-8').splitlines()), 300)
            session = json.loads((dossier/'session_secours.json').read_text(encoding='utf-8'))
            scans_lus, _, _ = valider_session(session)
            self.assertEqual(len(scans_lus), 300)                   # la dernière carte est bien sauvegardée

    def test_la_sauvegarde_de_secours_est_espacee(self):
        modele = demonstration()[0]
        scans = [copy.deepcopy(modele) for _ in range(10)]
        with tempfile.TemporaryDirectory() as tmp:
            j = JournalDirect(tmp)                                 # intervalle de 20 s : rien d'écrit avant
            for n in range(1, 11):
                j.resultat(SimpleNamespace(sequence=n), self.faux_etat(scans, n), dict(mini=.05, maxi=12., intensite=0))
            time.sleep(1.3)
            self.assertFalse((Path(j.dossier)/'session_secours.json').exists())
            j.fermer()
            self.assertTrue((Path(j.dossier)/'session_secours.json').exists())

    def test_appels_apres_fermeture_ignores(self):
        with tempfile.TemporaryDirectory() as tmp:
            j = JournalDirect(tmp)
            j.fermer()
            j.evenement('tard'); j.ecrire(dict(a=1)); j.fermer()


class CarteUnique(unittest.TestCase):
    def doc_direct(self):
        scans = demonstration()
        carte = CarteDirecte()
        carte.charger_reference(scans)
        doc = DocumentCarte()
        doc.remplacer_par_direct(list(carte.cles), vue=dict(points=carte.points, appuis=carte.appuis, grille=carte.grille))
        return doc, carte

    def test_l_onglet_carte_montre_la_carte_fusionnee_du_direct(self):
        doc, carte = self.doc_direct()
        self.assertTrue(doc.liste()['fusion'])
        nuage = doc.nuage()
        self.assertTrue(nuage['fusion'])
        self.assertEqual(len(nuage['scans']), 1)
        self.assertEqual(len(nuage['scans'][0]['pts']), 2*len(carte.points))
        self.assertEqual(len(doc.plan()['segments']), len(carte.appuis))
        self.assertEqual(doc.grille(), grille_vers_json(carte.grille))

    def test_une_modification_revient_au_calcul_par_scan(self):
        doc, _ = self.doc_direct()
        doc.regler(0, visible=False)
        self.assertFalse(doc.liste()['fusion'])
        self.assertNotIn('fusion', doc.nuage())
        self.assertGreaterEqual(len(doc.plan()['segments']), 1)    # recalculé depuis les scans

    def test_sans_direct_comportement_inchange(self):
        doc = DocumentCarte()
        doc.ajouter(demonstration())
        self.assertFalse(doc.liste()['fusion'])
        self.assertEqual(len(doc.nuage()['scans']), 2)


if __name__ == '__main__':
    unittest.main()
