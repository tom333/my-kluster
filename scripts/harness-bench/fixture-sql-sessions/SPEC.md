# Sessions d'activité

Le fichier `evenements.sqlite` contient une table :

```sql
CREATE TABLE evenements (
  utilisateur INTEGER NOT NULL,
  horodatage  TEXT    NOT NULL   -- 'AAAA-MM-JJ HH:MM:SS'
);
```

## Contrat

Pour chaque utilisateur, ordonner ses événements par horodatage croissant et les
découper en **sessions**.

- Une nouvelle session commence quand l'écart avec l'événement précédent **du
  même utilisateur** dépasse **strictement 45 minutes**.
- Un écart de 45 minutes pile reste dans la MÊME session.
- La numérotation repart à `1` pour chaque utilisateur.

Rendre exactement ces six colonnes, dans cet ordre :

| colonne | contenu |
|---|---|
| `utilisateur` | |
| `session` | 1, 2, 3… par utilisateur |
| `debut` | horodatage du premier événement de la session |
| `fin` | horodatage du dernier événement de la session |
| `evenements` | nombre d'événements de la session |
| `duree_minutes` | minutes entières entre `debut` et `fin` |

Trier le résultat par `utilisateur` croissant, puis `session` croissant.

## Ce qu'on attend de toi

Écris la requête, et elle seule, dans **`reponse.sql`**. Un seul `SELECT`, sans
`CREATE`, sans `INSERT`, sans point-virgule final.

## Contrôle

```bash
python3 verifie_visible.py
```

Ce contrôle est **partiel** : il passe sur des cas simples et ne dit rien des cas
limites. Le passer ne prouve pas que la requête est juste.
