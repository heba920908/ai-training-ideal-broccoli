---
name: plantuml-diagrams
description: Create or update PlantUML diagrams for course docs under app_development/diagrams/ (.puml source + rendered .png) and embed them in the related Markdown file. Defaults to a colored deployment diagram when no diagram type is specified. Use when asked to "draw", "diagram", "add a diagram", "update the diagram", or "render the puml" for an exercise or topic doc.
---

# PlantUML diagrams

Diagrams live in `app_development/diagrams/`. Each diagram has two committed files with the
same basename: the editable source `<name>.puml` and the rendered `<name>.png`. The PNG is
embedded in the Markdown doc; the `.puml` is the source of truth.

## Rules

- **Default type: deployment diagram** (`node`, `cloud`, `database`, `frame`, `file`,
  `artifact`, `actor`, `rectangle`, `agent`...). Use another type (sequence, activity,
  component, C4) only when the user asks for it.
- **No Graphviz.** Deployment/component diagrams must declare `!pragma layout smetana`.
  Sequence and activity diagrams render natively.
- **Name**: kebab-case, prefixed with the topic, e.g. `t6-input-grounding`. Put the same
  name after `@startuml` (`@startuml t6-input-grounding`).
- **Color by stage/role** with inline styles, one color family per group:

  ```plantuml
  cloud c #pink;line:red;line.bold;text:red [
  c
  cloud description
  ]
  file f #palegreen;line:green;line.dashed;text:green {
  [c1]
  [c2]
  }
  frame frame {
  node n #aliceblue;line:blue;line.dotted;text:blue
  }
  ```

  Bracket descriptions (`[ ... ]`) take an alias only: `rectangle id #style [ ... ]`, not
  `rectangle "Label" as id #style [`. Put the title inside the brackets.
- Add a `title` and, when useful, one `note` with the key takeaway. Keep labels short.
- No secrets, real keys, or credential URLs in labels.

## Tooling

The PlantUML JAR is kept in the git-ignored workspace, never in the repo:

```bash
mkdir -p workspace/tools
[ -f workspace/tools/plantuml.jar ] || curl -sSL -o workspace/tools/plantuml.jar \
  https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar
```

## Create or update a diagram

1. Read the target Markdown doc to understand the flow being illustrated.
2. Create or edit `app_development/diagrams/<name>.puml` following the rules above.
3. Validate (from the repo root). On failure, locate the error with `-syntax`:

   ```bash
   java -jar workspace/tools/plantuml.jar -checkonly app_development/diagrams/*.puml
   java -jar workspace/tools/plantuml.jar -syntax < app_development/diagrams/<name>.puml
   ```

4. Render the PNG next to the source (overwrites the old PNG on update):

   ```bash
   java -jar workspace/tools/plantuml.jar -tpng app_development/diagrams/<name>.puml
   ```

5. View the PNG and check layout, colors, and that no labels overlap. Iterate if needed.
6. Embed it in the doc right after the text it illustrates (paths relative to the doc):

   ```markdown
   ![<short alt text>](diagrams/<name>.png)

   Source: [diagrams/<name>.puml](diagrams/<name>.puml)
   ```

   On update, keep the basename so existing links stay valid.

## Render externally

Paste the full `.puml` into a PlantUML-compatible renderer (PlantUML server, PlantText),
export PNG, and save it as `app_development/diagrams/<name>.png` with the same basename.
