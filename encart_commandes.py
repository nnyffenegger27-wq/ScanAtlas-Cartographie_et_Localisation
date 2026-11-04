"""Encart visuel des commandes de conduite : un pavé 3 × 3 qui se remplit en direct.

Rotation gauche / avance / rotation droite, gauche / croix d'arrêt / droite, recul. Derrière
chaque flèche, un carré vert se remplit proportionnellement à la puissance demandée, du côté
d'où part le mouvement (l'avance monte depuis le bas de la case, le recul descend depuis le haut,
etc.) ; le pourcentage s'écrit dans la case. Au joystick le remplissage suit l'inclinaison, au
clavier il reste fixe (tout ou rien) à la valeur du réglage PWM. La croix centrale est pleine
quand le robot est à l'arrêt. Le fond change de couleur quand le robot n'est pas connecté :
l'encart reste utile pour tester les commandes.

Le calcul est séparé du dessin (fonctions pures en haut du fichier) pour pouvoir
être vérifié sans écran.
"""
import math
import tkinter as tk
from apparence import ENCRE, SECONDAIRE, BORDURE

VERT = '#2f9e6e'
CASE = '#ffffff'
CASE_TEXTE = '#4d5f73'
FOND_CONNECTE = '#e6f2ea'
FOND_HORS_LIGNE = '#f2eadf'
BLEU = '#2a6fdb'

def pourcentages(surge, sway, yaw, pwm):
    """Niveaux [-1, 1] × réglage PWM → entiers signés de -100 à 100."""
    pwm = max(0., min(100., float(pwm)))
    return tuple(int(round(max(-1., min(1., float(n)))*pwm)) for n in (surge, sway, yaw))


def cellules_pave(surge, sway, yaw):
    """Fraction d'activation [0, 1] de chaque case du pavé (surge, sway, yaw en % signés).

    Positifs : avance, gauche, rotation à gauche. La croix centrale est active à l'arrêt.
    """
    f = lambda v: min(1., abs(float(v))/100.)
    return {'rot_g': f(yaw) if yaw > 0 else 0., 'rot_d': f(yaw) if yaw < 0 else 0.,
            'avance': f(surge) if surge > 0 else 0., 'recul': f(surge) if surge < 0 else 0.,
            'gauche': f(sway) if sway > 0 else 0., 'droite': f(sway) if sway < 0 else 0.,
            'arret': 1. if not (round(surge) or round(sway) or round(yaw)) else 0.}


def _tourner(points, quarts):
    """Rotation de quarts de tour (sens horaire à l'écran) autour de l'origine."""
    for _ in range(quarts % 4):
        points = [(-y, x) for x, y in points]
    return points


_FLECHE = [(0, -.82), (.74, -.02), (.3, -.02), (.3, .82), (-.3, .82), (-.3, -.02), (-.74, -.02)]  # vers le haut


def forme_rotation(gauche):
    """(polyligne de l'arc, pointe de flèche) d'une rotation, dans un carré de rayon 1."""
    r = .58
    arc = [(r*math.cos(math.radians(a)), -r*math.sin(math.radians(a))) for a in range(-35, 236, 15)]
    x, y = arc[-1]
    tx, ty = y, -x   # tangente anti-horaire à l'écran (y vers le bas)
    n = math.hypot(tx, ty)
    tx, ty = tx/n, ty/n
    px, py = -ty, tx
    pointe = [(x+tx*.5, y+ty*.5), (x+px*.36, y+py*.36), (x-px*.36, y-py*.36)]
    if not gauche:
        arc = [(-a, b) for a, b in arc]
        pointe = [(-a, b) for a, b in pointe]
    return arc, pointe


