# Contrôle vocal Home Assistant — Musique, Kodi, Alerte absence

> Objectif : piloter la maison à la voix avec un **maximum d'automatisations côté HA**,
> en privilégiant les **intents/scripts locaux (0 token)** et en ne déléguant à l'agent
> Hermes (payant, Gemini/OpenRouter) qu'en **fallback** sur miss d'intent.

Statut : **design** (rien d'appliqué). Date : 2026-06-10.
Auteur : Thomas + agent.

Apparenté : `docs/hermes-voice-hybrid.md` (câblage du pipeline voix HA ↔ agent Hermes,
plan plus large). Ce spec couvre uniquement les **3 capacités** demandées et leurs
automations/scripts HA.

---

## Principes directeurs (décisions actées)

1. **Coût token minimal.** Tout ce qui peut être un intent natif ou un script local
   HA le reste (gratuit, instantané, hors-ligne). L'agent Hermes (cerveau Gemini) =
   fallback uniquement.
2. **Telegram = sortant only.** Les alertes arrivent dans le chat Telegram via le
   **bot Hermes réutilisé** (`rest_command` HA → API Telegram directe). On ne fait
   **pas** transiter par l'agent Hermes (sinon : ~16k tokens/alerte + conversation
   HA↔Hermes polluant le chat). Telegram ne voit que le message d'alerte propre.
3. **Tout en `.storage` via MCP.** Automations, scripts, helpers, et phrases vocales
   custom (`trigger: conversation`) sont créables par l'API MCP — **aucun accès
   fichier `/config` requis**. Cohérent avec "max d'automatisations côté HA".
4. **Exécution = skill HA best-practices.** La création effective des automations doit
   suivre `home-assistant-best-practices` (sentence triggers, conditions natives, pas
   de `device_id`, anti-spam via helper, modes corrects).

---

## État réel découvert (inventaire 2026-06-10)

HA 2026.6.2, langue `fr`, TZ `Pacific/Noumea`. Areas : **Salon** (9 entités),
Cuisine (vide), Chambre (vide).

### Entités clés

| Entité | Nom | Rôle |
|---|---|---|
| `media_player.kodi` | Kodi salon | Lecteur Kodi réel (état `playing`). `supported_features=186303`. `kodi.call_method` (JSON-RPC) dispo. |
| `media_player.kodi_kodi_3` | Kodi (multiroom) | Wrapper Music Assistant de Kodi |
| `media_player.salon_2` | Salon (multiroom) | **Seul player Music Assistant** (cible musique) |
| `media_player.salon` | Nest | Cast direct |
| `person.thomas` / `person.emilie` | — | Présence (home / not_home) |

### Briques déjà en place

| Brique | État | Action prévue |
|---|---|---|
| `script.play_music` ("Jouer musique (MA)") | ✅ marche : search MA library → joue 1er hit sur `player` (défaut `salon_2`). Biblio **locale** (pas de streaming). Aujourd'hui appelé par Hermes. | **Réutiliser**, ajouter le déclenchement vocal natif + mapping pièce→player |
| `automation.alerte_lecture_kodi_quand_thomas_part` | ✅ existe MAIS : trigger = *Thomas part* ; action = **push mobile** `notify.mobile_app_portable_thomas` | **Réécrire** (nouvelle logique + Telegram) |
| Pipeline voix local | ✅ Whisper STT + Piper TTS + satellite `assist_satellite.work_laptop_voice_satellite_assist` | Réutiliser tel quel |
| Agents conversation | `conversation.home_assistant` (intents natifs) + Extended OpenAI | Fallback géré par le plan voix-hybride (hors scope) |
| Music Assistant | `music_assistant.search` / `play_media` / `play_announcement` | Réutiliser |

### Telegram / Hermes

- Bot Telegram = celui d'Hermes. Token dans le SealedSecret `hermes-secrets`
  (`TELEGRAM_BOT_TOKEN`), chat cible `TELEGRAM_HOME_CHANNEL=843341688` (Thomas).
