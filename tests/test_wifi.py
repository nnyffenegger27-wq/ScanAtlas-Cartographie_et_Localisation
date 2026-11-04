import copy
import queue
import socket
import struct
import subprocess
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
from atlas.calcul.cartographie import Scan
from atlas.robot.robot_wifi import (BailCommande, DecodeurScans, encoder_trame, TrameScan,
                        RobotWifi, dernier, valider_vecteur)
from atlas.calcul.cartographie_direct import CarteDirecte
from atlas.calcul.localisation import erreur_pose


def salle():
    return np.vstack([np.column_stack([np.linspace(-3,4,100),np.full(100,3.)]),
                      np.column_stack([np.full(90,4.),np.linspace(-2,3,90)]),
                      np.column_stack([np.linspace(-3,4,100),np.full(100,-2.)]),
                      np.column_stack([np.full(90,-3.),np.linspace(-2,3,90)]),
                      np.column_stack([np.linspace(.4,1.4,30),np.full(30,.8)])])


def trame_pose(pose, seq, fin=None):
    p=salle();a=np.deg2rad(pose[2]);R=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
    p=(p-np.asarray(pose[:2]))@R
    angles=np.rad2deg(np.arctan2(p[:,1],p[:,0]))%360
    m=np.column_stack([angles,np.linalg.norm(p,axis=1),np.full(len(p),230.)])
    m=m[np.argsort(angles)]
    return TrameScan(seq, 1_000_000+seq*100000 if fin is None else fin,100000,m)


