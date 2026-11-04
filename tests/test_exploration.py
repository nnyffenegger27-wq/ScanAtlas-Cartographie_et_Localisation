"""Exploration autonome en boucle fermée sur salles simulées (temps simulé : pas d'attente réelle)."""
import os
import unittest
import numpy as np
from atlas.calcul.cartographie import mesures_valides
from atlas.calcul.cartographie_direct import CarteDirecte
from atlas.robot.exploration import Explorateur
from atlas.calcul.localisation import erreur_pose
from atlas.simulation.simulation import SalleVirtuelle, SALLE_DEMO, SALLE_DEUX_PIECES, SALLES, distance_aux_murs


def points_locaux(etat):
    sc = etat.scan
    v = mesures_valides(sc, .12, 12., 0)
    th = np.deg2rad(sc.mesures[v, 0]-sc.angle_reference)
    r = sc.mesures[v, 1]
    return np.column_stack([r*np.cos(th), r*np.sin(th)])


def explorer(murs, depart, duree_max=240., puissance=60, mapping=lambda c: c, bruit=.003, **options):
    """Boucle : robot simulé → CarteDirecte (SLAM) → Explorateur → commande. Retourne un compte rendu."""
    salle = SalleVirtuelle(murs, pose=depart, derive=.05, bruit=bruit)
    carte, ex = CarteDirecte(), Explorateur()
    ex.demarrer(0.)
    cmd, dt = (0., 0., 0.), .1
    ecart_min, depart_vrai, erreurs, k = np.inf, np.asarray(depart, float), [], 0
    while salle.t < duree_max and ex.etat == 'exploration':
        k += 1
        v = mapping(cmd)
        salle.avancer((v[0]*puissance, v[1]*puissance, 0.), dt)
        ecart_min = min(ecart_min, distance_aux_murs(salle.pose[:2], murs))
        etat = carte.traiter(salle.trame())
        if not etat.accepte:
            cmd = (0., 0., 0.)
            continue
        # le suivi part de l'origine (0, 0, 0) : on compare dans ce repère
        c, s = np.cos(np.deg2rad(depart_vrai[2])), np.sin(np.deg2rad(depart_vrai[2]))
        d = salle.pose[:2]-depart_vrai[:2]
        attendu = np.array([c*d[0]+s*d[1], -s*d[0]+c*d[1]])
        erreurs.append(float(np.linalg.norm(carte.pose[:2]-attendu)))
        if k == 1 or k % 10 == 0 or ex.replanifier:
            ex.planifier(carte.grille, carte.pose, salle.t)
        cmd = ex.commande(carte.pose, points_locaux(etat), salle.t)
    return dict(ex=ex, carte=carte, salle=salle, ecart_min=ecart_min, erreur_max=max(erreurs or [0.]))


def observe_libre(grille, x, y):
    ix = int((x-grille.origine[0])/grille.resolution)
    iy = int((y-grille.origine[1])/grille.resolution)
    h, w = grille.log_odds.shape
    return 0 <= ix < w and 0 <= iy < h and bool(grille.observe[iy, ix]) and grille.log_odds[iy, ix] <= 0


class ExplorationComplete(unittest.TestCase):
    def test_deux_pieces_reliees_par_une_porte(self):
        r = explorer(SALLE_DEUX_PIECES, (0., -1., 0.))
        ex = r['ex']
        self.assertEqual(ex.etat, 'termine', ex.message)
        self.assertLess(r['salle'].t, 200)
        self.assertGreater(r['ecart_min'], .15)                    # jamais contre un mur (rayon du robot simulé : 17 cm)
        self.assertLess(r['erreur_max'], .06)                      # le suivi n'a pas dérivé pendant l'exploration
        # repère de la carte = pose de départ : la porte est à x = 3, y entre 0,2 et 1,2 (monde) soit y + 1 dans la carte
        g = r['carte'].grille
        for monde in [(-2., -1.), (-2., 2.), (1.5, -1.), (1.5, 2.), (5., -1.), (5., 2.), (7., 1.)]:
            self.assertTrue(observe_libre(g, monde[0]-0., monde[1]+1.), monde)    # les deux pièces sont vues
        self.assertEqual(ex.chemin, [])

    def test_salle_simple_avec_mur_interieur(self):
        r = explorer(SALLE_DEMO, (0., 0., 0.), duree_max=120.)
        self.assertEqual(r['ex'].etat, 'termine', r['ex'].message)
        self.assertGreater(r['ecart_min'], .15)
        self.assertLess(r['erreur_max'], .05)

    def test_depart_pres_d_un_mur(self):
        r = explorer(SALLE_DEMO, (-2.7, -1.7, 40.), duree_max=120.)       # presque dans un coin, cap quelconque
        self.assertEqual(r['ex'].etat, 'termine', r['ex'].message)
        self.assertGreater(r['ecart_min'], .12)


