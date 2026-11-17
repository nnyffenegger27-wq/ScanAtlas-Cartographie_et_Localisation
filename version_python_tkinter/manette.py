"""Manettes Xbox sous Windows via XInput, sans dépendance supplémentaire.

Stick gauche : surge (avant/arrière) et sway (gauche/droite) ensemble.
Stick droit, axe horizontal : yaw (rotation). Aucun bouton à maintenir : la
manette est activée depuis l'écran. B coupe immédiatement le mouvement et
désactive le pilotage jusqu'à sa réactivation ; un appui sur RB bascule la
cartographie. Recentrage des sticks, déconnexion, perte de focus et Espace
rétablissent STOP par les mêmes baux que le clavier. Les conversions ci-dessous sont des fonctions pures, testables sans
manette.
"""
from dataclasses import dataclass
import ctypes
import math
import sys

ZONE_MORTE = .22
BOUTON_RB, BOUTON_B = 0x200, 0x2000


def _sans_zone_morte(valeur, zone=ZONE_MORTE):
    """Zone morte linéaire : 0 sous le seuil, puis remise à l'échelle jusqu'à 1."""
    magnitude = abs(valeur)
    if magnitude <= zone:
        return 0.
    return math.copysign(min(1., (magnitude-zone)/(1.-zone)), valeur)


def vecteur_manette(lx, ly, rx, boutons):
    """(surge, sway, yaw) dans [-1, 1], positifs = avance, gauche, rotation à gauche.

    Zone morte radiale sur le stick gauche : une diagonale franche garde les deux
    axes, un léger effleurement ne produit rien. Avec B, tout est nul.
    """
    if boutons & BOUTON_B:
        return 0., 0., 0.
    magnitude = math.hypot(lx, ly)
    if magnitude <= ZONE_MORTE:
        surge = sway = 0.
    else:
        facteur = min(1., (magnitude-ZONE_MORTE)/(1.-ZONE_MORTE))/magnitude
        surge, sway = ly*facteur, -lx*facteur  # Stick vers la droite = déplacement à droite.
    yaw = _sans_zone_morte(-rx)               # Stick vers la droite = rotation à droite.
    clip = lambda v: max(-1., min(1., v))
    return clip(surge), clip(sway), clip(yaw)


@dataclass(frozen=True)
class EtatManette:
    presente: bool = False
    surge: float = 0.
    sway: float = 0.
    yaw: float = 0.
    rb: bool = False
    stop: bool = False


def commande_axes(x,y,rotation,boutons):
    if boutons & BOUTON_B:  # B = arrêt.
        return 'STOP',0
    valeurs=[('FORWARD' if y>0 else 'BACK',abs(y)),
             ('STRAFE_R' if x>0 else 'STRAFE_L',abs(x)),
             ('RIGHT' if rotation>0 else 'LEFT',abs(rotation))]
    cmd,niveau=max(valeurs,key=lambda item:item[1])
    return (cmd,min(1.,niveau)) if niveau>.22 else ('STOP',0)


class Gamepad(ctypes.Structure):
    _fields_=[('buttons',ctypes.c_ushort),('lt',ctypes.c_ubyte),('rt',ctypes.c_ubyte),
              ('lx',ctypes.c_short),('ly',ctypes.c_short),('rx',ctypes.c_short),('ry',ctypes.c_short)]


class State(ctypes.Structure):
    _fields_=[('packet',ctypes.c_uint32),('pad',Gamepad)]


class ManetteXbox:
    def __init__(self):
        self.api=None
        if sys.platform=='win32':
            for nom in ('xinput1_4','xinput1_3','xinput9_1_0'):
                try:
                    self.api=ctypes.WinDLL(nom).XInputGetState
                    self.api.argtypes=[ctypes.c_uint32,ctypes.POINTER(State)]
                    self.api.restype=ctypes.c_uint32
                    break
                except OSError:continue

    def lire_etat(self):
        """Lecture complète : vecteur de conduite et boutons, sans effet de bord."""
        if self.api is None:return EtatManette()
        for index in range(4):
            etat=State()
            if self.api(index,ctypes.byref(etat))==0:
                p=etat.pad
                surge,sway,yaw=vecteur_manette(p.lx/32768.,p.ly/32768.,p.rx/32768.,p.buttons)
                return EtatManette(True,surge,sway,yaw,bool(p.buttons&BOUTON_RB),bool(p.buttons&BOUTON_B))
        return EtatManette()

    def lire(self):
        if self.api is None:return False,'STOP',0
        for index in range(4):
            etat=State()
            if self.api(index,ctypes.byref(etat))==0:
                p=etat.pad
                cmd,niveau=commande_axes(p.lx/32768.,p.ly/32768.,p.rx/32768.,p.buttons)
                return True,cmd,niveau
        return False,'STOP',0
