# Dkron + python3 pour l'exécuteur shell de la veille (apps/veille).
# L'image officielle est une Alpine avec bash et tzdata, sans Python. Le code de la veille est
# en stdlib pure : python3 suffit, aucun paquet pip. Le code lui-même n'est PAS dans l'image,
# il arrive par ConfigMap depuis git (apps/veille/code) : modifier un script ne demande aucun build.
FROM dkron/dkron:4.2.1
RUN apk add --no-cache python3 tzdata
