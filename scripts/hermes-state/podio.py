"""Transport kubectl vers le pod Hermes.

L'exécuteur est injectable : c'est ce qui permet de tester les garde-fous et le
protocole d'écriture sans jamais toucher au cluster.

PIÈGE CENTRAL : `kubectl exec` tourne en root, l'agent Hermes tourne en uid
10000. Un fichier écrit sans chown est invisible pour l'agent, SANS AUCUNE
ERREUR. D'où le chown systématique puis la relecture de vérification.
"""
import subprocess
import time

NS = "hermes"
CONTAINER = "main"
AGENT_UID = "10000:10000"
POD_PREFIX = "hermes-agent"


class PodError(RuntimeError):
    pass


def default_executor(argv, stdin=None):
    r = subprocess.run(argv, input=stdin, capture_output=True)
    return r.returncode, r.stdout, r.stderr


def _msg(flux):
    return flux.decode("utf-8", errors="replace").strip()[:200]


class Pod:
    def __init__(self, executor=default_executor, ns=NS, container=CONTAINER):
        self.exec = executor
        self.ns = ns
        self.container = container
        self._name = None

    def name(self):
        if self._name:
            return self._name
        rc, out, err = self.exec([
            "kubectl", "get", "pods", "-n", self.ns, "--no-headers",
            "-o", "custom-columns=:metadata.name,:status.phase",
        ])
        if rc != 0:
            raise PodError(f"kubectl get pods a échoué: {_msg(err)}")
        for ligne in out.decode("utf-8", errors="replace").splitlines():
            morceaux = ligne.split()
            if len(morceaux) >= 2 and morceaux[0].startswith(POD_PREFIX):
                if morceaux[1] != "Running":
                    raise PodError(f"pod {morceaux[0]} en phase {morceaux[1]}, pas Running")
                self._name = morceaux[0]
                return self._name
        raise PodError(f"aucun pod {POD_PREFIX}* trouvé dans le namespace {self.ns}")

    def sh(self, script, stdin=None):
        return self.exec([
            "kubectl", "exec", "-i", "-n", self.ns, self.name(),
            "-c", self.container, "--", "sh", "-c", script,
        ], stdin=stdin)

    def read(self, chemin):
        rc, out, err = self.sh(f'cat "{chemin}"')
        if rc != 0:
            raise PodError(f"lecture de {chemin}: {_msg(err)}")
        return out

    def read_json_retry(self, chemin, parse, attente=5.0, dormir=time.sleep):
        """Lecture d'un JSON susceptible d'être réécrit pendant la lecture.

        jobs.json est protégé par .jobs.lock côté Hermes mais rien ne garantit
        l'atomicité vue de l'extérieur. Une capture tronquée committée serait
        pire qu'une capture manquée : on retente une fois, puis on abandonne.
        """
        for tentative in (0, 1):
            brut = self.read(chemin)
            try:
                return parse(brut)
            except ValueError:
                if tentative == 0:
                    dormir(attente)
                    continue
                raise PodError(f"{chemin}: JSON invalide après 2 tentatives "
                               f"(probable lecture pendant une écriture)")

    def exists(self, chemin):
        rc, _, _ = self.sh(f'test -e "{chemin}"')
        return rc == 0

    def list_tree(self, racine):
        rc, out, _ = self.sh(
            f'cd "{racine}" 2>/dev/null && find . -type f | sed "s|^\\./||" | sort')
        if rc != 0:
            return []
        return out.decode("utf-8", errors="replace").split()

    def write(self, chemin, donnees):
        """Écriture atomique, puis chown, puis relecture de vérification."""
        tmp = f"{chemin}.hermes-state.tmp"
        rc, _, err = self.sh(f'mkdir -p "$(dirname "{chemin}")" && cat > "{tmp}"',
                             stdin=donnees)
        if rc != 0:
            raise PodError(f"écriture de {tmp}: {_msg(err)}")
        rc, _, err = self.sh(f'mv -f "{tmp}" "{chemin}" && chown {AGENT_UID} "{chemin}"')
        if rc != 0:
            raise PodError(f"mv/chown de {chemin}: {_msg(err)}")
        if self.read(chemin) != donnees:
            raise PodError(f"relecture de {chemin} ne correspond pas à la source")
