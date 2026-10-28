---
name: unit-converter
description: "Use when asked to convert, compare, or express temperature, length, weight, volume, area, speed, time, data, pressure, or energy in different units, including recipe cups, storage sizes, and driving speeds."
license: Apache-2.0
metadata:
  author: ai-powered-apps-development-expert
  version: "1.0"
allowed-tools: execute_code
---

# Unit Converter

Use the [conversion script](scripts/convert.py), not mental arithmetic.
Read [examples.md](examples.md) for units and invocation examples, and
[execution instructions](references/how-code-execution-works.md) when needed.

## Workflow

### Step 1: Load the script

For the first execution call `execute_code` with
`script_path="/unit-converter/scripts/convert.py"`, `session_id=""`, and your
conversion code. The tool prepends the script; do not read its source into the
conversation merely to execute it. Save `session_info.session_id` from the result.

### Step 2: Write the conversion call
Call `convert_units(value, from_unit, to_unit)`, which returns `(result, category)`.
For multiple targets call it once per target and print each result with its unit:

```python
result, category = convert_units(98.6, "fahrenheit", "celsius")
print(f"Category: {category}\nInput: 98.6 fahrenheit\nResult: {fmt(result)} celsius")
```

Normalize degree symbols to supported names. Ask about ambiguous or invalid inputs.

### Step 3: Return output
Return the printed Category, Input, and Result without changing the numeric value.
State conventions: this starter's `tb`, `gb`, `mb`, and `kb` are binary powers
of 1024 despite their labels. Thus 1.5 TB gives 1,572,864 MB in the script's
binary convention (1.5 TiB to MiB). Standard decimal TB to MB gives 1,500,000;
do not mix the two. Bit prefixes use decimal factors. Cups are US cups:
1 cup = 236.588 ml, so 3 cups = 709.764 ml. Do not imply metric cups.
Conversion factors are rounded as supplied; round presentation only at the end.

### Step 4: Reuse session
On follow-up conversions omit `script_path` and send only `code` and the saved
`session_id`. Variables and functions persist. A new query can explicitly start
a new session if it has no prior state.

### Step 5: Error handling
For unknown units or incompatible categories report the error and consult
examples.md for supported units. Ask for clarification of invalid numbers.
On expired sessions or ambiguous transport failures report the failure and ask
before restarting. Never silently replay code that may have run already.