class Protocole(unittest.TestCase):
    def test_fragmentation_concat_et_unites(self):
        m=np.array([[1.23,2.345,220],[359.9,12.,255]])
        raw=encoder_trame(7,1000000,100000,m)
        d=DecodeurScans();out=[]
        for b in raw*2:out.extend(d.recevoir(bytes([b])))
        self.assertEqual(len(out),2);self.assertEqual(out[0].sequence,7)
        np.testing.assert_allclose(out[0].mesures,m)

    def test_crc_taille_version_et_horodatage(self):
        raw=encoder_trame(1,1000000,100000,[[0,1,10]])
        for idx in [0,4,5,6,24,27,-1]:
            bad=bytearray(raw);bad[idx]^=255
            with self.assertRaises(ValueError):DecodeurScans().recevoir(bad)
        with self.assertRaises(ValueError):DecodeurScans().recevoir(encoder_trame(1,100,100000,[[0,1,1]]))

    def test_file_ne_garde_que_le_plus_recent(self):
        q=queue.Queue(maxsize=1)
        for i in range(100):dernier(q,i)
        self.assertEqual(q.qsize(),1);self.assertEqual(q.get(),99)

    def test_bail_expire_apres_le_delai(self):
        bail=BailCommande();bail.actualiser('FORWARD',65,maintenant=10)
        self.assertEqual(bail.lire(10.1)[0],'FORWARD')
        self.assertEqual(bail.lire(10.3)[0],'STOP')

    def test_bail_vecteur_expire_et_vecteur_nul_est_un_arret(self):
        bail=BailCommande()
        bail.actualiser('DRIVE',60,maintenant=10,vecteur=(60,-30,15))
        self.assertEqual(bail.lire_complet(10.1),('DRIVE',60,(60,-30,15)))
        self.assertEqual(bail.lire_complet(10.3)[0::2],('STOP',(0,0,0)))
        bail.actualiser('DRIVE',0,maintenant=20,vecteur=(0,0,0))
        self.assertEqual(bail.lire(20.1)[0],'STOP')
        for mauvais in [(101,0,0),(0,-101,0),(0,0,float('nan')),(0,0,float('inf'))]:
            with self.assertRaises(ValueError):bail.actualiser('DRIVE',50,vecteur=mauvais)
        with self.assertRaises(ValueError):valider_vecteur('a',0,0)
        self.assertEqual(valider_vecteur(49.6,-0.4,100),(50,0,100))



    def test_cpp_watchdog_parseur_et_trame_compatibles(self):
        dossier=Path(__file__).resolve().parents[1]/'firmware'/'ScanAtlas_WiFi'
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'test.cpp';exe=Path(tmp)/'test'
            src.write_text(r'''
#include "protocol.h"
#include <assert.h>
#include <stdlib.h>
int main(){
  Command c;const char *token="0123456789abcdef0123456789abcdef";
  assert(parseCommand("SA1 0123456789abcdef0123456789abcdef 1 STOP 65",c));
  Lease l;l.open(0xfffffff0);assert(l.accept(c,0xfffffff5));assert(!l.expired(20));assert(l.expired(400));
  l.open(100);c.seq=2;c.motion=FORWARD;assert(!l.accept(c,101));c.motion=STOP;assert(l.accept(c,102));
  assert(!l.accept(c,103));c.seq=3;c.motion=FORWARD;assert(l.accept(c,104));
  {  // Trou de commandes : moteurs coupés à 300 ms, session gardée jusqu'à 6 s, reprise en deux temps.
    Lease g;Command k;k.seq=1;k.motion=STOP;g.open(1000);assert(g.accept(k,1010));
    assert(!g.expired(1300)&&g.expired(1311)&&!g.dead(1311)&&!g.silent(1311));
    assert(g.silent(2011)&&!g.dead(6000)&&g.dead(7011));
    k.seq=2;k.motion=FORWARD;assert(g.accept(k,3000)&&g.resumed&&!g.lapsed);   // reprise : appliquée comme STOP
    k.seq=3;assert(g.accept(k,3040)&&!g.resumed);                              // puis normalement
    k.seq=4;assert(!g.accept(k,3041+6001));                                    // session morte : refus
    g.open(0);k.seq=1;k.motion=STOP;assert(g.accept(k,10));g.close();assert(!g.active&&!g.expired(99999));
  }
  assert(!parseCommand("SA1 0123456789abcdef0123456789abcdef 4 FORWARD 255",c));
  assert(!parseCommand("SA1 0123456789abcdef0123456789abcdef 4 DRIVE 50",c));
  // Commande combinée SA2 : vecteur signé, arrêt si tout est nul, bornes strictes.
  assert(parseCommand("SA2 0123456789abcdef0123456789abcdef 5 60 -30 15",c));
  assert(c.motion==DRIVE&&c.vx==60&&c.vy==-30&&c.w==15&&c.pwm==60&&c.seq==5);
  assert(parseCommand("SA2 0123456789abcdef0123456789abcdef 6 0 0 0",c)&&c.motion==STOP&&c.pwm==0);
  assert(parseCommand("SA2 0123456789abcdef0123456789abcdef 7 -100 100 -100",c));
  assert(!parseCommand("SA2 0123456789abcdef0123456789abcdef 8 101 0 0",c));
  assert(!parseCommand("SA2 0123456789abcdef0123456789abcdef 8 0 -101 0",c));
  assert(!parseCommand("SA2 0123456789abcdef0123456789abcdef 0 10 0 0",c));
  assert(!parseCommand("SA2 0123456789abcdef0123456789abcdef 9 10 0",c));
  assert(!parseCommand("SA2 0123456789abcdef0123456789abcdef 9 10 0 0 7",c));
  assert(!parseCommand("SA2 zz23456789abcdef0123456789abcdef 9 10 0 0",c));
  l.open(500);parseCommand("SA2 0123456789abcdef0123456789abcdef 1 40 0 0",c);
  assert(!l.accept(c,501));  // Un mouvement ne peut pas ouvrir le bail : STOP d'abord.
  parseCommand("SA2 0123456789abcdef0123456789abcdef 2 0 0 0",c);assert(l.accept(c,502));
  parseCommand("SA2 0123456789abcdef0123456789abcdef 3 40 0 0",c);assert(l.accept(c,503)&&l.motion==DRIVE);
  {
    int m[4];
    mecanumMix(100,0,0,m);assert(m[0]==100&&m[1]==100&&m[2]==100&&m[3]==100);
    mecanumMix(0,100,0,m);assert(m[0]==-100&&m[1]==100&&m[2]==100&&m[3]==-100);   // gauche
    mecanumMix(0,0,100,m);assert(m[0]==-100&&m[1]==100&&m[2]==-100&&m[3]==100);   // rotation gauche
    mecanumMix(0,0,0,m);for(int i=0;i<4;++i)assert(m[i]==0);
    mecanumMix(100,100,0,m);assert(m[0]==0&&m[1]==100&&m[2]==100&&m[3]==0);        // saturation proportionnelle
    mecanumMix(100,0,-100,m);assert(m[0]==100&&m[1]==0&&m[2]==100&&m[3]==0);
    mecanumMix(50,25,-25,m);assert(m[0]==50&&m[1]==50&&m[2]==100&&m[3]==0);
    mecanumMix(100,100,100,m);for(int i=0;i<4;++i)assert(absInt(m[i])<=100);
    Command a,b;a.motion=b.motion=DRIVE;a.pwm=b.pwm=50;a.vx=b.vx=50;a.vy=b.vy=0;a.w=b.w=0;
    assert(sameDrive(a,b));b.w=10;assert(!sameDrive(a,b));
  }
  LidarParser p;ScanFrame frame;int frames=0;
  for(int turn=0;turn<4;++turn)for(int k=0;k<30;++k){
    uint8_t b[47]={0x54,0x2c};put16(b+2,3600);put16(b+4,k*1200);put16(b+42,k*1200+1100);
    for(int i=0;i<12;++i){put16(b+6+i*3,2345);b[8+i*3]=220;}
    b[46]=LidarParser::crc8(b,46);
    for(int i=0;i<47;++i)if(p.feed(b[i],1000000+turn*100000+k*3333,frame)){
      assert(frame.size==26+360*5+4);++frames;fwrite(frame.bytes,1,frame.size,stdout);
    }
  }
  assert(frames==2);return 0;
}
''')
            subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-I',str(dossier),str(src),'-o',str(exe)],check=True,capture_output=True)
            out=subprocess.run([str(exe)],check=True,capture_output=True).stdout
            frames=DecodeurScans().recevoir(out)
            self.assertEqual(len(frames),2);self.assertEqual(len(frames[0].mesures),360)
            np.testing.assert_allclose(frames[0].mesures[:,1],2.345)


