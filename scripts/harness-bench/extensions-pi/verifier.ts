/**
 * Boucle de vérification pour `pi` : lance la commande de test du PROJET quand
 * l'agent s'apprête à rendre la main, et le relance tant qu'elle échoue.
 *
 * POURQUOI. Mesuré les 2026-09-09/10 sur gemma-4-12b-it-qat, fixture tetris :
 * `pi` seul rend [41, 0, 0] — un bon tirage puis des effondrements. Le harnais
 * maison `harnais-nu` rendait 44/44 cinq fois sur cinq, mais avec
 * `HARNAIS_NU_VERIFY_CMD=/usr/bin/pytest -q` : on lui DONNAIT la commande
 * d'acceptation et il rebouclait dessus. Privé de cette béquille et mis sur le
 * même serveur, il retombe à [44, 0, 0] — soit le même résultat que `pi`.
 *
 * La conclusion n'est donc pas « ce harnais est meilleur » mais « la boucle de
 * vérification est le levier ». Cette extension la porte dans `pi`, avec ses
 * mécanismes officiels : `agent_settled` (l'agent devient inactif) puis
 * `ctx.sendUserMessage()` (relance un tour). Aucun contournement.
 *
 * CE N'EST PAS DE LA TRICHE, ET CE N'EST PAS SPÉCIFIQUE À PYTHON. La commande
 * vient du PROJET, jamais du harnais — comme un fichier de CI. Un projet Flutter
 * y met `flutter test`, un projet Rust `cargo test`. Graver `pytest` dans une
 * extension biaiserait toute mesure vers Python, et c'est précisément l'erreur
 * qu'on s'interdit ici.
 *
 * INERTE PAR DÉFAUT. Sans commande configurée l'extension ne fait rien, ce qui
 * la rend sûre en usage quotidien et permet l'A/B « pi avec » contre « pi sans »
 * sur le même binaire, à un seul facteur près.
 *
 * Configuration, par ordre de priorité :
 *   PI_VERIFY_CMD          la commande (c'est elle que passe le banc)
 *   .pi/verify-cmd         un fichier dans le projet, une commande par fichier
 *   PI_VERIFY_MAX          nombre de relances (défaut 3)
 *   PI_VERIFY_TIMEOUT_MS   plafond d'exécution (défaut 120000)
 *   PI_VERIFY_SORTIE_MAX   caractères de sortie réinjectés (défaut 4000)
 */

import { execFile } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const MAX_RELANCES = Number(process.env.PI_VERIFY_MAX ?? 3);
const TIMEOUT_MS = Number(process.env.PI_VERIFY_TIMEOUT_MS ?? 120_000);
const SORTIE_MAX = Number(process.env.PI_VERIFY_SORTIE_MAX ?? 4000);

/** La commande de test, déclarée par le projet. `null` = extension inerte. */
function commandeDeVerification(): string | null {
  const parEnv = process.env.PI_VERIFY_CMD?.trim();
  if (parEnv) return parEnv;
  const fichier = join(process.cwd(), ".pi", "verify-cmd");
  if (existsSync(fichier)) {
    const contenu = readFileSync(fichier, "utf8").trim();
    if (contenu) return contenu;
  }
  return null;
}

interface Resultat {
  ok: boolean;
  sortie: string;
}

/**
 * Exécute la commande dans le répertoire courant. Un échec d'exécution (binaire
 * absent, plafond de temps atteint) est rendu comme un échec de test avec son
 * message : l'agent doit le voir plutôt que de le subir en silence.
 */
function lance(commande: string): Promise<Resultat> {
  return new Promise((resoudre) => {
    execFile(
      "/bin/sh",
      ["-c", commande],
      { cwd: process.cwd(), timeout: TIMEOUT_MS, maxBuffer: 8 << 20 },
      (erreur, stdout, stderr) => {
        const brut = `${stdout ?? ""}${stderr ?? ""}`.trim();
        if (!erreur) return resoudre({ ok: true, sortie: brut });
        const cause = (erreur as NodeJS.ErrnoException).code === "ETIMEDOUT"
          ? `\n[la commande a dépassé ${TIMEOUT_MS} ms et a été interrompue]`
          : "";
        resoudre({ ok: false, sortie: brut + cause });
      },
    );
  });
}

/** Garde la FIN de la sortie : l'échec pytest et son traceback y sont, pas au début. */
function tronque(sortie: string): string {
  if (sortie.length <= SORTIE_MAX) return sortie;
  return `[...] (sortie tronquée, ${sortie.length} caractères)\n` +
    sortie.slice(-SORTIE_MAX);
}

export default function (pi: ExtensionAPI) {
  let relances = 0;
  // `agent_settled` peut se déclencher pendant qu'on attend la commande : sans ce
  // verrou on lancerait deux vérifications concurrentes sur le même workdir.
  let enCours = false;

  // Une saisie HUMAINE ouvre une nouvelle tâche, donc remet le compteur à zéro.
  // Les messages qu'on injecte soi-même portent `source === "extension"` et ne
  // doivent pas le faire, sinon la boucle ne s'arrête jamais.
  pi.on("user_message", async (event) => {
    if (event.source !== "extension") relances = 0;
    return { action: "continue" };
  });

  pi.on("agent_settled", async (_event, ctx) => {
    const commande = commandeDeVerification();
    if (!commande || enCours) return;

    if (relances >= MAX_RELANCES) {
      ctx.ui.notify(
        `Vérification : ${MAX_RELANCES} relances épuisées, la main est rendue.`,
        "warn",
      );
      return;
    }

    enCours = true;
    try {
      const { ok, sortie } = await lance(commande);
      if (ok) {
        ctx.ui.notify(`Vérification OK (${commande})`, "info");
        relances = 0;
        return;
      }
      relances += 1;
      ctx.ui.notify(
        `Vérification en échec, relance ${relances}/${MAX_RELANCES}`,
        "warn",
      );
      await ctx.sendUserMessage(
        `La commande de vérification du projet a échoué.\n\n` +
          `$ ${commande}\n\n${tronque(sortie)}\n\n` +
          `Corrige la cause, puis relance cette commande toi-même pour vérifier.`,
      );
    } finally {
      enCours = false;
    }
  });
}
