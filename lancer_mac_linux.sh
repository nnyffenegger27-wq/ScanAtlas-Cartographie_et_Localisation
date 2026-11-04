#!/usr/bin/env bash
# ScanAtlas - lanceur macOS / Linux. Premiere fois : installe les dependances dans .venv, puis ouvre l'application.
#   ./lancer_mac_linux.sh            (si "Permission denied" : bash lancer_mac_linux.sh)
set -e
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "Python 3.10 ou plus recent est introuvable : installe-le (https://www.python.org/downloads/) puis relance." >&2
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "Premiere utilisation : creation de l'environnement Python..."
  "$PY" -m venv .venv
fi
if ! .venv/bin/python -c "import numpy, scipy, serial" >/dev/null 2>&1; then
  echo "Installation des dependances (une seule fois, connexion Internet necessaire)..."
  .venv/bin/python -m pip install -r requirements.txt
fi
echo "Demarrage de ScanAtlas : le navigateur va s'ouvrir. Ctrl+C quitte l'application."
exec .venv/bin/python scanatlas.py "$@"
