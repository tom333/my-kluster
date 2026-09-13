# Paseo + Claude Code : l'image officielle Paseo n'embarque aucun CLI d'agent,
# elle ne fait que les piloter. On ajoute donc Claude Code par-dessus.
#
# L'entrypoint amont démarre root, chowne $HOME puis drop vers paseo (1000:1000) :
# on installe donc en global (/usr/local/lib/node_modules), lisible par tous, et
# on ne touche NI à l'utilisateur NI à l'entrypoint.
# CLAUDE_CONFIG_DIR vaut déjà /home/paseo/.claude dans l'image de base → l'auth
# atterrit dans le PVC et survit aux redémarrages.
#
# Build :
#   docker build -t localhost:32000/paseo-agents:0.7.2-cc2.1.263 images/paseo-agents
#   docker push localhost:32000/paseo-agents:0.7.2-cc2.1.263
FROM ghcr.io/getpaseo/paseo:0.8.0

ARG CLAUDE_CODE_VERSION=2.1.263

RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force \
    && claude --version
