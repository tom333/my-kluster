# Pas de packaging (exécution via `uv run --with pytest`) : le répertoire des
# modules doit être ajouté au chemin d'import pour que `import normalize` marche.
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
