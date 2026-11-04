"""Transport robot SA1 : commande UDP indépendante du flux lidar TCP SA06.

Les threads réseau ne touchent jamais Tk. Le bail UI et le délai des scans
interdisent qu'un heartbeat réseau seul entretienne une ancienne commande.
"""
from dataclasses import dataclass
import queue
import secrets
import socket
import struct
import threading
import time
import zlib
import numpy as np
from cartographie import Scan, ANGLE_REFERENCE_DEFAUT

HEADER = struct.Struct('<4sBBHIQIH')
POINT = struct.Struct('<HHB')
COMMANDS = frozenset(('STOP', 'FORWARD', 'BACK', 'LEFT', 'RIGHT', 'STRAFE_L', 'STRAFE_R', 'DRIVE'))


@dataclass
class TrameScan:
    sequence: int
    fin_us: int
    duree_us: int
    mesures: np.ndarray

    def scan(self):
        return Scan(f'Wi-Fi {self.sequence}', self.mesures.copy(),
                    source='LD06 Wi-Fi — tour complet horodaté',
                    angle_reference=ANGLE_REFERENCE_DEFAUT)


def encoder_trame(sequence, fin_us, duree_us, mesures):
    """Même format que le firmware ; aussi utilisé par le robot de test."""
    m = np.asarray(mesures, float)
    if m.ndim != 2 or m.shape[1] != 3 or not 1 <= len(m) <= 1200 or not np.isfinite(m).all():
        raise ValueError('Mesures invalides.')
    if (m[:, 1] < 0).any() or (m[:, 1] > 65.535).any() or (m[:, 2] < 0).any() or (m[:, 2] > 255).any():
        raise ValueError('Mesures hors format.')
    payload = b''.join(POINT.pack(round(a*100) % 36000, round(d*1000), int(i)) for a, d, i in m)
    raw = HEADER.pack(b'SA06', 1, 0, len(m), sequence, fin_us, duree_us, len(payload)) + payload
    return raw + struct.pack('<I', zlib.crc32(raw))


class DecodeurScans:
    def __init__(self):
        self.buffer = bytearray()

    def recevoir(self, donnees):
        self.buffer.extend(donnees)
        resultat = []
        while len(self.buffer) >= HEADER.size:
            magic, version, flags, n, seq, fin, duree, taille = HEADER.unpack_from(self.buffer)
            if magic != b'SA06' or version != 1 or flags or not 1 <= n <= 1200 or taille != n*POINT.size:
                raise ValueError('Protocole lidar invalide ; reconnecter le robot.')
            if not 10_000 <= duree <= 1_000_000 or fin < duree:
                raise ValueError('Horodatage lidar invalide.')
            total = HEADER.size + taille + 4
            if len(self.buffer) < total:
                break
            raw = bytes(self.buffer[:total])
            if zlib.crc32(raw[:-4]) != struct.unpack('<I', raw[-4:])[0]:
                raise ValueError('CRC lidar invalide ; aucune insertion en carte.')
            m = np.array(list(POINT.iter_unpack(raw[HEADER.size:-4])), dtype=float)
            if (m[:, 0] >= 36000).any():
                raise ValueError('Angle lidar invalide.')
            m[:, 0] /= 100
            m[:, 1] /= 1000
            resultat.append(TrameScan(seq, fin, duree, m))
            del self.buffer[:total]
        return resultat


def dernier(queue_, valeur):
    """Une seule valeur en attente : le retard ne devient pas une file de scans."""
    try:
        queue_.put_nowait(valeur)
    except queue.Full:
        try:
            queue_.get_nowait()
        except queue.Empty:
            pass
        try:
            queue_.put_nowait(valeur)
        except queue.Full:
            pass


def valider_vecteur(vx, vy, w):
    """Trois entiers de -100 à 100 : avance (+), gauche (+), rotation à gauche (+)."""
    try:
        valeurs = tuple(int(round(v)) for v in (vx, vy, w))
    except (TypeError, ValueError, OverflowError):
        raise ValueError('Commande moteur invalide.')
    if any(not -100 <= v <= 100 for v in valeurs) or not all(np.isfinite([vx, vy, w])):
        raise ValueError('Commande moteur invalide.')
    return valeurs


_SIMPLES = {(0, 1):'FORWARD', (0, -1):'BACK', (1, 1):'STRAFE_L', (1, -1):'STRAFE_R',
            (2, 1):'LEFT', (2, -1):'RIGHT'}


