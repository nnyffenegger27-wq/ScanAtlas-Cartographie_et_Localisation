"""Rejoue les tours bruts d'un journal du robot (tours.jsonl) dans CarteDirecte, avec l'horloge du lidar.

    python outils/rejouer_journal.py %LOCALAPPDATA%\\ScanAtlas\\journaux\\<session>\\tours.jsonl

Affiche le taux de scans acceptés, le nombre de scans clés et les premiers refus : sert à comparer deux versions du
code sur les mêmes mesures réelles.
"""
import collections
import json
import sys
import time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cartographie_direct as cd
from robot_wifi import TrameScan


def rejouer(chemin):
    horloge = [0.]
    cd.perf_counter = lambda: horloge[0]          # sinon les attentes entre essais ne s'écoulent jamais en rejeu
    carte, n, acceptes, refus = cd.CarteDirecte(), 0, 0, []
    debut = time.time()
    with open(chemin, encoding='utf-8') as f:
        for ligne in f:
            j = json.loads(ligne)
            if j.get('type') != 'scan':
                continue
            horloge[0] = j['fin_us']/1e6
            etat = carte.traiter(TrameScan(j['sequence'], j['fin_us'], j['duree_us'], np.array(j['mesures'], float)))
            n += 1
            acceptes += bool(etat.accepte)
            if not etat.accepte:
                refus.append((n, etat.message))
    return n, acceptes, len(carte.cles), len(carte.points), refus, time.time()-debut


if __name__ == '__main__':
    n, ok, cles, pts, refus, duree = rejouer(sys.argv[1])
    print(f'{n} tours, {100*ok/max(n, 1):.0f} % acceptés, {cles} scans clés, {pts} points, {duree:.0f} s de calcul')
    print(collections.Counter(m.split(':')[0][:40] for _, m in refus).most_common(4))
    for numero, message in refus[:5]:
        print(f'  refus tour {numero} : {message[:160]}')