class SuiviDirect(unittest.TestCase):
    def test_trajectoire_connue_carte_incremente_sans_bouger_origine(self):
        c=CarteDirecte();anchor=None
        for i in range(12):
            pose=[i*.025,i*.01,i*.5]
            e=c.traiter(trame_pose(pose,i+1))
            self.assertTrue(e.accepte,e.message)
            ep,ea=erreur_pose(e.scan.pose,pose);self.assertLess(ep,.08);self.assertLess(ea,1.)
            if anchor is None:anchor=e.scans_cles[0].mesures.copy()
        self.assertGreater(e.cles,1);self.assertLess(e.cles,12)
        self.assertGreater(len(e.segments),3)
        self.assertEqual(e.scans_cles[0].pose,[0.,0.,0.])
        np.testing.assert_array_equal(anchor,e.scans_cles[0].mesures)

    def test_echec_ne_contamine_pas_carte_et_reprise_preserve_ancrage(self):
        c=CarteDirecte();a=c.traiter(trame_pose([0,0,0],1))
        mauvais=trame_pose([0,0,0],2);mauvais.mesures[:,1]=0
        b=c.traiter(mauvais);self.assertFalse(b.accepte)
        np.testing.assert_array_equal(a.points,b.points)
        self.assertFalse(c.traiter(trame_pose([0,0,0],3)).accepte)
        c.reprendre();r=c.traiter(trame_pose([.1,0,2],100))
        self.assertTrue(r.accepte,r.message);self.assertEqual(r.scans_cles[0].pose,[0.,0.,0.])

    def test_trou_temporel_refuse_et_scan_brut_inchange(self):
        c=CarteDirecte();tr=trame_pose([0,0,0],1);brut=tr.mesures.copy();c.traiter(tr)
        np.testing.assert_array_equal(brut,tr.mesures)
        self.assertFalse(c.traiter(trame_pose([0,0,0],2,12_000_000)).accepte)     # trou de 12 s : position inconnue

    def test_trou_de_liaison_court_n_est_pas_une_perte_de_position(self):
        # Wi-Fi : 1,5 à 8 s sans tour (le firmware a arrêté les moteurs) ; le robot n'a pas bougé : le suivi continue,
        # sous surveillance (pas de scan clé pendant la vérification).
        c=CarteDirecte();c.traiter(trame_pose([0,0,0],1))
        e=c.traiter(trame_pose([0,0,0],2,5_000_000))
        self.assertTrue(e.accepte,e.message)


