"""Direct filaire : démultiplexage du flux, client USB contre un faux firmware, logique C++ de la session."""
import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from robot_wifi import encoder_trame
from robot_usb import DemuxFlux, RobotUsb, DEBIT_INITIAL, DEBIT_DIRECT, trouver_port

DOSSIER = Path(__file__).resolve().parents[1]/'firmware/ScanAtlas_WiFi'


def trame(sequence=1, fin_us=200_000, points=40):
    angles = np.linspace(0, 359, points)
    return encoder_trame(sequence, fin_us, 100_000, np.column_stack([angles, np.full(points, 1.5), np.full(points, 100)]))


class DemuxTests(unittest.TestCase):
    def test_trames_et_lignes_en_morceaux_et_avec_bruit(self):
        flux = DemuxFlux()
        t1, t2 = trame(1, 200_000), trame(2, 300_000)
        donnees = (b'[1234 ms] bruit de demarrage\n' + b'READY ' + b'a'*32 + b' SA2\n' + t1 +
                   b'SA1 ' + b'a'*32 + b' 7 STOP\n' + t2)
        sortie = []
        for i in range(0, len(donnees), 37):          # lecture par petits morceaux arbitraires
            sortie += flux.recevoir(donnees[i:i+37])
        self.assertEqual([g for g, _ in sortie], ['ligne', 'trame', 'ligne', 'trame'])
        self.assertEqual(sortie[0][1], 'READY '+'a'*32+' SA2')
        self.assertEqual([x.sequence for g, x in sortie if g == 'trame'], [1, 2])
        self.assertEqual(flux.erreurs, 0)

    def test_trame_corrompue_ignoree_puis_resynchronisation(self):
        flux = DemuxFlux()
        mauvaise = bytearray(trame(1, 200_000))
        mauvaise[40] ^= 0xFF                           # un octet abîmé : CRC invalide
        sortie = flux.recevoir(bytes(mauvaise) + trame(2, 300_000))
        self.assertEqual([x.sequence for g, x in sortie if g == 'trame'], [2])   # la bonne trame suivante passe
        self.assertGreater(flux.erreurs, 0)

    def test_debit_incoherent_ne_produit_rien(self):
        flux = DemuxFlux()
        self.assertEqual(flux.recevoir(bytes([0xFF, 0x00, 0x55, 0xAA])*500), [])
        self.assertEqual(flux.recevoir(trame(5, 900_000))[0][1].sequence, 5)

    def test_marqueur_coupe_en_deux(self):
        flux = DemuxFlux()
        t = trame(3, 400_000)
        self.assertEqual(flux.recevoir(t[:2]), [])
        self.assertEqual(len(flux.recevoir(t[2:])), 1)


