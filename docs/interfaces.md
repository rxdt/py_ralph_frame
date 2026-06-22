# Interfaces

> The seams between packages: the public functions/types each package exposes and what it must never
> import. Keep this in sync with the code — it is the contract workers build against.

## src/

_List each package and its public surface as it is created, e.g.:_

```
src/<name>/
  public:  fn(args) -> Type        # what callers may use
  depends: <other packages it may import>
  never:   <packages/layers it must not import>
```

## Rules

- Absolute imports only (enforced by lint).
- Packages depend downward through declared seams; no cycles.
