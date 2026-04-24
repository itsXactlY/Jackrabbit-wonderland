---
name: hermes-skin-system
description: "How to create and debug custom skins for Hermes Agent CLI"
version: 1.0.0
---

# Hermes Skin System

## How Skins Work

Skins are YAML files in `~/.hermes/skins/<name>.yaml`. They customize banner colors, logo art, hero art, and prompt styling.

### Loading Flow
1. CLI starts, calls `init_skin_from_config(config)` from `skin_engine.py`
2. Reads `config.yaml` → `display.skin` (e.g., `"neural"`)
3. Loads `~/.hermes/skins/neural.yaml`
4. Creates `SkinConfig` object with all fields
5. `build_welcome_banner()` uses `_bskin.banner_hero` or falls back to `HERMES_CADUCEUS`

### Layout Structure
```
┌─────────────────────────────────────────────────────────┐
│ [banner_logo] (above panel, optional)                    │
│ ┌───────────────────────────────────────────────────────┐
│ │ [banner_hero] (left col)  │  Tools / Skills (right)   │
│ │ Model info, CWD, Session  │                           │
│ └───────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────┘
```

- `banner_logo`: Printed ABOVE the panel (e.g., HERMES_AGENT_LOGO text art)
- `banner_hero`: Left column INSIDE the panel (replaces HERMES_CADUCEUS)
- `banner_hero` + model/cwd/session = left column content
- Tools + skills = right column content

### YAML Pitfalls (CRITICAL)

**1. Block scalar indentation (most common failure)**
Every line after `banner_hero: |` MUST be indented to at least the column after `|`. Typically 2 spaces to match other YAML keys. Without indentation, YAML silently drops the content.
```yaml
# WRONG - art lines not indented (YAML silently drops content, banner_hero=EMPTY)
banner_hero: |
[#BF00FF]line one[/]
[#BF00FF]line two[/]

# RIGHT - 2-space indent
banner_hero: |
  [#BF00FF]line one[/]
  [#BF00FF]line two[/]
```
**Always verify:** `python3 -c "import yaml; d=yaml.safe_load(open('skin.yaml')); print(len(d.get('banner_hero','')))"`

**2. No trailing space preservation**
YAML `|` block scalar strips trailing whitespace. Art lines should NOT rely on trailing spaces for width. Rich handles positioning.

**3. Rich markup closing tags**
Colors need `[/]` to close. Without them, colors bleed into subsequent lines. However, the LAST line of banner_hero can omit `[/]` if followed by blank lines (color doesn't bleed past newline in Rich).

**4. Verify YAML parses**
Always test: `python3 -c "import yaml; yaml.safe_load(open('skin.yaml'))"`

### Skin YAML Template
```yaml
name: myskin
description: "Description"

banner_border: "#COLOR"
banner_title: "#COLOR"
banner_accent: "#COLOR"
banner_dim: "#COLOR"
banner_text: "#COLOR"

banner_logo: ""  # Empty if using hero instead

banner_hero: |
  [color]art line 1[/]
  [color]art line 2[/]
  [color]status line[/]

prompt-working: "#COLOR italic"
prompt-idle: "#COLOR"
```

### Monkey-Patching (NOT Recommended)
Attempts to monkey-patch `HERMES_CADUCEUS` from plugin `__init__.py` fail because:
- Banner renders BEFORE plugins load
- `.pth` files only execute lines starting with `import`
- `sitecustomize.py` timing is unreliable

**Best approach:** Edit `banner.py` directly (one-line change for justify) + use skin YAML for art.

### Debugging
```python
from hermes_cli.skin_engine import get_active_skin, get_active_skin_name
print(get_active_skin_name())  # Should match config
skin = get_active_skin()
print(skin.banner_hero[:60])  # Should have your art
```

## Quick Reference

| Field | Effect |
|-------|--------|
| `banner_logo` | Above panel, standalone |
| `banner_hero` | Left column in panel |
| `banner_border` | Panel border color |
| `banner_title` | Version label color |
| `banner_accent` | Headers, highlights |
| `prompt-working` | Prompt during API call |
| `prompt-idle` | Prompt waiting |
