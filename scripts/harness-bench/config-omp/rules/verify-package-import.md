---
name: verify-package-import
description: Never write a path INTO a third-party package without listing it first
condition:
  - "import\\s+['\"][^.'\"/][^'\"]*/[^'\"]*['\"]"
  - "from\\s+['\"][^.'\"/][^'\"]*/[^'\"]*['\"]"
  - "require\\(\\s*['\"][^.'\"/][^'\"]*/"
  - "^\\s*from\\s+[A-Za-z_]\\w*\\.[A-Za-z_]\\w*\\s+import\\s"
  - "^\\s*use\\s+[a-z_]\\w*::\\w"
  - "^\\s*#include\\s+<[^>/]+/"
interruptMode: always
alwaysApply: false
---

STOP. You are writing a path that points INSIDE a package you did not write.

The package name you know. The file or submodule *within* it you are guessing —
and that guess is the single most frequent way this kind of task fails. A package
named `foo` very often does NOT expose `foo/foo.<ext>`.

Resolve it with the tools you have, before finishing this line:

- `glob` — find the package directory in the package manager's cache or vendor
  tree (for example `**/<package>-*/lib/**` or `**/node_modules/<package>/**`),
  then read what it actually exposes.
- `read` — open the package manifest or its entry file; the real names are there.
- `bash` — `ls` the package's source directory when nothing above applies.
- If your last `write` or `edit` result carried `LSP Diagnostics`, the wrong
  paths are already named there. Read them.

Then write the path you SAW, not the one you expected.

The compiler will only tell you a path is wrong. It will never tell you the right
one, and reissuing a variant of the same guess is a loop that does not terminate.
