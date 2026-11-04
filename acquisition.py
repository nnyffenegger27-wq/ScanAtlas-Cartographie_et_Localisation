"""Capture du CSV ESP32 : le microcontrôleur décode déjà les trames LD06.
Aucun accès à l'interface graphique dans ce module.
"""
import time
import numpy as np
from cartographie import Scan, ANGLE_REFERENCE_DEFAUT, diagnostic_scan


class AssembleurCSV:
    """Attend un indice 0 et refuse les trous/doublons ; ignore le démarrage partiel."""
    def __init__(self):
        self.points = []
        self.attend_zero = True
        self.rejets = 0

    def ajouter(self, ligne):
        ligne = ligne.strip()
        if not ligne:
            if not self.attend_zero and len(self.points) >= 20:
                resultat = np.array(self.points)
                self.points, self.attend_zero = [], True
                return resultat
            self.points, self.attend_zero = [], True
            return None
        if ligne.startswith('N,'):
            return None
        try:
            v = [float(x) for x in ligne.split(',')]
            if len(v) != 6 or not np.isfinite(v).all():
                raise ValueError()
            i, a, d, intensite, _, _ = v
            if i != int(i) or i < 0 or d < 0 or not 0 <= intensite <= 255:
                raise ValueError()
        except ValueError:
            self.rejets += 1
            self.points, self.attend_zero = [], True
            return None
        if i == 0:
            # Un zéro sans séparateur termine aussi le scan précédent.
            resultat = np.array(self.points) if not self.attend_zero and len(self.points) >= 20 else None
            self.points = [[a % 360, d/1000., intensite]]
            self.attend_zero = False
            return resultat
        if self.attend_zero:
            return None
        if i != len(self.points):
            self.rejets += 1
            self.points, self.attend_zero = [], True
            return None
        self.points.append([a % 360, d/1000., intensite])
        return None


def capturer(port, baud, quantite, annuler, progression, delai=40, demander_scan=False):
    """À appeler dans un thread. Une ligne incomplète reste en tampon.

    Chaque résultat couvre au moins 340°. Les blocs multiples sont conservés ; cela ne garantit
    pas l'absence de pertes de trames binaires en amont de l'ESP32.
    """
    import serial
    scans, tampon, assembleur = [], bytearray(), AssembleurCSV()
    debut = time.monotonic()
    with serial.Serial(port, baudrate=baud, timeout=.2) as liaison:
        if demander_scan and annuler.wait(1.8):return []
        liaison.reset_input_buffer()
        if demander_scan:liaison.write(f'SCAN {quantite}\n'.encode('ascii'))
        try:
            while len(scans) < quantite:
                if annuler.is_set():
                    return []
                if time.monotonic()-debut > delai:
                    raise TimeoutError(f'{len(scans)}/{quantite} scans reçus en {delai}s ; '
                                       f'{assembleur.rejets} lignes/blocs rejetés. Vérifie le baud et la sortie CSV.')
                tampon.extend(liaison.read(liaison.in_waiting or 1))
                if len(tampon) > 65536:
                    raise ValueError('Aucune fin de ligne reconnue : vérifie le baud.')
                while b'\n' in tampon:
                    ligne, _, reste = tampon.partition(b'\n')
                    tampon = bytearray(reste)
                    try:
                        donnees = assembleur.ajouter(ligne.decode('ascii'))
                    except UnicodeDecodeError:
                        assembleur.ajouter('ERREUR ENCODAGE')
                        continue
                    if donnees is not None:
                        # Angles déjà mathématiques : ils décroissent dans le flux.
                        diagnostic = diagnostic_scan(donnees)
                        if diagnostic['etendue'] < 340.:
                            assembleur.rejets += 1
                            progression(f"Bloc rejeté : {diagnostic['etat']} ({diagnostic['etendue']:.1f}°)")
                            continue
                        scans.append(Scan(f'USB {len(scans)+1}', donnees, source='Acquisition USB réelle',
                                          angle_reference=ANGLE_REFERENCE_DEFAUT))
                        detail = f" · {diagnostic['etat']} conservé à pose unique" if not diagnostic['tour_plausible'] else ''
                        progression(f'{len(scans)}/{quantite} scans reçus' + detail)
                        if len(scans) >= quantite:
                            break
        finally:
            if demander_scan:
                try:liaison.write(b'SCAN 0\n')
                except OSError:pass
    return scans



def capturer_wifi(hote, quantite, annuler, progression, delai=40,
                  port_commande=4210, port_scans=4211):
    """Capture brute sans recalage, uniquement commandes STOP ; mesures préservées."""
    import queue
    from robot_wifi import RobotWifi
    if not 1 <= quantite <= 20:
        raise ValueError('Choisir entre 1 et 20 scans.')
    robot = RobotWifi(hote, port_commande, port_scans)
    scans = []
    if annuler.wait(.4):  # Expiration du bail de l'ancienne connexion.
        return scans
    debut = time.monotonic()
    try:
        robot.demarrer()
        while len(scans) < quantite:
            if annuler.is_set():
                return []
            if robot.arret.is_set():
                messages = list(robot.etats.queue)
                raise ConnectionError(messages[-1] if messages else 'Connexion Wi-Fi interrompue.')
            if time.monotonic()-debut > delai:
                raise TimeoutError(f'{len(scans)}/{quantite} scans reçus ; vérifier le Wi-Fi.')
            try:
                trame = robot.scans.get(timeout=.1)
            except queue.Empty:
                continue
            scan = trame.scan()
            scan.source = 'Acquisition Wi-Fi réelle — scan brut'
            scans.append(scan)
            progression(f'{len(scans)}/{quantite} scans Wi-Fi reçus')
        return scans
    finally:
        robot.fermer()
        for thread in robot.threads:
            thread.join(2.5)
        time.sleep(.35)
