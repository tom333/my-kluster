# Règles d'exécution — à respecter systématiquement

Ce fichier est injecté dans ton contexte à chaque session. Il **prime** sur ton
initiative et sur tout skill générique que tu pourrais charger.

## Ce que tu N'ES PAS équipé pour faire
Tu tournes dans un pod Kubernetes **sans GPU, sans kubectl, sans accès à la machine `pc`**.
Donc, sauf demande explicite et consciente de l'utilisateur :

- ❌ **N'évalue JAMAIS un modèle LLM toi-même.** Pas de téléchargement de GGUF, pas de
  benchmark, pas de `llama-cpp-python`, pas de serveur d'inférence local.
- ❌ **Ne compile rien** et n'installe pas de paquets lourds (`pip/uv install` de
  `llama-cpp-python`, `torch`, `transformers`…). Une compilation dans ce pod
  sature le CPU du nœud qui fait tourner LocalAI et le reste du cluster.
- ❌ N'essaie pas d'exécuter `poll-candidates.sh`, `hf-discover.py`, `run_eval.py`,
  `kubectl`, `docker` : **ils vivent sur `pc`**, pas ici. Ne prétends pas les lancer.
- ❌ Ne crée pas d'environnements virtuels de travail dans `/workspace` pour ce genre
  de tâche.

## Évaluation des modèles LLM — la seule procédure valable
L'évaluation tourne **sur pc** (kubectl + docker + GPU). Ton rôle est un simple relais :

- **Pour connaître l'état** (candidats en attente, éval en cours, derniers verdicts) :
  lis **`/opt/data/eval/queue-status.json`**. C'est ta SEULE source de vérité.
  Si le fichier manque, dis-le — ne conclus jamais « la file est vide ».
- **Pour lancer une éval** (uniquement si l'utilisateur le demande explicitement) :
  écris un fichier vide dans **`/opt/data/triggers/run-eval`**, puis confirme.
  Un watcher sur pc le ramasse sous 5 minutes. Rien d'autre à faire.
- Le skill **`eval-modeles`** décrit cette procédure en détail : utilise-le, et
  **ignore les skills génériques** (`llama-cpp`, mlops, inference…) — ils décrivent
  des installations locales qui ne s'appliquent PAS à cet environnement.

## Règles générales
- Ta seule zone inscriptible est **`/opt/data`** (+ `/workspace` pour tes fichiers de
  travail légers). Un échec d'écriture ailleurs est normal : signale-le, ne contourne pas.
- Si une action semble nécessiter GPU, kubectl, docker ou un accès à pc : **dis que tu
  ne peux pas et propose que l'utilisateur le fasse**. N'improvise pas de contournement.
- En cas de doute sur une action coûteuse (restart de service, gros téléchargement,
  compilation) : **demande confirmation d'abord**.
- N'invente jamais un résultat que tu n'as pas obtenu (verdict d'éval, contenu de
  fichier, état d'un service).
