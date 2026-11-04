"""Journal append-only des tours reçus et sauvegarde atomique des scans clés."""
from pathlib import Path
from datetime import datetime
import json
import math
import os
import threading


def serialiser_scan(scan):
    return dict(nom=scan.nom,mesures=scan.mesures.tolist(),pose=list(scan.pose),source=scan.source,
                angle_reference=scan.angle_reference,intensite_disponible=scan.intensite_disponible,
                pose_connue=scan.pose_connue,suivi_recalage=scan.suivi_recalage,inclus=True,visible=True)


def sauver_carte(chemin, scans, filtres):
    chemin=Path(chemin);chemin.parent.mkdir(parents=True,exist_ok=True)
    contenu=dict(version=2,parametres={k:str(v) for k,v in filtres.items()},
                 scans=[serialiser_scan(s) for s in scans])
    temporaire=chemin.with_suffix(chemin.suffix+'.tmp')
    temporaire.write_text(json.dumps(contenu,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    temporaire.replace(chemin)


class JournalDirect:
    def __init__(self, dossier=None):
        racine=Path(dossier) if dossier else Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'ScanAtlas'/'journaux'
        self.dossier=racine/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        self.dossier.mkdir(parents=True,exist_ok=True)
        self.fichier=(self.dossier/'tours.jsonl').open('a',encoding='utf-8',buffering=1)
        self.lock=threading.Lock();self.erreur='';self.nombre_cles=-1

    def ecrire(self, data):
        try:
            with self.lock:
                self.fichier.write(json.dumps(data,ensure_ascii=False,allow_nan=False)+'\n')
        except (OSError,ValueError) as exc:
            self.erreur='Journal indisponible : '+str(exc)

    def brut(self,trame):
        self.ecrire(dict(type='scan',sequence=trame.sequence,fin_us=trame.fin_us,
                         duree_us=trame.duree_us,mesures=trame.mesures.tolist()))

    def resultat(self,trame,etat,filtres):
        self.ecrire(dict(type='localisation',sequence=trame.sequence,accepte=etat.accepte,
            message=etat.message,pose=list(etat.scan.pose) if etat.accepte else None,
            concordance=etat.concordance if math.isfinite(etat.concordance) else None,
            enrichissement=etat.enrichissement))
        if etat.cles!=self.nombre_cles:
            try:
                sauver_carte(self.dossier/'session_secours.json',etat.scans_cles,filtres)
                self.nombre_cles=etat.cles
            except (OSError,ValueError) as exc:self.erreur='Sauvegarde de secours indisponible : '+str(exc)

    def fermer(self):
        with self.lock:
            if not self.fichier.closed:self.fichier.close()
