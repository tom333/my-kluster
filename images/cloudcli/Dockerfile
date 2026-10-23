# CloudCLI (ex-claudecodeui, https://github.com/siteboon/claudecodeui) : UI web
# pour Claude Code. Pas d'image officielle serveur (seules des "sandbox
# templates" microVM existent) → image maison.
#
# Choix structurants :
#   - uid 1000 et HOME=/home/moi, IDENTIQUES au host : CloudCLI lit les sessions
#     dans os.homedir()/.claude/projects (pas de CLAUDE_CONFIG_DIR), et les hooks
#     de ~/.claude/settings.json pointent en absolu sur /home/moi/.claude/hooks/*.
#   - Claude Code installé en global : sur Linux CloudCLI spawne `claude` (PATH)
#     via le SDK et le terminal /shell lance aussi le binaire. jq pour le hook
#     rtk-rewrite (il se désactive proprement si rtk est absent), python3 pour
#     status.py, git/rg pour l'agent.
#
# Build :
#   docker build -t localhost:32000/cloudcli:1.37.4-cc2.1.296 images/cloudcli
#   docker push localhost:32000/cloudcli:1.37.4-cc2.1.296
FROM node:24-bookworm-slim

ARG CLOUDCLI_VERSION=1.37.4
ARG CLAUDE_CODE_VERSION=2.1.296

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git openssh-client ripgrep jq python3 procps tini \
        make g++ \
    && npm install -g "@cloudcli-ai/cloudcli@${CLOUDCLI_VERSION}" \
                      "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force \
    && apt-get purge -y make g++ && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && cloudcli --version && claude --version

# node (1000:1000) devient moi, home /home/moi — même uid et même HOME que sur le host.
RUN usermod -l moi -d /home/moi -m node && groupmod -n moi node

USER moi
WORKDIR /home/moi
ENV HOME=/home/moi \
    HOST=0.0.0.0 \
    PORT=3001 \
    SERVER_PORT=3001 \
    CLAUDE_CLI_PATH=/usr/local/bin/claude \
    DATABASE_PATH=/home/moi/.cloudcli/auth.db

EXPOSE 3001
ENTRYPOINT ["tini", "--"]
CMD ["cloudcli", "start"]
