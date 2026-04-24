---
name: dayz-integrations
version: 1.0.0
category: dayz
description: DayZ integration guides — LBMaster groups/admin integration, client-server mod separation, RPC routing, and deployment patterns.
tags: [dayz, lbmaster, integration, client-server, rpc]
---

# DayZ Integrations — Complete Guide


## LBMaster Groups Integration


# LBMaster Groups Integration Workflow

> Based on integrating LBMaster Advanced Groups (122 classes, 150 .c files, 43 layouts) into VanillaPPMap codebase.

## Context
We do NOT copy-paste LBMaster code. We **port functionally** while preserving our A+++ patterns.
LBMaster uses `LBMenuBase` + `LBGroupPage` tab system, `LBLayoutManager.CreateWidgets()`, `LBConfigLoader<T>`, modded vanilla classes.
We use `UIScriptedMenu` + `ScriptedWidgetEventHandler`, `CreateWidgets()` directly, event-based config management.

## Step 1: Audit + ADR

Map every LBMaster class to our architecture:
```
LBMaster class → Our approach: ADOPT (copy), ADAPT (port with our patterns), or SKIP
```

Create `ADR_LBMASTER_SYSTEMS.md` with class-by-class mapping, execution order, and decision rationale.

Key LBMaster classes to audit:
- **LBGroupUI** (map menu shell, 648 lines) → Port as VPPGroupMapMenu (ScriptedWidgetEventHandler)
- **LBGroupPage** (base + 6 subclasses) → Port as VPPGroupPage with same lifecycle
- **LBGroup** (661 lines data model) → Port as VPPGroup with same WriteToCtx/ReadFromCtx
- **13 Admin pages** → Wire into existing VPPAdminMenuShell as new tabs
- **Chat system** → Keep our VPPChatWidget, adopt LBMaster's GridSpacer 4-col layout
- **Marker system** → Enhance our existing marker pool, add LBMaster types
- **14 Config classes** → Port event system, use our singleton pattern

## Step 2: PRD + Ralph Loop

Create `prd.json` with 12 stories in dependency order:
1. Audit + ADR
2. Config system (foundational)
3. Data models + RPC
4. Menu shell (VPPGroupMapMenu)
5. Page subclasses
6. Layout files
7. Marker system
8. Chat system
9. Admin pages
10. Mission lifecycle wiring
11. Final integration

No codex/claude-code on server? Use delegate_task with 50 iterations, then manually integrate the output.

## Step 3: Autonomous Execution

Spawn subagent with full context:
- LBMaster reference at `/path/to/LBMaster/LBmaster_Groups/scripts/`
- Target codebase at `/path/to/VanillaPPMap/scripts/`
- ADR with class mapping
- PRD with story list
- Enforce Script syntax rules

Key instruction: **"Never break existing A+++ code — only add new files/classes or update incrementally. Prefix all new classes with VPPGroup."**

## Step 4: Manual Integration (Post-Subagent)

After subagent creates files, verify and wire:

### 4a: Wire menu into VPPMapMenu
```c
// In VPPMapMenu member vars
private ref VPPGroupMapMenu m_GroupMapMenu;

// In Init()
if (!m_GroupMapMenu) m_GroupMapMenu = new VPPGroupMapMenu(this, m_PanelClan);

// In RefreshGroupUI()
if (m_GroupMapMenu) m_GroupMapMenu.RefreshGroupData();
```

### 4b: Wire RPC handler in missionGameplay
```c
// In MissionGameplay constructor
if (GetGame().IsClient() || !GetGame().IsMultiplayer()) {
    VPPGroupRPCHandler.Get();
}
```

### 4c: Wire admin pages into VPPAdminMenuShell
Add new tabs to PAGE_LAYOUTS and PAGE_NAMES arrays:
```c
"VanillaPPMap/GUI/Layouts/Menu/AdminGroups.layout",
// ... etc
```

### 4d: Fix layout naming if mismatched
LBMaster GetLayoutName() returns "Map Page 0 0" but files may be "page_0_0_default.layout". Fix:
```c
string GetLayoutName() { return "page_" + pageID + "_" + pageSubID + "_default"; }
```

## Step 5: Syntax Audit

Run before committing:
```bash
# Check for forbidden patterns in all new .c files
grep -rn '\?.*:' path/to/new/code | grep -v '//'    # No ternary
grep -rn '^\s*switch' path/to/new/code               # No switch
grep -rn 'int\[' path/to/new/code                     # No int[]
grep -rn 'string\[' path/to/new/code                  # No string[]

# Check cross-module (3_Game must not reference 5_Mission)
grep -rn '5_Mission_class_names' path/to/3_Game/      # Should be 0
```

