"""Exécuter : python -m unittest discover -s tests -v"""
import tempfile
import unittest
from pathlib import Path
import numpy as np
from cartographie import (EPS, Scan, Grille, lire_csv, exporter_scan, demonstration,
    intersection, decouper, proches, fusionner, angle_segments, extraire_segments,
    carte_vectorielle, cellules_ligne)
from acquisition import AssembleurCSV


def seg(a,b):
    return np.array([a,b],float)


class Geometrie(unittest.TestCase):
    def setUp(self):
        self.a=seg([0,0],[4,0])

    def test_intersection_interieure(self):
        b=seg([1,-1],[1,1])
        np.testing.assert_allclose(intersection(self.a,b),[1,0])
        np.testing.assert_allclose(decouper(self.a,b),[[1,0],[4,0]])

    def test_egalite_garde_premier_point(self):
        np.testing.assert_allclose(decouper(self.a,seg([2,-1],[2,1])),[[0,0],[2,0]])

    def test_egalite_a_tolerance_pres(self):
        x=2-EPS/4
        np.testing.assert_allclose(decouper(self.a,seg([x,-1],[x,1])),[[0,0],[x,0]])

    def test_hors_tolerance_garde_plus_long(self):
        x=2-2*EPS
        np.testing.assert_allclose(decouper(self.a,seg([x,-1],[x,1])),[[x,0],[4,0]])

    def test_extremites_inchangees(self):
        for x in [0,4,EPS/2,4-EPS/2]:
            np.testing.assert_allclose(decouper(self.a,seg([x,-1],[x,1])),self.a)

    def test_colineaire_inchange(self):
        b=seg([1,0],[3,0])
        self.assertIsNone(intersection(self.a,b))
        np.testing.assert_allclose(decouper(self.a,b),self.a)

    def test_parallele_inchange(self):
        b=seg([0,1],[4,1])
        self.assertIsNone(intersection(self.a,b))
        np.testing.assert_allclose(decouper(self.a,b),self.a)

    def test_intersection_hors_second_segment(self):
        b=seg([2,1],[2,2])
        self.assertIsNone(intersection(self.a,b))
        np.testing.assert_allclose(decouper(self.a,b),self.a)

    def test_intersection_hors_premier_segment(self):
        np.testing.assert_allclose(decouper(self.a,seg([5,-1],[5,1])),self.a)

    def test_extremite_second_segment_peut_couper(self):
        np.testing.assert_allclose(decouper(self.a,seg([1,0],[1,1])),[[1,0],[4,0]])

    def test_degenere(self):
        np.testing.assert_allclose(decouper(self.a,seg([1,0],[1,0])),self.a)
        with self.assertRaises(ValueError):
            angle_segments(self.a,seg([1,0],[1,0]))

    def test_proximite_et_fusion(self):
        b=seg([4.05,0],[6,0])
        self.assertTrue(proches(self.a,b))
        self.assertFalse(proches(self.a,seg([4.5,0],[6,0])))
        self.assertFalse(proches(self.a,seg([2,-1],[2,1])))
        self.assertAlmostEqual(angle_segments(self.a,self.a[::-1]),0)
        c=fusionner(self.a,b)
        self.assertAlmostEqual(np.linalg.norm(c[1]-c[0]),6)


class Donnees(unittest.TestCase):
    def test_nouveau_zero_ancien_180(self):
        s=Scan("reference",np.array([[180,1,200],[90,1,200],[0,1,200]]),angle_reference=180.)
        np.testing.assert_allclose(s.points(),[[1,0],[0,-1],[-1,0]],atol=1e-10)
        np.testing.assert_allclose(s.mesures[:,0],[180,90,0])

    def test_pose_et_reference_separees(self):
        s=Scan("reference",np.array([[180,1,200]]),[2,3,90],angle_reference=180.)
        np.testing.assert_allclose(s.points(),[[2,4]],atol=1e-10)

    def test_pose(self):
        s=Scan('test',np.array([[0,1,200],[90,1,200]]),[2,3,90])
        np.testing.assert_allclose(s.points(),[[2,4],[1,3]],atol=1e-10)

    def test_csv_scans_et_unites(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'scan.csv'
            p.write_text('N,Angle(°),Distance(mm),Intensity,x(mm),y(mm)\n0,0,1000,200,1000,0\n1,90,500,200,0,-500\n\n0,180,2000,220,-2000,0\n',encoding='utf-8')
            scans=lire_csv(p)
            self.assertEqual(scans[0].angle_reference,180.)
            self.assertEqual(len(scans),2)
            self.assertEqual(scans[0].mesures[0,1],1)
            exporter_scan(scans[0],p)
            np.testing.assert_allclose(lire_csv(p)[0].mesures,scans[0].mesures)

    def test_csv_rejet_explicite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'scan.csv'
            p.write_text('>lidar:10:20;|xy\n')
            with self.assertRaises(ValueError):
                lire_csv(p)

    def test_assembleur_ignore_debut_partiel_et_trous(self):
        a=AssembleurCSV()
        self.assertIsNone(a.ajouter('12,90,500,200,0,-500'))
        for i in range(30):
            self.assertIsNone(a.ajouter(f'{i},{359-i*12},1000,200,0,0'))
        m=a.ajouter('')
        self.assertEqual(m.shape,(30,3))
        self.assertEqual(m[0,1],1)
        a.ajouter('0,359,1000,200,0,0')
        a.ajouter('2,357,1000,200,0,0')
        self.assertIsNone(a.ajouter(''))
        self.assertEqual(a.rejets,1)

    def test_grille_libre_impact_inconnu(self):
        s=Scan('rayon',np.array([[0,1,200.]]))
        g=Grille.creer([s],.1)
        g.mettre_a_jour(s)
        debut=np.floor((np.array([0,0])-g.origine)/.1).astype(int)
        fin=np.floor((np.array([1,0])-g.origine)/.1).astype(int)
        self.assertLess(g.probabilites()[debut[1],debut[0]],.5)
        self.assertGreater(g.probabilites()[fin[1],fin[0]],.5)
        self.assertFalse(g.observe[0,0])
        premiere=g.log_odds.copy()
        g.mettre_a_jour(s)
        np.testing.assert_allclose(g.log_odds,2*premiere)

    def test_rayon_invalide_ignore(self):
        s=Scan('invalide',np.array([[0,0,200],[90,12,200.]]))
        g=Grille.creer([s],.1)
        g.mettre_a_jour(s)
        self.assertFalse(g.observe.any())

    def test_bresenham(self):
        for fin in [(3,2),(-3,2),(0,-3),(0,0),(2,-3)]:
            p=list(cellules_ligne(0,0,*fin))
            self.assertEqual(p[0],(0,0))
            self.assertEqual(p[-1],fin)
            self.assertEqual(len(p),max(abs(v) for v in fin)+1)

    def test_demo_segments_cartes(self):
        scans=demonstration()
        self.assertEqual(len(scans),2)
        self.assertTrue(len(extraire_segments(scans[0]))>=4)
        vect=carte_vectorielle(scans)
        self.assertGreaterEqual(len(vect),4)
        self.assertTrue(all(np.isfinite(s).all() for s in vect))
        g=Grille.creer(scans)
        for s in scans:
            g.mettre_a_jour(s)
        self.assertGreater(g.observe.sum(),500)


if __name__=='__main__':
    unittest.main()
