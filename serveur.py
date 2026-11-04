"""Serveur local de ScanAtlas : l'interface web est servie et pilotée par ce programme, rien ne sort du PC.

- uniquement sur 127.0.0.1 ; l'en-tête Host est vérifié et chaque ordre exige le jeton de la session
  (une autre page ouverte dans le navigateur ne peut donc pas piloter le robot) ;
- GET /api/flux : événements en direct (Server-Sent Events) ; tout le reste est du JSON ;
- aucune dépendance en dehors de la bibliothèque standard et des modules de calcul.
"""
import json
import queue
import gzip
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from document_carte import DocumentCarte, grille_vers_json
from session_directe import SessionDirecte, Diffuseur

DOSSIER_WEB = Path(__file__).with_name('web')
TYPES = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
         '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.json': 'application/json'}
TAILLE_MAX_IMPORT = 200*1024*1024


class Taches:
    """Un seul calcul long à la fois (recalage, assemblage), annulable, avec progression."""
    def __init__(self, diffuseur):
        self.diffuseur = diffuseur
        self.courante = None
        self.annuler = threading.Event()
        self.verrou = threading.Lock()

    def lancer(self, nom, fonction):
        with self.verrou:
            if self.courante is not None and self.courante.is_alive():
                raise ValueError('Un calcul est déjà en cours.')
            self.annuler = threading.Event()
            annuler = self.annuler

            def travail():
                self.diffuseur.publier('tache', dict(nom=nom, etat='en_cours', texte=nom+'…'))
                try:
                    resultat = fonction(annuler, lambda t: self.diffuseur.publier('tache', dict(nom=nom, etat='en_cours', texte=str(t))))
                    self.diffuseur.publier('tache', dict(nom=nom, etat='fini', resultat=resultat,
                                                          texte='Annulé.' if annuler.is_set() else 'Terminé.'))
                except Exception as exc:
                    self.diffuseur.publier('tache', dict(nom=nom, etat='erreur', texte=str(exc)))
            self.courante = threading.Thread(target=travail, daemon=True)
            self.courante.start()

    def interrompre(self):
        self.annuler.set()


class Application:
    def __init__(self, fabrique_robot=None):
        self.jeton = secrets.token_urlsafe(16)
        self.diffuseur = Diffuseur()
        self.doc = DocumentCarte()
        self.session = SessionDirecte(self.doc, self.diffuseur, fabrique_robot=fabrique_robot)
        self.taches = Taches(self.diffuseur)

    def fermer(self):
        self.session.fermer()


