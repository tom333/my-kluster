# Voix hybride Home Assistant + Hermes — plan d'implémentation

> Objectif : piloter la maison à la voix avec le bon curseur **intent-local-d'abord,
> cerveau Hermes au besoin**. Les commandes device courantes restent locales (Whisper +
> intents natifs HA = gratuit, instantané, hors-ligne) ; ce que les intents ne savent pas
> faire part dans l'agent Hermes (mémoire/skills/cron, continuité avec Telegram).

Statut : **plan** (rien d'appliqué côté pipeline voix au moment d'écrire). Date 2026-06-09.

## Pourquoi hybride (rappel décision)

| | HA cerveau (intents) | Hermes cerveau |
|---|---|---|
| Coût token | 0 sur intents | ~16k tokens/parole |
| Latence | ~100-300ms local | 2-8s (OpenRouter glm-4.5-air) |
| Privacy/offline | 100% local | cloud + data-training free-tier |
| Mémoire/raisonnement | faible | fort (mémoire partagée Telegram) |

→ Hybride = intents natifs pour ~90% (device), Hermes en fallback pour le complexe. On paie
tokens/latence **seulement** quand on a besoin du cerveau.

## État actuel (déjà en place)

Pipeline voix local **complet** :

| Brique | Entité / entry | État |
|---|---|---|
| STT | Wyoming `faster-whisper` (`01KSM71WKJTFFPT099JKXKFFTZ`) | loaded |
| TTS | Wyoming `piper` (`01KSM72QMRQJ5X2PFVBTKE4K90`), `tts.piper` | loaded |
| Satellite voix | `assist_satellite.work_laptop_voice_satellite_assist` | idle |
| Agent intents natifs | `conversation.home_assistant` | — |
| Agent LLM | `conversation.extended_openai_conversation` ("ChatGPT", entry `01KSY9BM8KMVCVKFYZP3RGDTB4`, config dans un **subentry** `conversation` reconfigurable) | pointe sur **OpenAI** |
| Hermes → HA | serveur MCP officiel HA (sens contrôle déjà câblé) | OK |
| Hermes | agent complet (mémoire/skills/cron) sur `glm-4.5-air` via OpenRouter ; gateway **OpenAI-compat `:8642`** (`model: hermes-agent`, auth `API_SERVER_KEY`) | OK |
| Features HA | `script.play_music`, `automation.alerte_lecture_kodi_quand_thomas_part`, Kodi exposé | OK |

**Tout le hardware + un agent LLM HA existent.** Manque : le brancher sur Hermes et activer
le mode local-d'abord.

## À changer / ajouter

1. Agent LLM HA → pointer sur **Hermes `:8642`** (au lieu d'OpenAI) pour la continuité mémoire voix↔Telegram.
2. Pipeline Assist : agent = Hermes, **"prefer handling commands locally" ON**.
3. Élagage de l'exposition Assist (49 → keep-list) pour fiabiliser les tool-calls quand Hermes intervient.
4. (option) wake word pour mains-libres.

## Inconnues à lever — Phase 0 (rien ne casse)

- **`:8642` = agent Hermes complet (mémoire/tools) ou passthrough modèle ?** Détermine si la
  voix hérite de la mémoire. Quasi-sûr "agent complet" (canal utilisé par le workspace).
  Test : `POST :8642/v1/chat/completions` avec un prompt sondant la mémoire/persona.
- **Double-contrôle** : si l'agent HA passe ses tools Assist à Hermes ET Hermes pilote via
  MCP → conflit. Décision : l'agent HA **relaie** (Assist-control OFF), **Hermes pilote via son MCP**.
- Confirmer le nom exact du toggle "prefer local intents" dans la version HA installée.
- Vérifier la **route réseau HA → Hermes** (`:8642` joignable depuis HA ; service/ingress, auth).

## Plan d'implémentation

### Phase 0 — Vérifications
- Test `:8642` full-agent vs passthrough.
- Joignabilité réseau HA → Hermes `:8642` + `API_SERVER_KEY`.
- Toggle prefer-local dans HA.

### Phase 1 — Hermes comme agent de conversation HA
- Reconfigurer le subentry `conversation` de `extended_openai_conversation` :
  `base_url = http://<hermes-svc>:8642/v1`, `model = hermes-agent`, clé = `API_SERVER_KEY`.
  Désactiver son contrôle-HA (relai pur).
- **Probablement étape UI manuelle** (Settings → Devices & Services → ChatGPT → reconfigure) :
  saisie de l'URL + clé. Non scellable côté HA via MCP.
- Alt : créer un **2e agent "Hermes"** et garder ChatGPT en secours (réversibilité).

### Phase 2 — Pipeline voix
- Pipeline = Whisper STT → agent Hermes → Piper TTS, **prefer-local ON**, assignée au
  satellite `work_laptop_voice`.

### Phase 3 — Élagage exposition Assist
Garder exposé à `conversation` UNIQUEMENT (keep-list) :
- `script.play_music`
- `media_player.kodi` (Kodi salon)
- `media_player.kodi_kodi_3` (**Kodi multiroom — cible confirmée**)
- `media_player.salon_2` (player Music Assistant)
- `media_player.salon` (= "Nest", cast, contrôle direct)

Retirer les ~44 autres (16 ports switch mikrotik, capteurs openweathermap, temp/humidité,
`vacuum.*`, `pi_hole`, bridge zigbee, `osmc`, `work_laptop_voice`, scripts test…).
⚠️ Exposition partagée avec le vocal HA — confirmer non-usage du vocal pour ces entités avant de couper.

### Phase 4 — Tests
- "allume X" / "pause Kodi" → **local, instantané, 0 token** (intent natif).
- "joue Daft Punk sur le salon" → `script.play_music` (biblio MA locale).
- "joue un truc calme et tamise le salon" → fallback Hermes (multi-étapes, mémoire).
- Vérifier latence + mémoire partagée voix↔Telegram.

### Phase 5 — (option) wake word
- microWakeWord / openWakeWord pour mains-libres sur le satellite.

## Risques / notes

- Chaque miss-intent = 1 tour glm-4.5-air (~16k tokens system prompt, 2-8s) → garder
  prefer-local agressif ; surveiller le quota OpenRouter (1000 req/j).
- Privacy : le path Hermes envoie le transcript à OpenRouter (+ data-training du free-tier).
- Music Assistant = **bibliothèque locale uniquement** (pas de streaming) → `play_music` ne
  résout que la musique possédée. Player MA = `media_player.salon_2` (cf. `docs/hermes-model-choice.md` pour le contexte Hermes).
- Réversibilité : garder `conversation.extended_openai_conversation` (ChatGPT) ou un 2e agent en secours.
- L'élagage exposition (Phase 3) impacte le vocal HA natif (exposition partagée) — décision utilisateur.
