"""Serveur local : sécurité (hôte, jeton), API de la carte, import, tâches, flux d'événements."""
import http.client
import json
import threading
import time
import unittest
import serveur
from test_session_directe import attendre


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = serveur.Application()
        cls.srv = serveur.ServeurLocal(('127.0.0.1', 0), serveur.fabriquer_gestionnaire(cls.app))
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); cls.app.fermer()

    def setUp(self):
        self.app.taches.interrompre()
        t = self.app.taches.courante
        if t is not None:
            t.join(30)
        self.app.doc.vider()

    def req(self, methode, chemin, corps=None, jeton=True, hote=None, octets=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port)
        h = {}
        if jeton:
            h['X-Jeton'] = self.app.jeton
        if hote:
            h['Host'] = hote
        if corps is not None:
            octets = json.dumps(corps).encode(); h['Content-Type'] = 'application/json'
        c.request(methode, chemin, octets, h)
        r = c.getresponse(); donnees = r.read(); c.close()
        try:
            return r.status, json.loads(donnees)
        except ValueError:
            return r.status, donnees


class Securite(Base):
    def test_la_page_porte_le_jeton_et_les_ordres_l_exigent(self):
        s, page = self.req('GET', '/', jeton=False)
        self.assertEqual(s, 200)
        self.assertIn(self.app.jeton.encode(), page)
        self.assertNotIn(b'{{JETON}}', page)
        self.assertEqual(self.req('POST', '/api/arret', {}, jeton=False)[0], 403)
        self.assertEqual(self.req('GET', '/api/carte', jeton=False)[0], 403)
        self.assertEqual(self.req('POST', '/api/arret', {})[0], 200)

    def test_hote_etranger_refuse(self):
        self.assertEqual(self.req('GET', '/', hote='evil.example')[0], 403)
        self.assertEqual(self.req('POST', '/api/arret', {}, hote='evil.example:80')[0], 403)

    def test_pas_d_evasion_hors_du_dossier_web(self):
        for chemin in ('/static/../serveur.py', '/static/%2e%2e/serveur.py', '/static/..%2fserveur.py'):
            self.assertIn(self.req('GET', chemin, jeton=False)[0], (403, 404), chemin)

    def test_requetes_invalides(self):
        self.assertEqual(self.req('POST', '/api/inconnu', {})[0], 400)
        self.assertEqual(self.req('POST', '/api/pilote', {'surge': 'abc'})[0], 400)
        self.assertEqual(self.req('POST', '/api/pilote', {'surge': float('nan')})[0], 400)
        self.assertEqual(self.req('POST', '/api/reglages', {'inconnu': 1})[0], 400)
        self.assertEqual(self.req('POST', '/api/connexion', {'liaison': 'bluetooth'})[0], 400)
        self.assertEqual(self.req('POST', '/api/carte/scan', {'id': 99, 'visible': False})[0], 400)


class Carte(Base):
    def test_exemple_puis_representations(self):
        self.assertEqual(self.req('POST', '/api/carte/demo', {})[0], 200)
        s, carte = self.req('GET', '/api/carte')
        self.assertEqual(len(carte['scans']), 2)
        for chemin in ('/api/carte/nuage', '/api/carte/grille', '/api/carte/plan'):
            self.assertEqual(self.req('GET', chemin)[0], 200, chemin)
        s, csv = self.req('GET', '/api/carte/scan/0.csv')
        self.assertEqual(s, 200); self.assertIn(b',', csv)
        s, session = self.req('GET', '/api/carte/session')
        self.assertEqual(s, 200); self.assertTrue(session)

    def test_visibilite_pose_et_suppression(self):
        self.req('POST', '/api/carte/demo', {})
        v0 = self.req('GET', '/api/carte')[1]['version']
        self.assertEqual(self.req('POST', '/api/carte/scan', {'id': 0, 'visible': False})[0], 200)
        self.assertEqual(self.req('POST', '/api/carte/scan', {'id': 1, 'pose': [10, 20, 30]})[0], 200)
        carte = self.req('GET', '/api/carte')[1]
        self.assertGreater(carte['version'], v0)
        self.assertFalse(carte['scans'][0]['visible'])
        self.assertEqual(self.req('POST', '/api/carte/supprimer', {'id': 0})[0], 200)
        self.assertEqual(len(self.req('GET', '/api/carte')[1]['scans']), 1)

    def test_import_csv_et_refus_d_un_fichier_invalide(self):
        self.req('POST', '/api/carte/demo', {})
        csv = self.req('GET', '/api/carte/scan/0.csv')[1]
        self.req('POST', '/api/carte/vider', {})
        s, r = self.req('POST', '/api/carte/importer?nom=essai.csv', octets=csv)
        self.assertEqual(s, 200, r)
        self.assertEqual(len(self.req('GET', '/api/carte')[1]['scans']), 1)
        s, r = self.req('POST', '/api/carte/importer?nom=vide.csv', octets=b'n\xc3\xa9ant')
        self.assertEqual(s, 400)

    def test_recalage_est_une_tache_annulable_qui_publie_son_resultat(self):
        self.req('POST', '/api/carte/demo', {})
        abonne = self.app.diffuseur.abonner()
        try:
            self.assertEqual(self.req('POST', '/api/carte/recaler', {'id': 1})[0], 200)
            vus = []
            fin = time.monotonic()+20
            while time.monotonic() < fin:
                try:
                    genre, donnees = abonne.get(timeout=.5)
                except Exception:
                    continue
                if genre == 'tache':
                    vus.append(donnees)
                    if donnees['etat'] != 'en_cours':
                        break
            self.assertTrue(vus and vus[-1]['etat'] == 'fini', vus[-3:])
            self.assertIn('pose', json.dumps(vus[-1]['resultat']).lower())
        finally:
            self.app.diffuseur.desabonner(abonne)

    def test_un_seul_calcul_a_la_fois(self):
        self.req('POST', '/api/carte/demo', {})
        gele = threading.Event()
        self.app.taches.lancer('Test', lambda annuler, progression: gele.wait(10))
        try:
            s, r = self.req('POST', '/api/carte/assembler', {})
            self.assertEqual(s, 400); self.assertIn('déjà en cours', r['erreur'])
        finally:
            gele.set()
            self.app.taches.courante.join(5)