- Hermes n'expose **pas** de webhook entrant simple ; son seul canal entrant
  (`:8642`) est un gateway OpenAI-compat (= tour LLM coûteux). → on ne l'utilise pas
  pour l'alerte.

---

## Feature 1 — "joue X dans le salon" (musique vocale)

**But** : commande vocale "joue {artiste/titre/album} dans le salon" → lecture MA.

**Gap** : `script.play_music` prend `player` en argument et est appelé par Hermes ;
pas de déclenchement vocal natif ni de mapping pièce→player.

**Approche (local-first)** :
1. Affecter `media_player.salon_2` à l'area **Salon** ; l'exposer à Assist
   (`conversation`).
2. **Tester d'abord l'intent natif `HassMediaSearchAndPlay`** (HA 2026.6 + Music
   Assistant) : "joue Daft Punk dans le salon" peut marcher **sans phrase custom**.
   Si OK → 0 dev pour le cas nominal.
3. **Fallback fiabilité** : automation `trigger: conversation` avec
   `command: ["joue {query} dans {room}", "mets {query} dans {room}", ...]` →
   `script.play_music` avec un mapping `{room}` → player :
   - `salon` → `media_player.salon_2`
   - (cuisine / chambre : aucun player MA aujourd'hui → réponse vocale "pas
     d'enceinte dans cette pièce")

**Réalité multiroom (à acter)** : seul **Salon** possède un player Music Assistant.
"Multiroom" est donc **salon-only** tant qu'aucun autre player MA n'est ajouté. Le
mapping pièce→player est conçu extensible (ajouter une ligne quand un player
cuisine/chambre existera).

**Sortie** : musique sur l'enceinte du salon, 0 token.

---

## Feature 2 — contrôle vocal de Kodi

### 2a. Transport (stop / pause / reprise / suivant) — natif

- Exposer `media_player.kodi` à Assist + area Salon.
- Les intents natifs (`HassMediaPause`, `HassMediaUnpause`, `HassMediaNext`, stop)
  couvrent "pause", "reprends", "suivant", "arrête". 0 token.
- Vérifier le rendu FR des phrases ; ajouter des alias/`trigger: conversation` de
  confort si besoin ("mets pause sur Kodi").

### 2b. "lance le film X" (recherche biblio Kodi) — script + JSON-RPC

- Pas d'intent natif "joue le film par titre" → **phrase custom**.
- Automation `trigger: conversation`, `command: ["lance le film {titre}",
  "lance {titre} sur kodi", "joue le film {titre}"]` → `script.kodi_play_title`.
- `script.kodi_play_title(titre)` :
  1. `kodi.call_method` → `VideoLibrary.GetMovies` (avec `filter` sur le titre, ou
     récupération + match flou côté template).
  2. Si hit → `kodi.call_method` `Player.Open` sur le `movieid` trouvé.
  3. Sinon → (option) recherche épisode `VideoLibrary.GetEpisodes`, sinon réponse
     vocale "film introuvable dans la médiathèque".
- **Pièce la plus risquée** → **spike Phase 0** pour valider le schéma JSON-RPC réel
  (format `filter`, champs retournés, `Player.Open` par id) sur ce Kodi.

---

## Feature 3 — alerte "lecture Kodi pendant absence" (réécriture)

Remplace `automation.alerte_lecture_kodi_quand_thomas_part`.

**Nouvelle logique** :
- **Trigger** : `media_player.kodi` → `playing` (avec `for: 30s` pour ignorer les
  faux départs / zapping).
- **Conditions** (personne à la maison) : `person.thomas` != `home` **ET**
  `person.emilie` != `home` (deux conditions `state` natives, AND).
- **Anti-spam** : helper `input_boolean.kodi_alerte_envoyee`.
  - Condition supplémentaire : alerte seulement si `kodi_alerte_envoyee` = off.
  - À l'envoi : passer le booléen à on.
  - Reset (→ off) par une 2e automation quand `media_player.kodi` quitte `playing`
    **ou** quand quelqu'un rentre (`person.*` → `home`).
  - → **1 alerte par session de lecture**, pas de spam sur pause/reprise.
- **Action** : `rest_command.telegram_alerte` (cf. ci-dessous), message :
  > « Kodi salon lit "{{ titre }}" et personne n'est à la maison. »

### Canal Telegram — `rest_command`

- Définir un `rest_command.telegram_alerte` (créable côté HA ; **stocke le token**
  dans les secrets HA — copie du `TELEGRAM_BOT_TOKEN` Hermes) :
  ```yaml
  rest_command:
    telegram_alerte:
      url: "https://api.telegram.org/bot{{ token }}/sendMessage"
      method: POST
      content_type: "application/json"
      payload: '{"chat_id": "843341688", "text": "{{ message }}"}'
  ```
  (Le token doit venir d'un secret HA, pas en clair ; `rest_command` vit dans
  `configuration.yaml`/`secrets.yaml` → **accès `/config` requis** — voir Phase 0.)
- **Sortant only** : Telegram ne reçoit que ce message, aucune conversation
  HA↔Hermes.

> ⚠️ `rest_command` n'est **pas** créable via MCP `.storage` (c'est du YAML
> `configuration.yaml`). C'est le **seul** morceau nécessitant l'accès fichier HA.
> Alternative si pas d'accès `/config` : utiliser `notify.mobile_app_portable_thomas`
> (push, déjà dispo) en attendant — à trancher Phase 0.