class FauxRobot:
    def __init__(self, vieux=False, retard_ack=False, force_stop=False, ancien_firmware=False):
        self.udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.udp.bind(('127.0.0.1',0));self.udp.settimeout(.05)
        self.tcp=socket.socket();self.tcp.bind(('127.0.0.1',0));self.tcp.listen();self.tcp.settimeout(.1)
        self.fin=threading.Event();self.commandes=[];self.flux=True;self.vieux=vieux
        self.force_stop=force_stop;self.degrade=False;self.vecteurs=[];self.ancien_firmware=ancien_firmware
        self.retard_ack=retard_ack;self.ack_precedent=''
        self.threads=[threading.Thread(target=self.commandes_loop,daemon=True),threading.Thread(target=self.scans_loop,daemon=True)]
        for t in self.threads:t.start()

    def commandes_loop(self):
        while not self.fin.is_set():
            try:raw,addr=self.udp.recvfrom(256)
            except socket.timeout:continue
            p=raw.decode().split()
            if p[0]=='HELLO':rep=f'READY {p[1]}\n' if self.ancien_firmware else f'READY {p[1]} SA2\n'
            elif p[0]=='SA2' and self.ancien_firmware:continue   # Commande inconnue : aucune réponse.
            elif p[0]=='SA2':
                v=tuple(int(x) for x in p[3:6]);etat='DRIVE' if any(v) else 'STOP'
                self.vecteurs.append(v);self.commandes.append((time.monotonic(),etat))
                rep=f'SA1 {p[1]} {p[2]} {etat}\n'
                if self.force_stop:rep=f'SA1 {p[1]} {p[2]} STOP\n'
                if self.retard_ack:rep,self.ack_precedent=self.ack_precedent,rep
            else:
                self.commandes.append((time.monotonic(),p[3]));rep=' '.join(p[:4])+'\n'
                if self.force_stop:rep=' '.join(p[:3])+ ' STOP\n'
                if self.retard_ack:rep,self.ack_precedent=self.ack_precedent,rep
            if rep:self.udp.sendto(rep.encode(),addr)

    def scans_loop(self):
        client=None
        try:
            while not self.fin.is_set():
                try:client,_=self.tcp.accept();break
                except socket.timeout:continue
            if client is None:return
            client.settimeout(.3);client.recv(128)
            i=0
            while not self.fin.wait(.05):
                if not self.flux:continue
                i+=1;t=trame_pose([0,0,0],1 if self.vieux else i)
                if self.degrade:t.mesures[:,1]=0
                raw=encoder_trame(t.sequence,t.fin_us,t.duree_us,t.mesures)
                client.sendall(raw[:17]);client.sendall(raw[17:])
        except OSError:pass
        finally:
            if client:client.close()

    def fermer(self):
        self.fin.set()
        for t in self.threads:t.join(1)
        self.udp.close();self.tcp.close()


