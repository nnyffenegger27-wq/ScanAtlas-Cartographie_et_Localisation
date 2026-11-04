"""Parcours dans un vrai navigateur (ignoré si Playwright n'est pas installé) : pas d'erreur JS,
la carte se dessine, le clavier pilote, Espace arrête."""
import json
import threading
import unittest
from atlas.application import serveur
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

    def test_un_scan_importe_est_cadre_et_dessine(self):
        """Régression : après un import, la vue restait là où elle était (scan hors écran) quand l'événement du document
        arrivait avant la fin de l'import."""
        self.app.doc.vider()
        page = self.page()
        page.goto(self.url+'#carte')
        page.click('#vide-exemple')
        page.wait_for_selector('#liste-scans li')
        page.wait_for_timeout(500)
        session = json.loads(self.app.doc.session_json())
        for sc in session['scans']:
            sc['pose'] = [sc['pose'][0]+35., sc['pose'][1]-22., sc['pose'][2]]       # très loin de la vue actuelle
        def retarder(route):                                   # la réponse de l'import arrive après l'événement « document » (SSE)
            rep = route.fetch(); page.wait_for_timeout(900); route.fulfill(response=rep)
        page.route('**/api/carte/importer*', retarder)
        for i in range(3):
            page.set_input_files('#fichier', dict(name='loin.json', mimeType='application/json', buffer=json.dumps(session).encode()))
            page.wait_for_function("document.getElementById('carte-nom').textContent.includes('loin')", timeout=5000)
            page.wait_for_timeout(2500)
            sombres = page.evaluate("""() => { const c = document.getElementById('toile-carte'); const d = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
                let n = 0; for (let i = 0; i < d.length; i += 4*37) if (d[i+3] && (d[i] < 120)) n++; return n; }""")
            self.assertGreater(sombres, 50, 'import n°%d : la carte importée n\'est pas visible' % (i+1))
            for sc in session['scans']:
                sc['pose'] = [sc['pose'][0]-60., sc['pose'][1]+40., sc['pose'][2]]   # et encore ailleurs au tour suivant
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

    def test_choix_de_la_salle_simulee(self):
        page = self.page()
        page.goto(self.url+'#direct')
        page.wait_for_function("document.querySelectorAll('#accueil .choix-salle option').length >= 3", timeout=5000)
        page.select_option('#accueil .choix-salle', 'deux_pieces')
        page.click('#accueil-demo')
        page.wait_for_function("document.getElementById('etat-suivi-texte').textContent.includes('suivie')", timeout=20000)
        self.assertEqual(self.app.session.demo['salle'], 'deux_pieces')
        page.click('#puce-connexion')
        self.assertEqual(page.locator('#popover-connexion .choix-salle').input_value(), 'deux_pieces')     # les deux listes restent synchronisées
        page.click('#bouton-demo')
        page.wait_for_function("document.getElementById('puce-texte').textContent.includes('Hors')", timeout=8000)
        self.assertEqual(self.erreurs, [])

    def test_recalage_tp_et_evaluation_depuis_l_interface(self):
        self.app.doc.vider()
        page = self.page()
        requetes = []
        page.on('request', lambda r: r.method == 'POST' and requetes.append((r.url.split('/api')[-1], json.loads(r.post_data or '{}'))))
        page.goto(self.url+'#carte')
        page.click('#vide-exemple')
        page.wait_for_selector('#liste-scans li')
        page.click('#liste-scans li:nth-child(2)')
        page.wait_for_selector('#insp-methode', state='visible')
        self.assertTrue(page.locator('#champ-ref-scan').is_hidden())
        page.select_option('#insp-methode', 'scan:multi')
        self.assertTrue(page.locator('#champ-ref-scan').is_visible())
        self.assertEqual(page.locator('#insp-ref option').count(), 1)          # le seul autre scan inclus
        page.click('#insp-recaler')
        page.wait_for_function("document.getElementById('insp-resultat-texte').textContent.includes('Multi-résolution')", timeout=30000)
        envoi = [c for u, c in requetes if u == '/carte/localiser']
        self.assertEqual(len(envoi), 1)
        self.assertEqual((envoi[0]['reference'], envoi[0]['methode']), ('scan', 'multi'))
        # banc d'évaluation : fenêtre, tableau de 6 lignes, deux exports
        page.click('#c-evaluer')
        self.assertTrue(page.locator('#dialogue-tp').is_visible())
        page.click('#tp-lancer')
        page.wait_for_function("document.querySelectorAll('#tp-table tbody tr').length === 6", timeout=120000)
        self.assertTrue(page.locator('#tp-synthese').is_visible())
        self.assertEqual(self.erreurs, [])

    def test_connecter_de_l_accueil_se_connecte_et_le_menu_reste_ouvrable(self):
        page = self.page()
        envois = []
        page.route('**/api/connexion', lambda route: (envois.append(json.loads(route.request.post_data or '{}')), route.fulfill(status=200, content_type='application/json', body='{"ok":true}')))
        page.goto(self.url+'#direct')
        page.wait_for_selector('#accueil-connecter', state='visible')
        page.click('#accueil-liaison')                                   # ouvre le menu et ne le referme pas aussitôt
        self.assertTrue(page.locator('#popover-connexion').is_visible())
        page.click('#accueil-connecter')                                 # envoie la connexion avec l'adresse du menu
        page.wait_for_function("true"); page.wait_for_timeout(300)
        self.assertEqual(len(envois), 1)
        self.assertEqual(envois[0]['liaison'], 'wifi')
        self.assertEqual(envois[0]['hote'], '192.168.4.1')
        self.assertEqual(self.erreurs, [])

    def test_espace_arrete_meme_avec_le_focus_sur_un_curseur_ou_une_touche_maintenue(self):
        page = self.page()
        page.goto(self.url+'#direct')
        page.click('#accueil-demo')
        page.wait_for_function("document.getElementById('etat-suivi-texte').textContent.includes('suivie')", timeout=20000)
        page.click('#bouton-auto')
        page.wait_for_function("document.getElementById('bouton-auto').textContent.includes('Arrêter')", timeout=5000)
        page.focus('#puissance')                                         # le focus est resté sur un curseur
        page.keyboard.press(' ')
        page.wait_for_function("document.getElementById('bouton-auto').textContent.includes('Explorer')", timeout=5000)
        self.assertFalse(self.app.session.explorateur.actif)
        # touche de déplacement maintenue (répétition clavier) puis Espace : le robot reste arrêté jusqu'au relâchement
        page.evaluate("document.activeElement.blur()")
        page.keyboard.down('z'); page.wait_for_timeout(300)
        self.assertGreater(self.app.session.consigne[0], 0)
        page.keyboard.press(' ')
        for _ in range(4):
            page.keyboard.down('z'); page.wait_for_timeout(120)         # répétitions de la touche enfoncée
        self.assertEqual(self.app.session.consigne, (0., 0., 0.))
        page.keyboard.up('z'); page.wait_for_timeout(150)
        page.keyboard.down('z'); page.wait_for_timeout(300)             # une nouvelle pression repart
        self.assertGreater(self.app.session.consigne[0], 0)
        page.keyboard.up('z')
        page.click('#puce-connexion'); page.click('#bouton-demo')
        page.wait_for_function("document.getElementById('puce-texte').textContent.includes('Hors')", timeout=8000)
        self.assertEqual(self.erreurs, [])

    def test_prendre_un_scan_depuis_le_direct(self):
        page = self.page()
        page.goto(self.url+'#direct')
        self.assertTrue(page.locator('#bouton-scan').is_disabled())     # hors connexion : rien à prendre
        page.click('#accueil-demo')
        page.wait_for_function("document.getElementById('etat-suivi-texte').textContent.includes('suivie')", timeout=20000)
        page.click('#seg-mode button[data-mode=localiser]')             # la carte ne grossit plus toute seule
        page.wait_for_function("!document.getElementById('bouton-scan').disabled", timeout=5000)
        avant = len(self.app.session.carte.cles)
        page.click('#bouton-scan')
        page.wait_for_function("document.getElementById('bandeau').textContent.includes('Scan manuel 1')", timeout=8000)
        self.assertEqual(len(self.app.session.carte.cles), avant+1)
        page.goto(self.url+'#carte')
        page.wait_for_selector('#liste-scans li')
        self.assertIn('Manuel 1', page.inner_text('#liste-scans'))
        page.goto(self.url+'#direct')
        page.click('#puce-connexion'); page.click('#bouton-demo')
        page.wait_for_function("document.getElementById('puce-texte').textContent.includes('Hors')", timeout=8000)
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
