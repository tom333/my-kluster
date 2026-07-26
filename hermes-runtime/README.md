# hermes-runtime — artefacts Hermes versionnés (PVC, pas GitOps)

Hermes charge ces fichiers depuis son **PVC** (`hermes-agent-data` / `hermes-agent-files`),
pas depuis Git : ils ne sont donc **pas** appliqués automatiquement. Copie ici pour
survivre à un wipe de PVC et garder l'historique des modifications.

| Fichier ici | Destination dans le pod |
|---|---|
| `HERMES.md` | `/workspace/HERMES.md` — *context file* injecté dans le system prompt à chaque session (priorité `.hermes.md`/`HERMES.md` > `AGENTS.md` > `CLAUDE.md`). Contient les garde-fous d'exécution. |
| `skills/eval-modeles.SKILL.md` | `/opt/data/skills/eval-modeles/SKILL.md` |
| `skills/decouvertes.SKILL.md` | `/opt/data/skills/decouvertes/SKILL.md` |

## Réappliquer après un rebuild
```bash
HPOD=$(kubectl get pods -n hermes --no-headers | awk '/hermes-agent/{print $1}' | head -1)
kubectl cp HERMES.md "hermes/$HPOD:/workspace/HERMES.md" -c main
for s in eval-modeles decouvertes; do
  kubectl exec -n hermes "$HPOD" -c main -- mkdir -p "/opt/data/skills/$s"
  kubectl cp "skills/$s.SKILL.md" "hermes/$HPOD:/opt/data/skills/$s/SKILL.md" -c main
done
# ⚠️ kubectl exec tourne en root alors que l'agent tourne en uid 10000 :
kubectl exec -n hermes "$HPOD" -c main -- chown -R 10000:10000 /opt/data/skills /workspace/HERMES.md
```

⚠️ `jobs.json` (crons) n'est PAS ici : il contient des identifiants de chat et se
modifie depuis le dashboard. Voir la mémoire du projet pour la procédure d'édition.