---

## Phasage

| Phase | Contenu | Risque | Valeur |
|---|---|---|---|
| **0 — Vérifs / spikes** | (a) `HassMediaSearchAndPlay` couvre-t-il "joue X dans le salon" ? (b) intents transport FR sur Kodi. (c) schéma JSON-RPC `VideoLibrary.GetMovies`/`Player.Open` réel. (d) accès `/config` HA pour `rest_command` (addon File editor / Studio Code Server / Samba ?) sinon fallback push. | — | débloque tout |
| **1 — Alerte (F3)** | Helper `input_boolean`, réécriture automation + automation de reset, canal Telegram (ou push fallback). 100% HA, indépendant voix. | faible | immédiate |
| **2 — Musique vocale (F1)** | Exposition `salon_2` + area, intent natif, fallback `conversation`→`play_music` avec mapping pièce. | faible | haute |
| **3 — Kodi vocal (F2)** | Transport natif (2a) + `script.kodi_play_title` + sentence trigger (2b). | moyen (2b) | haute |

Ordre conseillé : **0 → 1 → 2 → 3** (valeur immédiate + risque croissant en fin).

---

## Risques / notes

- **Multiroom = salon-only** aujourd'hui (1 seul player MA). Acté ; design extensible.
- **Music Assistant = biblio locale** (pas de streaming) : `play_music` ne résout que
  la musique possédée.
- **`rest_command` Telegram** = seul élément hors-`.storage` (YAML `/config`). Si
  l'accès fichier n'est pas dispo → fallback push mobile décidé Phase 0.
- **Kodi JSON-RPC** : format `filter`/`Player.Open` à valider par spike (varie selon
  version Kodi).
- **Exposition Assist partagée** avec le vocal HA existant : exposer/affecter des
  entités peut impacter d'autres usages — vérifier avant.
- **Fallback Hermes** (cerveau Gemini) : hors scope de ce spec (cf.
  `docs/hermes-voice-hybrid.md`) ; ici on ne crée que des intents/scripts locaux.

---

## Critères de succès

- "joue {X} dans le salon" → musique sur `salon_2`, **0 token**.
- "pause / reprends / arrête / suivant" sur Kodi → transport, **0 token**.
- "lance le film {X}" → Kodi lance le film de la médiathèque (ou réponse "introuvable").
- Kodi démarre alors que **Thomas ET Emilie absents** → **1** message Telegram
  sortant (pas de spam, pas de conversation agent dans le chat).
