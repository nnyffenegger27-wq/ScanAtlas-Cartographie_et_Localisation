"""Transport filaire : mêmes trames SA06 et mêmes commandes SA1 / SA2 que le Wi-Fi, sur le câble USB.

Déroulement : le PC ouvre le port au débit historique (115200), envoie `LIVE jeton débit`, le firmware
répond `READY jeton SA2` puis les deux côtés passent au débit demandé (921600 par défaut : 115200 est
trop lent pour dix tours lidar par seconde). Ensuite, le PC envoie une commande toutes les 40 ms
(elle sert aussi de bail : sans commande pendant 300 ms, le firmware coupe les moteurs et revient à
115200) et le firmware envoie les tours lidar, entrecoupés des acquittements texte.

La classe reprend l'interface de RobotWifi (états, scans, bail de commande, journal) : l'interface
et les calculs de carte ne distinguent pas les deux liaisons. Aucun thread ne touche Tk.
"""
import struct
import threading
import time
import zlib
import numpy as np
from robot_wifi import (RobotWifi, TrameScan, HEADER, POINT, COMMANDS, DELAI_SANS_REPONSE, commande_simple, dernier)

DEBIT_INITIAL = 115200
DEBIT_DIRECT = 921600
# Puces USB-série des cartes ESP32 courantes : CP210x, CH340, FTDI, Espressif natif.
VID_CONNUS = (0x10C4, 0x1A86, 0x0403, 0x303A)
_TEXTES = (b'READY ', b'SA1 ', b'BUSY')
_DEBUTS = (b'SA06',)+_TEXTES


def lister_ports():
    """[(port, description)] des ports série présents."""
    from serial.tools import list_ports
    return [(p.device, p.description or '') for p in list_ports.comports()]


def trouver_port(demande='auto'):
    """Le port demandé, ou le seul port plausible quand la demande est vide ou « auto »."""
    demande = (demande or '').strip()
    if demande and demande.lower() != 'auto':
        return demande
    from serial.tools import list_ports
    ports = list_ports.comports()
    candidats = [p for p in ports if p.vid in VID_CONNUS] or list(ports)
    if not candidats:
        raise OSError('Aucun port USB trouvé : brancher le robot avec un câble de données.')
    if len(candidats) > 1:
        noms = ', '.join(p.device for p in candidats)
        raise OSError(f'Plusieurs ports possibles ({noms}) : écrire le bon dans le champ de connexion.')
    return candidats[0].device


def ouvrir_serie(port):
    """Ouvre le port sans activer DTR / RTS, pour ne pas redémarrer la carte à l'ouverture."""
    import serial
    liaison = serial.Serial()
    liaison.port = port
    liaison.baudrate = DEBIT_INITIAL
    liaison.timeout = .02
    liaison.write_timeout = 1.
    liaison.dtr = False
    liaison.rts = False
    liaison.open()
    return liaison


class DemuxFlux:
    """Sépare un flux binaire en trames SA06 valides et en lignes texte (READY, SA1, BUSY).

    Tout octet qui n'appartient ni à l'un ni à l'autre (journal de démarrage, trame abîmée) est
    ignoré jusqu'au prochain début reconnaissable, et compté dans `erreurs` quand une trame était
    annoncée mais invalide : un câble ou un débit douteux ne doit jamais insérer de points en carte.
    """
    def __init__(self):
        self.buffer = bytearray()
        self.erreurs = 0

    def recevoir(self, donnees):
        b = self.buffer
        b.extend(donnees)
        sortie = []
        while b:
            if b.startswith(b'SA06'):
                if len(b) < HEADER.size:
                    break
                _, version, flags, n, seq, fin, duree, taille = HEADER.unpack_from(b)
                if (version != 1 or flags or not 1 <= n <= 1200 or taille != n*POINT.size or
                        not 10_000 <= duree <= 1_000_000 or fin < duree):
                    self.erreurs += 1
                    del b[0]
                    continue
                total = HEADER.size+taille+4
                if len(b) < total:
                    break
                brut = bytes(b[:total])
                if zlib.crc32(brut[:-4]) != struct.unpack('<I', brut[-4:])[0]:
                    self.erreurs += 1
                    del b[0]
                    continue
                m = np.array(list(POINT.iter_unpack(brut[HEADER.size:-4])), dtype=float)
                if (m[:, 0] >= 36000).any():
                    self.erreurs += 1
                    del b[0]
                    continue
                m[:, 0] /= 100
                m[:, 1] /= 1000
                sortie.append(('trame', TrameScan(seq, fin, duree, m)))
                del b[:total]
                continue
            if any(b.startswith(p) for p in _TEXTES):
                fin = b.find(b'\n')
                if fin < 0:
                    if len(b) > 200:
                        self.erreurs += 1
                        del b[0]
                        continue
                    break
                sortie.append(('ligne', bytes(b[:fin]).decode('ascii', 'replace').strip()))
                del b[:fin+1]
                continue
            if any(p.startswith(bytes(b)) for p in _DEBUTS):
                break  # Début d'un marqueur encore incomplet.
            suivants = [i for i in (b.find(p, 1) for p in _DEBUTS) if i > 0]
            del b[:min(suivants) if suivants else max(1, len(b)-6)]
        return sortie


