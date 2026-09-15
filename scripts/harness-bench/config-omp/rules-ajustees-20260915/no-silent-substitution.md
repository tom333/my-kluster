---
name: no-silent-substitution
description: Do not hand-roll a substitute for a dependency the task names
condition:
  - "CustomPainter"
  - "(?i)implement(ing)? (it|this) (manually|by hand|myself)"
  - "(?i)(instead of|rather than) using the (library|package|dependency)"
interruptMode: always
alwaysApply: false
---

STOP. You appear to be replacing a named dependency with your own implementation.

If the task names a library, using it IS the deliverable. You may not satisfy the
build by removing it, stubbing it, or writing an equivalent yourself.

If it genuinely blocks you, say so explicitly and report what you tried. A
reported blocker is a result. A silent substitution is a false one, and it will
be detected.
