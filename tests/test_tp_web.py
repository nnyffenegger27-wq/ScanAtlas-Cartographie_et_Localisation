"""Les TP du Jour 2 dans la version web : localisation d'un scan sur grille / plan / scan, banc d'évaluation, exports CSV."""
import csv
import io
import threading
import time
import unittest
import serveur
from document_carte import DocumentCarte


class LocalisationTP(unittest.TestCase):
    def test_trois_references_deux_strategies_sur_la_demo(self):
        doc = DocumentCarte()
        doc.demonstration()
        avant = [list(s['pose']) for s in doc.liste()['scans']]
        for reference in ('grille', 'plan', 'scan'):
            for methode in ('locale', 'multi'):
                r = doc.localiser_tp(1, reference, methode, 0 if reference == 'scan' else None)
                self.assertEqual(r['id'], 1)
                self.assertIn('pose', r)
                self.assertEqual(len(r['pose']), 3)
                self.assertGreater(r['duree'], 0)
        self.assertEqual([list(s['pose']) for s in doc.liste()['scans']], avant)       # ne modifie jamais la carte

    def test_refus_propres(self):
        doc = DocumentCarte()
        doc.demonstration()
        with self.assertRaises(ValueError):
            doc.localiser_tp(1, 'inconnue', 'locale')
        with self.assertRaises(ValueError):
            doc.localiser_tp(1, 'grille', 'magique')
        with self.assertRaises(ValueError):
            doc.localiser_tp(1, 'scan', 'locale', 1)            # un scan ne se localise pas sur lui-même
        doc.regler(0, inclus=False)
        with self.assertRaises(ValueError):
            doc.localiser_tp(1, 'grille', 'locale')             # plus d'autre scan : pas de référence


class EvaluationTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = serveur.Application()
        cls.srv = serveur.ServeurLocal(('127.0.0.1', 0), serveur.fabriquer_gestionnaire(cls.app))
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); cls.app.fermer()

    def req(self, methode, chemin, corps=None):
        import http.client, json
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        c.request(methode, chemin, json.dumps(corps) if corps is not None else None,
                  {'Content-Type': 'application/json', 'X-Jeton': getattr(self.app, 'jeton', '')})
        r = c.getresponse(); donnees = r.read(); c.close()
        return r.status, donnees

    def test_csv_absents_avant_calcul_puis_complets(self):
        self.app.doc.evaluation_tp = None
        for nom in ('essais', 'synthese'):
            self.assertEqual(self.req('GET', f'/api/carte/evaluation_{nom}.csv')[0], 404)
        resultat = self.app.doc.evaluer_tp()
        self.assertEqual(len(resultat['synthese']), 6)                   # 3 références × 2 stratégies
        self.assertEqual(resultat['essais'], 42)                         # × 7 départs
        s, essais = self.req('GET', '/api/carte/evaluation_essais.csv')
        self.assertEqual(s, 200)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(essais.decode('utf-8-sig'))))), 42)
        s, synthese = self.req('GET', '/api/carte/evaluation_synthese.csv')
        lignes = list(csv.DictReader(io.StringIO(synthese.decode('utf-8-sig'))))
        self.assertEqual(len(lignes), 6)
        self.assertEqual(len({l['reference'] for l in lignes}), 3)       # trois références distinctes


if __name__ == '__main__':
    unittest.main()
