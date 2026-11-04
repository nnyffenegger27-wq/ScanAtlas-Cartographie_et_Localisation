"""Le robot en direct, sans interface : connexion, pilotage, suivi, carte, reconnexion automatique.

Tout se passe dans des threads du serveur ; l'interface web ne reçoit que des événements (`publier`) et envoie
des ordres (connecter, piloter, régler). Règles de sécurité conservées :
- une consigne de pilotage ne vaut que 0,35 s : si la page se ferme, se fige ou perd le focus, STOP ;
- aucune commande ne part sans flux lidar récent ;
- l'arrêt n'efface aucun réglage.
"""
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
import numpy as np
from robot_wifi import RobotWifi, dernier
from cartographie import mesures_valides
from cartographie_direct import CarteDirecte
from exploration import Explorateur
from simulation import SALLES, SALLE_PAR_DEFAUT

VALIDITE_CONSIGNE = .35
ESSAIS_RECONNEXION = 8
DELAI_RECONNEXION = 3.
MAX_POINTS_CARTE = 16000


def pourcentages(surge, sway, yaw, puissance, rotation_max):
    """Niveaux [-1, 1] → pourcentages signés ; la rotation est plafonnée (un tour lidar déformé n'est plus recalable)."""
    puissance = max(0., min(100., float(puissance)))
    plafond = max(10., min(100., float(rotation_max)))/100
    borne = lambda v: max(-1., min(1., float(v))) if np.isfinite(float(v)) else 0.
    return (int(round(borne(surge)*puissance)), int(round(borne(sway)*puissance)),
            int(round(borne(yaw)*plafond*puissance)))


def _mm(tableau):
    return np.rint(np.asarray(tableau, float)*1000).astype(int).ravel().tolist()


def _decimer(points, maximum):
    if len(points) <= maximum:
        return points
    return points[np.linspace(0, len(points)-1, maximum).astype(int)]


class Diffuseur:
    """Un abonné par page ouverte ; un abonné lent perd des événements, il ne bloque personne."""
    def __init__(self):
        self.abonnes = []
        self.verrou = threading.Lock()

    def abonner(self):
        q = queue.Queue(maxsize=300)
        with self.verrou:
            self.abonnes.append(q)
        return q

    def desabonner(self, q):
        with self.verrou:
            if q in self.abonnes:
                self.abonnes.remove(q)

    def publier(self, genre, donnees):
        with self.verrou:
            abonnes = list(self.abonnes)
        for q in abonnes:
            try:
                q.put_nowait((genre, donnees))
            except queue.Full:
                pass


