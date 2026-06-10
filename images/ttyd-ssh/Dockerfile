# ttyd + client SSH : ttyd lance `ssh` (absent de l'image de base).
# Sert un terminal web qui se connecte en SSH au host (option B, hop LAN interne).
# Build : docker build -t localhost:32000/ttyd-ssh:1.0 images/ttyd-ssh && docker push localhost:32000/ttyd-ssh:1.0
FROM tsl0922/ttyd:latest
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*