## Dependency Graph (Critical!)

```
Config (3_Game) → Data Models (3_Game) → Menu Shell (5_Mission) → Pages (5_Mission)
                                                                      ↓
                                                             Admin Pages (5_Mission)
                                                                      ↓
                                               Chat + Markers + RPC Handlers (5_Mission)
                                                                      ↓
                                              MissionGameplay wiring (OnCreate + OnInit)
```

**DO NOT port pages before menu shell. DO NOT wire mission before RPC exists.**

## Pitfalls

1. **Layout naming mismatch**: Ensure `GetLayoutName()` matches actual `.layout` filenames exactly
2. **Double RPC registration**: New VPPGroupRPCHandler may register RPCs already handled by missionGameplay handlers. Use `VPPGroupRPCHandler.Get()` as a parallel system, not a replacement.
3. **Cross-module violations**: 3_Game CANNOT reference 5_Mission classes. Keep data models in 3_Game, UI in 5_Mission.
4. **Constructor HUD init**: Never create widgets in MissionGameplay constructor — defer to OnUpdate or CallLater from OnInit.
5. **Backwards compatibility**: Keep old GroupMenuUI alongside new VPPGroupMapMenu during transition period.

## Status Tracking

Use `prd.json` with story objects:
```json
{
  "id": "S02",
  "title": "Port LBGroupUI as VPPGroupMapMenu",
  "passes": true
}
```

Log progress in `progress.txt`:
```
[S02 2026-04-03] VPPGroupMapMenu.c created with tab+page system. 
  315 lines, 5 pages wired. Layout matches.
```

## LBMaster Admin Layout


# LBmaster Admin Menu Layout Architecture

## When to Use
- Building or replicating an admin menu in DayZ that matches LBmaster's visual style
- Creating tabbed admin pages loaded dynamically into a container
- Debugging why page layouts don't render correctly when loaded by a shell

## Architecture: Shell vs Page

LBmaster uses a **two-layer layout system**:

### Shell Layout (the menu container)
Contains the menu chrome — tab bar, close button, save button, page container.

```
PanelWidgetClass rootFrame {
  color 0.506 0.506 0.506 0.392       // semi-transparent dark background
  style rover_sim_colorable            // applies background rendering
  size 1 1
  halign center_ref
  valign center_ref
  {
    // Page content area — pages are LOADED into here
    PanelWidgetClass pageWidgets {
      ignorepointer 1
      position 0 5
      size 1 1
      halign center_ref
      valign bottom_ref
      scriptclass "LBGapHandler"
      gapHorizontal 10
      gapVertical 85
    }

    // Tab buttons — horizontal wrap, 165px gap
    WrapSpacerWidgetClass buttonWidgets {
      clipchildren 0
      ignorepointer 1
      position 5 5
      size 1 70
      scriptclass "LBGapHandler"
      gapHorizontal 165
    }

    // Close button (top-right)
    ButtonWidgetClass btn_close_admin {
      position 5 5
      size 150 25
      halign right_ref
      hexactpos 1 | vexactpos 1
      hexactsize 1 | vexactsize 1
      style Empty
      {
        PanelWidgetClass close_panel {
          ignorepointer 1
          size 1 1
          color 1 0.196 0.196 1          // red outline
          style LB_Clean_outline
          {
            TextWidgetClass close_text {
              ignorepointer 1 | size 1 1
              text "#close"
              font "gui/fonts/Metron14"
              "text halign" center
              "text valign" center
              color 1 1 1 1
            }
          }
        }
      }
    }

    // Save button (bottom-right)
    ButtonWidgetClass btn_save {
      position 5 5
      size 200 25
      halign right_ref
      valign bottom_ref
      priority 600
      style Empty
      {
        PanelWidgetClass save_panel {
          ignorepointer 1
          size 1 1
          color 0 1 0 1                    // green outline
          style LB_Clean_outline
          {
            TextWidgetClass save_text {
              text "SAVE CONFIG"
              font "gui/fonts/Metron14"
              color 0 0 0 1                 // black text on green
            }
          }
        }
      }
    }

    // Version text
    MultilineTextWidgetClass txt_version {
      ignorepointer 1
      position 5 35
      size 150 15
      halign right_ref
      font "gui/fonts/sdf_MetronBook72"
      "exact text" 1 | "exact text size" 10
      color 0.47 0.47 0.47 1
    }

    // Optional: right-aligned mod tabs
    WrapSpacerWidgetClass buttonWidgetsNew {
      clipchildren 0 | position 5 5 | size 1 70
      content_halign right
      scriptclass "LBGapHandler"
      gapHorizontal 165
    }
  }
}
```