class SessionDirecte:
    def __init__(self, document, diffuseur, fabrique_robot=None, lancer_demo=None):
        self.doc, self.diffuseur = document, diffuseur
        self.fabrique_robot = fabrique_robot or self._fabrique_defaut
        self.reglages = dict(puissance=60, rotation_max=60, mode='cartographier', recup_auto=True, reconnexion_auto=True)
        self.liaison, self.hote = 'wifi', '192.168.4.1'
        self.robot = None
        self.carte = None
        self.version_carte = -1          # version du document au moment où la carte de suivi a été construite
        self.generation = 0              # change à chaque nouvelle carte : un ancien thread de calcul s'arrête seul
        self.journal = None
        self.arret_calcul = threading.Event()
        self.thread_calcul = None
        self.consigne, self.consigne_t = (0., 0., 0.), 0.
        self.actif_demande = False       # l'utilisateur veut être connecté (sert à la reconnexion automatique)
        self.tentatives, self.reconnexion_a = 0, None
        self.message = 'Hors connexion.'
        self.messages = []
        self.dernier_etat = None         # dernier EtatDirect
        self.dernier_scan = None         # dernier événement « scan » (pour les nouvelles pages)
        self.derniere_carte_t, self.derniere_carte_cles = 0., -1
        self.version_publiee = -1
        self.demo = None                 # None ou dict(processus, avant) pendant la démonstration
        self.explorateur = Explorateur()  # exploration autonome (inactive tant que l'utilisateur ne la demande pas)
        self.points_locaux = np.empty((0, 2))   # dernier tour, repère du robot, en mètres (évitement d'obstacles)
        self.dernier_suivi_t = 0.        # heure du dernier tour traité
        self.perdu_auto_t = None         # début de la perte de position pendant l'exploration
        self.dernier_plan_t = 0.
        self.verrou = threading.RLock()
        self.arret = threading.Event()
        self.thread = threading.Thread(target=self._boucle, daemon=True)
        self.thread.start()
        self.thread_plan = threading.Thread(target=self._boucle_plan, daemon=True)
        self.thread_plan.start()

    # -- outils -----------------------------------------------------------------------------------
    @staticmethod
    def _fabrique_defaut(liaison, hote):
        if liaison == 'usb':
            from robot_usb import RobotUsb
            return RobotUsb(hote)
        return RobotWifi(hote)

    def dire(self, texte, grave=False):
        with self.verrou:
            self.message = texte
            self.messages.append(dict(t=time.strftime('%H:%M:%S'), texte=texte, grave=grave))
            self.messages = self.messages[-60:]
        self.diffuseur.publier('message', dict(texte=texte, grave=grave, t=self.messages[-1]['t']))

    def ports(self):
        try:
            from robot_usb import lister_ports
            return [dict(port=p, description=d) for p, d in lister_ports()]
        except Exception:
            return []

    def pret(self):
        r = self.robot
        return r is not None and r.connecte.is_set() and time.monotonic()-r.dernier_scan <= .6

    def etat_public(self):
        with self.verrou:
            r = self.robot
            etat = self.dernier_etat
            if r is None:
                connexion = 'attente' if self.reconnexion_a is not None else 'hors_ligne'
            else:
                connexion = 'connecte' if r.connecte.is_set() else 'connexion'
            restant = None if self.reconnexion_a is None else max(0., self.reconnexion_a-time.monotonic())
            return dict(connexion=connexion, liaison=self.liaison, hote=self.hote, demo=self.demo is not None, salle_demo=None if self.demo is None else self.demo['salle'],
                        salles=[dict(id=k, titre=v['titre']) for k, v in SALLES.items()],
                        pret=self.pret(), reglages=dict(self.reglages), message=self.message,
                        reconnexion=None if restant is None else dict(essai=self.tentatives, restant=round(restant, 1)),
                        suivi=None if etat is None else dict(actif=etat.accepte, message=etat.message),
                        recus=0 if r is None else r.recus, journal=str(self.journal.dossier) if self.journal else None,
                        commande=None if r is None else r.diagnostic_commande(),
                        auto=dict(etat=self.explorateur.etat, message=self.explorateur.message))

    def publier_etat(self):
        self.diffuseur.publier('etat', self.etat_public())

    def instantane_complet(self):
        """Tout ce qu'une page qui s'ouvre doit savoir."""
        sortie = [('etat', self.etat_public())]
        sortie.append(('messages', dict(messages=list(self.messages))))
        if self.dernier_scan is not None:
            sortie.append(('scan', self.dernier_scan))
        sortie.append(('auto', self.explorateur.diagnostic()))
        if self.dernier_etat is not None:
            sortie.append(('carte', self._charge_carte(self.dernier_etat)))
        return sortie

    # -- réglages et ordres ---------------------------------------------------------------------
    def regler(self, **valeurs):
        with self.verrou:
            for cle, valeur in valeurs.items():
                if cle not in self.reglages:
                    raise ValueError('Réglage inconnu : '+cle)
                if cle in ('puissance', 'rotation_max'):
                    valeur = int(max(10 if cle == 'rotation_max' else 0, min(100, float(valeur))))
                elif cle == 'mode':
                    if valeur not in ('cartographier', 'localiser'):
                        raise ValueError('Mode : cartographier ou localiser.')
                else:
                    valeur = bool(valeur)
                self.reglages[cle] = valeur
            if self.carte is not None:
                self.carte.recup_auto = self.reglages['recup_auto']
            if not self.reglages['reconnexion_auto']:
                self.reconnexion_a = None
        self.publier_etat()

    def piloter(self, surge, sway, yaw):
        brut = [float(v) for v in (surge, sway, yaw)]
        if not np.isfinite(brut).all():        # avant de borner : min(1, nan) vaudrait 1 (pleine vitesse)
            raise ValueError('Consigne invalide.')
        vecteur = tuple(max(-1., min(1., v)) for v in brut)
        if self.explorateur.actif and max(abs(v) for v in vecteur) > .15:
            self.arreter_auto('Pilotage manuel repris : exploration autonome arrêtée.')
        with self.verrou:
            self.consigne, self.consigne_t = vecteur, time.monotonic()

    def arreter(self):
        self.arreter_auto('Arrêt : exploration autonome arrêtée.')
        with self.verrou:
            self.consigne, self.consigne_t = (0., 0., 0.), 0.
        if self.robot is not None:
            self.robot.commander('STOP')

    # -- exploration autonome ---------------------------------------------------------------------
    def demarrer_auto(self):
        with self.verrou:
            if self.robot is None or not self.pret():
                raise ValueError('Connecte le robot et attends le premier tour du lidar avant l’exploration autonome.')
            if self.reglages['mode'] != 'cartographier':
                raise ValueError('L’exploration autonome ajoute des scans à la carte : passe en mode Cartographier.')
            etat = self.dernier_etat
            if etat is None or not etat.accepte:
                raise ValueError('Position non suivie : attends que le suivi soit actif (ou replace le robot).')
            self.explorateur.demarrer(time.monotonic())
            self.perdu_auto_t = None
            self.dernier_plan_t = 0.
        self.dire('Exploration autonome démarrée. Tout pilotage manuel ou Espace l’arrête.')
        self.diffuseur.publier('auto', self.explorateur.diagnostic())
        self.publier_etat()

    def arreter_auto(self, message=None, etat='inactif', grave=False):
        with self.verrou:
            if self.explorateur.etat != 'exploration':
                return
            self.explorateur.arreter(etat, message or '')
        if message:
            self.dire(message, grave=grave)
        self.diffuseur.publier('auto', self.explorateur.diagnostic())
        self.publier_etat()

    def _boucle_plan(self):
        """Planification (frontières, chemin) hors de la boucle de sécurité : elle prend de 10 à 200 ms selon la carte."""
        while not self.arret.wait(.2):
            ex = self.explorateur
            try:
                if not ex.actif:
                    continue
                etat = self.dernier_etat
                maintenant = time.monotonic()
                if etat is None or not etat.accepte or etat.grille is None or not len(etat.trajectoire):
                    continue
                if maintenant-self.dernier_plan_t < 1. and not ex.replanifier:
                    continue
                self.dernier_plan_t = maintenant
                avant = ex.etat
                ex.planifier(etat.grille, np.asarray(etat.trajectoire[-1], float), maintenant)
                self.diffuseur.publier('auto', ex.diagnostic())
                if ex.etat != avant:
                    self.dire(ex.message, grave=ex.etat in ('bloque', 'erreur'))
                    self.publier_etat()
            except Exception as exc:
                self.dire('Planification : '+str(exc), grave=True)
                ex.arreter('erreur', 'Erreur interne de planification : '+str(exc))
                self.publier_etat()

    def replacer(self, x, y, cap):
        """Indique où le robot est sur la carte (point + direction approximatifs, repère de la carte)."""
        with self.verrou:
            if self.robot is None:
                raise ValueError('Connecte le robot avant de le replacer sur la carte.')
            if self.carte is None or not len(self.carte.points):
                raise ValueError('Pas encore de carte où replacer le robot.')
            self.carte.replacer(x, y, cap)
        self.dire('Recherche de la position autour du point indiqué…')

    def retrouver(self):
        """Recherche sur toute la carte au prochain tour."""
        with self.verrou:
            if self.carte is None or not len(self.carte.points):
                raise ValueError('Pas encore de carte où se retrouver.')
            self.carte.relocaliser()
        self.dire('Recherche de la position sur toute la carte…')

    def reprendre(self):
        with self.verrou:
            if self.carte is None:
                raise ValueError('Pas de carte à reprendre.')
            self.carte.reprendre()
        self.dire('Reprise près de la dernière position connue.')

    def nouvelle_carte(self):
        self.arreter_auto('Exploration autonome arrêtée : nouvelle carte.')
        with self.verrou:
            self.generation += 1
            self.carte, self.dernier_etat, self.dernier_scan = None, None, None
            self.derniere_carte_cles = -1
            self.doc.vider()
            self.version_carte = self.doc.version
            connecte = self.robot is not None
        if connecte:
            self._lancer_calcul()
        self.diffuseur.publier('carte', dict(vide=True))
        self.dire('Nouvelle carte vide.')
        self.publier_etat()

    # -- connexion ------------------------------------------------------------------------------
    def connecter(self, liaison=None, hote=None, automatique=False):
        with self.verrou:
            if self.robot is not None:
                raise ValueError('Déjà connecté : déconnecter d’abord.')
            if liaison is not None:
                if liaison not in ('wifi', 'usb'):
                    raise ValueError('Liaison : wifi ou usb.')
                self.liaison = liaison
            if hote is not None:
                hote = str(hote).strip()
                if hote:
                    self.hote = hote
            if not self.hote:
                raise ValueError('Adresse du robot (Wi-Fi) ou port (USB) manquant.')
            if not automatique:
                self.tentatives, self.reconnexion_a = 0, None
            self.actif_demande = True
            from journal_direct import JournalDirect
            try:
                self.journal = JournalDirect()
            except OSError as exc:
                raise ValueError('Impossible de créer le journal : '+str(exc))
            if self.carte is None or self.version_carte != self.doc.version:
                # La carte a changé hors du direct (import, retrait d'un scan) : repartir de ses scans inclus.
                self.carte = None
            robot = self.fabrique_robot(self.liaison, self.hote)
            robot.journal = self.journal
            self.robot = robot
        robot.demarrer()
        self._lancer_calcul()
        self.dire('Connexion…')
        self.publier_etat()

    def deconnecter(self, automatique=False):
        self.arreter_auto('Exploration autonome arrêtée : robot déconnecté.', etat='inactif', grave=automatique)
        with self.verrou:
            if not automatique:
                self.actif_demande = False
                self.tentatives, self.reconnexion_a = 0, None
            demo, self.demo = self.demo, None if not automatique else self.demo
        if demo is not None and not automatique:
            self._fin_demo(demo)
        self.arret_calcul.set()
        with self.verrou:
            robot, self.robot = self.robot, None
            journal, self.journal = self.journal, None
            self.consigne = (0., 0., 0.)
            if self.carte is not None:
                self.carte.annuler.set()
        if robot is not None:
            robot.fermer()
        if journal is not None:
            threading.Thread(target=journal.fermer, daemon=True).start()
        if not automatique:
            self.dire('Déconnecté. La carte reste disponible.')
        self.publier_etat()

    def demarrer_demo(self, salle=None):
        salle = salle or SALLE_PAR_DEFAUT
        if salle not in SALLES:
            raise ValueError('Salle simulée inconnue : %s.' % salle)
        with self.verrou:
            if self.demo is not None:
                return
        self.deconnecter()
        avant = (self.liaison, self.hote, self.doc.instantane())
        self.doc.vider()
        self.carte, self.dernier_etat, self.dernier_scan = None, None, None
        script = Path(__file__).with_name('simuler_robot_wifi.py')
        processus = subprocess.Popen([sys.executable, str(script), '--salle', salle])
        with self.verrou:
            self.demo = dict(processus=processus, avant=avant, salle=salle)
        self.liaison, self.hote = 'wifi', '127.0.0.1'
        self.dire('Démonstration : robot simulé sur ce PC (%s).' % SALLES[salle]['titre'])
        threading.Timer(.8, lambda: self._connecter_demo()).start()

    def _connecter_demo(self):
        if self.demo is not None:
            try:
                self.connecter('wifi', '127.0.0.1')
            except ValueError as exc:
                self.dire(str(exc), grave=True)

    def quitter_demo(self):
        with self.verrou:
            demo = self.demo
        if demo is None:
            return
        self.deconnecter()          # appelle _fin_demo

    def _fin_demo(self, demo):
        processus = demo['processus']
        if processus.poll() is None:
            processus.terminate()
        threading.Thread(target=processus.wait, daemon=True).start()      # évite un processus zombie
        liaison, hote, instantane = demo['avant']
        self.liaison, self.hote = liaison, hote
        self.carte, self.dernier_etat, self.dernier_scan = None, None, None
        self.derniere_carte_cles = -1
        self.doc.restaurer(instantane)
        self.version_carte = -1
        self.diffuseur.publier('carte', dict(vide=True))
        self.dire('Démonstration terminée ; adresse du robot rétablie.')

    # -- calcul de la carte ---------------------------------------------------------------------
    def _lancer_calcul(self):
        with self.verrou:
            self.arret_calcul.set()
            ancien = self.thread_calcul
        if ancien is not None:
            ancien.join(timeout=3.)
        with self.verrou:
            self.arret_calcul = threading.Event()
            robot, journal, generation = self.robot, self.journal, self.generation
            if robot is None:           # déconnecté entre-temps : rien à calculer
                return
            arret, recup = self.arret_calcul, self.reglages['recup_auto']
            self.thread_calcul = threading.Thread(target=self._calculer, args=(robot, journal, generation, arret, recup), daemon=True)
            self.thread_calcul.start()

    def _calculer(self, robot, journal, generation, arret, recup):
        carte = self.carte
        if carte is None:
            try:
                sources = self.doc.scans_inclus()
                if sources:
                    robot._etat(f'Chargement de la carte de départ ({len(sources)} scans)…')
                carte = CarteDirecte(self.doc.filtres, scans=[s for s in sources])
                carte.recup_auto = recup
                if arret.is_set() or robot.arret.is_set() or generation != self.generation:
                    return
                with self.verrou:
                    self.carte, self.version_carte = carte, self.doc.version
            except Exception as exc:
                robot._etat('Carte de départ refusée : '+str(exc))
                robot.fermer()
                return
        else:
            carte.annuler.clear()
            carte.recup_auto = recup
            carte.reprendre()   # après une reconnexion le robot est en général au même endroit
        while not arret.is_set() and not robot.arret.is_set() and generation == self.generation:
            try:
                trame = robot.scans.get(timeout=.1)
            except queue.Empty:
                continue
            try:
                etat = carte.traiter(trame, enrichir=self.reglages['mode'] == 'cartographier')
                if journal is not None:
                    journal.resultat(trame, etat, carte.filtres)
            except Exception as exc:
                robot.commander('STOP')
                robot._etat('Suivi arrêté : '+str(exc))
                robot.arret.set()
                break
            etat.scan.nom = f'Direct {robot.session[:6]} / {trame.sequence}'
            self._publier_scan(etat, robot, trame.sequence)

    def _charge_carte(self, etat):
        pts = _decimer(np.asarray(etat.points), MAX_POINTS_CARTE)
        trajet = _decimer(np.asarray(etat.trajectoire), 600)
        return dict(vide=False, pts=_mm(pts), cles=etat.cles,
                    segments=[[round(float(v), 3) for v in np.asarray(s).ravel()] for s in etat.segments[:1500]],
                    trajet=[[round(float(p[0]), 3), round(float(p[1]), 3)] for p in trajet])

    def _publier_scan(self, etat, robot, sequence):
        pose = np.asarray(etat.trajectoire[-1] if len(etat.trajectoire) else (0., 0., 0.), float)
        scan = etat.scan
        if etat.accepte:
            pose_scan = list(scan.pose)
        else:
            pose_scan = list(pose)
        valides = mesures_valides(scan, **self.doc.filtres)
        theta = np.deg2rad(scan.mesures[valides, 0]-scan.angle_reference)
        rayon = scan.mesures[valides, 1]
        local = _decimer(np.column_stack((rayon*np.cos(theta), rayon*np.sin(theta))), 450)
        perdu = None if self.carte is None or getattr(self.carte, 'perdu_t', None) is None else round(time.monotonic()-self.carte.perdu_t, 1)
        evenement = dict(sequence=int(sequence),
                         accepte=bool(etat.accepte), message=etat.message, pose=[round(float(v), 4) for v in pose],
                         pose_scan=[round(float(v), 4) for v in pose_scan], pts=_mm(local),
                         concordance=None if not np.isfinite(etat.concordance) else round(float(etat.concordance), 1),
                         rmse=None if not np.isfinite(etat.rmse) else round(float(etat.rmse), 4),
                         duree_ms=round(1000*etat.duree), cles=etat.cles, segments=len(etat.segments), perdu=perdu,
                         verification=int(getattr(self.carte, 'probation', 0)), recus=robot.recus)
        precedent = self.dernier_etat
        with self.verrou:
            self.dernier_etat, self.dernier_scan = etat, evenement
            self.points_locaux, self.dernier_suivi_t = np.column_stack((rayon*np.cos(theta), rayon*np.sin(theta))), time.monotonic()
        if self.journal is not None and (precedent is None or precedent.accepte != etat.accepte):
            self.journal.evenement('Suivi actif.' if etat.accepte else 'Suivi perdu : '+etat.message)
        if etat.accepte:
            self.tentatives = 0
        self.diffuseur.publier('scan', evenement)
        maintenant = time.monotonic()
        if etat.cles != self.derniere_carte_cles or (maintenant-self.derniere_carte_t > 2. and etat.accepte):
            if maintenant-self.derniere_carte_t > .4 or self.derniere_carte_cles < 0:
                self.derniere_carte_t = maintenant
                if etat.cles != self.derniere_carte_cles:
                    self.derniere_carte_cles = etat.cles
                    carte = self.carte
                    if carte is None:        # déconnexion pendant le calcul de ce scan : plus rien à publier
                        return
                    self.doc.remplacer_par_direct(list(etat.scans_cles), vue=dict(points=etat.points, appuis=carte.appuis, grille=etat.grille))
                    self.version_carte = self.doc.version
                self.diffuseur.publier('carte', self._charge_carte(etat))

    # -- boucle de contrôle (pilotage, état, reconnexion) ---------------------------------------
    def _boucle(self):
        derniere_pub = 0.
        while not self.arret.wait(.05):
            try:
                self._tour()
                if time.monotonic()-derniere_pub > 1.:
                    derniere_pub = time.monotonic()
                    self.publier_etat()
            except Exception as exc:    # la boucle de sécurité ne doit jamais mourir
                self.dire('Erreur interne : '+str(exc), grave=True)

    def _tour(self):
        with self.verrou:
            robot = self.robot
            consigne, t = self.consigne, self.consigne_t
            reglages = dict(self.reglages)
        if robot is not None:
            if robot.arret.is_set():
                self._perte(robot)
                return
            while not robot.etats.empty():
                self.dire(robot.etats.get_nowait())
            if self.pret():
                if self.explorateur.actif:
                    consigne, frais = self._consigne_auto(), True
                else:
                    frais = time.monotonic()-t <= VALIDITE_CONSIGNE
                surge, sway, yaw = pourcentages(*(consigne if frais else (0, 0, 0)), reglages['puissance'], reglages['rotation_max'])
                robot.conduire(surge, sway, yaw)
            else:
                robot.commander('STOP')
        if self.doc.version != self.version_publiee:
            self.version_publiee = self.doc.version
            self.diffuseur.publier('document', dict(version=self.doc.version))
        if robot is not None:
            return
        if self.reconnexion_a is not None and time.monotonic() >= self.reconnexion_a:
            self.reconnexion_a = None
            if self.actif_demande and self.reglages['reconnexion_auto']:
                try:
                    self.connecter(automatique=True)
                except ValueError as exc:
                    self.dire(str(exc), grave=True)

    def _consigne_auto(self):
        """Consigne de la boucle de sécurité en exploration autonome ; immobile tant que la position n'est pas suivie."""
        ex, etat, maintenant = self.explorateur, self.dernier_etat, time.monotonic()
        suivi = etat is not None and etat.accepte and len(etat.trajectoire) and maintenant-self.dernier_suivi_t <= .6
        if not suivi:
            if self.perdu_auto_t is None:
                self.perdu_auto_t = maintenant
                self.dire('Position perdue : le robot s’arrête et cherche où il est (exploration en pause).')
            elif maintenant-self.perdu_auto_t > 45.:
                self.arreter_auto('Position perdue depuis plus de 45 s : exploration arrêtée. Replace le robot sur la carte.',
                                  etat='erreur', grave=True)
            return (0., 0., 0.)
        self.perdu_auto_t = None
        surge, sway, yaw = ex.commande(np.asarray(etat.trajectoire[-1], float), self.points_locaux, maintenant)
        if not ex.actif:                                  # terminé, bloqué ou erreur détectée par la surveillance
            self.dire(ex.message, grave=ex.etat in ('bloque', 'erreur'))
            self.diffuseur.publier('auto', ex.diagnostic())
            self.publier_etat()
        return (surge, sway, yaw)

    def _perte(self, robot):
        messages = []
        while not robot.etats.empty():
            messages.append(robot.etats.get_nowait())
        perte = messages[-1] if messages else 'Connexion perdue ; moteurs arrêtés.'
        self.deconnecter(automatique=True)
        if (self.actif_demande and self.reglages['reconnexion_auto'] and self.tentatives < ESSAIS_RECONNEXION):
            self.tentatives += 1
            self.reconnexion_a = time.monotonic()+DELAI_RECONNEXION
            self.dire(f'{perte} Reconnexion automatique dans {DELAI_RECONNEXION:.0f} s (essai {self.tentatives}/{ESSAIS_RECONNEXION}) ; la carte est conservée.', grave=True)
        else:
            self.actif_demande = False
            self.dire(perte, grave=True)
        self.publier_etat()

    def fermer(self):
        self.arret.set()
        with self.verrou:
            demo = self.demo
        self.deconnecter()
        if demo is not None and demo['processus'].poll() is None:
            demo['processus'].terminate()