class FauxFirmware:
    """Reproduit le comportement du firmware côté liaison filaire, y compris le débit."""
    def __init__(self, occupe=False, muet=False, trames=None, ancienne_session=False, grace=6.):
        self.occupe, self.muet, self.max_trames, self.grace = occupe, muet, trames, grace
        self.debit = DEBIT_INITIAL
        self.actif, self.jeton, self.dernier_ordre = False, None, 0.
        if ancienne_session:   # session d'un PC disparu, encore ouverte au débit rapide depuis 2 s
            self.actif, self.jeton, self.debit = True, 'ancienne', DEBIT_DIRECT
            self.dernier_ordre = time.monotonic()-2.
        self.vecteur, self.mouvement = (0, 0, 0), 'STOP'
        self.port, self.tampon = None, bytearray()
        self.sequence, self.fin = 0, 200_000
        self.stop = threading.Event()
        threading.Thread(target=self._vie, daemon=True).start()

    def emettre(self, donnees):
        if self.port is not None:
            junk = bytes([0xFF, 0x00, 0x55])*(len(donnees)//3+1)
            self.port.recevoir(donnees if self.port.baudrate == self.debit else junk)

    def recevoir(self, donnees, debit_pc):
        if debit_pc != self.debit or self.muet:
            return
        self.tampon.extend(donnees)
        while b'\n' in self.tampon:
            ligne, _, reste = bytes(self.tampon).partition(b'\n')
            self.tampon = bytearray(reste)
            self._ligne(ligne.decode('ascii', 'replace').strip())

    def _ligne(self, ligne):
        mots = ligne.split()
        if mots[:1] == ['LIVE'] and len(mots) == 3:
            if self.occupe or (self.actif and self.jeton != mots[1] and time.monotonic()-self.dernier_ordre <= 1.):
                return self.emettre(b'BUSY\n')
            self.emettre(f'READY {mots[1]} SA2\n'.encode())
            self.jeton, self.actif, self.dernier_ordre = mots[1], True, time.monotonic()
            self.debit = int(mots[2])        # le firmware passe au nouveau débit juste après READY
        elif ligne == 'LIVE_STOP':
            self._fermer()
        elif self.actif and mots[:1] in (['SA1'], ['SA2']) and mots[1] == self.jeton:
            self.dernier_ordre = time.monotonic()
            if mots[0] == 'SA2':
                self.vecteur, self.mouvement = tuple(int(v) for v in mots[3:6]), 'DRIVE'
            else:
                self.vecteur, self.mouvement = (0, 0, 0), mots[3]
            self.emettre(f'SA1 {self.jeton} {mots[2]} {self.mouvement}\n'.encode())

    def _fermer(self):
        self.actif, self.debit, self.vecteur, self.mouvement = False, DEBIT_INITIAL, (0, 0, 0), 'STOP'

    def _vie(self):
        while not self.stop.wait(.1):
            age = time.monotonic()-self.dernier_ordre
            if self.actif and age > self.grace:
                self._fermer()                # session morte : retour à 115200
                continue
            if self.actif and age > .3:
                self.vecteur, self.mouvement = (0, 0, 0), 'STOP'   # moteurs coupés, session gardée
            if self.actif and (self.max_trames is None or self.sequence < self.max_trames):
                self.sequence += 1
                self.fin += 100_000
                self.emettre(trame(self.sequence, self.fin))


class FauxSerie:
    def __init__(self, firmware):
        self.firmware, self.baudrate, self.ferme = firmware, DEBIT_INITIAL, False
        self._rx, self._lock = bytearray(), threading.Lock()
        firmware.port = self

    @property
    def in_waiting(self):
        with self._lock:
            return len(self._rx)

    def recevoir(self, donnees):
        with self._lock:
            self._rx.extend(donnees)

    def read(self, n=1):
        fin = time.monotonic()+.02
        while time.monotonic() < fin:
            with self._lock:
                if self._rx:
                    sortie = bytes(self._rx[:n])
                    del self._rx[:n]
                    return sortie
            time.sleep(.002)
        return b''

    def write(self, donnees):
        self.firmware.recevoir(bytes(donnees), self.baudrate)
        return len(donnees)

    def flush(self):
        pass

    def reset_input_buffer(self):
        with self._lock:
            self._rx.clear()

    def close(self):
        self.ferme = True


def messages(robot):
    """Tous les messages d'état émis par le robot, dans l'ordre."""
    sortie = []
    while not robot.etats.empty():
        sortie.append(robot.etats.get_nowait())
    return sortie


def attendre(predicat, delai=5.):
    fin = time.monotonic()+delai
    while time.monotonic() < fin:
        if predicat():
            return True
        time.sleep(.01)
    return False


class RobotUsbTests(unittest.TestCase):
    def setUp(self):
        self.a_fermer, self.firmwares = [], []

    def tearDown(self):
        for r in self.a_fermer:
            r.fermer()
        for f in self.firmwares:
            f.stop.set()

    def creer(self, delai_connexion=6., **options):
        firmware = FauxFirmware(**options)
        serie = FauxSerie(firmware)
        robot = RobotUsb('COM9', ouvrir=lambda port: serie, delai_connexion=delai_connexion)
        self.a_fermer.append(robot)
        self.firmwares.append(firmware)
        return robot, serie, firmware

    def test_connexion_changement_de_debit_scans_et_commandes(self):
        robot, serie, fw = self.creer()
        robot.demarrer()
        self.assertTrue(attendre(robot.connecte.is_set))
        self.assertEqual((serie.baudrate, fw.debit), (DEBIT_DIRECT, DEBIT_DIRECT))
        self.assertTrue(robot.combine)
        self.assertTrue(attendre(lambda: robot.recus >= 3))             # les tours arrivent, au bon débit
        self.assertGreater(robot.dernier_scan, 0)
        self.assertEqual(len(robot.scans.get(timeout=1).mesures), 40)
        robot.conduire(40, 0, -25)                                       # combiné : SA2
        self.assertTrue(attendre(lambda: fw.vecteur == (40, 0, -25)))
        self.assertTrue(attendre(lambda: robot.diagnostic_commande()['effective'] == 'DRIVE'))
        robot.conduire(60, 0, 0)                                         # un seul axe : SA1 compatible
        self.assertTrue(attendre(lambda: fw.mouvement == 'FORWARD'))
        robot.conduire(0, 0, 0)
        self.assertTrue(attendre(lambda: fw.mouvement == 'STOP'))

    def test_reprise_sur_une_session_rapide_restee_ouverte(self):
        # Le PC précédent a disparu sans LIVE_STOP : le firmware est encore au débit rapide, session ouverte.
        # La poignée de main essaie les deux débits et remplace la session muette (plus de « Robot déjà utilisé »).
        robot, serie, fw = self.creer(ancienne_session=True, delai_connexion=8.)
        robot.demarrer()
        self.assertTrue(attendre(robot.connecte.is_set, 8.))
        self.assertEqual((serie.baudrate, fw.debit, fw.jeton), (DEBIT_DIRECT, DEBIT_DIRECT, robot.session))
        self.assertTrue(attendre(lambda: robot.recus >= 2))

    def test_trou_de_liaison_ne_ferme_plus_la_session(self):
        # Le firmware coupe les moteurs après 300 ms sans commande mais garde la session : le PC, lui,
        # voit simplement une pause et reprend sans reconnexion.
        robot, serie, fw = self.creer()
        robot.demarrer()
        self.assertTrue(attendre(robot.connecte.is_set))
        robot.conduire(40, 0, 0)
        self.assertTrue(attendre(lambda: fw.mouvement in ('DRIVE', 'FORWARD')))
        ecrire = serie.write
        serie.write = lambda donnees: len(donnees)             # le câble « avale » les commandes 0,8 s
        self.assertTrue(attendre(lambda: fw.mouvement == 'STOP'))
        time.sleep(.5)
        self.assertTrue(fw.actif and fw.debit == DEBIT_DIRECT and robot.connecte.is_set())
        serie.write = ecrire
        robot.conduire(40, 0, 0)
        self.assertTrue(attendre(lambda: fw.mouvement in ('DRIVE', 'FORWARD')))
        self.assertTrue(robot.connecte.is_set())

    def test_fermeture_arrete_les_moteurs_et_rend_le_debit_historique(self):
        robot, serie, fw = self.creer()
        robot.demarrer()
        self.assertTrue(attendre(robot.connecte.is_set))
        self.assertTrue(attendre(lambda: robot.recus >= 2))
        robot.conduire(50, 0, 0)
        self.assertTrue(attendre(lambda: fw.mouvement in ('DRIVE', 'FORWARD')))
        robot.fermer()
        self.assertTrue(attendre(lambda: serie.ferme))
        self.assertEqual((fw.mouvement, fw.debit, fw.actif), ('STOP', DEBIT_INITIAL, False))
        self.assertFalse(robot.connecte.is_set())

    def test_pas_de_commande_sans_flux_lidar_recent(self):
        robot, serie, fw = self.creer(trames=2)                          # le lidar se tait après 2 tours
        robot.demarrer()
        self.assertTrue(attendre(robot.connecte.is_set))
        self.assertTrue(attendre(lambda: robot.recus >= 2))
        time.sleep(.9)                                                   # flux périmé (> 0,6 s)
        robot.conduire(70, 0, 0)
        time.sleep(.3)
        self.assertEqual(fw.vecteur, (0, 0, 0))

    def test_firmware_muet_message_explicite(self):
        robot, serie, fw = self.creer(muet=True, delai_connexion=.6)
        robot.demarrer()
        self.assertTrue(attendre(robot.arret.is_set, 4))
        message = messages(robot)[-1]
        self.assertIn('ne répond pas', message)
        self.assertIn('firmware', message)
        self.assertTrue(attendre(lambda: serie.ferme))

    def test_robot_deja_utilise(self):
        robot, serie, fw = self.creer(occupe=True)
        robot.demarrer()
        self.assertTrue(attendre(robot.arret.is_set, 4))
        self.assertIn('déjà utilisé', messages(robot)[-1])

    def test_flux_lidar_interrompu_detecte(self):
        robot, serie, fw = self.creer(trames=2)
        robot.demarrer()
        self.assertTrue(attendre(robot.connecte.is_set))
        self.assertTrue(attendre(robot.arret.is_set, 6))
        dits = messages(robot)
        self.assertTrue(any('interrompu' in m or 'sans réponse' in m for m in dits), dits)

    def test_choix_du_port(self):
        self.assertEqual(trouver_port('COM3'), 'COM3')
        self.assertEqual(trouver_port('  /dev/ttyUSB0 '), '/dev/ttyUSB0')


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Écran Tk requis')
class InterfaceUsb(unittest.TestCase):
    def test_choix_de_la_liaison_et_connexion_usb(self):
        from app import Atelier
        app = Atelier(); app.geometry('1500x950')
        firmware = FauxFirmware()
        serie = FauxSerie(firmware)
        try:
            app.onglets.select(app.wifi_cadre); app.update()
            self.assertEqual(app.wifi_liaison.get(), 'Wi-Fi'); self.assertEqual(app.wifi_hote.get(), '192.168.4.1')
            app.wifi_liaison.set('USB filaire'); app.wifi_liaison_changer()
            self.assertEqual(app.wifi_hote.get(), 'auto')                       # port choisi automatiquement
            app.wifi_hote.set('COM8'); app.wifi_liaison.set('Wi-Fi'); app.wifi_liaison_changer()
            self.assertEqual(app.wifi_hote.get(), '192.168.4.1')                # COM8 n'est pas une adresse : retour au Wi-Fi
            app.wifi_hote.set('10.0.0.5'); app.wifi_liaison.set('USB filaire'); app.wifi_liaison_changer()
            self.assertEqual(app.wifi_hote.get(), '10.0.0.5')                   # une saisie personnalisée n'est pas écrasée
            app.wifi_hote.set('COM9')
            with patch('interface_wifi.RobotUsb', side_effect=lambda hote: RobotUsb(hote, ouvrir=lambda port: serie)):
                app.wifi_connecter()
                self.assertIsInstance(app.wifi_robot, RobotUsb)
                self.assertEqual(app.wifi_robot.hote, 'COM9')
                fin = time.monotonic()+5
                while time.monotonic() < fin and not (app.wifi_robot and app.wifi_robot.connecte.is_set() and app.wifi_robot.recus >= 2):
                    app.update(); time.sleep(.01)
                self.assertTrue(app.wifi_robot.connecte.is_set())
                self.assertGreaterEqual(app.wifi_robot.recus, 2)
                app.wifi_pilotage()
                self.assertTrue(app.wifi_encart._connecte)                      # fond « connecté » aussi en filaire
        finally:
            app.wifi_deconnecter(); app.destroy(); firmware.stop.set()


class FirmwareLiveCpp(unittest.TestCase):
    def test_analyse_et_etat_de_session(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d/'main.cpp').write_text(r'''#include "usb_live.h"
#include <cassert>
int main(){
  const char *t="0123456789abcdef0123456789abcdef", *u="fedcba9876543210fedcba9876543210";
  char s[96];LiveRequest r;
  snprintf(s,sizeof s,"LIVE %s 921600",t);assert(parseLive(s,r)&&r.baud==921600&&!strcmp(r.token,t));
  snprintf(s,sizeof s,"LIVE %s 115200",t);assert(parseLive(s,r)&&r.baud==115200);
  snprintf(s,sizeof s,"LIVE %s 12345",t);assert(!parseLive(s,r));            // débit non autorisé
  snprintf(s,sizeof s,"LIVE %s 921600 x",t);assert(!parseLive(s,r));          // texte en trop
  snprintf(s,sizeof s,"LIVE %s",t);assert(!parseLive(s,r));
  assert(!parseLive("LIVE court 921600",r));assert(!parseLive("SCAN 5",r));
  assert(isLiveStop("LIVE_STOP")&&!isLiveStop("LIVE_STOPX")&&!isLiveStop("LIVE"));
  UsbLive live;snprintf(s,sizeof s,"LIVE %s 921600",t);parseLive(s,r);
  assert(!live.active&&!live.owns(t));
  assert(live.open(r,1000)==UsbLive::OPENED&&live.active&&live.owns(t)&&!live.owns(u));
  assert(live.open(r,1010)==UsbLive::AGAIN);
  LiveRequest autre=r;strcpy(autre.token,u);assert(live.open(autre,1020)==UsbLive::REFUSED);
  assert(!live.fresh(1100));                                                    // pas de tour : pas de mouvement
  live.lastFrame=1100;assert(live.fresh(1500)&&!live.fresh(1800));
  // Bail : la première commande doit être un arrêt, puis le bail expire après 300 ms.
  Command c;snprintf(s,sizeof s,"SA2 %s 1 50 0 0",t);assert(parseCommand(s,c));
  assert(!live.lease.accept(c,1050));                                           // mouvement avant tout STOP : refusé
  snprintf(s,sizeof s,"SA1 %s 2 STOP 0",t);assert(parseCommand(s,c)&&live.lease.accept(c,1060));
  snprintf(s,sizeof s,"SA2 %s 3 50 0 -20",t);assert(parseCommand(s,c)&&live.lease.accept(c,1100)&&c.vx==50&&c.w==-20);
  assert(!live.lease.expired(1350)&&live.lease.expired(1401));
  assert(!live.lease.dead(1401)&&live.lease.silent(2101)&&!live.lease.silent(2000)&&live.lease.dead(7101));
  snprintf(s,sizeof s,"SA2 %s 4 50 0 0",t);assert(parseCommand(s,c)&&live.lease.accept(c,3000)&&live.lease.resumed);
  live.close();assert(!live.active&&live.baud==115200&&!live.owns(t));
  assert(live.open(r,2000)==UsbLive::OPENED);                                    // réutilisable après fermeture
  return 0;
}
''')
            r = subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-I', str(DOSSIER), str(d/'main.cpp'), '-o', str(d/'t')],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            subprocess.run([str(d/'t')], check=True, capture_output=True)


# Faux en-têtes minimaux : seule la syntaxe du sketch est vérifiée, rien ne s'exécute.
STUBS = {'Arduino.h': '#pragma once\n#include <cstdint>\n#include <cstdio>\n#include <cstring>\n#include <cstdarg>\n#include <cmath>\n#include <algorithm>\nusing std::min; using std::max;\n#define OUTPUT 1\n#define INPUT 0\n#define HIGH 1\n#define LOW 0\n#define SERIAL_8N1 0\nvoid pinMode(int,int);void digitalWrite(int,int);void delay(unsigned long);unsigned long millis();\ndouble ledcSetup(int,int,int);void ledcAttachPin(int,int);void ledcWrite(int,unsigned);\nstruct SerialPort{\n  void begin(unsigned long,int=0,int=0,int=0);int available();int read();size_t write(const uint8_t*,size_t);\n  void println(const char*);void println();void print(const char*);template<class T> void print(T){} template<class T> void println(T){}\n  int printf(const char*,...) __attribute__((format(printf,2,3)));void flush();void updateBaudRate(unsigned long);\n  void setRxBufferSize(size_t);\n};\nextern SerialPort Serial,Serial2;\n', 'esp_arduino_version.h': '#define ESP_ARDUINO_VERSION_MAJOR 2\n', 'esp_timer.h': '#pragma once\n#include <cstdint>\nint64_t esp_timer_get_time();\n', 'esp_system.h': '#pragma once\nenum esp_reset_reason_t{ESP_RST_POWERON,ESP_RST_EXT,ESP_RST_SW,ESP_RST_PANIC,ESP_RST_INT_WDT,ESP_RST_TASK_WDT,ESP_RST_WDT,ESP_RST_DEEPSLEEP,ESP_RST_BROWNOUT,ESP_RST_SDIO,ESP_RST_UNKNOWN};\nesp_reset_reason_t esp_reset_reason();\n', 'freertos/semphr.h': '#pragma once\n#include <cstdint>\n#include <cstddef>\ntypedef void* SemaphoreHandle_t; typedef void* QueueHandle_t; typedef int BaseType_t;\n#define portMAX_DELAY 0xffffffffu\n#define pdTRUE 1\n#define pdPASS 1\n#define pdMS_TO_TICKS(x) (x)\nBaseType_t xSemaphoreTake(SemaphoreHandle_t,uint32_t);void xSemaphoreGive(SemaphoreHandle_t);SemaphoreHandle_t xSemaphoreCreateMutex();\nQueueHandle_t xQueueCreate(int,size_t);BaseType_t xQueueReceive(QueueHandle_t,void*,uint32_t);void xQueueReset(QueueHandle_t);void xQueueOverwrite(QueueHandle_t,const void*);\nBaseType_t xTaskCreate(void(*)(void*),const char*,int,void*,int,void*);void vTaskDelay(uint32_t);\n', 'WiFi.h': '#pragma once\n#include <Arduino.h>\nstruct IPAddress{IPAddress(){} IPAddress(int,int,int,int){} bool operator==(const IPAddress&)const{return true;}};\ntypedef int WiFiEvent_t;\n#define ARDUINO_EVENT_WIFI_AP_STACONNECTED 1\n#define ARDUINO_EVENT_WIFI_AP_STADISCONNECTED 2\nstruct ApEv{uint8_t mac[6];};\nunion WiFiEventInfo_t{ApEv wifi_ap_staconnected;ApEv wifi_ap_stadisconnected;};\n#define WIFI_AP 1\nstruct WiFiClass{\n  void mode(int);void setSleep(bool);bool softAPConfig(IPAddress,IPAddress,IPAddress);bool softAP(const char*,const char*,int,int,int);IPAddress softAPIP();\n  void onEvent(void(*)(WiFiEvent_t,WiFiEventInfo_t),WiFiEvent_t);\n};\nextern WiFiClass WiFi;\nstruct WiFiUDP{void begin(uint16_t);int parsePacket();int read(char*,size_t);IPAddress remoteIP();uint16_t remotePort();void beginPacket(IPAddress,uint16_t);size_t write(const uint8_t*,size_t);void endPacket();};\nstruct WiFiClient{void setNoDelay(bool);void setTimeout(int);bool connected();int available();int read();size_t write(const uint8_t*,size_t);void stop();IPAddress remoteIP();operator bool();};\nstruct WiFiServer{WiFiServer(uint16_t);void begin();WiFiClient available();};\n', 'WiFiUdp.h': '#pragma once\n'}


class SketchSyntaxe(unittest.TestCase):
    """Le sketch .ino est compilé (syntaxe seule) contre de faux en-têtes Arduino/ESP32, avec chaque pilote."""
    def test_syntaxe_pour_les_deux_pilotes(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for nom, contenu in STUBS.items():
                (d/nom).parent.mkdir(exist_ok=True)
                (d/nom).write_text(contenu)
            (d/'main.cpp').write_text('#include <Arduino.h>\n#include <WiFi.h>\n#include "ScanAtlas_WiFi.ino"\n')
            for pilote in (1, 2):
                r = subprocess.run(['g++', '-std=gnu++11', '-fsyntax-only', '-Wall', '-Wextra', '-Wno-unused-parameter',
                                    '-Wno-misleading-indentation', '-I', str(d), '-I', str(DOSSIER), f'-DMOTOR_DRIVER={pilote}',
                                    str(d/'main.cpp')], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stderr.strip(), '', r.stderr)


if __name__ == '__main__':
    unittest.main()