### Page Layout (individual admin page content)
**CRITICAL:** Pages are FLAT `PanelWidgetClass` children loaded into `pageWidgets`. Do NOT add `FrameWidgetClass`, `scriptclass`, or nested panels.

```
PanelWidgetClass AdminPage_YourPage {
  visible 1
  size 500 550                           // standard LBmaster page size
  style blank                            // no background — shell handles that
  {
    // Section header
    TextWidgetClass lbl_title {
      ignorepointer 1
      position 0 0
      size 500 25
      hexactpos 1 | hexactsize 1
      font "gui/fonts/sdf_MetronBook72"
      color 1 1 1 1
      "text halign" center
      text "SECTION TITLE"
    }

    // Checkbox
    CheckBoxWidgetClass chkSomething {
      position 10 35
      size 480 20
      hexactpos 1 | hexactsize 1
      text "Label" | checked 0
    }

    // Label (right-aligned)
    TextWidgetClass lblSomething {
      ignorepointer 1
      position 10 65
      size 250 20
      hexactpos 1 | hexactsize 1
      font "gui/fonts/sdf_MetronBook72"
      color 0.8 0.8 0.8 1                // slightly dimmed
      text "Field Name"
      "text halign" right
    }

    // Edit box
    EditBoxWidgetClass editSomething {
      position 270 65
      size 80 20
      hexactpos 1 | hexactsize 1
      text "default"
    }

    // Slider
    SliderWidgetClass sldSomething {
      color 1 0.5 0 1                    // orange fill
      position 10 90
      size 340 20
      hexactpos 1 | hexactsize 1
      maximum 100
      current 50
      "fill in" 1
    }

    // List
    TextListboxWidgetClass list_items {
      position 10 Y
      size 400 150
      hexactpos 1 | hexactsize 1
      lines 8
    }

    // Button
    ButtonWidgetClass btnAction {
      position X Y
      size 80 20
      hexactpos 1 | hexactsize 1
      text "Label"
    }
  }
}
```

## Common Mistakes

| Mistake | Why It Breaks | Fix |
|---|---|---|
| Page uses `FrameWidgetClass rootFrame` with `scriptclass "LBMenuPopulator"` | Page already loaded into shell's `pageWidgets`; duplicate structure confuses widget finding | Use flat `PanelWidgetClass` with `style blank` |
| Page nests `panel_left`/`panel_right` containers | Shell expects flat widget list for `FindAnyWidget()` | Put widgets directly inside the PanelWidgetClass |
| Page includes its own background/overlay | Shell's `rover_sim_colorable` already provides background | `style blank` on pages |
| Widgets missing `hexactpos 1` / `hexactsize 1` | LBmaster uses exact pixel positioning; without these, widgets float | Always set both flags |
| Using `size 1 1` for widget-sized elements | Relative sizing wraps to parent; widgets need pixel sizes | Use pixel sizes for child widgets |

## Widget Property Cheat Sheet

| Widget Type | Sizing | Positioning | Notes |
|---|---|---|---|
| `TextWidgetClass` | `size W 20` | `hexactpos 1 hexactsize 1` | Labels: `color 0.8 0.8 0.8 1`, `text halign right` |
| `CheckBoxWidgetClass` | `size 480 20` | `hexactpos 1 hexactsize 1` | Checkbox size is fixed by engine |
| `EditBoxWidgetClass` | `size 80-120 20` | `hexactpos 1 hexactsize 1` | |
| `SliderWidgetClass` | `size 340 20` | `hexactpos 1 hexactsize 1` | Fill color: `1 0.5 0 1` (orange) |
| `TextListboxWidgetClass` | `size W H` | `hexactpos 1 hexactsize 1` | `lines N` for visible row count |
| `ButtonWidgetClass` | `size 80-150 20` | `hexactpos 1 hexactsize 1` | |

## Color Constants

| Element | RGBA | Notes |
|---|---|---|
| Shell background | `0.506 0.506 0.506 0.392` | Semi-transparent dark gray |
| Text (bright) | `1 1 1 1` | White — headers, active labels |
| Text (dim) | `0.8 0.8 0.8 1` | Slightly dimmed — field labels |
| Text (muted) | `0.47 0.47 0.47 1` | Gray — version info |
| Close button | `1 0.196 0.196 1` | Red |
| Save button | `0 1 0 1` | Green, black text `0 0 0 1` |
| Slider fill | `1 0.5 0 1` | Orange |
| Role headers | `1 0.8 0.2 1` | Gold/amber — permission tiers |
| Style: LB_Clean_outline | — | White 1px border on colored backgrounds |
| Style: rover_sim_colorable | — | Shell background rendering |
| Style: blank | — | No background/border |

