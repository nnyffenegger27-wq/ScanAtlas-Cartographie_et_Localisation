"""Parcours dans un vrai navigateur (ignoré si Playwright n'est pas installé) : pas d'erreur JS,
la carte se dessine, le clavier pilote, Espace arrête."""
import json
import threading
import unittest
import serveur
try:
    from playwright.sync_api import sync_playwright
except ImportError:      # pragma: no cover
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, 'Playwright absent')
class Navigateur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = serveur.Application()
        cls.srv = serveur.ServeurLocal(('127.0.0.1', 0), serveur.fabriquer_gestionnaire(cls.app))
        cls.url = f'http://127.0.0.1:{cls.srv.server_address[1]}/'
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        try:
            cls.nav = cls.pw.chromium.launch()
        except Exception as exc:
            cls.pw.stop(); cls.srv.shutdown(); cls.srv.server_close(); cls.app.fermer()
            raise unittest.SkipTest('Chromium indisponible : %s' % exc)

    @classmethod
    def tearDownClass(cls):
        cls.nav.close(); cls.pw.stop(); cls.srv.shutdown(); cls.srv.server_close(); cls.app.fermer()

    def page(self):
        page = self.nav.new_page(viewport=dict(width=1280, height=800))
        self.erreurs = []
        page.on('pageerror', lambda e: self.erreurs.append(str(e)))
        page.on('console', lambda m: m.type == 'error' and self.erreurs.append(m.text))
        return page

    def test_carte_exemple_dessinee_sans_erreur(self):
        self.app.doc.vider()
        page = self.page()
        page.goto(self.url+'#carte')
        page.click('#vide-exemple')
        page.wait_for_selector('#liste-scans li')
        self.assertEqual(page.locator('#liste-scans li').count(), 2)
        page.wait_for_timeout(500)
        sombres = page.evaluate("""() => { const c = document.getElementById('toile-carte'); const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            let n = 0; for (let i = 0; i < d.length; i += 4*37) if (d[i+3] && (d[i] < 120)) n++; return n; }""")
        self.assertGreater(sombres, 50)                      # des points sont dessinés
        self.assertEqual(self.erreurs, [])

    def test_clavier_pilote_et_espace_arrete(self):
        page = self.page()
        envois = []
        page.on('request', lambda r: r.url.endswith('/api/pilote') and envois.append(json.loads(r.post_data or '{}')))
        page.goto(self.url+'#direct')
        page.wait_for_timeout(500)
        page.keyboard.down('z'); page.wait_for_timeout(400)
        self.assertTrue(any(e.get('surge', 0) > 0 for e in envois), envois[-3:])
        page.keyboard.up('z')
        page.wait_for_timeout(400)
        self.assertEqual(envois[-1].get('surge', 1), 0)      # relâcher = arrêt
        self.assertEqual(self.erreurs, [])

    def test_connexion_demo_depuis_l_interface(self):
        page = self.page()
        page.goto(self.url+'#direct')
        page.click('#puce-connexion'); page.click('#bouton-demo')
        page.wait_for_function("document.getElementById('puce-texte').textContent.includes('Connecté') || document.getElementById('etat-suivi-texte').textContent.includes('suivie')", timeout=15000)
        page.click('#puce-connexion'); page.click('#bouton-connexion')   # « Déconnecter » quitte la démo
        page.wait_for_function("document.getElementById('puce-texte').textContent.includes('Hors')", timeout=8000)
        self.assertIsNone(self.app.session.demo)
        self.assertEqual(self.erreurs, [])

    def test_couches_replacer_et_exploration_depuis_l_interface(self):
        page = self.page()
        requetes = []
        page.on('request', lambda r: requetes.append((r.method, r.url.split('?')[0].split('/api')[-1], r.post_data)))
        page.goto(self.url+'#direct')
        page.click('#accueil-demo')
        page.wait_for_function("document.getElementById('etat-suivi-texte').textContent.includes('suivie')", timeout=20000)
        page.click('#seg-couches-direct button[data-couche=grille]')
        page.wait_for_function("() => true")
        page.wait_for_timeout(1800)
        self.assertTrue(any(m == 'GET' and u == '/direct/grille' for m, u, _ in requetes))   # la grille n'est demandée que visible
        # replacer : un clic-glisser sur la carte envoie point + cap
        page.click('#bouton-replacer')
        boite = page.locator('#toile-direct').bounding_box()
        x, y = boite['x']+boite['width']/2, boite['y']+boite['height']/2
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x+80, y, steps=4); page.mouse.up()
        page.wait_for_timeout(500)
        envoi = [json.loads(d) for m, u, d in requetes if u == '/replacer']
        self.assertEqual(len(envoi), 1)
        self.assertAlmostEqual(envoi[0]['cap'], 0., delta=1.)                 # glissé vers la droite = cap 0°
        # exploration : le bouton bascule et la commande part
        page.wait_for_function("document.getElementById('etat-suivi-texte').textContent.includes('suivie')", timeout=15000)
        page.click('#bouton-auto')
        page.wait_for_function("document.getElementById('bouton-auto').textContent.includes('Arrêter')", timeout=5000)
        self.assertTrue(self.app.session.explorateur.actif)
        page.click('#bouton-auto')
        page.wait_for_function("document.getElementById('bouton-auto').textContent.includes('Explorer')", timeout=5000)
        self.assertFalse(self.app.session.explorateur.actif)
        page.click('#puce-connexion'); page.click('#bouton-demo')
        page.wait_for_function("document.getElementById('puce-texte').textContent.includes('Hors')", timeout=8000)
        self.assertEqual(self.erreurs, [])


if __name__ == '__main__':
    unittest.main()
