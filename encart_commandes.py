"""Encart visuel des commandes de conduite : pavé directionnel + surge, sway et yaw en pourcentage.

À gauche, un pavé 3 × 3 : rotation gauche / avance / rotation droite, gauche / croix d'arrêt /
droite, recul. Une case devient verte quand la commande correspondante est active, d'autant plus
franchement que la puissance est élevée ; la croix centrale est verte quand le robot est à l'arrêt.
À droite, chaque axe (Surge, Sway, Yaw) a deux cases qui se remplissent en vert depuis le centre,
proportionnellement à la puissance demandée : au joystick le remplissage suit l'inclinaison, au
clavier il reste fixe (tout ou rien) à la valeur du réglage PWM. Le fond change de couleur quand le
robot n'est pas connecté : l'encart reste utile pour tester les commandes.

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

# (axe, case de gauche, case de droite, le sens positif est-il à gauche ?)
# Surge positif = avance (case de droite). Sway et yaw positifs = gauche.
LIGNES = (('Surge', 'Recul', 'Avance', False),
          ('Sway', 'Gauche', 'Droite', True),
          ('Yaw', 'Gauche', 'Droite', True))


def pourcentages(surge, sway, yaw, pwm):
    """Niveaux [-1, 1] × réglage PWM → entiers signés de -100 à 100."""
    pwm = max(0., min(100., float(pwm)))
    return tuple(int(round(max(-1., min(1., float(n)))*pwm)) for n in (surge, sway, yaw))


def remplissages(valeur, positif_a_gauche):
    """Pourcentage signé → (fraction case gauche, fraction case droite), dans [0, 1]."""
    v = max(-100., min(100., float(valeur)))
    positif, negatif = max(0., v)/100., max(0., -v)/100.
    return (positif, negatif) if positif_a_gauche else (negatif, positif)


def cellules_pave(surge, sway, yaw):
    """Fraction d'activation [0, 1] de chaque case du pavé (surge, sway, yaw en % signés).

    Positifs : avance, gauche, rotation à gauche. La croix centrale est active à l'arrêt.
    """
    f = lambda v: min(1., abs(float(v))/100.)
    return {'rot_g': f(yaw) if yaw > 0 else 0., 'rot_d': f(yaw) if yaw < 0 else 0.,
            'avance': f(surge) if surge > 0 else 0., 'recul': f(surge) if surge < 0 else 0.,
            'gauche': f(sway) if sway > 0 else 0., 'droite': f(sway) if sway < 0 else 0.,
            'arret': 1. if not (round(surge) or round(sway) or round(yaw)) else 0.}


def teinte(fraction):
    """Blanc → vert selon l'activation ; un minimum reste visible dès qu'une case est active."""
    if fraction <= 0:
        return CASE
    t = max(.35, min(1., fraction))
    base = tuple(int(CASE[i:i+2], 16) for i in (1, 3, 5))
    cible = tuple(int(VERT[i:i+2], 16) for i in (1, 3, 5))
    return '#%02x%02x%02x' % tuple(round(b+(c-b)*t) for b, c in zip(base, cible))


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
        super().__init__(parent, height=176, highlightthickness=1, highlightbackground=BORDURE,
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

    def _case_pave(self, cx, cy, cote, fraction, icone):
        self.create_rectangle(cx-cote/2, cy-cote/2, cx+cote/2, cy+cote/2, fill=teinte(fraction),
                              outline=VERT if fraction > 0 else BORDURE, tags=('pave',))
        r = cote*.36
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
        largeur = max(self.winfo_width(), 280)
        self.configure(background=FOND_CONNECTE if self._connecte else FOND_HORS_LIGNE)
        self.create_text(10, 12, anchor='w', font=('TkDefaultFont', 9, 'bold'),
                         fill=ENCRE if self._connecte else SECONDAIRE,
                         text='ROBOT CONNECTÉ' if self._connecte else 'ROBOT NON CONNECTÉ · TEST DES COMMANDES')
        # Pavé 3 × 3 à gauche.
        cote, trou, marge = 36, 4, 10
        x0, y0 = marge, 26
        fractions = cellules_pave(*self._valeurs)
        disposition = (('rot_g', 'rot_g'), ('avance', 'haut'), ('rot_d', 'rot_d'),
                       ('gauche', 'gauche'), ('arret', 'croix'), ('droite', 'droite'),
                       (None, None), ('recul', 'bas'), (None, None))
        for indice, (nom, icone) in enumerate(disposition):
            if nom is None:
                continue
            ligne, colonne = divmod(indice, 3)
            self._case_pave(x0+cote/2+colonne*(cote+trou), y0+cote/2+ligne*(cote+trou), cote, fractions[nom], icone)
        pave_largeur = 3*cote+2*trou
        # Barres Surge / Sway / Yaw à droite.
        gauche_barres = x0+pave_largeur+14
        ecart, haut = 6, 24
        case = (largeur-marge-gauche_barres-ecart)/2
        for (axe, nom_g, nom_d, positif_a_gauche), valeur in zip(LIGNES, self._valeurs):
            self.create_text(gauche_barres, haut+2, anchor='w', text=axe.upper(), fill=SECONDAIRE,
                             font=('TkDefaultFont', 8, 'bold'))
            pourcent = f'{abs(valeur)} %' if valeur else ''
            self.create_text(largeur-marge, haut+2, anchor='e', text=pourcent, fill=ENCRE,
                             font=('TkDefaultFont', 8, 'bold'))
            fractions_barre = remplissages(valeur, positif_a_gauche)
            for indice, (nom, fraction) in enumerate(zip((nom_g, nom_d), fractions_barre)):
                xa = gauche_barres+indice*(case+ecart)
                xb = xa+case
                ya, yb = haut+12, haut+34
                self.create_rectangle(xa, ya, xb, yb, fill=CASE, outline=BORDURE, tags=('barre',))
                if fraction > 0:
                    # Le remplissage part du centre : de la droite pour la case de gauche.
                    if indice == 0:
                        self.create_rectangle(xb-case*fraction, ya, xb, yb, fill=VERT, outline=VERT, tags=('barre', 'rempli'))
                    else:
                        self.create_rectangle(xa, ya, xa+case*fraction, yb, fill=VERT, outline=VERT, tags=('barre', 'rempli'))
                self.create_text((xa+xb)/2, (ya+yb)/2, text=nom, fill='white' if fraction > .5 else CASE_TEXTE,
                                 font=('TkDefaultFont', 8))
            haut += 40
        if self._note:
            self.create_text(10, max(haut, y0+3*cote+2*trou+10)+2, anchor='w', text=self._note, fill=SECONDAIRE,
                             font=('TkDefaultFont', 8))