def commande_simple(vecteur):
    """Équivalent SA1 (nom, puissance) d'un vecteur à un seul axe non nul ; sinon None."""
    actifs = [i for i, v in enumerate(vecteur) if v]
    if len(actifs) != 1:
        return None
    i = actifs[0]
    return _SIMPLES[(i, 1 if vecteur[i] > 0 else -1)], abs(vecteur[i])


class BailCommande:
    def __init__(self):
        self.lock = threading.Lock()
        self.commande = 'STOP'
        self.pwm = 65
        self.vecteur = (0, 0, 0)
        self.pulse = 0.

    def actualiser(self, commande, pwm=65, maintenant=None, vecteur=(0, 0, 0)):
        if commande not in COMMANDS or not 0 <= pwm <= 100:
            raise ValueError('Commande moteur invalide.')
        vecteur = valider_vecteur(*vecteur)
        if commande == 'DRIVE' and vecteur == (0, 0, 0):
            commande = 'STOP'  # Un vecteur nul est un arrêt, jamais un mouvement.
        with self.lock:
            self.commande, self.pwm, self.vecteur = commande, int(pwm), vecteur
            self.pulse = time.monotonic() if maintenant is None else maintenant

    def lire_complet(self, maintenant=None):
        t = time.monotonic() if maintenant is None else maintenant
        with self.lock:
            if 0 <= t-self.pulse < .25:
                return self.commande, self.pwm, self.vecteur
            return 'STOP', self.pwm, (0, 0, 0)

    def lire(self, maintenant=None):
        commande, pwm, _ = self.lire_complet(maintenant)
        return commande, pwm


