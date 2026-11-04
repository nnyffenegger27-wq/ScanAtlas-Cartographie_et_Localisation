import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from atlas.calcul.cartographie import (Scan, demonstration, extraire_multiscans, extraire_segments,
                         proches, carte_vectorielle, nettoyer_segments)


def scan_points(points):
    points = np.asarray(points, float)
    return Scan('rayons', np.column_stack([
        np.rad2deg(np.arctan2(points[:,1],points[:,0])) % 360.,
        np.linalg.norm(points,axis=1), np.full(len(points),200.)]))


class SegmentsTousScans(unittest.TestCase):
    def test_extraction_par_scan_et_pose_sans_pont(self):
        scans=demonstration()
        scans[1].pose=[15.,0.,15.]
        attendus=[extraire_segments(s) for s in scans]
        segments,origines=extraire_multiscans(scans)
        self.assertEqual(len(segments),sum(map(len,attendus)))
        self.assertEqual(origines,[0]*len(attendus[0])+[1]*len(attendus[1]))

    def test_deux_tours_conserves_mais_non_relies(self):
        s=demonstration()[0]
        double=Scan('deux tours',np.tile(s.mesures,(2,1)),s.pose)
        self.assertEqual(len(extraire_segments(double)),2*len(extraire_segments(s)))


class Fusions(unittest.TestCase):
    def test_intersection_et_angle_ne_suffisent_pas(self):
        a=np.array([[0.,0.],[10.,0.]])
        b=np.array([[0.,-.5],[10.,.5]])
        self.assertFalse(proches(a,b,angle_max=8,distance_max=.12))

    def carte_factice(self, hauteurs, erreur=.05):
        scans=[Scan(str(i),np.empty((0,3))) for i in hauteurs]
        supports=[]
        for h in hauteurs:
            points=np.column_stack([np.linspace(1,3,20),np.full(20,h)])
            supports.append([(np.array([points[0],points[-1]]),points)])
        with patch('atlas.calcul.cartographie.extraire_segments',side_effect=supports):
            return carte_vectorielle(scans,angle_max=10,distance_max=1.,erreur=erreur)

    def test_meme_mur_fusionne(self):
        self.assertEqual(len(self.carte_factice([0.,.02])),1)

    def test_murs_paralleles_distincts_meme_avec_distance_un_metre(self):
        self.assertEqual(len(self.carte_factice([0.,.4])),2)

    def test_fusion_en_chaine_ne_derive_pas(self):
        self.assertEqual(len(self.carte_factice([0.,.06,.12],erreur=.04)),2)


class NettoyagePrudent(unittest.TestCase):
    def setUp(self):
        self.mur=np.array([[2.,-2.],[2.,2.]])

    def test_trois_rayons_raccourcissent_garde_cote_premier_point(self):
        scan=scan_points([[5,-1],[5,0],[5,1]])
        carte,coupes=nettoyer_segments([self.mur],scan,marge=.1)
        self.assertEqual(coupes,1)
        np.testing.assert_allclose(carte[0],[[2,-2],[2,0]],atol=1e-10)

    def test_un_rayon_repete_trois_fois_ne_coupe_pas(self):
        scan=scan_points([[5,0],[5,0],[5,0]])
        carte,coupes=nettoyer_segments([self.mur],scan,marge=.1)
        self.assertEqual(coupes,0)
        np.testing.assert_array_equal(carte[0],self.mur)

    def test_impact_proche_du_mur_ne_coupe_pas(self):
        scan=scan_points([[2.02,-.3],[2.02,0],[2.02,.3]])
        carte,coupes=nettoyer_segments([self.mur],scan,marge=.1)
        self.assertEqual(coupes,0)
        np.testing.assert_array_equal(carte[0],self.mur)

    def test_obstacle_avant_le_mur_ne_prouve_pas_son_absence(self):
        scan=scan_points([[1,-.2],[1,0],[1,.2]])
        carte,coupes=nettoyer_segments([self.mur],scan,marge=.1)
        self.assertEqual(coupes,0)