def entier(valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        raise ValueError('Identifiant de scan invalide.')
    return valeur


def fabriquer_gestionnaire(app):
    class Gestionnaire(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        server_version = 'ScanAtlas'

        def log_message(self, *args):
            pass

        # -- réponses ---------------------------------------------------------------------------
        def envoyer(self, code, contenu, type_contenu, extra=None):
            self.send_response(code)
            self.send_header('Content-Type', type_contenu)
            self.send_header('Content-Length', str(len(contenu)))
            self.send_header('Cache-Control', 'no-store')
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(contenu)

        def json(self, donnees, code=200):
            corps = json.dumps(donnees, ensure_ascii=False, allow_nan=False).encode('utf-8')
            extra = None
            if len(corps) > 4096 and 'gzip' in (self.headers.get('Accept-Encoding') or ''):
                corps, extra = gzip.compress(corps, 3), {'Content-Encoding': 'gzip'}    # grilles et nuages : très compressibles
            self.envoyer(code, corps, 'application/json; charset=utf-8', extra)

        def erreur(self, texte, code=400):
            self.json(dict(erreur=texte), code)

        # -- contrôles --------------------------------------------------------------------------
        def hote_valide(self):
            hote = (self.headers.get('Host') or '').split(':')[0]
            return hote in ('127.0.0.1', 'localhost')

        def jeton_valide(self, requete):
            fourni = self.headers.get('X-Jeton') or parse_qs(requete.query).get('jeton', [''])[0]
            return secrets.compare_digest(fourni, app.jeton)

        def corps(self):
            n = int(self.headers.get('Content-Length') or 0)
            if n > TAILLE_MAX_IMPORT:
                raise ValueError('Fichier trop gros.')
            return self.rfile.read(n) if n else b''

        def modifiable(self):
            if app.session.robot is not None:
                raise ConflitCarte('Déconnecte le robot avant de modifier la carte.')

        # -- GET --------------------------------------------------------------------------------
        def do_GET(self):
            if not self.hote_valide():
                return self.erreur('Hôte refusé.', 403)
            requete = urlparse(self.path)
            chemin = unquote(requete.path)
            try:
                if chemin == '/' or chemin == '/index.html':
                    page = (DOSSIER_WEB/'index.html').read_text(encoding='utf-8').replace('{{JETON}}', app.jeton)
                    return self.envoyer(200, page.encode('utf-8'), TYPES['.html'])
                if chemin.startswith('/static/'):
                    cible = (DOSSIER_WEB/chemin[len('/static/'):]).resolve()
                    if DOSSIER_WEB.resolve() not in cible.parents or not cible.is_file():
                        return self.erreur('Introuvable.', 404)
                    return self.envoyer(200, cible.read_bytes(), TYPES.get(cible.suffix, 'application/octet-stream'))
                if not chemin.startswith('/api/'):
                    return self.erreur('Introuvable.', 404)
                if not self.jeton_valide(requete):
                    return self.erreur('Jeton invalide.', 403)
                if chemin == '/api/flux':
                    return self.flux()
                if chemin == '/api/carte':
                    return self.json(app.doc.liste())
                if chemin == '/api/carte/nuage':
                    return self.json(app.doc.nuage())
                if chemin == '/api/carte/grille':
                    return self.json(app.doc.grille())
                if chemin == '/api/direct/grille':
                    etat = app.session.dernier_etat
                    if etat is None or etat.grille is None:
                        return self.json(dict(vide=True))
                    return self.json(dict(vide=False, cles=etat.cles, **grille_vers_json(etat.grille)))
                if chemin == '/api/carte/plan':
                    return self.json(app.doc.plan())
                if chemin == '/api/carte/session':
                    nom = ''.join(c for c in app.doc.nom if c.isalnum() or c in '-_ ') or 'session'
                    return self.envoyer(200, app.doc.session_json(), 'application/json',
                                        {'Content-Disposition': f'attachment; filename="{nom}.json"'})
                if chemin.startswith('/api/carte/scan/') and chemin.endswith('.csv'):
                    indice = int(chemin[len('/api/carte/scan/'):-4])
                    nom = app.doc.liste()['scans'][indice]['nom']
                    nom = ''.join(c for c in nom if c.isalnum() or c in '-_ ') or 'scan'
                    return self.envoyer(200, app.doc.scan_csv(indice), 'text/csv; charset=utf-8',
                                        {'Content-Disposition': f'attachment; filename="{nom}.csv"'})
                if chemin == '/api/ports':
                    return self.json(dict(ports=app.session.ports()))
                return self.erreur('Introuvable.', 404)
            except (ValueError, IndexError) as exc:
                self.erreur(str(exc))
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as exc:
                self.erreur('Erreur interne : '+str(exc), 500)

        def flux(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            q = app.diffuseur.abonner()
            try:
                for genre, donnees in app.session.instantane_complet():
                    self.evenement(genre, donnees)
                self.evenement('document', dict(version=app.doc.version))
                while True:
                    try:
                        genre, donnees = q.get(timeout=10.)
                        self.evenement(genre, donnees)
                    except queue.Empty:
                        self.wfile.write(b': ping\n\n')
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                app.diffuseur.desabonner(q)
                self.close_connection = True

        def evenement(self, genre, donnees):
            texte = json.dumps(donnees, ensure_ascii=False, allow_nan=False)
            self.wfile.write(f'event: {genre}\ndata: {texte}\n\n'.encode('utf-8'))
            self.wfile.flush()

        # -- POST -------------------------------------------------------------------------------
        def do_POST(self):
            if not self.hote_valide():
                return self.erreur('Hôte refusé.', 403)
            requete = urlparse(self.path)
            if not self.jeton_valide(requete):
                return self.erreur('Jeton invalide.', 403)
            chemin = unquote(requete.path)
            try:
                brut = self.corps()
                if chemin == '/api/carte/importer':
                    self.modifiable()
                    nom = parse_qs(requete.query).get('nom', ['import'])[0]
                    return self.json(dict(message=app.doc.importer(nom, brut)))
                donnees = json.loads(brut.decode('utf-8')) if brut else {}
                if not isinstance(donnees, dict):
                    raise ValueError('Corps JSON attendu.')
                self.json(self.ordre(chemin, donnees))
            except ConflitCarte as exc:
                self.erreur(str(exc), 409)
            except (ValueError, KeyError, TypeError, IndexError, UnicodeError) as exc:
                self.erreur(str(exc) or 'Requête invalide.')
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as exc:
                self.erreur('Erreur interne : '+str(exc), 500)

        def ordre(self, chemin, d):
            s, doc = app.session, app.doc
            if chemin == '/api/connexion':
                s.connecter(d.get('liaison'), d.get('hote'))
            elif chemin == '/api/deconnexion':
                s.deconnecter()
            elif chemin == '/api/demo':
                s.demarrer_demo(d.get('salle')) if d.get('actif', True) else s.quitter_demo()
            elif chemin == '/api/pilote':
                s.piloter(d.get('surge', 0), d.get('sway', 0), d.get('yaw', 0))
            elif chemin == '/api/arret':
                s.arreter()
            elif chemin == '/api/reglages':
                s.regler(**d)
            elif chemin == '/api/auto':
                s.demarrer_auto() if d.get('actif', True) else s.arreter_auto('Exploration autonome arrêtée.')
            elif chemin == '/api/replacer':
                s.replacer(float(d['x']), float(d['y']), float(d['cap']))
            elif chemin == '/api/retrouver':
                s.retrouver()
            elif chemin == '/api/reprendre':
                s.reprendre()
            elif chemin == '/api/nouvelle_carte':
                s.nouvelle_carte()
            elif chemin == '/api/carte/scan':
                indice = entier(d.get('id'))
                if s.robot is not None and any(k in d for k in ('inclus', 'pose', 'nom')):
                    raise ConflitCarte('Déconnecte le robot avant de modifier la carte.')
                doc.regler(indice, visible=d.get('visible'), inclus=d.get('inclus'), pose=d.get('pose'), nom=d.get('nom'))
            elif chemin == '/api/carte/supprimer':
                self.modifiable()
                doc.supprimer(entier(d.get('id')))
            elif chemin == '/api/carte/tous':
                if s.robot is not None and 'inclus' in d:
                    raise ConflitCarte('Déconnecte le robot avant de modifier la carte.')
                doc.regler_tous(visible=d.get('visible'), inclus=d.get('inclus'))
            elif chemin == '/api/carte/filtres':
                self.modifiable()
                doc.regler_filtres(**{k: d[k] for k in ('mini', 'maxi', 'intensite', 'resolution') if k in d})
            elif chemin == '/api/carte/demo':
                self.modifiable()
                return dict(message=doc.demonstration())
            elif chemin == '/api/carte/vider':
                self.modifiable()
                doc.vider()
            elif chemin == '/api/carte/recaler':
                self.modifiable()
                indice = entier(d.get('id'))
                app.taches.lancer('Recalage', lambda annuler, progression: doc.recaler(indice, annuler))
            elif chemin == '/api/carte/assembler':
                self.modifiable()
                app.taches.lancer('Assemblage', lambda annuler, progression: dict(message=doc.assembler(annuler, progression)))
            elif chemin == '/api/carte/annuler':
                app.taches.interrompre()
            else:
                raise ValueError('Ordre inconnu.')
            return dict(ok=True)

    return Gestionnaire


class ConflitCarte(Exception):
    pass


class ServeurLocal(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def handle_error(self, request, client_address):
        # Une page fermée en plein flux coupe la connexion : ce n'est pas une erreur à afficher.
        import sys
        if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            super().handle_error(request, client_address)


def demarrer(port=8765, ouvrir=True, fabrique_robot=None):
    """Lance le serveur (bloquant). Si le port est pris, essaie les suivants."""
    app = Application(fabrique_robot=fabrique_robot)
    serveur = None
    for essai in range(port, port+20):
        try:
            serveur = ServeurLocal(('127.0.0.1', essai), fabriquer_gestionnaire(app))
            break
        except OSError:
            continue
    if serveur is None:
        raise OSError('Aucun port libre entre %d et %d.' % (port, port+19))
    serveur.application = app
    adresse = f'http://127.0.0.1:{serveur.server_address[1]}/'
    print(f'ScanAtlas — {adresse}   (Ctrl+C pour quitter)')
    if ouvrir:
        threading.Timer(.6, lambda: webbrowser.open(adresse)).start()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.fermer()
        serveur.server_close()


if __name__ == '__main__':
    demarrer()