class ReseauReelBoucleLocale(unittest.TestCase):
    def attendre(self,predicat,timeout=2.):
        fin=time.monotonic()+timeout
        while time.monotonic()<fin:
            if predicat():return
            time.sleep(.01)
        self.fail('Événement réseau attendu absent.')

    def test_mouvement_bail_expire_et_perte_lidar(self):
        faux=FauxRobot();r=RobotWifi('127.0.0.1',faux.udp.getsockname()[1],faux.tcp.getsockname()[1])
        try:
            r.demarrer();self.attendre(lambda:r.recus>0)
            r.commander('FORWARD');self.attendre(lambda:any(c=='FORWARD' for _,c in faux.commandes))
            self.attendre(lambda:faux.commandes[-1][1]=='STOP')
            faux.flux=False;time.sleep(.7)
            for _ in range(5):r.commander('FORWARD');time.sleep(.06)
            self.assertEqual(faux.commandes[-1][1],'STOP')
            self.assertLessEqual(r.scans.qsize(),1)
        finally:r.fermer();faux.fermer()

    def test_commande_combinee_envoyee_en_sa2_puis_arret(self):
        faux=FauxRobot();r=RobotWifi('127.0.0.1',faux.udp.getsockname()[1],faux.tcp.getsockname()[1])
        try:
            r.demarrer();self.attendre(lambda:r.recus>0)
            for _ in range(6):r.conduire(60,-30,15);time.sleep(.06)
            self.attendre(lambda:(60,-30,15) in faux.vecteurs)
            self.attendre(lambda:r.diagnostic_commande()['effective']=='DRIVE')
            self.assertFalse(r.arret.is_set())
            r.conduire(0,0,0);self.attendre(lambda:faux.commandes[-1][1]=='STOP')
            with self.assertRaises(ValueError):r.conduire(101,0,0)
            r.conduire(30,-20,0);self.attendre(lambda:(30,-20,0) in faux.vecteurs)
            self.attendre(lambda:faux.commandes[-1][1]=='STOP',timeout=2.)   # Le bail UI expire sans renouvellement.
        finally:r.fermer();faux.fermer()

    def test_un_seul_axe_reste_en_sa1_compatible_et_combine_en_sa2(self):
        faux=FauxRobot();r=RobotWifi('127.0.0.1',faux.udp.getsockname()[1],faux.tcp.getsockname()[1])
        try:
            r.demarrer();self.attendre(lambda:r.recus>0)
            self.assertTrue(r.combine)
            for _ in range(5):r.conduire(65,0,0);time.sleep(.06)
            self.attendre(lambda:any(c=='FORWARD' for _,c in faux.commandes))
            self.assertEqual(faux.vecteurs,[])           # Rien en SA2 pour un seul axe.
            for _ in range(5):r.conduire(0,0,-40);time.sleep(.06)
            self.attendre(lambda:any(c=='RIGHT' for _,c in faux.commandes))
            self.assertEqual(faux.vecteurs,[])
            for _ in range(5):r.conduire(65,0,-40);time.sleep(.06)
            self.attendre(lambda:(65,0,-40) in faux.vecteurs)
        finally:r.fermer();faux.fermer()

    def test_ancien_firmware_garde_la_liaison_et_l_axe_dominant(self):
        faux=FauxRobot(ancien_firmware=True);r=RobotWifi('127.0.0.1',faux.udp.getsockname()[1],faux.tcp.getsockname()[1])
        try:
            r.demarrer();self.attendre(lambda:r.recus>0)
            self.assertFalse(r.combine)
            for _ in range(8):r.conduire(65,0,-40);time.sleep(.06)
            self.attendre(lambda:any(c=='FORWARD' for _,c in faux.commandes))   # Axe dominant, pas de coupure.
            self.assertEqual(faux.vecteurs,[]);self.assertFalse(r.arret.is_set())
            self.assertTrue(any('Reflasher' in m for m in list(r.etats.queue)),list(r.etats.queue))
        finally:r.fermer();faux.fermer()

    def test_rejeu_de_scan_force_deconnexion(self):
        faux=FauxRobot(vieux=True);r=RobotWifi('127.0.0.1',faux.udp.getsockname()[1],faux.tcp.getsockname()[1])
        try:
            r.demarrer();self.attendre(r.arret.is_set)
            self.assertEqual(r.bail.lire()[0],'STOP')
            messages=list(r.etats.queue)
            self.assertTrue(any('Scan ancien' in m for m in messages),messages)
            self.assertEqual(r.recus,1)
        finally:r.fermer();faux.fermer()

    def test_acquittement_du_paquet_precedent_ne_perd_pas_la_connexion(self):
        faux=FauxRobot(retard_ack=True);r=RobotWifi('127.0.0.1',faux.udp.getsockname()[1],faux.tcp.getsockname()[1])
        try:
            r.demarrer();self.attendre(lambda:r.recus>10)
            self.assertFalse(r.arret.is_set());self.assertTrue(r.connecte.is_set())
        finally:r.fermer();faux.fermer()


if __name__=='__main__':unittest.main()

