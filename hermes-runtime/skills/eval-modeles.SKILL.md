---
name: eval-modeles
version: 2.0.0
description: Consulter l'état de la file de candidats modèles LLM, ET (sur demande explicite seulement) déclencher leur évaluation sur pc. Utilise dès que l'user parle des modèles candidats, de la file d'attente, ou veut lancer l'éval.
---

# Modèles candidats : consulter l'état, et déclencher l'éval

Deux opérations **distinctes**. Ne les confonds jamais.

## ⚠️ Ce que tu ne peux PAS savoir par toi-même
La file de candidats vit **sur la machine pc** (`~/.config/brain/model-candidates.queue`), hors de ta portée : tu n'as ni `kubectl` ni accès à pc. **Chercher dans `/opt/data`, dans tes sessions passées ou dans tes souvenirs ne te dira RIEN sur la file.** Ne conclus JAMAIS « la file est vide » à partir de ce que tu ne trouves pas chez toi — c'est faux et ça a déjà induit l'user en erreur.

La seule source de vérité à ta disposition = **`/opt/data/eval/queue-status.json`**, un instantané publié par pc (toutes les ~15 min et après chaque découverte/éval).

## A. « Y a-t-il des candidats en attente ? » (question d'ÉTAT → ne déclenche RIEN)
1. Lis **`/opt/data/eval/queue-status.json`**.
2. Réponds avec ce qu'il contient : `pending` (liste + `pending_count`), `running` (candidat en cours d'éval ou `none`), `recent_verdicts` (derniers résultats : overall, agentic, hermes_ready).
3. Mentionne `generated_at` si l'instantané a plus de ~1 h (« état daté de … »).
4. Si le fichier est **absent ou illisible** : dis-le franchement (« je ne peux pas lire l'état de la file »). **N'invente pas**, ne réponds pas « vide ».
5. **N'écris AUCUN drapeau** dans ce cas. Une question d'état n'est pas une demande de lancement.

## B. « Lance l'éval » (ACTION → seulement sur demande EXPLICITE)
Déclenche uniquement si l'user demande clairement de **lancer / démarrer / exécuter** l'évaluation (« lance l'éval », « teste les candidats », « traite la file »).
**Ne déclenche PAS** si l'user : pose une question, te montre un message/notification, demande un état, ou parle des modèles sans demander d'action. En cas de doute → **demande confirmation d'abord** (chaque candidat = 1 restart LocalAI ~15 min, ce qui coupe brièvement le chat et les autres usages du GPU).

Procédure :
1. Vérifie d'abord `/opt/data/eval/queue-status.json` : si `running` ≠ `none`, une éval est **déjà en cours** → dis-le et **ne repose pas de drapeau**.
2. Écris un fichier (contenu libre, p.ex. la date) à ce chemin exact — ta seule zone writable :
   `/opt/data/triggers/run-eval`
3. Confirme : « ✅ Éval lancée — le watcher sur pc ramasse le drapeau d'ici ~5 min. Tu recevras le verdict de chaque candidat (métriques + Hermes-readiness) et le lien de la PR si un modèle bat le courant. 2 candidats max par déclenchement, 1 restart LocalAI (~15 min) chacun. »

## Notes
- **`poll-candidates.sh`, `hf-discover.py`, la queue : tout ça vit sur pc**, pas chez toi. Ne prétends pas les exécuter ni les inspecter.
- Le pipeline est **PR-gated** : aucun modèle n'est déployé automatiquement, la PR sur `my-kluster` reste la validation humaine.
- Tu n'as pas les résultats immédiatement : ne les invente jamais, ils arrivent dans un message ultérieur du pipeline.
- Si l'écriture du drapeau échoue, dis-le — ne prétends pas avoir lancé l'éval.