class Verrou(Base):
    def test_carte_non_modifiable_pendant_la_connexion(self):
        self.req('POST', '/api/carte/demo', {})
        self.app.session.robot = object()            # robot « connecté » (aucun appel réel n'est fait)
        try:
            for chemin, corps in (('/api/carte/supprimer', {'id': 0}), ('/api/carte/vider', {}),
                                  ('/api/carte/scan', {'id': 0, 'inclus': False}), ('/api/carte/assembler', {})):
                self.assertEqual(self.req('POST', chemin, corps)[0], 409, chemin)
            self.assertEqual(self.req('POST', '/api/carte/scan', {'id': 0, 'visible': False})[0], 200)  # l'affichage reste libre
        finally:
            self.app.session.robot = None


class Direct(Base):
    def test_ordres_refuses_sans_robot(self):
        s, r = self.req('POST', '/api/auto', {'actif': True})
        self.assertEqual(s, 400); self.assertIn('Connecte', r['erreur'])
        s, r = self.req('POST', '/api/replacer', {'x': 0, 'y': 0, 'cap': 0})
        self.assertEqual(s, 400)
        self.assertEqual(self.req('POST', '/api/replacer', {'x': 'a', 'y': 0, 'cap': 0})[0], 400)
        self.assertEqual(self.req('POST', '/api/replacer', {'x': 0})[0], 400)
        self.assertEqual(self.req('POST', '/api/auto', {'actif': False})[0], 200)     # arrêter hors exploration : sans effet

    def test_grille_du_direct_vide_puis_compressee(self):
        self.assertEqual(self.req('GET', '/api/direct/grille')[1], {'vide': True})
        # un scan suivi donne une grille ; on l'injecte sans robot en construisant la carte directe à la main
        from simulation import SalleVirtuelle, SALLE_DEMO
        from cartographie_direct import CarteDirecte
        salle, carte = SalleVirtuelle(SALLE_DEMO, pose=(0, 0, 0)), CarteDirecte()
        for _ in range(3):
            salle.avancer((30, 0, 0), .1)
            etat = carte.traiter(salle.trame())
        self.app.session.dernier_etat = etat
        try:
            c = http.client.HTTPConnection('127.0.0.1', self.port)
            c.request('GET', '/api/direct/grille', headers={'X-Jeton': self.app.jeton, 'Accept-Encoding': 'gzip'})
            r = c.getresponse(); brut = r.read()
            self.assertEqual(r.getheader('Content-Encoding'), 'gzip')
            import gzip
            g = json.loads(gzip.decompress(brut))
            self.assertFalse(g['vide']); self.assertGreater(g['largeur'], 10); self.assertGreater(g['cles'], 0)
            import base64
            self.assertEqual(len(base64.b64decode(g['donnees'])), g['largeur']*g['hauteur'])
            self.assertLess(len(brut), len(g['donnees']))             # la compression sert
        finally:
            self.app.session.dernier_etat = None


class Flux(Base):
    def test_le_flux_envoie_l_etat_a_la_connexion(self):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        c.request('GET', '/api/flux?jeton='+self.app.jeton)
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        self.assertIn('text/event-stream', r.getheader('Content-Type'))
        genres = set()
        fin = time.monotonic()+5
        while time.monotonic() < fin and 'etat' not in genres:
            ligne = r.fp.readline()
            if ligne.startswith(b'event:'):
                genres.add(ligne.split()[1].decode())
        c.close()
        self.assertIn('etat', genres)

    def test_flux_sans_jeton_refuse(self):
        self.assertEqual(self.req('GET', '/api/flux', jeton=False)[0], 403)


if __name__ == '__main__':
    unittest.main()
