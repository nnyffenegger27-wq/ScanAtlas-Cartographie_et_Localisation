"""Gestes souris sur une pose ; aucune modification des mesures polaires.

Le scan est choisi dans la liste, puis le geste commence dans le graphique.
La rotation se fait autour de l'origine du scan, jamais autour du curseur.
"""
import numpy as np


class ManipulationScan:
    def __init__(self, canvas, axe, mode, selection, apercu, terminer):
        self.canvas, self.axe = canvas, axe
        self.mode, self.selection = mode, selection
        self.apercu, self.terminer = apercu, terminer
        self.geste = None
        for nom, action in [('button_press_event', self.presser),
                            ('motion_notify_event', self.bouger),
                            ('button_release_event', self.relacher),
                            ('key_press_event', self.touche)]:
            canvas.mpl_connect(nom, action)

    def actif(self):
        barre = getattr(self.canvas, 'toolbar', None)
        return bool(barre and barre.mode)

    def position(self, event):
        if event.inaxes is not self.axe or event.xdata is None or event.ydata is None:
            return None
        p = np.array([event.xdata, event.ydata], float)
        return p if np.isfinite(p).all() else None

    def angle(self, p, origine):
        # Trop près du pivot, l'angle devient numériquement et visuellement instable.
        if np.linalg.norm(self.axe.transData.transform(p) -
                          self.axe.transData.transform(origine)) < 8:
            return None
        d = p - origine
        return float(np.arctan2(d[1], d[0]))

    def presser(self, event):
        self.annuler()
        mode = self.mode()
        if event.button != 1 or self.actif() or mode not in ('deplacer', 'tourner'):
            return
        p = self.position(event)
        scan = self.selection() if p is not None else None
        if scan is None:
            return
        pose = list(scan.pose)
        angle = self.angle(p, pose[:2]) if mode == 'tourner' else None
        if mode == 'tourner' and angle is None:
            return
        self.geste = dict(scan=scan, pose=pose, debut=p, mode=mode,
                          angle=angle, rotation=0., limites=(self.axe.get_xlim(), self.axe.get_ylim()))

    def bouger(self, event):
        g = self.geste
        if g is None:
            return
        if self.mode() != g['mode'] or self.actif():
            self.annuler()
            return
        p = self.position(event)
        if p is None:
            return
        pose = list(g['pose'])
        if g['mode'] == 'deplacer':
            pose[:2] = (np.asarray(pose[:2]) + p - g['debut']).tolist()
        else:
            angle = self.angle(p, pose[:2])
            if angle is None:
                return
            # Écart signé court : passage +180/-180 sans saut de tour complet.
            g['rotation'] += np.arctan2(np.sin(angle-g['angle']), np.cos(angle-g['angle']))
            g['angle'] = angle
            pose[2] = (pose[2] + np.rad2deg(g['rotation']) + 180.) % 360. - 180.
        g['scan'].pose = pose
        self.apercu(g['scan'], g['limites'])

    def relacher(self, event):
        if self.geste is None or event.button != 1:
            return
        self.bouger(event)
        g, self.geste = self.geste, None
        if g is not None and not np.allclose(g['scan'].pose, g['pose'], rtol=0, atol=1e-12):
            self.terminer()

    def annuler(self):
        g, self.geste = self.geste, None
        if g is not None:
            g['scan'].pose = g['pose']
            self.apercu(g['scan'], g['limites'])

    def touche(self, event):
        if event.key == 'escape':
            self.annuler()