class Appartement(unittest.TestCase):
    """Salle de 16 m × 10 m avec couloir, portes de 90 cm et une vingtaine de meubles."""
    murs, depart = SALLES['appartement']['murs'], SALLES['appartement']['depart']

    def test_sortie_du_salon_par_la_porte_sans_toucher_un_meuble(self):
        r = explorer(self.murs, self.depart, duree_max=100., puissance=100)
        self.assertGreater(r['salle'].pose[1], 6.3)                # le robot est passé par la porte (y = 6) et est dans le couloir
        self.assertGreater(r['ecart_min'], .15)
        self.assertLess(r['erreur_max'], .12)       # pics de 9 cm à pleine vitesse près d'une table, sans dérive cumulée

    @unittest.skipUnless(os.environ.get('SCANATLAS_LENT'), 'exploration complète (~1 min) : SCANATLAS_LENT=1')
    def test_exploration_complete(self):
        r = explorer(self.murs, self.depart, duree_max=600., puissance=100)
        self.assertEqual(r['ex'].etat, 'termine', r['ex'].message)
        self.assertGreater(r['ecart_min'], .15)
        self.assertLess(r['erreur_max'], .12)       # pics de 9 cm à pleine vitesse près d'une table, sans dérive cumulée
        g = r['carte'].grille
        for monde in [(2., 4.6), (8., 3.), (14.8, 2.5), (.8, 6.6), (15.2, 6.6), (2.5, 8.2), (8.8, 8.5), (11., 8.7)]:
            self.assertTrue(observe_libre(g, monde[0]-self.depart[0], monde[1]-self.depart[1]), monde)


class Securites(unittest.TestCase):
    def explorateur_avec_chemin(self, chemin):
        ex = Explorateur()
        ex.demarrer(0.)
        ex.chemin = [tuple(p) for p in chemin]
        return ex

    def test_obstacle_devant_arrete_la_translation(self):
        ex = self.explorateur_avec_chemin([(3., 0.)])
        libre = ex.commande((0., 0., 0.), np.empty((0, 2)), 0.)
        self.assertGreater(libre[0], .4)
        ex2 = self.explorateur_avec_chemin([(3., 0.)])
        mur = np.column_stack([np.full(20, .19), np.linspace(-.3, .3, 20)])   # mur à 19 cm devant
        surge, sway, yaw = ex2.commande((0., 0., 0.), mur, 0.)
        self.assertLessEqual(surge, 0.01)                          # ne pousse pas contre le mur
        self.assertEqual(yaw, 0.)
        self.assertTrue(ex2.replanifier)                           # et demande un nouveau chemin

    def test_ralentit_en_approchant(self):
        vitesses = []
        for d in (1.5, .5, .3):
            ex = self.explorateur_avec_chemin([(5., 0.)])
            mur = np.column_stack([np.full(10, d), np.linspace(-.1, .1, 10)])
            vitesses.append(ex.commande((0., 0., 0.), mur, 0.)[0])
        self.assertGreater(vitesses[0], vitesses[1]); self.assertGreater(vitesses[1], vitesses[2])

    def test_repousse_le_long_d_un_mur_lateral(self):
        ex = self.explorateur_avec_chemin([(3., 0.)])
        mur = np.column_stack([np.linspace(-.5, .5, 30), np.full(30, .2)])     # mur à 20 cm sur la gauche
        surge, sway, _ = ex.commande((0., 0., 0.), mur, 0.)
        self.assertGreater(surge, .2)                              # continue d'avancer
        self.assertLess(sway, 0.)                                  # en s'écartant du mur (à droite)

    def test_chemin_dans_le_repere_monde_avec_cap(self):
        ex = self.explorateur_avec_chemin([(0., 3.)])             # cible au nord ; robot orienté vers l'est (cap 0)
        surge, sway, _ = ex.commande((0., 0., 0.), np.empty((0, 2)), 0.)
        self.assertAlmostEqual(surge, 0., places=2); self.assertGreater(sway, .4)     # va à sa gauche
        ex = self.explorateur_avec_chemin([(0., 3.)])
        surge, sway, _ = ex.commande((0., 0., 90.), np.empty((0, 2)), 0.)             # orienté au nord
        self.assertGreater(surge, .4); self.assertAlmostEqual(sway, 0., places=2)

    def test_hors_exploration_aucune_commande(self):
        ex = Explorateur()
        self.assertEqual(ex.commande((0., 0., 0.), np.empty((0, 2)), 0.), (0., 0., 0.))
        ex.demarrer(0.); ex.chemin = [(3., 0.)]
        ex.arreter('inactif', 'arrêt')
        self.assertEqual(ex.commande((0., 0., 0.), np.empty((0, 2)), 0.), (0., 0., 0.))

    def test_axes_inverses_detectes_et_exploration_arretee(self):
        r = explorer(SALLE_DEMO, (0., 0., 0.), duree_max=60., mapping=lambda c: (c[0], -c[1], c[2]))
        self.assertEqual(r['ex'].etat, 'erreur', r['ex'].message)
        self.assertIn('direction commandée', r['ex'].message)
        self.assertGreater(r['ecart_min'], .15)                    # arrêté avant de toucher un mur

    def test_moteurs_bloques_detectes(self):
        r = explorer(SALLE_DEUX_PIECES, (0., -1., 0.), duree_max=60., mapping=lambda c: (0., 0., 0.))   # des zones restent à voir
        self.assertEqual(r['ex'].etat, 'bloque', r['ex'].message)


if __name__ == '__main__':
    unittest.main()
