---
name: verify-package-import
description: Never write a package import path you have not listed first
condition:
  - "import\\s+['\"]package:"
interruptMode: always
alwaysApply: false
---

You are about to write a package import path.

STOP. Have you listed that package's exported files in THIS session?

If not, do it now — the package lives under the local dependency cache; `bash`
with `ls` on its `lib/` directory tells you exactly what it exports. Then write
the import you SAW, not the one you expect.

A package named `foo` very often does NOT export `foo/foo.<ext>`. That guess is
the single most frequent cause of failure on this task. The compiler will only
tell you the path is wrong — it will never tell you the right one, and reissuing
a variant of the same guess is a loop that does not terminate.
