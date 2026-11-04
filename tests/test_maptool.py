import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
import numpy as np
from cartographie import lire_csv, exporter_scan, mesures_valides
from localisation import points_filtres

CONTENU = '''# Robot position: x=2m, y=-3m, theta=90deg
angle_deg,r_m,x_rel_m,y_rel_m
0,1,1,0
90,2,0,2
180,1,-1,0
270,2,0,-2
45,1,0.7071,0.7071
135,1,-0.7071,0.7071
'''


class MapTool(unittest.TestCase):
    def test_repere_pose_et_intensite_absente(self):
        s = lire_csv('test.csv', CONTENU)[0]
        self.assertEqual(s.pose, [2, -3, 90])
        self.assertEqual(s.pose_connue, [2, -3, 90])
        self.assertEqual(s.angle_reference, 0.)
        self.assertFalse(s.intensite_disponible)
        self.assertIn('SIMULATION MapTool', s.source)
        np.testing.assert_allclose(s.points()[:4], [[2,-2], [0,-3], [2,-4], [4,-3]], atol=1e-10)
        self.assertTrue(mesures_valides(s, intensite=255).all())
        self.assertEqual(len(points_filtres(s, dict(mini=.05, maxi=12, intensite=255), locaux=True)), 6)
        self.assertEqual(mesures_valides(s, mini=1.5, intensite=255).sum(), 2)

    def test_pose_absente_et_bom(self):
        s = lire_csv('test.csv', '\ufeff'+CONTENU.split('\n',1)[1])[0]
        self.assertEqual(s.pose, [0.,0.,0.])
        self.assertIsNone(s.pose_connue)

    def test_coordonnees_pose_et_valeurs_invalides(self):
        for contenu in [CONTENU.replace('0,1,1,0', '0,1,0,1'),
                        CONTENU.replace('x=2m', 'x=nanm'),
                        CONTENU.replace('theta=90deg', 'theta=abcdeg'),
                        CONTENU.replace('0,1,1,0', '0,-1,-1,0')]:
            with self.subTest(contenu=contenu[:60]), self.assertRaises(ValueError):
                lire_csv('test.csv', contenu)

    def test_zip_multifichiers_sans_extraction(self):
        with tempfile.TemporaryDirectory() as dossier:
            p = Path(dossier)/'scans.zip'
            with ZipFile(p,'w') as z:
                z.writestr('sous/scan.csv', CONTENU)
                z.writestr('sous/autre.CSV', CONTENU)
                z.writestr('explication.txt', 'pas un scan')
            scans = lire_csv(p)
            self.assertEqual(len(scans), 2)
            self.assertEqual(sum(len(s.mesures) for s in scans), 12)
            self.assertEqual(len(list(Path(dossier).iterdir())),1)

    def test_zip_vide_ou_csv_invalide(self):
        with tempfile.TemporaryDirectory() as dossier:
            p = Path(dossier)/'scans.zip'
            with ZipFile(p,'w') as z: z.writestr('note.txt', 'vide')
            with self.assertRaisesRegex(ValueError, 'Aucun fichier CSV'): lire_csv(p)
            with ZipFile(p,'w') as z: z.writestr('faux.csv', '1,2,3,4')
            with self.assertRaisesRegex(ValueError, 'faux.csv'): lire_csv(p)

    def test_export_et_reimport(self):
        s = lire_csv('test.csv', CONTENU)[0]
        with tempfile.TemporaryDirectory() as dossier:
            p = Path(dossier)/'export.csv'
            exporter_scan(s,p)
            relu = lire_csv(p)[0]
            self.assertFalse(relu.intensite_disponible)
            self.assertEqual(relu.pose, s.pose)
            np.testing.assert_allclose(relu.points(), s.points())



if __name__ == '__main__': unittest.main()
