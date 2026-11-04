"""Encart visuel des commandes de conduite : surge, sway et yaw en pourcentage.

Chaque axe a deux cases, une par sens. Une case se remplit en vert depuis le
centre vers l'extérieur, proportionnellement à la puissance demandée :
au joystick le remplissage suit l'inclinaison, au clavier il reste fixe
(tout ou rien) à la valeur du réglage PWM. Le fond change de couleur quand le
robot n'est pas connecté : l'encart reste utile pour tester les commandes.

Le calcul est séparé du dessin (fonctions pures en haut du fichier) pour pouvoir
être vérifié sans écran.
"""
import tkinter as tk
from apparence import ENCRE, SECONDAIRE, BORDURE

VERT = '#2f9e6e'
CASE = '#ffffff'
CASE_TEXTE = '#4d5f73'
FOND_CONNECTE = '#e6f2ea'
FOND_HORS_LIGNE = '#f2eadf'

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


class EncartCommandes(tk.Canvas):
    def __init__(self, parent, **options):
        super().__init__(parent, height=158, highlightthickness=1, highlightbackground=BORDURE,
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

    def dessiner(self):
        self.delete('all')
        largeur = max(self.winfo_width(), 220)
        self.configure(background=FOND_CONNECTE if self._connecte else FOND_HORS_LIGNE)
        self.create_text(10, 12, anchor='w', font=('TkDefaultFont', 9, 'bold'),
                         fill=ENCRE if self._connecte else SECONDAIRE,
                         text='ROBOT CONNECTÉ' if self._connecte else 'ROBOT NON CONNECTÉ · TEST DES COMMANDES')
        marge, ecart, haut = 10, 6, 24
        case = (largeur-2*marge-ecart)/2
        for (axe, gauche, droite, positif_a_gauche), valeur in zip(LIGNES, self._valeurs):
            self.create_text(marge, haut+2, anchor='w', text=axe.upper(), fill=SECONDAIRE,
                             font=('TkDefaultFont', 8, 'bold'))
            pourcent = f'{abs(valeur)} %' if valeur else ''
            self.create_text(largeur-marge, haut+2, anchor='e', text=pourcent, fill=ENCRE,
                             font=('TkDefaultFont', 8, 'bold'))
            fractions = remplissages(valeur, positif_a_gauche)
            for indice, (nom, fraction) in enumerate(zip((gauche, droite), fractions)):
                x0 = marge+indice*(case+ecart)
                x1 = x0+case
                y0, y1 = haut+12, haut+34
                self.create_rectangle(x0, y0, x1, y1, fill=CASE, outline=BORDURE)
                if fraction > 0:
                    # Le remplissage part du centre : de la droite pour la case de gauche.
                    if indice == 0:
                        self.create_rectangle(x1-case*fraction, y0, x1, y1, fill=VERT, outline=VERT)
                    else:
                        self.create_rectangle(x0, y0, x0+case*fraction, y1, fill=VERT, outline=VERT)
                self.create_text((x0+x1)/2, (y0+y1)/2, text=nom, fill='white' if fraction > .5 else CASE_TEXTE,
                                 font=('TkDefaultFont', 9))
            haut += 40
        if self._note:
            self.create_text(10, haut+2, anchor='w', text=self._note, fill=SECONDAIRE, font=('TkDefaultFont', 8))
