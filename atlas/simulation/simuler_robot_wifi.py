"""Robot Wi-Fi simulé sur le PC, sans moteurs : python -m atlas.simulation.simuler_robot_wifi.

Dans l'application, « Essayer avec un robot simulé » le lance tout seul. À la main : adresse 127.0.0.1,
et --salle appartement | deux_pieces | salle (voir simulation.SALLES). Le robot simulé se déplace dans une salle
connue : ceci ne valide ni le Wi-Fi radio ni le matériel.
"""
import argparse
import os
import socket
import threading
import time
import numpy as np
from atlas.robot.robot_wifi import encoder_trame, COMMANDS

from atlas.simulation.simulation import SALLES, SALLE_PAR_DEFAUT, mesures_simulees, deplacer


def main():
    ap=argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--salle',choices=sorted(SALLES),default=SALLE_PAR_DEFAUT)
    ap.add_argument('--coupures',default=os.environ.get('SCANATLAS_SIM_COUPURES',''),
                    help='PERIODE,DUREE en secondes : coupe la liaison (commandes et scans) comme un trou Wi-Fi, pour tester la reprise')
    args=ap.parse_args()
    salle=SALLES[args.salle];murs=salle['murs']
    periode,duree_coupure=(float(x) for x in args.coupures.split(',')) if args.coupures else (0.,0.)
    debut_sim=time.monotonic()
    def coupee():
        return periode>0 and (time.monotonic()-debut_sim)%periode>periode-duree_coupure
    fin=threading.Event();lock=threading.Lock();pose=np.array(salle['depart'],float)
    state={'token':None,'adresse':None,'last':0.,'seq':0,'cmd':'STOP','pwm':65,'vecteur':(0,0,0),'dernier_scan':0.}
    udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.bind(('127.0.0.1',4210));udp.settimeout(.02)
    server=socket.socket();server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    server.bind(('127.0.0.1',4211));server.listen(1);server.settimeout(.1)
    def commandes():
        while not fin.is_set():
            try:raw,addr=udp.recvfrom(256)
            except socket.timeout:continue
            if coupee():continue                  # trou de liaison : le paquet n'arrive pas
            p=raw.decode('ascii',errors='ignore').split();now=time.monotonic();rep=''
            with lock:
                # comme le firmware : silence > 300 ms = moteurs coupés ; > 6 s = session perdue ; > 1 s = une autre session peut la reprendre
                if now-state['last']>.3:state['cmd']='STOP'
                if now-state['last']>6.:state['token']=None
                if len(p)==2 and p[0]=='HELLO' and len(p[1])==32:
                    if state['token'] is None or (state['token']!=p[1] and now-state['last']>1.):
                        state.update(token=p[1],adresse=addr,last=now,seq=0,cmd='STOP')
                    rep='READY '+p[1]+' SA2' if state['token']==p[1] and state['adresse']==addr else 'BUSY'
                elif (len(p)==5 and p[0]=='SA1' and p[1]==state['token'] and addr==state['adresse'] and p[3] in COMMANDS and p[3]!='DRIVE'):
                    try:seq,pwm=int(p[2]),int(p[4])
                    except ValueError:continue
                    if seq>state['seq'] and 0<=pwm<=100 and (state['seq'] or p[3]=='STOP'):
                        state.update(seq=seq,last=now,cmd=p[3],pwm=pwm,vecteur=(0,0,0));rep=' '.join(p[:4])
                elif (len(p)==6 and p[0]=='SA2' and p[1]==state['token'] and addr==state['adresse']):
                    try:seq,v=int(p[2]),tuple(int(x) for x in p[3:])
                    except ValueError:continue
                    if seq>state['seq'] and all(abs(x)<=100 for x in v) and (state['seq'] or not any(v)):
                        etat='DRIVE' if any(v) else 'STOP'
                        if now-state['last']>.3:etat,v='STOP',(0,0,0)       # comme le firmware : la première commande après une coupure est appliquée comme STOP
                        state.update(seq=seq,last=now,cmd=etat,pwm=max(map(abs,v)),vecteur=v);rep=f"SA1 {p[1]} {seq} {etat}"
            if rep:udp.sendto((rep+'\n').encode(),addr)
    def scans():
        rng=np.random.default_rng(42);sequence=0
        while not fin.is_set():
            try:client,addr=server.accept()
            except socket.timeout:continue
            try:
                client.settimeout(1);token=b''
                while len(token)<34 and not token.endswith(b'\n'):
                    b=client.recv(1)
                    if not b:break
                    token+=b
                with lock:allowed=token.decode().strip()==state['token']
                if not allowed:continue
                while not fin.wait(.1):
                    with lock:
                        p=pose.copy();allowed=token.decode().strip()==state['token']
                    if not allowed:break
                    sequence+=1                       # le lidar continue de tourner pendant un trou, les tours sont perdus
                    if coupee():continue
                    with lock:state['dernier_scan']=time.monotonic()
                    client.sendall(encoder_trame(sequence,time.monotonic_ns()//1000,100000,mesures_simulees(p,rng,murs)))
            except (OSError,UnicodeError):pass
            finally:client.close()
    threads=[threading.Thread(target=f,daemon=True) for f in (commandes,scans)]
    for t in threads:t.start()
    print(f"SIMULATION uniquement ({salle['titre']}) — adresse du robot : 127.0.0.1. Ctrl+C pour quitter.",flush=True)
    last=time.monotonic()
    try:
        while not fin.wait(.02):
            now=time.monotonic();dt=min(.1,now-last);last=now
            with lock:
                cmd=state['cmd'] if now-state['last']<.3 and now-state['dernier_scan']<.6 else 'STOP'
                if cmd=='DRIVE':
                    avance,gauche,tourne=state['vecteur']
                else:
                    p=state['pwm']
                    avance,gauche=({'FORWARD':(p,0),'BACK':(-p,0),'STRAFE_L':(0,p),'STRAFE_R':(0,-p)}.get(cmd,(0,0)))
                    tourne=p*(1 if cmd=='LEFT' else -1 if cmd=='RIGHT' else 0)
                pose[:]=deplacer(pose,avance,gauche,tourne,dt,murs)
    except KeyboardInterrupt:pass
    finally:
        fin.set()
        for t in threads:t.join(2)
        udp.close();server.close()


if __name__=='__main__':main()
