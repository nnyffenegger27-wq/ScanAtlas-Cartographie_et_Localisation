"""Journal des tours reçus, événements et sauvegarde de secours des scans clés.

Toute l'écriture se fait dans un fil à part. Le fil de calcul et la boucle de commande n'attendent jamais le
disque ni la sérialisation : un arrêt de plus de 300 ms de la boucle de commande fait expirer le bail du robot,
qui coupe alors le flux lidar. La session de secours croît avec la carte ; elle est écrite scan par scan (le GIL
est rendu entre deux scans) et au plus une fois toutes les INTERVALLE_SECOURS secondes, plus une fois à la fermeture.
"""
from pathlib import Path
from datetime import datetime
import json
import math
import os
import queue
import threading
import time

INTERVALLE_SECOURS = 20.
FILE_MAX = 400           # au-delà, les tours bruts en attente sont abandonnés (le disque ne suit pas) ; le reste est conservé
_FIN = object()


def serialiser_scan(scan):
    return dict(nom=scan.nom,mesures=scan.mesures.tolist(),pose=list(scan.pose),source=scan.source,
                angle_reference=scan.angle_reference,intensite_disponible=scan.intensite_disponible,
                pose_connue=scan.pose_connue,suivi_recalage=scan.suivi_recalage,inclus=True,visible=True)


def sauver_carte(chemin, scans, filtres, ceder=None):
    """Écriture atomique de la session ; `ceder` est appelé après chaque scan pour laisser la main aux autres fils."""
    chemin=Path(chemin);chemin.parent.mkdir(parents=True,exist_ok=True)
    temporaire=chemin.with_suffix(chemin.suffix+'.tmp')
    parametres={k:str(v) for k,v in filtres.items()}
    with temporaire.open('w',encoding='utf-8') as fichier:
        fichier.write('{"version": 2, "parametres": '+json.dumps(parametres,ensure_ascii=False)+', "scans": [')
        for i,scan in enumerate(scans):
            if i:fichier.write(', ')
            fichier.write(json.dumps(serialiser_scan(scan),ensure_ascii=False,allow_nan=False))
            if ceder is not None:ceder()
        fichier.write(']}')
    temporaire.replace(chemin)


class JournalDirect:
    def __init__(self, dossier=None):
        racine=Path(dossier) if dossier else Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'ScanAtlas'/'journaux'
        self.dossier=racine/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        self.dossier.mkdir(parents=True,exist_ok=True)
        self.fichier=(self.dossier/'tours.jsonl').open('a',encoding='utf-8',buffering=1)
        self.lock=threading.Lock();self.erreur='';self.nombre_cles=-1
        self.taches=queue.Queue()
        self.a_sauver=None           # (scans clés, filtres) le plus récent, pas encore écrit
        self.dernier_secours=time.monotonic()       # première sauvegarde de secours après INTERVALLE_SECOURS
        self.abandonnes=0
        self.ferme=False
        self.fil=threading.Thread(target=self._ecrivain,name='journal',daemon=True)
        self.fil.start()

    # -- appelés depuis les fils de calcul et de liaison : ne font que déposer une tâche ---------
    def ecrire(self, data):
        if not self.ferme:self.taches.put(('ligne',data))

    def evenement(self,texte):
        """Une ligne horodatée dans evenements.log : connexion, coupures, pertes de suivi."""
        if not self.ferme:self.taches.put(('evenement',datetime.now().strftime('%H:%M:%S.%f')[:-3]+'  '+str(texte)))

    def brut(self,trame):
        if self.ferme:return
        if self.taches.qsize()>FILE_MAX:
            self.abandonnes+=1
            return
        self.taches.put(('brut',trame))

    def resultat(self,trame,etat,filtres):
        if self.ferme:return
        self.ecrire(dict(type='localisation',sequence=trame.sequence,accepte=etat.accepte,
            message=etat.message,pose=list(etat.scan.pose) if etat.accepte else None,
            concordance=etat.concordance if math.isfinite(etat.concordance) else None,
            enrichissement=etat.enrichissement))
        if etat.cles!=self.nombre_cles:
            self.nombre_cles=etat.cles
            with self.lock:self.a_sauver=(etat.scans_cles,filtres)

    # -- fil d'écriture ------------------------------------------------------------------------
    def _ecrivain(self):
        while True:
            try:tache=self.taches.get(timeout=1.)
            except queue.Empty:tache=None
            if tache is _FIN:break
            if tache is not None:self._executer(tache)
            if time.monotonic()-self.dernier_secours>=self._intervalle():self._secours()
        self._secours()
        try:self.fichier.close()
        except OSError:pass

    def _executer(self,tache):
        genre,contenu=tache
        try:
            if genre=='evenement':
                with (self.dossier/'evenements.log').open('a',encoding='utf-8') as f:f.write(contenu+'\n')
            else:
                if genre=='brut':
                    contenu=dict(type='scan',sequence=contenu.sequence,fin_us=contenu.fin_us,
                                 duree_us=contenu.duree_us,mesures=contenu.mesures.tolist())
                self.fichier.write(json.dumps(contenu,ensure_ascii=False,allow_nan=False)+'\n')
        except (OSError,ValueError) as exc:
            self.erreur='Journal indisponible : '+str(exc)

    def _intervalle(self):
        """Plus la carte est grande, plus la sauvegarde complète est espacée (au plus ~10 % du temps du fil d'écriture)."""
        with self.lock:
            n=0 if self.a_sauver is None else len(self.a_sauver[0])
        return max(INTERVALLE_SECOURS,.05*n)

    def _secours(self):
        with self.lock:
            demande,self.a_sauver=self.a_sauver,None
        self.dernier_secours=time.monotonic()
        if demande is None:return
        try:sauver_carte(self.dossier/'session_secours.json',demande[0],demande[1],ceder=lambda:time.sleep(.001))
        except (OSError,ValueError) as exc:self.erreur='Sauvegarde de secours indisponible : '+str(exc)

    def fermer(self):
        """Vide ce qui est en attente, écrit la session de secours une dernière fois et ferme les fichiers."""
        if self.ferme:return
        self.ferme=True
        self.taches.put(_FIN)
        self.fil.join(timeout=20.)
