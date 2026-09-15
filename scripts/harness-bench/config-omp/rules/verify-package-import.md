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

Resolve it with the tools you already have, before finishing this line:

- `lsp` — document and workspace symbols tell you what a dependency actually
  exports, in every language the server covers. These tools are available on
  every turn and are the fastest answer.
- `glob` — match the dependency's source tree and read the entry points back.
- `read` — open the manifest, the index, or the entry file and see the real
  names.
- `bash` — list the dependency directory when nothing above applies.

Then write the path you SAW, not the one you expected.

The compiler will only tell you a path is wrong. It will never tell you the right
one, and reissuing a variant of the same guess is a loop that does not terminate.
