"""Manettes Xbox sous Windows via XInput, sans dépendance supplémentaire.

Le maintien de LB autorise le mouvement. Relâchement, déconnexion, perte de
focus et Espace rétablissent STOP par les mêmes baux que le clavier.
"""
import ctypes
import sys


def commande_axes(x,y,rotation,boutons):
    if boutons & 0x2000 or not boutons & 0x100:  # B = arrêt ; LB maintenu.
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

    def lire(self):
        if self.api is None:return False,'STOP',0
        for index in range(4):
            etat=State()
            if self.api(index,ctypes.byref(etat))==0:
                p=etat.pad
                cmd,niveau=commande_axes(p.lx/32768.,p.ly/32768.,p.rx/32768.,p.buttons)
                return True,cmd,niveau
        return False,'STOP',0