## Fonts

| Font | Usage |
|---|---|
| `gui/fonts/sdf_MetronBook72` | Main UI font — headers, labels, all text |
| `gui/fonts/Metron14` | Button text (close, save) |

## Variant: Full-Screen Standalone Config Panel (4-Quadrant)

A modal overlay covering the entire screen — NOT loaded into the shell's `pageWidgets`. Used for settings/config that needs maximum space.

### Layout Root
Placed at ROOT level of the parent menu (e.g., VPPMapMenu), NOT inside any shell container:
```
PanelWidgetClass panel_settings_root {
  visible 0
  position 0 0
  size 1 1
  priority 800              // float above map/markers
  hexactpos 1
  vexactpos 1
  hexactsize 0
  vexactsize 0
  color 0.506 0.506 0.506 0.392    // full-screen overlay
  style rover_sim_colorable
  scriptclass "LBMenuPopulator"
  {
    // 4 quadrants + buttons (see below)
  }
}
```

### Quadrant Pattern
```
PanelWidgetClass quadrantName {
  ignorepointer 1
  position X Y              // 0 or 0.51 for X, 0 or 0.51+ for Y
  size 0.49 0.46            // ~49% width, ~46% height (1% gap between)
  hexactpos 1
  vexactpos 1|0
  hexactsize 0
  vexactsize 0
  style LB_Clean_outline    // white 1px border
  {
    // Section header
    TextWidgetClass lblName {
      ignorepointer 1
      position 0 5
      size 1 25
      halign center_ref
      hexactpos 1 vexactpos 1 hexactsize 0 vexactsize 1
      font "gui/fonts/MetronBold16"
      color 1 0.6 0.1 1              // amber/gold
      text "Section Title"
      "text halign" center
    }
    // Controls inside...
  }
}
```

### Quadrant Layout Map
```
+--------------------------+--------------------------+
| position 0 0             | position 0.51 0          |
| size 0.49 0.46           | size 0.49 0.46           |
| (Top-Left)               | (Top-Right)              |
+--------------------------+--------------------------+
| position 0 0.51          | position 0.51 0.51       |
| size 0.49 0.46           | size 0.49 0.46           |
| (Bottom-Left)            | (Bottom-Right)           |
+--------------------------+--------------------------+
```

### Header Inside Quadrants
Color: `1 0.6 0.1 1` (amber) — matches the gold headers in LBmaster admin panels.

### Close Button Wiring (Critical Pattern)
When the config panel is a separate layout (`panel_settings_root`) that needs to show/hide sibling widgets:

1. **Panel handler needs parent root reference:**
```cpp
class MyConfigHandler extends ScriptedWidgetEventHandler {
    Widget layoutRoot;
    private Widget m_ParentRoot;

    void Init(Widget root, Widget parentRoot = null) {
        layoutRoot = root;
        m_ParentRoot = parentRoot;
    }

    override bool OnClick(Widget w, int x, int y, int button) {
        if (w == btnClose) {
            if (m_ParentRoot) {
                m_ParentRoot.FindAnyWidget("panel_settings_root").Show(false);
                m_ParentRoot.FindAnyWidget("panel_list_frame").Show(true);
                m_ParentRoot.FindAnyWidget("Sidebar_Root").Show(true);
            }
            return true;
        }
        return false;
    }
}
```

2. **Parent passes its root when creating the handler:**
```cpp
// In VPPMapMenu.c (parent)
m_SettingsHandler = new MyConfigHandler();
m_SettingsUIRoot.SetHandler(m_SettingsHandler);
m_SettingsHandler.Init(m_SettingsUIRoot, layoutRoot);  // <-- pass layoutRoot
```

### Styling Choices
| Element | Color | Notes |
|---|---|---|
| Section headers (inside quadrants) | `1 0.6 0.1 1` | Amber/gold |
| Labels | `0.8 0.8 0.8 1` | Dim white |
| Checkbox labels | `0.2 0.8 0.2 1` | Green |
| Slider colors | Varies per section | Red `1 0 0 1`, Green `0.2 0.8 0.2 1`, Orange `1 0.5 0 1` |
| Separators | `PanelWidgetClass` with `color 1 0.5 0 0.3` | 1px orange line |
| Font (headers) | `gui/fonts/MetronBold16` | Bold 16 |
| Font (body) | `gui/fonts/Metron14` | Regular 14 |
| Close button | `1 0.196 0.196 1` | Red outline |
| Save button | `0 1 0 1` | Green outline |
| Background | `0.506 0.506 0.506 0.392` + `rover_sim_colorable` | Semi-transparent overlay |

