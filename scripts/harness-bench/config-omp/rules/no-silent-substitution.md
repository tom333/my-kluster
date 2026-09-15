---
name: no-silent-substitution
description: Do not hand-roll a substitute for a dependency the task names
condition:
  - "(?i)\\b(implement|writ|rol|build)\\w*\\s+(it|this|my own|our own|a simple|a minimal)\\b[^.\\n]{0,40}\\b(manually|by hand|from scratch|myself|ourselves|instead)"
  - "(?i)\\b(instead of|rather than)\\s+(using|adding|depending on|pulling in)\\b[^.\\n]{0,40}\\b(library|package|dependency|plugin|crate|module)"
  - "(?i)\\b(remove|removing|drop|dropping|comment out|commenting out)\\b[^.\\n]{0,40}\\b(the\\s+)?(dependency|package|library|import|plugin|crate)"
  - "(?i)\\b(simplif|work around|workaround|bypass)\\w*\\b[^.\\n]{0,40}\\b(dependency|package|library|plugin|requirement)"
# Defaut omp : allowText true, allowAnyTool true, allowThinking FALSE. Or la
# decision de contourner une dependance se prend dans le raisonnement, avant
# d'atteindre la prose ou un outil. Lister les trois remet `thinking` dedans.
scope: ["text", "thinking", "tool"]
interruptMode: always
alwaysApply: false
---

STOP. You appear to be replacing a named dependency with your own code.

If the task names a library, USING it is the deliverable. You may not satisfy the
build by removing it from the manifest, stubbing it, or writing an equivalent
yourself. A build that goes green because the requirement was deleted is a
failure that looks like a success, and it is checked for.

Before you decide the dependency is unusable, you have not yet exhausted the
tools that answer the question:

- `lsp` — symbols, definitions and diagnostics say what the dependency really
  offers, and what the real error is.
- `read` / `glob` — the dependency's own source and examples.
- `bash` — build or analyse and read the ACTUAL message, not the one you expect.

If it genuinely blocks you after that, say so explicitly and report what you
tried. A reported blocker is a result. A silent substitution is a false one.
