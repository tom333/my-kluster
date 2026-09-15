# Configuration omp du banc

Copie versionnée de `~/.omp/agent/`, qui est la configuration **réellement
utilisée** par le harnais `omp` du banc. Le lanceur ne passe aucun réglage en
ligne de commande : mesurer autre chose que ce qui est installé n'aurait pas
d'intérêt.

| fichier | rôle |
|---|---|
| `APPEND_SYSTEM.md` | prompt de méthode, chargé automatiquement (vérifié par sonde) |
| `lsp.json` | `dartls`, marqueurs racine dont `.git` — la détection est cwd-only **au démarrage**, sans récursion |
| `models.yml` | fournisseur LocalAI ; `apiKey` est un **nom de variable**, pas une clé |
| `rules/` | règles TTSR **génériques** — l'arme du banc |
| `rules-ajustees-20260915/` | les mêmes, **ajustées à la fixture** — conservées comme bras témoin |

## Pourquoi deux jeux de règles

Le premier jeu déclenchait sur `CustomPainter` et sur `import 'package:`. Les
deux sont du Dart, et `CustomPainter` est précisément la façon dont *cette*
fixture échoue. Une règle écrite en connaissant la réponse ne mesure pas un
mécanisme : elle mesure sa propre rédaction.

Le jeu générique déclenche sur l'invariant, pas sur le langage :

- `verify-package-import` — un chemin qui pointe **dans** un paquet tiers,
  c'est-à-dire un identifiant non relatif suivi d'un séparateur. Vérifié sur
  Dart, TypeScript, JavaScript, Python, Rust et C++ : 6 déclenchements. Les
  chemins relatifs (ton propre code) restent silencieux : 4 silences.
- `no-silent-substitution` — l'**intention** de remplacer une dépendance nommée
  par du code maison. Aucun mot d'un langage. `CustomPainter` ne déclenche plus.

Les deux renvoient vers les outils **génériques** du harnais (`lsp`, `glob`,
`read`, `bash`), pas vers un cache de paquets particulier. C'est le point : le
levier mesuré est « pousser le modèle vers un outil qu'il n'utilise jamais
spontanément » — zéro appel LSP sur 14 disponibles, serveur actif, sur toutes
les exécutions du 2026-09-15.

## Rejouer les tests de généricité

```bash
omp ttsr test -r ~/.omp/agent/rules/verify-package-import.md \
  --source tool --tool edit --path a.rs "use serde::Serialize;"
```
