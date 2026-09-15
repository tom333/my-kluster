## Verified-before-written

Before writing any code against a library you have not inspected in THIS session,
list what it actually exports: `glob` the package manager's cache for the
package directory, then `read` its entry file, or `bash ls` its source tree.
Never write an import path you have not seen with your own tools.
Guessing an import that "looks right" is the single most common way this task
fails.

## Read the diagnostics you were just given

When a `write` or `edit` result ends with `LSP Diagnostics`, every error listed
there is blocking. Fix them BEFORE writing another file. An error saying a URI
does not exist means the path is wrong or the file is outside the project — not
that the project needs another file. The project is where `pubspec`, `package.json`,
`Cargo.toml` or the equivalent manifest lives; code written elsewhere is not built.

## The compiler is not a suggestion box

When a build error names a path, symbol or type that does not exist, do NOT emit
a variant of the same guess. The error tells you the name is wrong; it does not
tell you the right one. Go and find it. Re-emitting a near-miss is a loop, and
the loop does not terminate.

## Replace means delete

When you change approach, remove what the old one left behind. An import that is
no longer used, a class no longer referenced, a file no longer reached: each is a
defect, and some of them break the build on their own. Adding without removing is
not a fix.

## Never drop a named requirement

If the task names a library, an API or a constraint, it is part of the
deliverable. You may not satisfy the build by removing it, stubbing it, or
hand-rolling a substitute. If it genuinely blocks you, say so explicitly and
report what you tried — a reported blocker is a result; a silent substitution is
a false one.

## Done means verified

Do not report completion while the build fails, while a required dependency is
absent, or while you have not run the thing you wrote. "It should work" is not a
verification. Run it, read the output, then speak.
