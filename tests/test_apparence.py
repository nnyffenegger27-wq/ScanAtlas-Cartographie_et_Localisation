"""Thème et ergonomie : le pavé de commandes et l'arrêt restent visibles sans défilement."""
import unittest


class Apparence(unittest.TestCase):
    def test_pave_et_arret_visibles_dans_une_fenetre_standard(self):
        from app import Atelier
        app = Atelier(); app.geometry('1366x768')
        try:
            app.onglets.select(app.wifi_cadre); app.update(); app.update_idletasks()
            bas = app.winfo_rooty()+app.winfo_height()
            encart = app.wifi_encart
            self.assertGreater(encart.winfo_width(), 200)
            self.assertLessEqual(encart.winfo_rooty()+encart.winfo_height(), bas)
            self.assertTrue(encart.winfo_viewable())
        finally:
            app.destroy()

    def test_constantes_de_palette_et_carte(self):
        import tkinter as tk
        from tkinter import ttk
        import apparence
        racine = tk.Tk()
        try:
            apparence.appliquer_theme(racine)
            interieur = apparence.carte_ui(racine, 'Titre')
            self.assertIsInstance(interieur, ttk.Frame)
            for nom in ('FOND', 'SURFACE', 'ENCRE', 'SECONDAIRE', 'ACCENT', 'BORDURE', 'DANGER', 'SUCCES'):
                self.assertRegex(getattr(apparence, nom), r'^#[0-9a-f]{6}$')
        finally:
            racine.destroy()


if __name__ == '__main__':
    unittest.main()