class RobotUsb(RobotWifi):
    """Robot relié par câble : même interface que RobotWifi, `hote` désigne le port (« COM8 » ou « auto »)."""

    def __init__(self, port='auto', debit=DEBIT_DIRECT, ouvrir=None, delai_connexion=6., attente_port=8.):
        super().__init__(hote=port)
        self.attente_port = attente_port
        self.debit = debit
        self._ouvrir = ouvrir or ouvrir_serie
        self.delai_connexion = delai_connexion
        self.erreurs_flux = 0

    def demarrer(self):
        if self.threads:
            raise RuntimeError('Client déjà démarré.')
        thread = threading.Thread(target=self._boucle, daemon=True)
        self.threads.append(thread)
        thread.start()

    # -- connexion ---------------------------------------------------------------------------
    def _poignee_de_main(self, liaison, flux):
        debut, dernier_envoi = time.monotonic(), 0.
        # Le firmware garde 6 s la session précédente (et son débit rapide) après une coupure : on essaie
        # donc tour à tour 115200 puis le débit rapide, pour le rejoindre quel que soit son état.
        debits = [DEBIT_INITIAL]+([self.debit] if self.debit != DEBIT_INITIAL else [])
        essai, change = 0, debut
        while not self.arret.is_set():
            t = time.monotonic()
            if len(debits) > 1 and t-change > 1.:
                essai, change = (essai+1) % len(debits), t
                liaison.baudrate = debits[essai]
                try:
                    liaison.reset_input_buffer()
                except AttributeError:
                    pass
                flux.buffer.clear()
            if t-debut > self.delai_connexion:
                raise TimeoutError('Le robot ne répond pas sur ce port : téléverser le firmware ScanAtlas_WiFi à jour '
                                   'et fermer le moniteur série d’Arduino.')
            if t-dernier_envoi >= .3:
                liaison.write(f'LIVE {self.session} {self.debit}\n'.encode('ascii'))
                dernier_envoi = t
            for genre, valeur in flux.recevoir(liaison.read(max(1, getattr(liaison, 'in_waiting', 0)))):
                if genre != 'ligne':
                    continue
                mots = valeur.split()
                if mots[:2] == ['READY', self.session]:
                    self.combine = mots[2:] == ['SA2']
                    return
                if mots[:1] == ['BUSY']:
                    raise ConnectionError('Robot déjà utilisé (session Wi-Fi ou autre programme) : le libérer d’abord.')

    # -- boucle principale -------------------------------------------------------------------
    def _boucle(self):
        liaison, seq = None, 0
        try:
            liaison = self._ouvrir_avec_attente()
            flux = DemuxFlux()
            self._poignee_de_main(liaison, flux)
            if self.debit != DEBIT_INITIAL:
                liaison.baudrate = self.debit
            try:
                liaison.reset_input_buffer()
            except AttributeError:
                pass
            flux = DemuxFlux()
            self._etat('Connecté au robot par câble ; moteurs arrêtés.')
            self.connecte.set()
            ack = debut = dernier_envoi = time.monotonic()
            dernier_flux = debut
            suite, envois, acquitte = None, {}, 0
            while not self.arret.is_set():
                t = time.monotonic()
                if t-dernier_envoi >= .04:
                    dernier_envoi = t
                    seq += 1
                    liaison.write(self._ligne_commande(seq, t).encode('ascii'))
                    envois[seq] = t
                    envois = {n: d for n, d in envois.items() if t-d < .5}
                for genre, valeur in flux.recevoir(liaison.read(max(1, getattr(liaison, 'in_waiting', 0)))):
                    if genre == 'trame':
                        if suite is not None and (valeur.sequence <= suite[0] or valeur.fin_us <= suite[1]):
                            raise ValueError('Scan ancien ou redémarrage ESP32 : reconnecter.')
                        suite = (valeur.sequence, valeur.fin_us)
                        self._noter_pause('scan', time.monotonic()-dernier_flux)
                        self.dernier_scan = dernier_flux = time.monotonic()
                        if self.journal is not None:
                            self.journal.brut(valeur)
                        self.recus += 1
                        dernier(self.scans, valeur)
                        continue
                    mots = valeur.split()
                    if len(mots) == 4 and mots[:2] == ['SA1', self.session] and mots[2].isdigit() and mots[3] in COMMANDS:
                        numero = int(mots[2])
                        if acquitte < numero <= seq and numero in envois and time.monotonic()-envois[numero] < .5:
                            acquitte = numero
                            self._noter_pause('acquittement', time.monotonic()-ack)
                            ack = time.monotonic()
                            with self.lock:
                                self.effective, self.date_ack = mots[3], ack
                    elif mots[:1] == ['BUSY']:
                        raise ConnectionError('Robot déjà utilisé par une autre session.')
                self.erreurs_flux = flux.erreurs
                if time.monotonic()-ack > DELAI_SANS_REPONSE:
                    raise TimeoutError('Robot sans réponse : commande arrêtée, reconnecter.')
                if time.monotonic()-dernier_flux > DELAI_SANS_REPONSE:
                    raise TimeoutError('Flux lidar interrompu ; moteurs arrêtés.')
        except (OSError, ValueError, UnicodeError) as exc:
            self._etat(str(exc))
        finally:
            self.bail.actualiser('STOP')
            if liaison is not None:
                try:  # Redondance : le bail du firmware reste l'arrêt indépendant.
                    for _ in range(3):
                        seq += 1
                        liaison.write(f'SA1 {self.session} {seq} STOP 0\n'.encode('ascii'))
                    liaison.write(b'LIVE_STOP\n')
                    liaison.flush()
                except (OSError, ValueError, AttributeError):
                    pass
                try:
                    liaison.close()
                except OSError:
                    pass
            self.connecte.clear()
            self.arret.set()

    def _trouver(self):
        return trouver_port(self.hote)

    def _ouvrir_avec_attente(self):
        """Ouvre le port ; après une coupure, Windows met quelques secondes à le rendre (« Accès refusé »,
        port absent le temps que l'ESP32 redémarre) : on réessaie plutôt que d'échouer tout de suite."""
        fin = time.monotonic()+self.attente_port
        premier = True
        while True:
            try:
                port = self._trouver()
                if premier:
                    self._etat(f'Ouverture de {port}…')
                return self._ouvrir(port)
            except OSError as exc:
                if self.arret.is_set() or time.monotonic() >= fin:
                    raise
                if premier:
                    self._etat('Port USB pas encore disponible (le robot redémarre ?) : nouvel essai automatique…')
                    premier = False
                self.arret.wait(.5)

    def _ligne_commande(self, seq, t):
        cmd, pwm, vecteur = self.bail.lire_complet(t)
        if t-self.dernier_scan > .6:
            cmd, vecteur = 'STOP', (0, 0, 0)
        simple = commande_simple(vecteur) if cmd == 'DRIVE' else None
        if cmd == 'DRIVE' and simple is None and not self.combine:
            axe = max(range(3), key=lambda i: abs(vecteur[i]))
            simple = commande_simple(tuple(v if i == axe else 0 for i, v in enumerate(vecteur)))
            if not self.avis_combine:
                self.avis_combine = True
                self._etat('Firmware sans déplacement combiné : seul l’axe dominant est envoyé. Reflasher ScanAtlas_WiFi.')
        if simple is not None:
            cmd, pwm = simple
        with self.lock:
            self.envoyee = cmd
        if cmd == 'DRIVE':
            return f'SA2 {self.session} {seq} {vecteur[0]} {vecteur[1]} {vecteur[2]}\n'
        return f'SA1 {self.session} {seq} {cmd} {pwm}\n'
