"""Point d'entrée : lance le serveur local et ouvre ScanAtlas dans le navigateur.

    python scanatlas.py [--port 8765] [--sans-navigateur]
"""
import argparse
import serveur


def main():
    p = argparse.ArgumentParser(description='ScanAtlas : cartographie et localisation avec le robot lidar.')
    p.add_argument('--port', type=int, default=8765, help='port local (8765 par défaut ; le suivant est pris s’il est occupé)')
    p.add_argument('--sans-navigateur', action='store_true', help='ne pas ouvrir le navigateur automatiquement')
    a = p.parse_args()
    serveur.demarrer(port=a.port, ouvrir=not a.sans_navigateur)


if __name__ == '__main__':
    main()
