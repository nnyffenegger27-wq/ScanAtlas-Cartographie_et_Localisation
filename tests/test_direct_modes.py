import copy
import ctypes
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from cartographie_direct import CarteDirecte
from journal_direct import JournalDirect, sauver_carte
from manette import commande_axes, State
from test_wifi import trame_pose
from localisation import erreur_pose


class ModesDirects(unittest.TestCase):
    def test_pause_fixe_toutes_les_references_mais_actualise_pose(self):
        c=CarteDirecte();a=c.traiter(trame_pose([0,0,0],1))
        points=c.points.copy();g=c.grille.log_odds.copy();segments=np.array(c.segments);cles=len(c.cles)
        for i in range(2,8):
            e=c.traiter(trame_pose([i*.02,0,i],i),enrichir=False)
            self.assertTrue(e.accepte,e.message)
            self.assertFalse(e.enrichissement)
        self.assertGreater(c.pose[0],.1)
        np.testing.assert_array_equal(points,c.points)
        np.testing.assert_array_equal(g,c.grille.log_odds)
        np.testing.assert_array_equal(segments,c.segments)
        self.assertEqual(cles,len(c.cles))
        e=c.traiter(trame_pose([.2,0,9],9),enrichir=True)
        self.assertTrue(e.accepte,e.message);self.assertGreater(len(c.cles),cles)

    def test_reference_copiee_et_vecteurs_preserves(self):
        scan=trame_pose([0,0,0],1).scan();scan.pose=[2,3,20]
        segments=[np.array([[1,1],[3,1.]])]
        avant=scan.mesures.copy()
        c=CarteDirecte(scans=[scan],segments=segments)
        self.assertTrue(c.localisation_globale_requise)
        np.testing.assert_array_equal(c.segments,segments)
        c.cles[0].pose[0]=99;c.cles[0].mesures[0,1]=99
        np.testing.assert_array_equal(scan.mesures,avant)
        self.assertEqual(scan.pose,[2,3,20])

    def test_global_depuis_position_inconnue_et_reprise_en_localisation_seule(self):
        reference=trame_pose([0,0,0],1).scan()
        c=CarteDirecte(scans=[reference]);avant=c.points.copy()
        e=c.traiter(trame_pose([.7,-.3,145],2),enrichir=False)
        self.assertTrue(e.accepte,e.message)
        ep,ea=erreur_pose(e.scan.pose,[.7,-.3,145]);self.assertLess(ep,.05);self.assertLess(ea,1)
        np.testing.assert_array_equal(c.points,avant)
        self.assertEqual(len(c.cles),1)
        c.relocaliser();self.assertTrue(c.localisation_globale_requise)

    def test_journal_brut_et_session_secours_sans_token(self):
        with tempfile.TemporaryDirectory() as d:
            j=JournalDirect(d);c=CarteDirecte();t=trame_pose([0,0,0],1)
            j.brut(t);e=c.traiter(t);j.resultat(t,e,c.filtres);j.fermer()
            lignes=[json.loads(l) for l in (j.dossier/'tours.jsonl').read_text().splitlines()]
            self.assertEqual(lignes[0]['mesures'],t.mesures.tolist())
            self.assertTrue(lignes[1]['accepte'])
            data=json.loads((j.dossier/'session_secours.json').read_text())
            self.assertEqual(data['version'],2);self.assertEqual(len(data['scans']),1)
            self.assertFalse((j.dossier/'session_secours.json.tmp').exists())

    def test_manette_zone_morte_lb_et_arret_b(self):
        self.assertEqual(ctypes.sizeof(State),16)
        self.assertEqual(commande_axes(0,1,0,0),('STOP',0))
        self.assertEqual(commande_axes(0,.1,0,0x100),('STOP',0))
        self.assertEqual(commande_axes(0,1,0,0x100),('FORWARD',1))
        self.assertEqual(commande_axes(-.7,0,0,0x100),('STRAFE_L',.7))
        self.assertEqual(commande_axes(0,0,1,0x2100),('STOP',0))

class AnnulationPose(unittest.TestCase):
    def test_annuler_pose_restaure_pose_et_metadonnees(self):
        from types import SimpleNamespace
        from app import Atelier
        scan=trame_pose([0,0,0],1).scan()
        scan.suivi_recalage={'valide':True}
        a=SimpleNamespace(scans=[scan],scans_grille=set(),annulations_pose=[],
            annuler_geste=lambda:None,invalider=lambda **kw:None,actualiser=lambda i:None,
            statut=SimpleNamespace(set=lambda texte:None))
        Atelier.memoriser_pose(a,scan)
        scan.pose=[1,2,30];scan.suivi_recalage=None
        Atelier.annuler_pose(a)
        self.assertEqual(scan.pose,[0,0,0]);self.assertEqual(scan.suivi_recalage,{'valide':True})
