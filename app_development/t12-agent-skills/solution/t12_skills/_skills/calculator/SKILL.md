---
name: calculator
description: >
  Use when asked to calculate, compute, evaluate, or solve numeric expressions.
  Covers arithmetic, powers, roots, logarithms, rounding, trigonometry, constants,
  and grouped expressions, rather than symbolic algebra or unit conversions.
---

# Calculator Skill

## Quick Start

Run the [supplied script](scripts/calculate.py) in the execution environment:

```sh
python /skills/calculator/scripts/calculate.py "2^10 + sqrt(144)"
```

Locate the mounted directory if the managed environment uses a different prefix.

## Supported Operations

- Arithmetic: `+`, `-`, `*`, `/`, unary `+` and `-`.
- Power / exponentiation: `^` or `**`; the script normalizes `^` to `**`.
- Square: `x**2`; square roots: `sqrt(x)`.
- Floor division and modulo: `//` and `%`.
- Trigonometry: `sin`, `cos`, and `tan`, with angles in radians.
- Constants: `pi` and `e`; grouping with parentheses.
- Other functions: `abs`, `round`, `floor`, `ceil`, `log` (natural or explicit base), `log10`.

Only numeric expressions and these names are supported, not assignments, imports,
attribute access, symbolic solving, or arbitrary Python.

## Workflow

1. Extract the expression. Clarify missing values or ambiguous operations.
2. Execute the script with the expression as one quoted argument. Do not invent a result.
3. Return its Expression and Result, with units only if supplied and meaningful.
4. Report syntax, unknown-name, unsafe-operation, domain, and division-by-zero errors.
   Ask for a corrected expression; do not hide an error behind a guessed answer.