class EncartCommandes(tk.Canvas):
    def __init__(self, parent, **options):
        super().__init__(parent, height=214, highlightthickness=1, highlightbackground=BORDURE,
                         background=FOND_HORS_LIGNE, **options)
        self._valeurs = (0, 0, 0)
        self._connecte = False
        self._note = ''
        self.bind('<Configure>', lambda event: self.dessiner())
        self.dessiner()

    def afficher(self, surge, sway, yaw, connecte, note=''):
        """Met à jour l'encart ; ne redessine que si quelque chose a changé."""
        nouveau = (tuple(int(round(v)) for v in (surge, sway, yaw)), bool(connecte), note)
        if nouveau == (self._valeurs, self._connecte, self._note):
            return
        self._valeurs, self._connecte, self._note = nouveau
        self.dessiner()

    def _fleche(self, cx, cy, rayon, quarts, **options):
        pts = [(cx+x*rayon, cy+y*rayon) for x, y in _tourner(_FLECHE, quarts)]
        self.create_polygon(pts, fill=BLEU, outline=BLEU, **options)

    def _case_pave(self, x0, y0, cote, fraction, icone, sens):
        """Case x0,y0 de côté `cote` : fond blanc, remplissage vert depuis le côté `sens`, icône par-dessus."""
        self.create_rectangle(x0, y0, x0+cote, y0+cote, fill=CASE, outline=BORDURE, tags=('pave',))
        if fraction > 0:
            f = min(1., fraction)
            zone = {'bas': (x0, y0+cote*(1-f), x0+cote, y0+cote),      # monte depuis le bas
                    'haut': (x0, y0, x0+cote, y0+cote*f),              # descend depuis le haut
                    'droite': (x0+cote*(1-f), y0, x0+cote, y0+cote),   # va vers la gauche depuis la droite
                    'gauche': (x0, y0, x0+cote*f, y0+cote)}[sens]
            self.create_rectangle(*zone, fill=VERT, outline=VERT, tags=('pave', 'rempli'))
        cx, cy, r = x0+cote/2, y0+cote/2, cote*.36
        if icone in ('haut', 'droite', 'bas', 'gauche'):
            self._fleche(cx, cy, r, ('haut', 'droite', 'bas', 'gauche').index(icone), tags=('pave',))
        elif icone == 'croix':
            d = r*.78
            for sx in (-1, 1):
                self.create_line(cx-d, cy-sx*d, cx+d, cy+sx*d, fill=BLEU, width=4, capstyle='round', tags=('pave',))
        else:
            arc, pointe = forme_rotation(icone == 'rot_g')
            self.create_line([(cx+x*r*1.25, cy+y*r*1.25) for x, y in arc], fill=BLEU, width=4,
                             capstyle='round', joinstyle='round', tags=('pave',))
            self.create_polygon([(cx+x*r*1.25, cy+y*r*1.25) for x, y in pointe], fill=BLEU, outline=BLEU, tags=('pave',))

    def dessiner(self):
        self.delete('all')
        largeur = max(self.winfo_width(), 220)
        self.configure(background=FOND_CONNECTE if self._connecte else FOND_HORS_LIGNE)
        self.create_text(10, 12, anchor='w', font=('TkDefaultFont', 9, 'bold'),
                         fill=ENCRE if self._connecte else SECONDAIRE,
                         text='ROBOT CONNECTÉ' if self._connecte else 'ROBOT NON CONNECTÉ · TEST DES COMMANDES')
        trou, marge, haut = 5, 10, 26
        cote = max(36, min(56, (largeur-2*marge-2*trou)/3))
        x0 = (largeur-(3*cote+2*trou))/2
        fractions = cellules_pave(*self._valeurs)
        # (nom, icône, côté d'où part le remplissage) par case, ligne par ligne.
        disposition = (('rot_g', 'rot_g', 'bas'), ('avance', 'haut', 'bas'), ('rot_d', 'rot_d', 'bas'),
                       ('gauche', 'gauche', 'droite'), ('arret', 'croix', 'bas'), ('droite', 'droite', 'gauche'),
                       None, ('recul', 'bas', 'haut'), None)
        pourcent = dict(zip(('avance', 'gauche', 'rot_g'), (abs(v) for v in self._valeurs)))
        pourcent.update(recul=abs(self._valeurs[0]), droite=abs(self._valeurs[1]), rot_d=abs(self._valeurs[2]))
        for indice, entree in enumerate(disposition):
            if entree is None:
                continue
            nom, icone, sens = entree
            ligne, colonne = divmod(indice, 3)
            xa, ya = x0+colonne*(cote+trou), haut+ligne*(cote+trou)
            self._case_pave(xa, ya, cote, fractions[nom], icone, sens)
            if nom != 'arret' and fractions[nom] > 0:
                self.create_text(xa+cote-3, ya+cote-2, anchor='se', text=f'{pourcent[nom]}', fill=ENCRE,
                                 font=('TkDefaultFont', 8, 'bold'), tags=('pave', 'pourcent'))
        if self._note:
            self.create_text(10, haut+3*cote+2*trou+10, anchor='w', text=self._note, fill=SECONDAIRE,
                             font=('TkDefaultFont', 8))
