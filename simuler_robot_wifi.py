"""Robot Wi-Fi simulé sur le PC, sans moteurs : python simuler_robot_wifi.py.

Dans l'onglet Robot Wi-Fi, adresse 127.0.0.1. Les touches déplacent le robot
simulé dans une salle connue. Ceci ne valide ni le Wi-Fi radio ni le matériel.
"""
import socket
import threading
import time
import numpy as np
from robot_wifi import encoder_trame, COMMANDS

MURS = np.array([[[-3,-2],[4,-2]],[[4,-2],[4,3]],[[4,3],[-3,3]],
                 [[-3,3],[-3,-2]],[[.6,.8],[1.4,.8]],[[1.4,.8],[1.4,1.5]]],float)


def mesures_simulees(pose, rng):
    angles=np.linspace(0,360,450,endpoint=False)
    a=np.deg2rad(angles+pose[2]);rays=np.column_stack([np.cos(a),np.sin(a)])
    dist=np.full(len(angles),12.)
    def cross(a,b):return a[...,0]*b[...,1]-a[...,1]*b[...,0]
    for p,q in MURS:
        v=q-p;w=p-np.asarray(pose[:2]);den=cross(rays,v)
        with np.errstate(divide='ignore',invalid='ignore'):
            t=cross(w,v)/den;u=cross(w,rays)/den
        valid=(np.abs(den)>1e-9)&(t>.05)&(u>=0)&(u<=1)
        dist[valid]=np.minimum(dist[valid],t[valid])
    dist=np.maximum(.05,dist+rng.normal(0,.003,len(dist)))
    return np.column_stack([angles,dist,np.full(len(dist),230)])


def main():
    fin=threading.Event();lock=threading.Lock();pose=np.zeros(3)
    state={'token':None,'adresse':None,'last':0.,'seq':0,'cmd':'STOP','pwm':65,'vecteur':(0,0,0)}
    udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);udp.bind(('127.0.0.1',4210));udp.settimeout(.02)
    server=socket.socket();server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    server.bind(('127.0.0.1',4211));server.listen(1);server.settimeout(.1)
    def commandes():
        while not fin.is_set():
            try:raw,addr=udp.recvfrom(256)
            except socket.timeout:continue
            p=raw.decode('ascii',errors='ignore').split();now=time.monotonic();rep=''
            with lock:
                if now-state['last']>.3:state['token']=None;state['cmd']='STOP'
                if len(p)==2 and p[0]=='HELLO' and len(p[1])==32:
                    if state['token'] is None:
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
                    sequence+=1
                    client.sendall(encoder_trame(sequence,time.monotonic_ns()//1000,100000,mesures_simulees(p,rng)))
            except (OSError,UnicodeError):pass
            finally:client.close()
    threads=[threading.Thread(target=f,daemon=True) for f in (commandes,scans)]
    for t in threads:t.start()
    print('SIMULATION uniquement — adresse du robot : 127.0.0.1. Ctrl+C pour quitter.',flush=True)
    last=time.monotonic()
    try:
        while not fin.wait(.02):
            now=time.monotonic();dt=min(.1,now-last);last=now
            with lock:
                cmd=state['cmd'] if now-state['last']<.3 else 'STOP'
                if cmd=='DRIVE':
                    avance,gauche,tourne=(x/65. for x in state['vecteur'])
                    local=np.array([.3*avance,.3*gauche]);rotation_signee=35.*tourne
                else:
                    speed=.3*state['pwm']/65.;rotation=35.*state['pwm']/65.
                    local=np.array({'FORWARD':[speed,0],'BACK':[-speed,0],
                                    'STRAFE_L':[0,speed],'STRAFE_R':[0,-speed]}.get(cmd,[0,0]))
                    rotation_signee=rotation*(1 if cmd=='LEFT' else -1 if cmd=='RIGHT' else 0)
                a=np.deg2rad(pose[2]);R=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
                pose[:2]+=R@local*dt
                pose[2]+=rotation_signee*dt
    except KeyboardInterrupt:pass
    finally:
        fin.set()
        for t in threads:t.join(2)
        udp.close();server.close()


if __name__=='__main__':main()