## Verification
- [ ] Shell has `pageWidgets` (PanelWidgetClass with `LBGapHandler`) and `buttonWidgets` (WrapSpacerWidgetClass)
- [ ] Each page is a flat `PanelWidgetClass` with `style blank`, `size 500 550`
- [ ] All widgets have `hexactpos 1` and `hexactsize 1`
- [ ] Widget names match what the C# script expects via `FindAnyWidget()`
- [ ] No nested panel containers inside pages
- [ ] Shell background uses `0.506 0.506 0.506 0.392` + `rover_sim_colorable`
- [ ] Standalone config panels use `priority 800`, `visible 0`, `size 1 1` at root level
- [ ] Config panel handler receives parent root via Init() for close/show sibling logic
- [ ] Quadrant panels use `style LB_Clean_outline`, `ignorepointer 1`, 0.49×0.46 sizing


## Client-Server Mod Separation


# DayZ Client/Server Mod Separation

## Core Pattern
Two mods in this architecture:
- **VanillaPPMap** (client mod) — UI, markers, user-facing features
- **VanillaPPMap_Server** (server mod) — group management, server-side state

## Critical Rule: missionServer.c Runs on BOTH
`missionServer.c` executes on the server for ALL connected players. Adding server-side handlers (like GROUP_CREATE) to the client mod's missionServer.c creates **duplicate handlers** — both fire on the server.

## Symptoms of Duplicate Handlers
- "String CORRUPTED - FIX OnStoreLoad()" errors
- `ctx.Read(tag)` fails because first handler consumed the ctx buffer
- Error at line where `ParamsReadContext.Read()` is called

## RPC Routing Chain
```
Client RPC → DayZGame.OnRPC → VanillaPlusPlus.OnRPC (client mod)
    ↓ (if GROUP_RPC_MIN <= rpc <= GROUP_RPC_MAX)
VPPRPCManager.OnRPC → registered handler (GroupServerManager)
```

## What Goes Where

| Component | Client Mod (VanillaPPMap) | Server Mod (VanillaPPMap_Server) |
|-----------|--------------------------|----------------------------------|
| missionServer.c | Only marker RPCs (GetRPCManager) | N/A — no missionServer.c |
| Group RPCs | UI sends via ScriptRPC | GroupServerManager handles |
| VPPRPCManager | Routes to VPPGroupRPCs | N/A — client mod provides |
| Chat/VPPChatManager | Client UI | Server-side state |

## Anti-Patterns
1. ❌ Adding GROUP_CREATE/etc handlers to client mod's missionServer.c
2. ❌ Assuming server mod has its own VPPRPCManager (uses client mod's)
3. ❌ Not clearing compiled script cache after reverting missionServer.c

## RPC Override Order: super.OnRPC() Causes ctx Corruption

When overriding `OnRPC` (e.g., `VanillaPlusPlus.OnRPC`), calling `super.OnRPC()` BEFORE your handler **consumes/corrupts `ParamsReadContext`** data.

**Bad (ctx consumed by super before VPP reads it):**
```c
override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    super.OnRPC(sender, target, rpc_type, ctx); // ← ctx may be consumed here
    if (rpc_type >= VPPGroupRPCs.GROUP_RPC_MIN && rpc_type <= VPPGroupRPCs.GROUP_RPC_MAX) {
        VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx); // ← reads corrupted ctx
    }
}
```

**Fix (route VPP RPCs before super, then return):**
```c
override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    if (rpc_type >= VPPGroupRPCs.GROUP_RPC_MIN && rpc_type <= VPPGroupRPCs.GROUP_RPC_MAX) {
        VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx);
        return; // ← skip super for VPP-managed RPCs
    }
    super.OnRPC(sender, target, rpc_type, ctx); // ← non-VPP RPCs still get base handling
}
```

**Rule:** If your mod manages its own RPC range, intercept BEFORE calling super. The `return` prevents the base class from touching data your handler needs.

## Fix: Compiled Cache
If String CORRUPTED persists after source revert:
1. Stop server completely
2. Delete `storage_x/` in server profile
3. Delete `.c.cache` files in `mpmissions/`
4. Restart — server recompiles from source

## Debug Check
Look for this in server logs:
```
[VPPGroups] Server-side group handlers registered.
```
If present, your client mod's missionServer.c still has old group code in compiled cache.

