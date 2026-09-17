# Crépuscule — serveur de monde partagé

Plusieurs joueurs se déplacent sur une grille commune. Le serveur est en Python,
le client est une page web. Cette tranche ne couvre **que** le déplacement et la
synchronisation : ni combat, ni inventaire, ni persistance sur disque.

## Ce qui est imposé — la surface observable

Elle est imposée parce que d'autres programmes doivent parler à ton serveur.
Tout le reste est à toi.

Lancement :

```bash
python3 serveur.py --port <N>
```

WebSocket sur `ws://127.0.0.1:<N>/ws`.

Messages **client → serveur** :

```json
{"type": "entrer",  "jeton": "<chaine>"}
{"type": "bouger",  "dx": <entier>, "dy": <entier>}
```

Messages **serveur → client** :

```json
{"type": "bienvenue", "id": "<chaine>", "x": <entier>, "y": <entier>}
{"type": "etat", "tick": <entier>, "joueurs": {"<id>": [x, y]}}
```

Le client web expose, dans `client/reduction.js` :

```js
export function reduire(etat, message) { /* rend le NOUVEL etat, sans muter */ }
```

`etat` est un objet `{ tick, joueurs }`, `joueurs` associant un identifiant à
`[x, y]`. Un message inconnu laisse l'état inchangé.

## Le contrat — ce qui doit être VRAI

La grille fait 32 × 32, coins `(0,0)` et `(31,31)`.

1. Un joueur qui entre avec un jeton jamais vu apparaît en `(0,0)`.
2. Un joueur qui entre avec un jeton **déjà vu** retrouve la position qu'il avait
   en partant.
3. Un déplacement vaut au plus une case par axe. Un `bouger` qui ne respecte pas
   ça laisse la position **inchangée**.
4. Une position reste dans la grille.
5. **Tout client connecté doit pouvoir connaître la position de tous les joueurs
   connectés** — y compris ceux qui étaient déjà là avant son arrivée.
6. Quand plusieurs déplacements arrivent pendant le même tick, tous les clients
   finissent par voir **le même état**. Aucun client ne doit observer un monde
   qui diverge de celui d'un autre.

Rien ci-dessus ne dit COMMENT. Les mécanismes sont ta décision.

## Contrôle

```bash
python3 verifie_visible.py
```

Ce contrôle est **partiel** : deux joueurs entrent et bougent, c'est tout. Le
passer ne dit rien des points 2, 3, 5 et 6.