class RobotWifi:
    def __init__(self, hote='192.168.4.1', port_commande=4210, port_scans=4211):
        self.hote, self.port_commande, self.port_scans = hote, port_commande, port_scans
        self.session = secrets.token_hex(16)
        self.bail = BailCommande()
        self.scans = queue.Queue(maxsize=1)
        self.etats = queue.Queue(maxsize=8)
        self.arret = threading.Event()
        self.connecte = threading.Event()
        self.lock = threading.Lock()
        self.dernier_scan = 0.
        self.sockets = []
        self.threads = []
        self.recus = 0
        self.envoyee = "STOP"
        self.combine = False  # Le firmware connecté comprend-il SA2 ? Annoncé dans READY.
        self.avis_combine = False
        self.effective = "EN ATTENTE"
        self.date_ack = 0.
        self.journal = None

    def diagnostic_commande(self):
        with self.lock:
            return dict(envoyee=self.envoyee,
                        effective=self.effective if time.monotonic()-self.date_ack < .6 else 'EN ATTENTE')

    def demarrer(self):
        if self.threads:
            raise RuntimeError('Client déjà démarré.')
        for fonction in (self._commandes, self._scans):
            thread = threading.Thread(target=fonction, daemon=True)
            self.threads.append(thread)
            thread.start()

    def _etat(self, texte):
        try:
            self.etats.put_nowait(texte)
        except queue.Full:
            pass

    def commander(self, commande='STOP', pwm=65):
        self.bail.actualiser(commande, pwm)

    def conduire(self, avance=0, gauche=0, rotation=0):
        """Mouvement combiné en pourcentages signés ; (0, 0, 0) arrête le robot."""
        vecteur = valider_vecteur(avance, gauche, rotation)
        self.bail.actualiser('DRIVE' if any(vecteur) else 'STOP', max(map(abs, vecteur)), vecteur=vecteur)

    def _commandes(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(.04)
        self.sockets.append(sock)
        seq, ack, debut = 0, 0., time.monotonic()
        envois, acquitte = {}, 0
        try:
            sock.connect((self.hote, self.port_commande))
            while not self.arret.is_set():
                t = time.monotonic()
                if not self.connecte.is_set():
                    sock.send(f'HELLO {self.session}\n'.encode('ascii'))
                else:
                    cmd, pwm, vecteur = self.bail.lire_complet(t)
                    if t-self.dernier_scan > .6:
                        cmd, vecteur = 'STOP', (0, 0, 0)
                    seq += 1
                    simple = commande_simple(vecteur) if cmd == 'DRIVE' else None
                    if cmd == 'DRIVE' and simple is None and not self.combine:
                        # Ancien firmware : on garde l'axe le plus fort plutôt que de perdre la liaison.
                        axe = max(range(3), key=lambda i: abs(vecteur[i]))
                        simple = commande_simple(tuple(v if i == axe else 0 for i, v in enumerate(vecteur)))
                        if not self.avis_combine:
                            self.avis_combine = True
                            self._etat('Firmware sans déplacement combiné : seul l’axe dominant est envoyé. Reflasher ScanAtlas_WiFi.')
                    if simple is not None:
                        cmd, pwm = simple
                    if cmd == 'DRIVE':
                        sock.send(f'SA2 {self.session} {seq} {vecteur[0]} {vecteur[1]} {vecteur[2]}\n'.encode('ascii'))
                    else:
                        sock.send(f'SA1 {self.session} {seq} {cmd} {pwm}\n'.encode('ascii'))
                    with self.lock:
                        self.envoyee = cmd
                    envois[seq] = t
                    envois = {n:date for n,date in envois.items() if t-date < .5}
                try:
                    reponse = sock.recv(256).decode('ascii').strip().split()
                    if reponse[:2] == ['READY', self.session] and reponse[2:] in ([], ['SA2']):
                        self.combine = reponse[2:] == ['SA2']
                        if not self.connecte.is_set():
                            self._etat('Connecté au robot ; moteurs arrêtés.')
                            self.connecte.set()
                            ack = time.monotonic()
                    elif (len(reponse) == 4 and reponse[:2] == ['SA1', self.session] and
                          reponse[2].isdigit() and reponse[3] in COMMANDS):
                        numero = int(reponse[2])
                        if (acquitte < numero <= seq and numero in envois and
                            time.monotonic()-envois[numero] < .5):
                            acquitte = numero
                            ack = time.monotonic()
                            with self.lock:
                                self.effective, self.date_ack = reponse[3], ack
                    elif reponse and reponse[0] == 'BUSY':
                        raise ConnectionError('Robot déjà contrôlé par une autre session.')
                except socket.timeout:
                    pass
                if time.monotonic()-(ack or debut) > (2. if self.connecte.is_set() else 3.):
                    raise TimeoutError('Robot sans réponse : commande arrêtée, reconnecter.')
                self.arret.wait(.04)
        except (OSError, ValueError, UnicodeError) as exc:
            self._etat(str(exc))
        finally:
            self.bail.actualiser('STOP')
            # Redondance UDP ; le watchdog ESP32 reste l'ultime arrêt indépendant.
            for _ in range(3):
                try:
                    seq += 1
                    sock.send(f'SA1 {self.session} {seq} STOP 0\n'.encode('ascii'))
                except OSError:
                    break
            self.connecte.clear()
            self.arret.set()
            sock.close()

    def _scans(self):
        sock = None
        try:
            while not self.connecte.wait(.05):
                if self.arret.is_set():
                    return
            sock = socket.create_connection((self.hote, self.port_scans), timeout=2.)
            self.sockets.append(sock)
            sock.sendall((self.session+'\n').encode('ascii'))
            sock.settimeout(.2)
            decodeur = DecodeurScans()
            seq, fin = None, None
            dernier_recu = time.monotonic()
            while not self.arret.is_set():
                try:
                    data = sock.recv(8192)
                except socket.timeout:
                    if time.monotonic()-dernier_recu > 2.:
                        raise TimeoutError('Flux lidar interrompu ; moteurs arrêtés.')
                    continue
                if not data:
                    raise ConnectionError('Flux lidar fermé ; moteurs arrêtés.')
                for trame in decodeur.recevoir(data):
                    if (seq is not None and (trame.sequence <= seq or trame.fin_us <= fin)):
                        raise ValueError('Scan ancien ou redémarrage ESP32 : reconnecter.')
                    seq, fin = trame.sequence, trame.fin_us
                    self.dernier_scan = dernier_recu = time.monotonic()
                    if self.journal is not None:self.journal.brut(trame)
                    self.recus += 1
                    dernier(self.scans, trame)
        except (OSError, ValueError) as exc:
            self._etat(str(exc))
            self.bail.actualiser('STOP')
            self.arret.set()
        finally:
            if sock is not None:
                sock.close()

    def fermer(self):
        self.bail.actualiser('STOP')
        self.arret.set()
        # Ne pas attendre les threads sur le thread Tk ; leurs sockets ont un timeout.
        self.connecte.clear()

