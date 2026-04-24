---
name: dayz-mod-development
version: 1.0.0
category: dayz
description: Complete DayZ mod development guide — UI components, rendering patterns, RPC handlers, server config, admin layouts, settings menus, audit workflows, and crash prevention.
tags: [dayz, mod-dev, ui, rpc, rendering, settings, admin]
---

# DayZ Mod Development — Complete Guide


## Core Methodology & Patterns

--- 
name: dayz-mod-ui-dev
description: Techniques for developing DayZ-compatible UI components by examining existing mods to extract proper standards, adapting UI design principles to DayZ context, creating modular component specifications, building reusable templates, and ensuring format compliance
category: devops
---
# DayZ Mod UI Development Using Observed Standards

## Overview
This skill provides techniques for developing DayZ-compatible UI components when direct references are unavailable or need validation. The approach involves analyzing existing working mods to extract true standards, adapting proven UI design principles (like LBMaster's "how to code properly") to the DayZ context, creating reusable component specifications, building templates for team collaboration, and establishing verification processes against actual mod files.

## When to Use
- Starting UI development in contexts where direct references are scarce or unreliable
- Needing to adapt established design principles to specific technical contexts (like DayZ XML format)
- Creating reusable UI components that follow modular design approaches
- Building documentation that translates general principles to specific implementation contexts
- Ensuring output complies with existing working systems rather than theoretical specifications

## Core Principles

### 1. Observe Before Assuming
Analyze existing working DayZ mods to extract actual GUI layout standards rather than assuming conventions based on documentation alone.

### 2. Adapt Proven Principles
Take established approaches (like LBMaster's "how to code properly") and adapt them to the specific constraints and capabilities of the target system (DayZ mod system).

### 3. Build Modular Components
Use Atomic/Molecular/Organism principles to break complex UIs into reusable, testable components with clear interfaces.

### 4. Create Team-Collaborative Assets
Build reusable templates, examples, and documentation that enable consistent implementation across team members.

### 5. Verify Against Working Systems
Establish validation processes that check output against actual working examples to ensure real-world compatibility.

## Step-by-Step Approach

### Phase 1: Standard Extraction
1. Locate existing working DayZ mods with similar UI requirements
2. Extract actual .xml headers and .layout files from these mods
3. Identify the precise format, structure, and conventions used
4. Document observed patterns vs. assumed or documented patterns
5. Create baseline templates from the observed standards

### Phase 2: Principle Adaptation
1. Identify UI design principles to apply (e.g., LBMaster's modular approach)
2. Analyze DayZ mod system constraints and capabilities
3. Adapt principles to fit within DayZ's XML-based GUI system
4. Define how each principle translates to specific DayZ implementation techniques
5. Create adapted guidelines that maintain principle intent while respecting system limits

### Phase 3: Component Development
1. Break down target UI into Atomic/Molecular/Organism components
2. Define clear interfaces and responsibilities for each component
3. Implement components following adapted principles
4. Create reusable specifications for each component type
5. Build examples demonstrating component usage and composition

### Phase 4: Team Enablement
1. Create mod.xml and layout.html templates from observed standards
2. Build component examples showing proper usage
3. Develop comprehensive documentation that explains both what and why
4. Establish naming conventions and file organization standards
5. Create validation checklists for team members to use

### Phase 5: Validation & Verification
1. Test generated files against known working mods
2. Verify DayZ XML format compliance through actual loading tests
3. Check component composition produces expected visual results
4. Validate against accessibility and performance requirements
5. Document any discrepancies and their resolutions

## Key Applications
- DayZ mod UI development for custom interfaces
- VPPmaps touch interface creation and enhancement (see `vppmaps-sidebar-layout` for sidebar constraints)
- Custom admin panels, sidepanels, 3D markers, and no build zones
- Adapting technical documentation standards (LBMaster, etc.) to specific contexts
- Creating reusable UI component libraries for game modding
- Building team-shareable development foundations

## Related Skills
- `vppmaps-sidebar-layout` — VPPMaps-specific: 440px sidebar constraint, LBmaster quadrant grid, server connect hooks

## Verification Checklist
- [] Generated mod.xml matches observed DayZ mod header format exactly
- [] Layout files follow observed .layout structure and syntax
- [] Component specifications enable Atomic/Molecular/Organism composition
- [] Templates produce working output when integrated
- [] Documentation explains adaptations from source principles
- [] Validation passes against actual working DayZ examples
- [] Approach works with existing infrastructure rather than requiring rebuilds
- [] Output is suitable for team collaboration and sharing

## RPC Handler Registration Pattern (VPPRPCManager)

VPPRPCManager stores handlers in `m_RPCMap<int, ScriptCaller>`. The `OnRPC` dispatcher in DayZGame checks the range and routes to `VPPRPCManager.OnRPC()`.

**Registration (client side):**
```cpp
VPPRPCManager rpc = VPPRPCManager.Get();
rpc.RegisterRPC(VPPGroupRPCs.GROUP_SYNC_DATA, ScriptCaller.Create(HandleSyncData));
rpc.RegisterRPC(VPPGroupRPCs.GROUP_SYNC_PLAYERS, ScriptCaller.Create(HandleSyncPlayers));
rpc.RegisterRPC(VPPGroupRPCs.GROUP_MEMBER_POS_UPDATE, ScriptCaller.Create(HandleMemberPosUpdate));
rpc.RegisterRPC(VPPGroupRPCs.GROUP_INVITE_RECEIVED, ScriptCaller.Create(HandleInviteReceived));
// ... all 9 handlers
```

**In DayZGame.OnRPC():**
```cpp
override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    super.OnRPC(sender, target, rpc_type, ctx);
    if (rpc_type >= VPPGroupRPCs.GROUP_RPC_MIN && rpc_type <= VPPGroupRPCs.GROUP_RPC_MAX) {
        VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx);
    }
}
```

**Critical gap:** RPC handlers defined in ClientManager.c but NEVER registered = handlers exist but never fire. Always verify `RegisterRPC` calls exist in constructor or init.

## 3D Marker Map-Open Guard

VPP3DMarker.DoUpdate() renders 3D world overlays but doesn't check if the map menu is open. When map is full-screen, 3D markers render on top of the map. Fix:

```cpp
void DoUpdate() {
    // FIX: Don't render 3D markers when the map menu is open
    if (GetGame() && GetGame().GetUIManager().FindMenu(VPP_MENU_MAP)) {
        if (m_VisualRoot && m_VisualRoot.IsVisible()) m_VisualRoot.Show(false);
        return;
    }
    // ... existing rendering logic
}
```

Also call `g_Game.HideAll3dMarkers()` in map menu `OnShow()` and `g_Game.ShowAllHidden3dMarkers()` in `OnHide()`.

## MissionGameplay HUD Update Loop Driver

HUD components that aren't UIScriptedMenu (plain Widget classes) need an explicit update loop. The architecture:

```cpp
modded class MissionGameplay {
    private ref VPPHUDManager m_HUDManager;
    private ref VPPCompassWidget m_Compass;

    override void OnMissionStart() {
        super.OnMissionStart();
        m_HUDManager = VPPHUDManager.Get();
        m_Compass = new VPPCompassWidget();
        m_Compass.Init();
        m_HUDManager.RegisterWidget("Compass", m_Compass.GetRoot());
    }

    override void OnUpdate(float timeslice) {
        super.OnUpdate(timeslice);
        if (m_HUDManager) m_HUDManager.OnUpdate(timeslice);
        if (m_Compass) m_Compass.UpdateHud(timeslice);
        if (g_Game) g_Game.UpdateAllMarkers();
    }
};
```

## XML Layout to DayZ FrameWidgetClass Rewrite

XML-style layouts (`<rect>`, `<text>`, `<progressbar>`) from external tools must be rewritten to DayZ's FrameWidgetClass format:

**Wrong (XML):** `<rect name="BG" x="10" y="30" w="300" h="200" rgba="0.1,0.1,0.1,0.8"/>`
**Correct (DayZ):** `class FrameWidgetClass: BackgroundBase { x = 10; y = 30; w = 300; h = 200; color = "0.1 0.1 0.1 0.8"; };`

**Notes:** No commas in values — use spaces. Font: `gui/fonts/PuristaBold`, `gui/fonts/PuristaMedium`.

## Server-Side Group Sync: InvokeOnConnect

`OnClientReadyEvent` override crashes all client connections silently. Use `InvokeOnConnect` instead with a delayed sync:

```cpp
override void InvokeOnConnect(PlayerBase player, PlayerIdentity identity) {
    super.InvokeOnConnect(player, identity);
    if (!identity) return;
    GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(SendGroupSync, 3000, false, identity);
}
```

## Critical Debugging Notes

### PanelWidgetClass vs Widget (layout vs script)
- `.layout` files use `PanelWidgetClass` — the `Class` suffix is for XML declarations only
- `.c` script code uses `Widget` (base type) — no `PanelWidgetClass` type exists in Enforce Script
- `FindAnyWidget()` returns `Widget` — no cast needed for panels
- Wrong: `PanelWidgetClass colorPreview;` in C# → compile error "Unknown type 'PanelWidgetClass'"
- Correct: `Widget colorPreview;` and `colorPreview = layoutRoot.FindAnyWidget("name");`

### OnClientReadyEvent override can crash connections
- Overriding `OnClientReadyEvent` in `MissionServer.c` can silently crash ALL client connections
- Safe: only override `OnInit()` for server-side initialization
- Client-side data sync should use RPC requests from client after a delay, not push from server on connect
- Race condition: server loads groups at 10s → client must request AFTER 10s (use 12s+)
- Pattern: `GetGame().GetCallQueue(CALL_CATEGORY_GUI).CallLater(this.RequestGroupData, 12000, false);`

### SetPos takes pixel offsets, not relative values
- `m_Root.SetPos(relX, relY)` with 0-1 range barely moves anything
- Correct: multiply by scale: `m_Root.SetPos(relX * 1000.0, relY * 1000.0)`
- Layout `position 0 60` means pixel offset from anchor — script SetPos adds to that base

### All-or-nothing exact pixel sizing
- When root has `hexactpos 1`, ALL children must also have `hexactpos/vexactpos/hexactsize/vexactsize 1`
- Mixing relative (`size 0.49 0.46`) with absolute (`hexactsize 1`) causes unpredictable rendering
- Rule: if parent is exact, children are exact. If parent is relative, children can be relative or exact (but be consistent)
- Example breakage: root `hexactpos 1` with child using `size 0.49 0.46` → child renders as 49×46 pixels instead of 49%

### FindWidget vs FindAnyWidget
- `FindWidget()` only searches immediate children — returns NULL for nested widgets
- `FindAnyWidget()` searches recursively through all descendants
- In `.layout` files, widgets nested inside other PanelWidgetClass containers need `FindAnyWidget`
- Always use `FindAnyWidget` in script code unless you specifically need top-level-only lookup
- Example breakage: `m_Root.FindWidget("CompassImage")` returns NULL when image is inside a panel
- Correct: `m_Root.FindAnyWidget("CompassImage")` — finds it at any depth

### FileExist on directory paths is unreliable
- `FileExist("$profile:SomePath/")` with trailing slash may return false even when directory exists
- `MakeDirectory` is idempotent — calling it on existing directory is safe (no-op in DayZ)
- Safe pattern: `MakeDirectory("$profile:VPPMap_Groups");` — creates if missing, skips if exists
- Wrong pattern: `if (!FileExist(path)) MakeDirectory(path);` — can fail silently when FileExist returns wrong value
- For multi-level paths, call MakeDirectory for each level in order (parent first)

### LBmaster script classes are for dynamic layouts only
- `LBMenuPopulator` — for LBmaster page patterns with dynamic content. Breaks static panel positioning
- `LBGapHandler` — auto-spacing between children. Breaks grid layouts with explicit positions
- For static config menus: omit `scriptclass` entirely, use explicit pixel positions

### Config overlay: hide map for FPS
- Full-screen overlay must hide map widgets to stop rendering: `Map_Root`, `Map_Frame_Border`, `Sidebar_Root`, `Tabs_Container`
- Use `widget.Show(false)` — prevents engine from rendering those subtrees

## VPPHUDManager Plain Widget Pattern
For HUD elements (compass, minimap) that should always be visible — NOT UIScriptedMenu, NOT entered via EnterScriptedMenu.

**Correct approach:**
1. Class does NOT extend UIScriptedMenu — just a plain class
2. Class has `Widget Init()` (not `override Widget Init()`)
3. Class has `void Update(float timeslice)` (not `override`)
4. Class has `void Show(bool state)` method for toggle
5. Created in missionGameplay.c: `m_Widget = new VPPWidgetClass(); Widget root = m_Widget.Init();`
6. Registered: `VPPHUDManager.Get().RegisterWidget("Name", root);`
7. Updated in `MissionGameplay::OnUpdate()`: `if (m_Widget) m_Widget.Update(timeslice);`
8. Member declared: `private ref VPPWidgetClass m_Widget;`

**VPPMissionBase.c — remove menu registration for plain widgets:**
- UIScriptedMenu entries (VPP_MENU_MAP) stay in MissionBase::CreateScriptedMenu
- Plain HUD widgets (compass, minimap) do NOT go in CreateScriptedMenu
- Compass is NOT VPP_MENU_COMPASS anymore — it's a plain widget

**Why:** UIScriptedMenu creates a menu layer that conflicts with map/menu transitions. Plain HUD widgets attached via VPPHUDManager stay on top consistently.

## Build-Debug Loop (Wine/Proton Server)
When building and restarting a DayZ server via Proton:
1. The build script `exec`-s the server (never returns to shell)
2. Always redirect stderr: `bash script.sh 2>&1 &` to capture output
3. Check logs at `$SERVER_DIR/profile/script_*.log` — grep for your mod's class names
4. Check `$SERVER_DIR/profile/server_console.log` for runtime behavior
5. Check `$SERVER_DIR/profile/*.RPT` for engine-level errors
6. `Can't compile` errors show as `SCRIPT (E)` in script_*.log — search for `@\"yourmod/path/file.c,line\":`

## Common Enforce Script Pitfalls (from Live Fixes)

### Method insertion breaks braces
When inserting a method via string replacement before a `return` statement inside a method body, the new method's braces get placed INSIDE the parent method. Always verify the brace balance after insertion.
- Wrong pattern: insert `void Show() { ... }` before `return m_RootWidget;` inside `Init()` → syntax error "Broken expression (missing ';'?)"
- Correct: find the CLOSING `}` of `Init()`, insert new method AFTER it

### Strong reference parameter warnings (DayZ compiler)
`FIX-ME: Method argument can't be strong reference` — DayZ doesn't allow strong refs as function params. Use `ref` or const ref patterns. This is a warning, not an error — compilation still succeeds.

### Override keyword on plain classes
- UIScriptedMenu subclass methods: use `override Widget Init()`, `override void Update()`, `override void OnShow()`
- Plain class (non-UIScriptedMenu): use `Widget Init()`, `void Update()`, `void OnShow()` — no `override` keyword
- Mixing causes: `Types 'X' and 'UIScriptedMenu' are unrelated`

### HideAll3dMarkers for map menu
When opening a fullscreen map menu, 3D markers render on top. Fix: call `g_Game.HideAll3dMarkers()` in `OnShow()`. Note: there's no built-in restore function — markers stay hidden until re-added or engine handles respawn.

## Anti-Patterns to Avoid
- Assuming documentation describes actual implementation without verification
- Forcing principles to fit systems where they create unnecessary complexity
- Creating components that are too granular or too monolithic for reuse
- Building documentation that only covers mechanics without reasoning
- Validating against theoretical specifications instead of working systems
- Requiring complete rebuilds when incremental adaptation would suffice
- Using `PanelWidgetClass` in script code (layout-only type, will not compile)
- Overriding `OnClientReadyEvent` in MissionServer (silent connection crash)
- Calling `SetPos` with relative 0-1 values (need pixel scaling)
- Using fonts that only exist in specific mods (e.g. `sdf_Metron*` in VPPAdminTools) — causes crash on load. Use standard DayZ fonts: `gui/fonts/Chat` (chat items), `gui/fonts/PuristaMedium` (labels/UI), `gui/fonts/PuristaBold` (headers)

## Example Workflow: DayZ VPPmaps Touch Interface
1. **Extract**: Examine VanillaPPMap mod for actual mod.xml and .layout format
2. **Adapt**: Apply LBMaster's Atomic/Molecular/Organism approach to DayZ XML constraints
3. **Componentize**: Break VPPmaps into MarkerAdminPanel, MarkerListItem, etc. components
4. **Template**: Create mod.xml and layout templates from observed standards
5. **Verify**: Test generated files load correctly in DayZ and produce expected UI
6. **Share**: Document approach and share templates with team

## Expected Outcomes
When properly applied, this approach produces:
- DayZ-compatible files that integrate seamlessly with existing mods
- Modular UI components that follow sound design principles
- Reusable team assets that reduce duplication and increase consistency
- Documentation that captures both implementation and rationale
- Development approaches that respect existing infrastructure investments
- Systems that are maintainable, extensible, and team-shareable

## UI Component Development

# DayZ Mod UI Development Workflow

## Overview
Reusable workflow for developing DayZ-compatible UI components with consistent theming, accessibility, and performance considerations.

## Trigger Conditions
- Starting new DayZ mod UI development
- Need to create consistent theming across multiple UI components
- Requirement for DayZ-compliant .layout files
- Desire to implement accessible, performant interfaces

## Workflow Steps

### 1. Theme Definition (Recommended First)
```xml
<!-- Create theme.xml in mod/addons/layouts/ -->
<?xml version="1.0" encoding="UTF-8"?>
<theme name="[ThemeName]">
    <!-- Define color palette -->
    <color name="primary">#AARRGGBB</color>
    <color name="secondary">#AARRGGBB</color>
    <!-- Add interactive states -->
    <color name="state-hover">#AARRGGBB</color>
    <!-- Define typography -->
    <font name="body-medium">EtceteraNarrow</font>
</theme>
```

### 2. Base Component Creation
Create reusable base components that reference theme values:
```xml
<!-- button_base.layout -->
<?xml version="1.0" encoding="UTF-8"?>
<button x="0" y="0" width="100" height="25">
    <color name="background">[theme reference]</color>
    <color name="border">[theme reference]</color>
    <font>EtceteraNarrow</font>
    <align>center</align>
    <!-- Add interactive state handlers -->
</button>
```

### 3. Component Implementation
For each UI component:
1. Create .layout file with proper DayZ structure
2. Use base components where applicable
3. Implement theme-consistent styling
4. Add accessibility features (tooltips, focus indicators)
5. Include initialization scripts for dynamic behavior
6. Validate against DayZ .layout requirements

### 4. Validation Checklist
- [ ] Valid .layout XML structure
- [ ] Proper attribute usage (x, y, width, height, color, font, align)
- [ ] Correct event handler syntax (onMouseClick, onMouseEnter, etc.)
- [ ] ARGB color format (#AARRGGBB)
- [ ] Pixel-based positioning with top-left origin
- [ ] Supported font usage (EtceteraNarrow, EtceteraNarrowBold, etc.)
- [ ] Accessibility: adequate contrast ratios, focus indicators
- [ ] Performance: <16ms render time target
- [ ] Interactive states: hover, pressed, focused visual feedback

### 5. Integration Pattern
For admin panels and complex interfaces:
- Use container frames with scrollable content areas
- Implement selection mechanisms with visual highlighting
- Provide clear action buttons with consistent styling
- Include tooltip guidance for all interactive elements
- Implement efficient update mechanisms (only refresh changed elements)

## DayZ .layout Specifics
- Root element: `<frame>`, `<button>`, `<edit>`, etc.
- Coordinates: Pixel-based, origin top-left (0,0)
- Colors: ARGB hex format (#AARRGGBB)
- Fonts: Limited to DayZ available fonts (TahomaB, EtceteraNarrow, etc.)
- Events: onMouseEnter, onMouseLeave, onMouseDown, onMouseUp, onMouseClick, onMouseDoubleClick, onMouseHold, onMouseWheel, onKeyDown, onKeyUp, onSetFocus, onKillFocus, onTimer, onShow, onHide, onItemSelect, onItemDeselect, onSliderPosChanged, onCheckboxChecked, onEditChanged
- Attributes: x, y, width, height, color, font, align, valign, shadow, autowidth, autoheight, text, tooltip

## Crash-Prevention Patterns (Init/Show/Hide)

DayZ GUI crashes most often from null dereferences during initialization. These patterns prevent common SEH exceptions (like `0x80000101` ACCESS_VIOLATION).

### 1. Re-entrancy Guard
`Init()` can be called multiple times. Use `layoutRoot` as the guard — don't use a separate bool:

```c
override Widget Init() {
    if (layoutRoot)
        return layoutRoot;  // Already initialized

    layoutRoot = GetGame().GetWorkspace().CreateWidgets("MyMod/GUI/Layouts/Main.layout");
    if (!layoutRoot) {
        Print("[MyMenu] FATAL: Failed to create main layout!");
        return layoutRoot;
    }
    // ... rest of Init
    return layoutRoot;
}
```

### 2. Lazy-Load Sub-Layouts
Don't create sub-layouts in `Init()`. Defer `CreateWidgets` to first tab click with an `Ensure*Loaded()` guard. This moves crash-prone calls out of the hot path:

```c
private bool m_SettingsLoaded = false;

private void EnsureSettingsLoaded() {
    if (m_SettingsLoaded) return;
    m_SettingsLoaded = true;

    if (!m_ContainerSettingsUI) return;
    m_SettingsUIRoot = GetGame().GetWorkspace().CreateWidgets(
        "MyMod/GUI/Layouts/SettingsUI.layout", m_ContainerSettingsUI);
    if (!m_SettingsUIRoot) {
        Print("[MyMenu] WARNING: Failed to create Settings layout!");
        return;
    }
    m_SettingsHandler = new MySettingsMenu();
    m_SettingsUIRoot.SetHandler(m_SettingsHandler);
    m_SettingsHandler.Init(m_SettingsUIRoot);
}

void SetSidebarTab(int index) {
    if (index == 3) EnsureSettingsLoaded();  // Lazy trigger
    if (m_ContainerSettingsUI) m_ContainerSettingsUI.Show(index == 3);
    // ...
}
```

### 3. Null-Safe OnShow / OnHide
`GetGame().GetMission()` and `GetHud()` can return null, especially during shutdown or transitions. Always null-check both:

```c
override void OnShow() {
    super.OnShow();
    Mission mission = GetGame().GetMission();
    if (mission && mission.GetHud()) {
        mission.GetHud().Show(false);
    }
}

override void OnHide() {
    super.OnHide();
    Mission mission = GetGame().GetMission();
    if (mission && mission.GetHud()) {
        mission.GetHud().Show(true);
    }
}
```

### 4. Null-Safe Destructor
Same pattern — check `GetMission()` and `GetHud()` before calling methods:

```c
void ~MyMenu() {
    Mission mission = GetGame().GetMission();
    if (mission) {
        mission.PlayerControlEnable(false);
        if (mission.GetHud()) {
            mission.GetHud().Show(true);
        }
    }
    // Save state, cleanup...
}
```

### 5. Null-Safe FindAnyWidget
Check every `FindAnyWidget` result before calling methods on it. One null widget can crash the whole menu:

```c
Widget sidebar = layoutRoot.FindAnyWidget("Sidebar_Root");
if (sidebar) sidebar.Show(true);  // Never call .Show() on null
```

### 6. Null-Safe CreateWidgets for Sub-Layouts
Always check the return value of `CreateWidgets` — missing .layout files return null:

```c
Widget root = GetGame().GetWorkspace().CreateWidgets("MyMod/GUI/Layouts/Sub.layout", container);
if (!root) {
    Print("[MyMenu] WARNING: Failed to create Sub layout!");
    return;  // Don't proceed — handler init on null will crash
}
```

### Common Crash Vectors
| Crash | Cause | Fix |
|-------|-------|-----|
| `VPPMapMenu::Init` SEH 0x80000101 | Null widget deref in Init | Re-entrancy guard + lazy-load |
| `OnShow` crash | `GetHud()` null during transition | Null-check mission + hud |
| Destructor crash | Stale mission reference | Null-check GetMission() |
| `CreateWidgets` null | Missing/malformed .layout file | Check return value |

## Chat Implementation: UIScriptedMenu > Modded Vanilla Classes > Plain Widget

**VERIFIED**: Plain C++ widgets with `new` + `CreateWidgets` ARE rendered by DayZ. The UIManager only manages them for input/lifecycle — rendering happens regardless. Use plain widgets for always-visible HUD elements (compass, minimap). Register with `VPPHUDManager.Get().RegisterWidget("Name", root)` for show/hide/position management.

**PITFALL (fragile)**: Modding vanilla `Chat`/`ChatLine` classes works but breaks easily when vanilla init changes, layout structures collide, or `Destroy()` on the root widget breaks the vanilla lifecycle.

**Correct approach: Extend UIScriptedMenu**

1. Class extends `UIScriptedMenu` (same as Compass, InfoPanel, MapMenu)
2. Register in missionGameplay via `EnterScriptedMenu(VPP_MENU_CHAT, null)` + `ShowScriptedMenu(m, null)`
3. `Init()` creates layout with `GetGame().GetWorkspace().CreateWidgets(...)` — returns `layoutRoot`
4. Ring buffer of pre-created ChatLine widgets for message display
5. LBMaster visual style: `sdf_MetronBook72` font, `outline size 2`, `shadow size 8`

```c
// VPPChatWidget.c — UIScriptedMenu for HUD rendering
class VPPChatWidget: UIScriptedMenu {
    private Widget m_ChatMessages;
    private ref array<Widget> m_LineWidgets;
    private int m_WriteIdx = 0;
    private int m_LineCount = 0;
    private const int MAX_LINES = 40;

    void VPPChatWidget() {
        m_LineWidgets = new array<Widget>;
    }

    override Widget Init() {
        layoutRoot = GetGame().GetWorkspace().CreateWidgets("Mod/GUI/Layouts/VPPChatWidget.layout");
        if (!layoutRoot) return layoutRoot;
        m_ChatMessages = layoutRoot.FindAnyWidget("ChatMessages");
        // Pre-create line widgets from sub-layout
        for (int i = 0; i < MAX_LINES; i++) {
            Widget line = GetGame().GetWorkspace().CreateWidgets("Mod/GUI/Layouts/ChatLine.layout", m_ChatMessages);
            if (line) {
                line.Show(false);
                m_LineWidgets.Insert(line);
            }
        }
        return layoutRoot;
    }

    void AddChatMessage(string sender, string message, int color) {
        int idx = m_WriteIdx;
        m_WriteIdx = (m_WriteIdx + 1) % MAX_LINES;
        if (m_LineCount < MAX_LINES) m_LineCount++;
        // ... populate line widgets, reposition
        m_LineWidgets.Get(idx).Show(true);
    }
};
```

```c
// missionGameplay.c — registration
m_ChatWidget = VPPChatWidget.Cast(GetGame().GetUIManager().EnterScriptedMenu(VPP_MENU_CHAT, null));
if (m_ChatWidget) {
    GetGame().GetUIManager().ShowScriptedMenu(m_ChatWidget, null);
}
VPPClientManager.GetInstance().SetChatWidget(m_ChatWidget);
```

## UIScriptedMenu Registration Pattern

**Rule**: Any HUD overlay (always-visible, non-blocking) MUST use UIScriptedMenu:
1. Define a static const menu ID in `constants.c`
2. Class extends `UIScriptedMenu`, overrides `Init()` returning `layoutRoot`
3. In missionGameplay: `EnterScriptedMenu(MENU_ID, null)` + `ShowScriptedMenu(menu, null)`
4. Store cast reference: `m_MyWidget = VPPMyWidget.Cast(...)`
5. `null` parent means "HUD overlay" (non-blocking, not modal)

Plain `Widget` instances created with `new` + `CreateWidgets` without EnterScriptedMenu are **invisible** — the UIManager doesn't know about them and never renders them.

## UIScriptedMenu vs Plain Widget — When to Use Which

**Decision tree**:
- Widget should ALWAYS be visible (compass, minimap, static HUD)? → Plain widget + VPPHUDManager
- Widget opens/closes with user action (map, admin menu, settings)? → UIScriptedMenu
- Widget needs keyboard input capture (chat input, text fields)? → UIScriptedMenu or modded vanilla

**UIScriptedMenu** (EnterScriptedMenu) — use when widget needs:
- Input focus (keyboard/mouse capture)
- Dynamic show/hide lifecycle (open/close)
- Auto-init/destroy lifecycle managed by UIManager
- Examples: Chat, MapMenu, AdminUI, SettingsUI

**Plain Widget** (new + CreateWidgets + RegisterWidget with VPPHUDManager) — use when widget is:
- Always-visible HUD element (no input, no lifecycle)
- Created once, always shown
- Managed by VPPHUDManager for position/visibility
- Examples: Compass bar, minimap, static info panels

```c
// Plain widget pattern (VERIFIED WORKING)
class MyHUDWidget {
    private Widget m_RootWidget;

    Widget Init() {
        m_RootWidget = GetGame().GetWorkspace().CreateWidgets("MyMod/GUI/Layouts/MyHUD.layout");
        return m_RootWidget;
    }

    void Show(bool state) {
        if (m_RootWidget) m_RootWidget.Show(state);
    }

    void Update(float timeslice) {
        if (!m_RootWidget || !m_RootWidget.IsVisible()) return;
        // per-frame logic here
    }
}

// In missionGameplay.c
m_MyHUD = new MyHUDWidget();
Widget root = m_MyHUD.Init();
if (root) {
    m_MyHUD.Show(true);
    VPPHUDManager.Get().RegisterWidget("MyHUD", root);
}

// In MissionGameplay.OnUpdate()
if (m_MyHUD) m_MyHUD.Update(timeslice);
```

**PITFALL**: Widgets created as children of a UIScriptedMenu's layoutRoot only exist when that menu is open. HUD overlays must be workspace-level children created with `CreateWidgets("path")` (no parent arg), NOT `CreateWidgets("path", someMenuRoot)`.

**PITFALL (verified broken)**: `VPPCompassWidget` as UIScriptedMenu was wrong — Update() only fires when the menu is active, and EnterScriptedMenu gives it input focus. Compass should be a plain widget with `new VPPCompassWidget()` + `Init()` returning the root widget, then registered with VPPHUDManager. The widget's `Update(float)` must be called manually from MissionGameplay's Update() or via CallLater.

## Texture Paths in .layout Files

**CRITICAL**: Use FORWARD SLASHES in imageTexture paths, not backslashes.

```xml
<!-- CORRECT -->
imageTexture "VanillaPPMap/GUI/Compass_slim.png"

<!-- BROKEN — causes white bars / invisible textures -->
imageTexture "VanillaPPMap\\GUI\\Compass_slim.png"
imageTexture "VanillaPPMap\\\\GUI\\\\Compass_slim.png"
```

The texture file must be included in the PBO build. Check with `pbo list` that the PNG/EDDS is present.

## Font Availability

**PITFALL**: `gui/fonts/Chat` may not exist in all modpacks. Use verified fonts:
- `gui/fonts/Metron14` — standard HUD font (safe fallback)
- `gui/fonts/MetronBold16` — bold headers
- `gui/fonts/Metron12` — small labels
- `gui/fonts/MetronBook18` — larger text
- `gui/fonts/sdf_MetronBook72` — chat (if VPPAdminTools loaded)

If a font doesn't exist, text widgets render empty/white — no crash, just invisible text.

## modded class MissionServer

**PITFALL**: `OnPlayerConnect()` does NOT exist in MissionBase/DayZMissionServer. Can't override it. Only these are valid:
- `override void OnInit()` — server init, after super
- `override void OnMissionStart()` — after mission loads

Player connect handling must be done differently (e.g., in PlayerBase events, or via GroupServerManager polling).

## Chat Line Visual Style (LBMaster-inspired)

Each chat line is a GridSpacerWidgetClass with 3 TextWidgets (group tag, sender, message):
```xml
TextWidgetClass ChatLineSender {
    font "gui/fonts/sdf_MetronBook72"
    "outline size" 2
    "outline color" 0 0 0 1
    "shadow size" 8
    "shadow color" 0 0 0 0.8
    "shadow offset" 1 1
    "bold text" 1
    "exact text" 1
    "exact text size" 14
}
```

## Input Suppression During Chat

When chat input is open, game keybinds (M, K, L, etc.) must be suppressed. Use `SetKeyboardBusy`:

```c
// modded ChatInputMenu.c
modded class ChatInputMenu {
    override void OnShow() {
        super.OnShow();
        GetGame().SetKeyboardBusy(true);   // Suppress ALL game keybinds
        VPPClientManager.GetInstance().GetChatWidget().ShowInput(true);
    }
    override void OnHide() {
        super.OnHide();
        GetGame().SetKeyboardBusy(false);  // Restore game keybinds
        VPPClientManager.GetInstance().GetChatWidget().ShowInput(false);
    }
};
```

In `OnUpdate`, guard custom keybind checks:
```c
// Only fire when NOT typing
if (chatChannelInput && chatChannelInput.LocalPress()) {
    if (!g_Game.IsKeyboardBusy()) {
        VPPClientManager.GetInstance().GetChatWidget().ToggleChannel();
    }
}
```

## Custom Input Actions (XML)

Register in `data/modded_Inputs.xml`:
```xml
<modded_inputs>
    <inputs>
        <actions>
            <input name="UAChatChannel_Groups" loc="Toggle Chat Channel" />
        </actions>
    </inputs>
    <preset>
        <input name="UAChatChannel_Groups">
            <btn name="kL" />  <!-- k + key code letter -->
        </input>
    </preset>
</modded_inputs>
```

Check in code:
```c
UAInput input = GetUApi().GetInputByName("UAChatChannel_Groups");
if (input && input.LocalPress()) { ... }
```

## Performance Considerations
- Minimize DOM-like operations in scripts
- Use efficient update patterns (only modify changed elements)
- Consider virtualization for long lists
- Limit expensive operations in per-frame handlers
- Target <16ms render time for 60FPS capability

## Accessibility Guidelines (WCAG 2.1 AA)
- Minimum 4.5:1 contrast ratio for normal text
- Minimum 3:1 contrast ratio for large text
- Visible focus indicators
- Touch target minimum size: 24x24 pixels
- Consistent navigation and labeling
- Error identification and suggestions
- Tooltips for all interactive elements
- Color not used as sole means of conveying information

## File Organization
```
/addons/
  /layouts/
    theme.xml           -- Theme definition
    /base/              -- Base components (button_base.layout, etc.)
    /components/        -- Specific UI components
    /panels/            -- Panel layouts
```

## Verification Steps
1. Validate XML syntax
2. Check against known good DayZ .layout examples
3. Test interactive states (hover, press, focus)
4. Verify color contrast ratios
5. Confirm font availability in DayZ
6. Test script execution paths
7. Validate responsive behavior if applicable

## Example Component Structure
```xml
<frame name="ExamplePanel" x="50" y="50" width="300" height="200">
    <color name="background">#FF0A0A0A</color>
    <color name="border">#FF9D4EDD</color>
    <border size="2"/>
    
    <frame name="header" x="0" y="0" width="300" height="30">
        <color name="background">#FF9D4EDD10</color>
        <richtext name="title" x="10" y="8" width="280" height="16">
            <color>#FFFFFFFF</color>
            <font>EtceteraNarrowBold</font>
            <text>Panel Title</text>
            <align>center</align>
        </richtext>
    </frame>
    
    <!-- Content area -->
    <frame name="content" x="10" y="40" width="280" height="150">
        <!-- Component-specific content -->
    </frame>
    
    <script>
        // Initialization and event handlers
    </script>
</frame>
```

## Audit & Fix Workflow


# DayZ Mod Audit + Fix Methodology

## Layout Syntax Errors Cause Cascade "Undefined Function" Errors
When a `.layout` file has syntax errors (e.g., invalid keywords like `vextpos` instead of `vexactpos`), the DayZ script compiler may fail to parse related `.c` files, producing misleading "Undefined function" errors. **Always check and fix layout syntax FIRST before assuming .c functions are missing.**

Example from this session:
```
Crash log: "Undefined function 'VPPMapMenu.SetMapNeedsUpdate'" (line 273)
Actual problem: Layout file had `vextpos` at lines 40 and 333
Fix: Replace `vextpos` → `vexactpos` in layout file only
Result: All "undefined" functions in .c file were already present
```

## Trust Original Files Before Adding Code
When fixing compilation errors, **audit the original source files FIRST**:
1. Run `wc -l` on original file to know its true size
2. `grep -n "FunctionName" original.c` to verify if functions actually exist
3. If original is 679 lines and has all functions, do NOT add them again
4. Error: truncating a complete 679-line file to 110 lines → catastrophic breakage

Pattern observed: User reported "Undefined function X" but X already existed in original file. Root cause was layout syntax breaking compilation, not missing functions.

## Pre-flight (MANDATORY — NEVER SKIP)
1. **Verify working directory**: `pwd` and `ls` — confirm the actual project dir before touching files. Users may have reference copies elsewhere.
2. **Check for existing files**: Before creating any new .c file, `grep -rn "class <ClassName>"` across the project to avoid duplicate class declarations.
3. **Check layout naming**: `TextListboxWidget` → must be `TextListboxWidgetClass` in .layout files. Missing `-Class` suffix = silent null.
4. **Coordinate convention**: DayZ HUD positions are 0-1 normalized (multiplied by 1000 for pixel offsets). Ensure all HUD widgets and ApplyPosition methods use the SAME convention — +60 or other offsets cause drift on restart.

## HUDManager Wiring Pattern (VPPMap-based projects)
The canonical VPPHUDManager pattern for this project:
```
// Client/VPPHUDManager.c — singleton, registers widgets, applies positions/colors
class VPPHUDManager {
    static VPPHUDManager Get() { ... }
    void RegisterWidget(string name, Widget w) { ... }
    void ApplyAllPositions() { ... }          // called after all widgets registered
    void SetWidgetPos(string name, float x, float y) { ... }  // save + apply
    void ApplyPositionLocal(string name, float x, float y) { ... } // live preview only
    void ApplyCompassColor(int bodyCol, int lineCol) { ... }  // live color push
    void SetCompassVisible(bool vis) { ... }  // toggle
}
```

Widget lifecycle:
```
widget.Init() → VPPHUDManager.Get().RegisterWidget("Name", root)
                VPPHUDManager.Get().ApplyAllPositions()

Settings UI OnChange → VPPHUDManager.ApplyPositionLocal() or ApplyCompassColor()
Settings UI Save     → VPPHUDManager.SetWidgetPos() + VPPClientManager.SaveClientSettings()
Server RPC back      → VPPHUDManager.ApplyCompassSettings() (push all 3: visibility, body col, line col)
```

## Compass Integration (LBMaster sliding-strip pattern)
- Image is 4x screen width, positioned -1.0 to +3.0
- SetPos offset = -1.0 + (angle / 360.0) * 2.0, where angle is VectorToAngles()[0]
- NOT SetRotation — LBMaster uses horizontal scrolling
- Layout: CompassImage (ImageWidget) + CompassLine (PanelWidget, center strip)
- Both must be FindAnyWidget-able by HUDManager for live color apply
- Hide when: GetUIManager().GetMenu() != null, HUD_HIDE_FLAGS, settings.CompassEnabled == false

## Common Audit Issues Checklist
- [ ] Widget class names in layout match DayZ naming (*Class suffix)
- [ ] No duplicate class declarations across project
- [ ] HUDManager exists as singleton, not duplicated
- [ ] Position coordinates consistent (0-1 normalized, * 1000 for pix)
- [ ] No hardcoded +60 offsets in Init that aren't in ApplyPosition
- [ ] Color picker indices match settings array order
- [ ] ResetAll includes all toggles including CompassEnabled
- [ ] LBMaster-proprietary scriptclass (LBGapHandler) → remove if not in this project scope
- [ ] Fonts: sdf_Metron* only exist in LBMaster — use PuristaBold/PuristaMedium as fallback
- [ ] UIScriptedMenu vs plain Widget: HUD overlays must be plain widgets, not UIScriptedMenu

## Webhook/Manager Disconnection Pattern
A recurring audit failure: manager classes are fully defined but **zero consumers call them**. Common in complex mods where infrastructure is built before wiring.
- After finding any *Manager class, immediately `grep -rn "<ClassName>.Get()\|<ClassName>.Get().Fire\|<ClassName>.Get().Handle"` across ALL server/client files
- If result is zero or only constructor init → it's wired to nothing
- Pattern: `VPPWebhookManager.FireX()` exists but no handler calls it. Fix by injecting calls into the relevant RPC handler methods.

## Duplicate Modded Class — Silent Conflict
Two files defining `modded class MissionBase` doesn't produce a compiler error — the engine silently loads one and ignores the other. Non-deterministic which "wins".
- Audit: `grep -rn "modded class <ClassName>" ./*.c` — if count > 1, you have a conflict
- Fix: keep one, empty or delete the other. NEVER have two files modding the same base class.

## Patch Tool Failures — Fall Through Strategy
The `patch` tool requires exact whitespace/newline matching. When it fails:
1. Use `grep -n` or `read_file` to get exact content
2. Try `patch` again with exact match
3. If still failing, use `write_file` to replace the entire file (only for files < 200 lines)
4. For large files, use multiple small patches with very short old_string anchors (3-5 lines max)
5. **CRITICAL**: The `read_file` tool may display corrupted output with spurious line prefixes (e.g., `     1|     1|     1|` for triple-prefixed lines). This is a display artifact of the tool — the actual file on disk is clean. Always verify with `head -N filename` or `grep` via terminal before doing string replacements. If `patch` keeps failing on content you know exists, assume the tool's string matching is hitting invisible prefix artifacts — fall back to terminal `sed -i` for reliable edits.

## Audit Workflow with Parallel Subagents
For comprehensive audits, use `delegate_task` with 3 parallel tasks:
1. Client-side code analysis (all .c in 5_Mission/, cross-ref with layouts)
2. Server-side code analysis (Server mod + RPC flow tracing)
3. Layout-only analysis (all .layout files, verify against .c FindAnyWidget calls)

## Null-Guarded Dead Code Pattern
`if (m_SomethingNeverInit) m_SomethingNeverInit.DoThing();` — this looks intentional but is always a no-op. The field was declared, never FindAnyWidget'd, and the null-guard masks the bug.
- Audit: find all `private`/`protected` fields that are used in null-guarded calls but never assigned
- Fix: either initialize the field or remove the field + its dead usage entirely

## Common Enforce Script Pitfalls Discovered
- **Dead onClick handlers**: `void OnClick()` in a class that's not a `ScriptedWidgetEventHandler` or not registered via `WidgetEventHandler.GetInstance().RegisterOnButton()` will never fire
- **`FindWidget` vs `FindAnyWidget`**: `FindWidget` returns exact-match child, `FindAnyWidget` does recursive search — mixing them up causes silent nulls
- **`setpos` vs `SetPos`**: Enforce Script is case-sensitive. Using lowercase method names won't compile
- **VPPGroupRPCs enum gap**: `VPP_CLIENT_SETTINGS_SYNC = 80600` but corresponding server handler sends via different enum value — audit BOTH client registration AND server Send calls


## Server Config & Admin Systems


# DayZ Server Configuration System

## Trigger
Use when creating or extending a JSON-backed server configuration system in DayZ Enforce Script, or building a multi-tab admin settings panel.

## Pattern Overview

Three-layer architecture:
1. **Config classes** (3_Game) — serializable data models
2. **Server manager** (4_World) — loads/saves $profile JSON, applies settings
3. **Admin UI** (5_Mission) — tabbed panel reads/writes config, sends RPC

## Step 1: Define Config Classes (3_Game)

File path: `scripts/3_Game/VPPAdminServerSettings.c`

Pattern: nested classes with WriteToCtx() / ReadFromCtx() for RPC transport.

### Serialization Pattern
```c
class VPPAdminServerSettings {
    string m_FilePath;
    ref array<ref VPPGroupLevelConfig> GroupLevels;
    ref VPPChatConfig ChatSettings;
    ref VPPTerritoryConfig TerritorySettings;

    static VPPAdminServerSettings Load() {
        VPPAdminServerSettings settings = new VPPAdminServerSettings();
        settings = JsonFileLoader<VPPAdminServerSettings>.Load(settings.m_FilePath);
        if (!settings) { settings = new VPPAdminServerSettings(); }
        return settings;
    }

    void Save() {
        JsonFileLoader<VPPAdminServerSettings>.Save(m_FilePath, this);
    }

    void WriteToCtx(ScriptRPC rpc) {
        rpc.Write(EnableGroups);
        rpc.Write(MaxGroupSize);
        // For sub-arrays, write count then iterate
        rpc.Write(GroupLevels.Count());
        for (int i = 0; i < GroupLevels.Count(); i++) {
            rpc.Write(GroupLevels[i].Tier);
            rpc.Write(GroupLevels[i].TierName);
            rpc.Write(GroupLevels[i].MaxMembers);
        }
    }

    bool ReadFromCtx(ParamsReadContext ctx) {
        // Mirror WriteToCtx - same order
        if (!ctx.Read(EnableGroups)) return false;
        if (!ctx.Read(MaxGroupSize)) return false;
    }
}
```

### Per-Tier Config
```c
class VPPGroupLevelConfig {
    int Tier;
    string TierName;
    int MaxMembers;
    int UpgradeCost;
    int MaxSubgroups;
    bool OfflineSubgroup;
}
```

### Dynamic Tier Loading
```c
class VPPClanTiers {
    private static ref map<int, ref VPPClanTier> m_Tiers;

    static void Reload() {
        m_Tiers.Clear();
        VPPAdminServerSettings cfg = VPPAdminServerSettings.Load();
        if (cfg && cfg.GroupLevels && cfg.GroupLevels.Count() > 0) {
            for (int i = 0; i < cfg.GroupLevels.Count(); i++) {
                VPPGroupLevelConfig lvl = cfg.GroupLevels.Get(i);
                m_Tiers.Insert(lvl.Tier, new VPPClanTier(...));
            }
        } else {
            // Hardcoded fallback
            m_Tiers.Insert(1, new VPPClanTier(1, 10, 25000, "Base"));
        }
    }
}
```

## Step 2: Server-Side Save/Reload (4_World)

In the admin settings handler, reload dynamic resources after save:
```c
void OnAdminSetServerSettings(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    if (!IsAdmin(sender)) return;
    VPPAdminServerSettings newSettings = new VPPAdminServerSettings();
    if (newSettings.ReadFromCtx(ctx)) {
        m_ServerSettings = newSettings;
        m_ServerSettings.Save();
        // CRITICAL: reload derived data from config
        VPPClanTiers.Reload();
        // Broadcast to all clients
        array<PlayerIdentity> allIdentities = new array<PlayerIdentity>;
        GetGame().GetPlayerIndentities(allIdentities);
        foreach (PlayerIdentity id : allIdentities) {
            if (id) PushGlobalSettings(id);
        }
    }
}
```

## Step 3: Tabbed Admin UI (5_Mission)

### Layout Pattern
File: `GUI/Layouts/Admin/VPPGlobalAdminDashboard.layout`

Use tab bar buttons + show/hide content panels:
```
FrameWidgetClass GlobalAdminRoot {
  PanelWidgetClass tabBar {
    ButtonWidgetClass btnTabGlobal { position 0 0 size 0.13 1 ... }
    ButtonWidgetClass btnTabLevels { position 0.14 0 size 0.13 1 ... }
  }
  PanelWidgetClass panelGlobal { visible 1 size 1 1 ... }
  PanelWidgetClass panelLevels { visible 0 size 1 1 ... }
}
```

Key: panelX.visible controls which tab shows. Use relative positions (size 1 1 to fill parent).

### UI Code Pattern
```c
class VPPGlobalAdminUI extends ScriptedWidgetEventHandler {
    CheckBoxWidget chkEnableGroups;
    SliderWidget sldMaxGroupSize;

    void ShowTab(int tab) {
        layoutRoot.FindAnyWidget("panelGlobal").Show(tab == 0);
        layoutRoot.FindAnyWidget("panelLevels").Show(tab == 1);
    }

    void ApplyAndSaveSettings() {
        m_CurrentSettings.EnableGroups = chkEnableGroups.IsChecked();
        ScriptRPC rpc = new ScriptRPC();
        m_CurrentSettings.WriteToCtx(rpc);
        rpc.Send(null, VPPGroupRPCs.GROUP_ADMIN_SET_SERVER_SETTINGS, true, null);
    }
}
```

## Step 4: RPC Registration

Add new RPC IDs to GroupRPCs.c enum:
```
GROUP_ADMIN_GET_SERVER_SETTINGS = 80550,
GROUP_ADMIN_SET_SERVER_SETTINGS = 80551,
```

Register both directions in server/client managers.

## Pitfalls

- **Layout widget names MUST match code FindAnyWidget() calls exactly** - typo = silent null
- **WriteToCtx/ReadFromCtx field order must match exactly** - mismatch = corrupted data
- **visible 0 in layout for hidden tabs** - don't omit, defaults to visible 1
- **Reload derived data on save** - if tiers change, cached data (group limits, upgrade costs) must refresh
- **Sub-arrays in RPC: write count first, then iterate** - reader needs count before loop
- **File path uses $profile: prefix** - not absolute paths; DayZ resolves at runtime
- **JsonFileLoader requires m_FilePath on the class** - used as key for serialization
- **NEVER send full ServerSettings.json to non-admin clients** — security leak. On `OnSyncPlayersRequest` or after admin save, only send tier limits (level, maxMembers, maxMarkers) to non-admins. Full settings only to admins who request them.
- **VPPAdminServerSettings.Save() is VOID** — cannot use `if (Save())`. Use direct `JsonFileLoader<VPPAdminServerSettings>.JsonSaveFile()` call instead if you need to check success.
- **Broadcast tier limits separately from full settings** — Create a `PushTierLimitsOnly(recipient)` method that writes only level/maxMembers/maxMarkers via a lightweight RPC. Non-admins don't need chat settings, feature flags, or tier names.
- **VPPAdminTools GetPermissionManager() returns NULL** — Admin permission checks via VPPAdminTools are unreliable. Always add fallback: JSON-config-based admin list (see pattern below).
- **NEVER hardcode Steam IDs** — Use a JSON config file loaded at runtime. Create a `VPPAdminList` singleton class that reads `$profile:VPPMap_Groups/AdminList.json`. This enables hot-reload and operator control without recompilation.
- **`GetGame().GetAdmins()` does NOT exist in DayZ Enforce Script** — This call causes "Undefined function" compile error. Use JSON-config-based admin list + VPPAdminTools only.
- **super.OnRPC() consumes ctx data** — If your `OnRPC` override calls `super.OnRPC()` BEFORE handling your custom RPCs, the `ParamsReadContext ctx` may be consumed/corrupted. Fix: check if rpc_type is yours FIRST, handle it, `return` before calling super. Example:
  ```c
  override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
      if (rpc_type >= GROUP_RPC_MIN && rpc_type <= GROUP_RPC_MAX) {
          VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx);
          return;  // DO NOT call super for custom RPCs
      }
      super.OnRPC(sender, target, rpc_type, ctx);
  }
  ```
- **VPPClanTierDef does NOT exist** — The correct type is `VPPClanTier` (defined in GroupModels.c). Properties: `Tier` (not `Level`), `MaxMembers`, `UpgradeCost`, `TierName`. No `MaxMarkers` property on VPPClanTier — check your config class for actual fields.

## JSON-Based Admin List Pattern

When you need admin checks without hardcoding Steam IDs, use this pattern:

### File: `scripts/4_World/VPPAdminList.c`

```c
class VPPAdminList {
    private static ref VPPAdminList m_Instance;
    private ref array<string> m_AdminSteamIds;
    private string m_ConfigPath = "$profile:VPPMap_Groups/AdminList.json";

    static VPPAdminList Get() {
        if (!m_Instance) {
            m_Instance = new VPPAdminList();
            m_Instance.Load();
        }
        return m_Instance;
    }

    void Load() {
        m_AdminSteamIds.Clear();
        if (!FileExist(m_ConfigPath)) {
            CreateDefault();
            return;
        }
        // Read file, parse JSON array manually: ["id1", "id2"]
        // Trim brackets, split by comma, strip quotes, validate 17-char Steam IDs
    }

    bool IsAdmin(string steamId) {
        for (int i = 0; i < m_AdminSteamIds.Count(); i++) {
            if (m_AdminSteamIds.Get(i) == steamId) return true;
        }
        return false;
    }

    void AddAdmin(string steamId) { ... }    // Insert + Save()
    void RemoveAdmin(string steamId) { ... } // Remove + Save()
    void Save() { ... }                      // Write JSON array back
}
```

### Config file: `$profile:VPPMap_Groups/AdminList.json`
```json
[
    "76561198000000000",
    "76561198123456789"
]
```

### Usage in IsAdmin() methods
```c
bool IsAdmin(string steamId) {
    // Priority 1: VPPAdminTools integration
    if (GetPermissionManager()) {
        return GetPermissionManager().IsSuperAdmin(steamId);
    }
    // Priority 2: JSON-config-based admin list
    return VPPAdminList.Get().IsAdmin(steamId);
}
```

### Pitfalls
- JSON parsing: DayZ Enforce Script has no built-in JSON array parser — parse manually (trim brackets, split comma, strip quotes)
- File path uses `$profile:` prefix — resolves to server profile directory at runtime
- Singleton pattern needed — Load() should only read once unless explicit reload
- Validate Steam ID length (17 chars) during parse to reject malformed entries

## Verification

1. Brace balance check: python3 -c "f=open('File.c'); c=f.read(); print('OK' if c.count('{')==c.count('}') else 'MISMATCH')"
2. Widget name audit: grep all FindAnyWidget("X") calls and verify each exists in the .layout file
3. RPC round-trip: verify WriteToCtx and ReadFromCtx have identical field order


## RPC Handler Patterns


## Routing Architecture

VanillaPlusPlus.OnRPC intercepts GROUP_RPC_MIN to GROUP_RPC_MAX and routes them through VPPRPCManager (not the standard GetRPCManager).

This means:
- **Do NOT** use `GetRPCManager().AddRPC()` for group RPCs
- **DO** use `VPPRPCManager.Get().RegisterRPC()` with ScriptCaller

## Registration Pattern (in MissionServer constructor)

```c
// In missionServer.c
modded class MissionServer {
    void MissionServer() {
        VPPRPCManager.Get().RegisterRPC(VPPGroupRPCs.GROUP_CREATE, ScriptCaller.Create(this.HandleGroupCreate));
        VPPRPCManager.Get().RegisterRPC(VPPGroupRPCs.GROUP_DISBAND, ScriptCaller.Create(this.HandleGroupDisband));
        // ... etc for all GROUP_* RPCs
    }

    void HandleGroupCreate(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
        if (!sender) return;
        string tag, clanName;
        if (!ctx.Read(tag)) { SendNotification(sender, "Error: Invalid tag"); return; }
        if (!ctx.Read(clanName)) { SendNotification(sender, "Error: Invalid name"); return; }
        string steamId = sender.GetPlainId();
        // ... server-side validation and group creation
    }
}
```

## Sending Notifications Back to Client

```c
void SendNotification(PlayerIdentity player, string message) {
    ScriptRPC rpc = new ScriptRPC();
    rpc.Write(message);
    rpc.Send(player, VPPGroupRPCs.GROUP_NOTIFICATION, true, player);
}
```

## Server-Side State Management

```c
private ref map<string, ref VPPEnhancedGroup> m_ServerGroups = new map<string, ref VPPEnhancedGroup>();
private ref map<string, string> m_PlayerToGroup = new map<string, string>(); // steamId -> clanTag
```

## VPPEnhancedGroup Constructor Gotcha

The constructor `VPPEnhancedGroup(tag, name, leaderId)` already calls `AddMember(leaderId, "Leader", "Leader")` internally. Do NOT manually insert the leader again after construction.

## Validation Checklist for GROUP_CREATE

1. Tag length 3-5 chars, alphanumeric only
2. Clan name 1-32 chars
3. Player not already in a group (`m_PlayerToGroup`)
4. Tag not taken (`m_ServerGroups`)
5. Name not taken (iterate `m_ServerGroups` with for loop — NOT foreach)
6. Use `sender.GetPlainId()` for Steam ID
7. Use `sender.GetName()` for display name

## CRITICAL: super.OnRPC() consumes ctx data

The community framework's `DayZGame.OnRPC()` consumes ParamsReadContext data BEFORE custom handlers can read it. If you call `super.OnRPC()` then route to VPPRPCManager, ctx will be corrupted/empty.

**WRONG** — ctx consumed by super:
```c
override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    super.OnRPC(sender, target, rpc_type, ctx);  // <-- consumes ctx!
    if (rpc_type >= GROUP_RPC_MIN && rpc_type <= GROUP_RPC_MAX) {
        VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx);  // <-- ctx already empty
    }
}
```

**CORRECT** — route VPP RPCs directly, skip super:
```c
override void OnRPC(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    if (rpc_type >= GROUP_RPC_MIN && rpc_type <= GROUP_RPC_MAX) {
        VPPRPCManager.Get().OnRPC(sender, target, rpc_type, ctx);
        return;  // <-- don't call super for VPP RPCs
    }
    super.OnRPC(sender, target, rpc_type, ctx);  // <-- only for non-VPP RPCs
}
```

Symptom: `String CORRUPTED` error on ctx.Read() calls in handlers.


## UI Rendering Patterns

# DayZ UI Rendering Patterns

## Core Rule
DayZ has TWO valid UI rendering patterns. Using the wrong one makes UIs invisible.

## Pattern 1: UIScriptedMenu + EnterScriptedMenu
**Use for:** Standalone overlay HUD widgets (compass bars, info panels, custom menus).

```c
// constants.c — menu ID
static const int VPP_MENU_COMPASS = 3815265486;

// Widget class
class VPPCompassWidget: UIScriptedMenu {
    Widget layoutRoot;

    override Widget Init() {
        layoutRoot = GetGame().GetWorkspace().CreateWidgets("VanillaPPMap/GUI/Layouts/VPPCompassWidget.layout", null);
        return layoutRoot;
    }
    
    override void OnShow() { super.OnShow(); }
    override void OnHide() { super.OnHide(); }
    
    override void OnUpdate(float timeslice) {
        super.OnUpdate(timeslice);
        // Update logic
    }
};

// missionGameplay.c — create/destroy lifecycle
private ref VPPCompassWidget m_CompassWidget;

void InitializeHUDWidgets() {
    m_CompassWidget = VPPCompassWidget.Cast(GetGame().GetUIManager().EnterScriptedMenu(VPP_MENU_COMPASS, null));
    if (m_CompassWidget) {
        GetGame().GetUIManager().ShowScriptedMenu(m_CompassWidget, null);
    }
}

void ~MissionGameplay() {
    if (m_CompassWidget) {
        GetGame().GetUIManager().HideScriptedMenu(m_CompassWidget);
        m_CompassWidget.Destroy();
    }
}
```

**Pitfall:** Plain `Widget` + `CreateWidgets` without UIScriptedMenu = INVISIBLE.

## Pattern 2: Modded Vanilla Classes (LBMaster Pattern)
**Use for:** Replacing/extending existing vanilla UI systems (Chat, Player List, Inventory).

```c
// Chat.c — modded class replaces vanilla Chat
modded class Chat {
    override void Init(Widget root_widget) {
        Destroy();
        // Use custom layout instead of vanilla
        vpp_chat_root = GetGame().GetWorkspace().CreateWidgets("MyMod/GUI/Layouts/Chat/ChatHistory.layout", root_widget);
        // ... setup scroll widget, create ChatLine instances
    }

    override void AddInternal(ChatMessageEventParams params) {
        // Intercept vanilla messages, route to custom display
        AddVPPChatFiltered(params.param1, "", params.param2, params.param3, 0, 0);
    }

    void AddVPPChatFiltered(int channelType, string prefix, string senderName, string message, int customColor, int roleColor) {
        // Custom display logic
    }
};

// ChatLine.c — modded class replaces vanilla ChatLine
modded class ChatLine {
    TextWidget m_GroupTag;

    void ChatLine(Widget root_widget) {
        if (m_RootWidget) m_RootWidget.Unlink();
        m_RootWidget = GetGame().GetWorkspace().CreateWidgets("MyMod/GUI/Layouts/Chat/ChatLine.layout", root_widget);
        m_NameWidget = TextWidget.Cast(m_RootWidget.FindAnyWidget("ChatSenderTagWidget"));
        m_TextWidget = TextWidget.Cast(m_RootWidget.FindAnyWidget("ChatTextWidget"));
        m_GroupTag = TextWidget.Cast(m_RootWidget.FindAnyWidget("ChatSenderGroupTagWidget"));
    }

    void SetVPP(int channel, string prefix, string name, string text, int tagColor, int roleColor) {
        m_RootWidget.Show(true);
        // Set group tag, sender name, message with channel-based coloring
    }
};

// ChatInputMenu.c — minimal intercept of vanilla input
modded class ChatInputMenu {
    override Widget Init() {
        Widget root = super.Init();
        // Hide vanilla channel prompt
        Widget prompt = root.FindAnyWidget("ChannelText");
        if (prompt) prompt.Show(false);
        return root;
    }
};
```

**Key:** `modded class` + `override` of vanilla methods. The vanilla game engine creates the object; you intercept behavior.

## Decision Matrix

| What to display | Use Pattern | Why |
|----------------|-------------|-----|
| Custom HUD overlay (compass, info panel) | 1 - UIScriptedMenu | No vanilla equivalent to replace |
| Chat display | 2 - Modded vanilla classes | Vanilla Chat system already manages lifecycle |
| Chat input | 2 - Modded vanilla classes | Vanilla ChatInputMenu already handles focus/key events |
| Map menu with custom controls | 1 - UIScriptedMenu | Custom fullscreen menu, no vanilla equivalent |
| 3D markers / world overlays | 1 - UIScriptedMenu | Standalone overlay |
| Player list extending vanilla | 2 - Modded vanilla classes | If overriding vanilla PlayerList |

## Layout Standards (LBMaster Style)

### Chat Line Layout
```
GridSpacerWidgetClass ChatLineRoot {
  Columns 3
  font "gui/fonts/sdf_MetronBook72"
  "outline size" 2
  "outline color" 0 0 0 1
  "shadow size" 10
  "shadow color" 0 0 0 1
  "shadow offset" 1 1
  "bold text" 1
  "exact text size" 14
  {
    TextWidgetClass ChatSenderGroupTagWidget { ... }  // [TAG]
    TextWidgetClass ChatSenderTagWidget { ... }       // Name:
    TextWidgetClass ChatTextWidget { ... }            // Message
  }
}
```

### Chat History Layout
```
FrameWidgetClass VPPChatHistoryRoot {
  ignorepointer 1
  position 0 60
  valign bottom_ref
  {
    ScrollWidgetClass RootPosition {
      ignorepointer 1
      valign bottom_ref
      "Scrollbar V" 1
      {
        WrapSpacerWidgetClass {
          valign bottom_ref
          "Size To Content H" 1
          "Size To Content V" 1
          {
            PanelWidgetClass ChatFrameWidget { ... }
          }
        }
      }
    }
  }
}
```

### Chat Input Layout
```
FrameWidgetClass VPPChatInputRoot {
  halign center_ref
  valign center_ref
  {
    PanelWidgetClass InputEditBoxWidget0 {
      color 0.1569 0.1569 0.1569 0.7843
      style rover_sim_colorable
      {
        EditBoxWidgetClass InputEditBoxWidget {
          font "gui/fonts/sdf_MetronLight24"
        }
      }
    }
  }
}
```

## Porting LBMaster Reference Code — Critical Rule

LBMaster's reference code calls methods **LBMaster itself adds** to modded classes.
When porting, these methods **don't exist** in your mod. You must find vanilla equivalents.

### Common LBMaster-only methods
| LBMaster Call | Vanilla Equivalent | Notes |
|---|---|---|
| `mission.SendChatMessage(text)` | `GetGame().ChatPlayer(text)` | Vanilla API, sends globally |
| `mission.GetCurrentChannel()` | N/A — hardcode "Global" or add own channel tracking | No vanilla public method |
| `ChannelCfg` (channel config class) | N/A — keep as internal mod state | LBMaster-only type |
| `LBMarkerVisibilityManager.Get.GetChatSize()` | Read from `VPPClientSettings.m_ChatSize` | Route through your settings system |
| `LBMarkerVisibilityManager.Get.GetChatBorderVisibility()` | Read from your own settings class | Same pattern |

### Pattern
```c
// ❌ BROKEN — LBMaster adds SendChatMessage to their modded MissionGameplay
mission.SendChatMessage(text);

// ✅ FIX — Use vanilla API or route through your own RPC
GetGame().ChatPlayer(text);  // vanilla global send

// ✅ FIX — Or route through VPP RPC for group/global channels
ScriptRPC rpc = new ScriptRPC();
rpc.Write(text);
rpc.Send(null, VPPGroupRPCs.CHAT_SEND_GLOBAL, true, null);
```

**Rule:** Before using any method from LBMaster reference, grep for it in your mod's codebase.
If it only exists in LBmaster, it's a mod-specific extension — find the vanilla equivalent.

## Chat Line Layout (Correct — LBMaster-Exact)

LBMaster uses a **4-column** GridSpacer (not 3). Each column has `size 0.2 1` except message at `size 0.8 1`.

```
GridSpacerWidgetClass ChatItemWidget {
  size 1104 25
  Columns 4
  Rows 1
  {
    TextWidgetClass ChatItemSenderTagWidget { size 0.2 1 ... }     // Clan tag [ABC]
    TextWidgetClass ChatItemSenderGroupTagWidget { size 0.2 1 ... } // Role/group prefix
    TextWidgetClass ChatItemSenderWidget { size 0.2 1 ... }         // Sender name
    TextWidgetClass ChatItemTextWidget { size 0.8 1 ... }           // Message text
  }
}
```

Widget names in layout **must match** `FindAnyWidget()` calls in ChatLine.c exactly:
- `ChatItemSenderTagWidget` → `m_NameTag`
- `ChatItemSenderGroupTagWidget` → `m_GroupTag`
- `ChatItemSenderWidget` → `m_NameWidget`
- `ChatItemTextWidget` → `m_TextWidget`

## Chat Settings Wiring

Wire chat font size + fade delay through VPPClientSettings:

```c
// ChatLine.c — configurable text size + fade
int m_TextSize = 15;
int m_FadeDelay = 10;

void ApplySettings(int textSize, int fadeDelay) {
    m_TextSize = textSize;
    m_FadeDelay = fadeDelay;
    m_NameWidget.SetTextExactSize(textSize);
    m_TextWidget.SetTextExactSize(textSize);
    m_GroupTag.SetTextExactSize(textSize);
    if (m_NameTag) m_NameTag.SetTextExactSize(textSize);
}

// Chat.c — apply to all lines
void ApplyChatSettings() {
    VPPClientSettings settings = VPPClientManager.GetInstance().GetClientSettings();
    if (!settings) return;
    int size = settings.m_ChatSize;
    foreach (ChatLine line : m_Lines) {
        line.ApplySettings(size, settings.m_ChatFadeDelay);
    }
}

// ClientManager.c — call after settings sync
void ApplyClientSettings() {
    // ... existing apply logic ...
    MissionGameplay mission = MissionGameplay.Cast(GetGame().GetMission());
    if (mission && mission.m_Chat) {
        mission.m_Chat.ApplyChatSettings();
    }
}
```

Config panel slider → `m_ChatSize`/`m_ChatFadeDelay` → `ApplyClientSettings()` → `ApplyChatSettings()` → live update.

## Enforce Script Gotchas
- **Ternary operator** (`? :`) NOT supported — use `if/else`
- **Bit shift operators** (`>>`, `<<`) NOT supported — parse as string or use `VectorMath` instead
- **`int.ToHex()`** NOT a method — write your own helper using string substring
- **`SetColor()`** takes ARGB int, NOT a color vector — never return `Vector(r,g,b)` for `SetColor()`
- **`ARGBToColor()`** does NOT exist — `ARGB()` returns int directly, use it or store/load components manually
- **`SetKeyboardBusy(true)`** breaks chat input permanently — never use
- **`foreach` variable names** must be unique within the same scope — rename duplicates
- **`switch` on enums** can fail — prefer `if/else`
- **Do NOT create BOTH** a UIScriptedMenu AND modded vanilla classes for the same system — pick one pattern
- **LBMaster calls its own modded methods** — never assume LBMaster reference code works as-is in your mod

## Common Mistake
Creating a standalone UIScriptedMenu for chat AND modding vanilla Chat class = two competing systems that fight each other. Pick ONE pattern per UI system.

## Critical Lesson: Chat System — When Pattern 2 Fails

Pattern 2 (modded vanilla classes) for Chat **requires** LBMaster's full infrastructure:
- `LBLayoutManager` — manages layout creation lifecycle
- `LBTextLengthCalculator` — measures text for auto-scroll
- `LBMarkerVisibilityManager` — drives settings (chat size, fade, border)
- Their modded `MissionGameplay` — provides `SendChatMessage()`, `GetCurrentChannel()`, channel tracking
- Custom scroll/cache system in Chat.c

**If you don't have these**, the modded Chat/ChatLine classes will compile but **render nothing** or show garbled text. The vanilla Chat system depends on these supporting classes to actually display content.

### Rule of Thumb for Chat

| Situation | Pattern | Why |
|-----------|---------|-----|
| Full LBMaster infrastructure available | 2 — Modded vanilla classes | Can override Chat/ChatLine behavior with full chain |
| Standalone mod, no LBMaster deps | 1 — UIScriptedMenu for chat | Works independently, no missing-function crashes |
| Porting from LBMaster reference | Always use 1 unless you also port the utility classes | Missing one class = broken chain |

### The UIScriptedMenu Chat Pattern

When you DON'T have LBMaster infrastructure, use UIScriptedMenu for chat:

```c
// VPPChatWidget.c — standalone chat as UIScriptedMenu
class VPPChatWidget: UIScriptedMenu {
    private MultilineTextWidget m_ChatDisplay;  // NOT TextWidget — use multiline for wrapping
    private TextWidget m_ChannelLabel;
    private ref array<string> m_Lines;  // Ring buffer
    private int m_WriteIdx;
    private int m_LineCount;
    private const int MAX_DISPLAY_LINES = 10;

    override Widget Init() {
        layoutRoot = GetGame().GetWorkspace().CreateWidgets("VanillaPPMap/GUI/Layouts/VPPChatWidget.layout");
        m_ChatDisplay = MultilineTextWidget.Cast(layoutRoot.FindAnyWidget("ChatDisplay"));
        m_ChannelLabel = TextWidget.Cast(layoutRoot.FindAnyWidget("ChannelLabel"));
        return layoutRoot;
    }

    void ShowInput(bool state) {
        // Visual feedback when chat input is active
        if (state) layoutRoot.SetColor(ARGB(150, 100, 0, 0));
        else layoutRoot.SetColor(ARGB(0, 0, 0, 0));
    }

    void AddChatMessage(string senderId, string senderName, string message,
                        int roleColor, string clanTag, int tagColor, bool isAdmin, bool isVIP) {
        // Build HTML-formatted line with clan tag + name + message
        string line = "";
        if (clanTag != "")
            line += "<color=" + IntToHexColor(tagColor) + ">[" + clanTag + "]</color> ";
        int nameColor = roleColor;
        if (isAdmin) nameColor = ARGB(255, 255, 100, 100);
        else if (isVIP) nameColor = ARGB(255, 255, 215, 0);
        line += "<color=" + IntToHexColor(nameColor) + ">" + senderName + "</color>: " + message;

        // Ring buffer — no memory leak
        m_Lines.Set(m_WriteIdx, line);
        m_WriteIdx = (m_WriteIdx + 1) % MAX_DISPLAY_LINES;
        if (m_LineCount < MAX_DISPLAY_LINES) m_LineCount++;
        RefreshDisplay();
    }

    void RefreshDisplay() {
        string displayText = "";
        int startIdx = m_WriteIdx - m_LineCount;
        if (startIdx < 0) startIdx += MAX_DISPLAY_LINES;
        for (int i = 0; i < m_LineCount; i++) {
            displayText += m_Lines.Get((startIdx + i) % MAX_DISPLAY_LINES) + "\n";
        }
        m_ChatDisplay.SetText(displayText);
    }

    // Chat history for up/down arrow recall
    string HistoryUp() { ... }
    string HistoryDown() { ... }

    // Color conversion helper (Enforce has no int.ToHex())
    string IntToHexColor(int color) {
        return "#" + IntToHex((color >> 16) & 0xFF) + IntToHex((color >> 8) & 0xFF) + IntToHex(color & 0xFF);
    }
    string IntToHex(int value) {
        const string hexChars = "0123456789ABCDEF";
        return hexChars.Substring((value >> 4) & 0x0F, 1) + hexChars.Substring(value & 0x0F, 1);
    }
};
```

```c
// ChatInputMenu.c — minimal modded class, just route to VPPChatWidget
modded class ChatInputMenu {
    override Widget Init() {
        Widget root = super.Init();
        Widget prompt = root.FindAnyWidget("ChannelText");
        if (prompt) prompt.Show(false);  // Hide vanilla channel prompt
        return root;
    }
    override bool OnChange(Widget w, int x, int y, bool finished) {
        if (!finished) return false;
        EditBoxWidget eb = EditBoxWidget.Cast(w);
        if (eb) {
            string text = eb.GetText();
            if (text != "") {
                VPPChatWidget chat = VPPClientManager.GetInstance().GetChatWidget();
                if (chat) chat.SendChat(text);
            }
            eb.SetText("");
        }
        Close();
        return true;
    }
};
```

```c
// missionGameplay.c — create chat widget
VPPChatWidget chatWidget = VPPChatWidget.Cast(GetGame().GetUIManager().EnterScriptedMenu(VPP_MENU_CHAT, null));
if (chatWidget) {
    GetGame().GetUIManager().ShowScriptedMenu(chatWidget, null);
    VPPClientManager.GetInstance().SetChatWidget(chatWidget);
}
```

**Key differences from modded-class approach:**
- No `modded class Chat` or `modded class ChatLine` — uses `UIScriptedMenu` instead
- No `mission.m_Chat` or `mission.SendChatMessage` — routes directly to widget
- No scroll widget or ChatLine instances — ring buffer + MultilineTextWidget
- No layout chain (Chat → ChatLine → ChatLine → ...) — single layout with tabs
- ChatInputMenu is the ONLY modded class (for vanilla input interception)

---

## LBMaster Admin Panel Widget Structure

When replicating LBmaster admin panels, these are the exact patterns from their source.

### Admin Menu Shell Layout
```
PanelWidgetClass rootFrame {
  color 0.506 0.506 0.506 0.392          // dark gray, ~100 alpha
  style rover_sim_colorable               // solid color fill
  {
    PanelWidgetClass pageWidgets {        // content area
      ignorepointer 1
      scriptclass "LBGapHandler"          // manages spacing
      gapHorizontal 10
      gapVertical 85                      // 85px from top for tabs
    }
    WrapSpacerWidgetClass buttonWidgets {  // tab buttons row
      scriptclass "LBGapHandler"
      gapHorizontal 165                   // 165px between tabs
    }
    ButtonWidgetClass btn_close {          // close button
      halign right_ref
      size 150 25
      style Empty                         // no bg on button itself
      {
        PanelWidgetClass close_panel {
          color 1 0.196 0.196 1           // red ~255/50/50
          style LB_Clean_outline           // 1px pixel border
          {
            TextWidgetClass close_text {
              text "#close"
              font "gui/fonts/Metron14"
              "text halign" center
              "text valign" center
            }
          }
        }
      }
    }
    ButtonWidgetClass btn_save {
      halign right_ref
      valign bottom_ref
      size 200 25
      style Empty
      {
        PanelWidgetClass save_panel {
          color 0 1 0 1                    // green
          style LB_Clean_outline
          {
            TextWidgetClass save_text { ... }
          }
        }
      }
    }
  }
}
```

### Button Pattern (LBmaster)
All LBmaster buttons use this structure:
1. `ButtonWidgetClass` with `style Empty` (transparent, interactive)
2. Child `PanelWidgetClass` with `style LB_Clean_outline` (1px border, colored fill)
3. Child `TextWidgetClass` inside panel (label)
4. `ignorepointer 1` on panel/text so clicks pass through to button

**Color reference (LBmaster):**
| Purpose | RGBA | Style |
|---------|------|-------|
| Menu background | 0.506 0.506 0.506 0.392 | rover_sim_colorable |
| Close/Reset button | 1 0.196 0.196 1 | LB_Clean_outline |
| Save button | 0 1 0 1 | LB_Clean_outline |
| Inactive tab | 0.12 0.12 0.12 0.9 | blank |
| Tab selected bar | 0 1 0 1 | rover_sim_colorable |

### Tab Button Pattern
```
ButtonWidgetClass btn_tab {
  size 120 28
  style Empty
  {
    PanelWidgetClass tab_bg {
      ignorepointer 1
      color 0.12 0.12 0.12 0.9
      style blank
      {
        PanelWidgetClass tab_border {
          color 0.4 0.4 0.4 0.6
          style Outline
        }
        TextWidgetClass tab_text {
          font "gui/fonts/Metron14"
          "text halign" center
          "text valign" center
          color 0.8 0.8 0.8 1
        }
        PanelWidgetClass panel_selected {
          visible 0
          position 0 0.9
          size 1 0.1
          color 0 1 0 1
          style rover_sim_colorable
        }
      }
    }
  }
}
```

### Chat Container Structure (LBmaster exact)
```
FrameWidgetClass rootFrame {
  ignorepointer 1
  position 0 60                           // 60px from bottom
  valign bottom_ref
  {
    ScrollWidgetClass {
      ignorepointer 1
      valign bottom_ref
      style blank
      "Scrollbar V" 1
      "Scrollbar V Left" 1
      {
        WrapSpacerWidgetClass {
          valign bottom_ref
          "Size To Content H" 1
          "Size To Content V" 1
          {
            PanelWidgetClass ChatFrameWidget {
              valign bottom_ref             // messages stack upward
            }
          }
        }
      }
    }
  }
}
```

**Chat message creation:** Each message is `CreateWidgets("ChatItem.layout", ChatFrameWidget)` — no MultilineTextWidget. Messages are individual GridSpacerWidgets appended to the WrapSpacer. Cap at MAX_ITEMS (~30) and remove oldest via `Unlink()` to prevent memory leak.

### Chat Item Layout (LBmaster exact)
```
GridSpacerWidgetClass ChatItemWidget {
  size 1104 25                            // exact pixel size
  Columns 4
  Rows 1
  style Empty
  Padding 0
  Margin 0
  "Size To Content H" 1
  {
    TextWidgetClass ChatItemSenderTagWidget {          // [CLAN]
      size 0.2 1
      font "gui/fonts/sdf_MetronBook72"
      "outline size" 2
      "outline color" 0 0 0 1
      "shadow size" 10
      "shadow color" 0 0 0 1
      "shadow offset" 1 1
      "bold text" 1
      "exact text" 1
      "exact text size" 15
      "size to text h" 1
      "size to text v" 0
      "text valign" center
    }
    TextWidgetClass ChatItemSenderGroupTagWidget { ... }  // role prefix
    TextWidgetClass ChatItemSenderWidget { ... }          // name:
    TextWidgetClass ChatItemTextWidget {                  // message
      size 0.8 1                                          // wider
      hexactpos 0                                         // NOT exact pos
      ...same font/outline/shadow...
    }
  }
}
```

## FPS Optimization for DayZ UI

DayZ renders UI every frame. With many widgets updating, this kills FPS.

### Update Throttling Pattern
```c
// Only update expensive operations every N frames
private int m_FrameCounter;

override void OnUpdate(float timeslice) {
    super.OnUpdate(timeslice);
    m_FrameCounter++;
    if (m_FrameCounter % 3 == 0) {
        UpdateMarkers();           // heavy: interpolate positions, check pool
    }
    if (m_FrameCounter % 10 == 0) {
        UpdateInfoPanel();         // light: text/textures
    }
}
```

### Chat Append-Only Pattern
Don't rebuild the entire chat each message. Instead:
1. Create one `GridSpacerWidget` per message via `CreateWidgets("ChatItem.layout", container)`
2. Cap at MAX_ITEMS (30-50)
3. Remove oldest: `m_AllItems.Get(0).Unlink()` then `Remove(0)`
4. This has O(1) append cost and prevents memory leak

### DateTime Per-Frame Cost
`GetGame().GetDate()`, `GetWorld().GetTime()`, `GetHourMinuteTotal()` are expensive — cache or call only every N frames.

### Chat Message Fade Pattern (UIScriptedMenu)

When chat is a UIScriptedMenu (not modded Chat), implement fade manually:

```c
class VPPChatWidget: UIScriptedMenu {
    private ref array<Widget> m_ChatItems = new array<Widget>;
    private ref array<int> m_ItemTimestamps = new array<int>;  // when each was added (ms)

    const int FADE_TIMEOUT_MS = 12000;   // start fading after 12s
    const int FADE_DURATION_MS = 3000;   // 3-second fade
    const int REMOVE_AFTER_MS = 18000;   // remove after 18s total

    void UpdateFade() {
        int now = GetGame().GetTime();
        for (int i = m_ChatItems.Count() - 1; i >= 0; i--) {
            int elapsed = now - m_ItemTimestamps.Get(i);
            if (elapsed > REMOVE_AFTER_MS) {
                // Remove old message
                m_ChatItems.Get(i).Unlink();
                m_ChatItems.Remove(i);
                m_ItemTimestamps.Remove(i);
            } else if (elapsed > FADE_TIMEOUT_MS) {
                // Fade out
                float fadeProgress = (elapsed - FADE_TIMEOUT_MS) / (float)FADE_DURATION_MS;
                if (fadeProgress > 1.0) fadeProgress = 1.0;
                int alpha = (int)(255.0 * (1.0 - fadeProgress));
                m_ChatItems.Get(i).SetAlpha(alpha);
            }
        }
    }

    void ResetFade() {
        // Call when chat opens — reset all to full opacity
        for (int i = 0; i < m_ChatItems.Count(); i++) {
            m_ChatItems.Get(i).SetAlpha(255);
        }
    }

    void AddChatMessage(...) {
        // ... create widget via CreateWidgets("ChatItem.layout", container) ...
        m_ChatItems.Insert(newLine);
        m_ItemTimestamps.Insert(GetGame().GetTime());
    }
};

// In missionGameplay.c OnUpdate:
if (chatWidget) {
    chatWidget.UpdateFade();  // lightweight — only touches alpha values
}
```

### Common Enforce Script Widget Names
- `LB_Clean_outline` — LBmaster custom: pixel border + solid fill (defined in lbstyles.styles)
- `rover_sim_colorable` — built-in DayZ: solid color fill (no border)
- `blank` — built-in: transparent/no visual
- `Empty` — built-in: no visual at all
- `LBGapHandler` — LBmaster scriptclass: manages spacing between children
- `LBMenuPopulator` — LBmaster scriptclass: populates menu pages

## Client Settings Panel Layout (LBmaster Reference)

Client-facing settings use a **2x2 grid of bordered panels** with sliders, checkboxes, and edit boxes. This is DIFFERENT from the admin menu shell (which uses tabs).

### Root Structure
```xml
PanelWidgetClass ClientSettingsRoot {
  visible 1
  position 0 0
  size 1 1
  halign center_ref
  valign center_ref
  hexactpos 1    vexactpos 1    hexactsize 0   vexactsize 0
  color 0.506 0.506 0.506 0.392    // LBmaster background
  style rover_sim_colorable
  {
    // Header text
    TextWidgetClass HeaderText {
      position 0 5    size 1 25    halign center_ref
      font "gui/fonts/sdf_MetronBook72"    color 1 1 1 1
      "text halign" center    "text valign" center
    }

    // Close button (top-right, red)
    ButtonWidgetClass btnClose {
      position 5 5    size 150 25    halign right_ref
      hexactpos 1    vexactpos 1    hexactsize 1    vexactsize 1
      style Empty
      { PanelWidgetClass { color 1 0.196 0.196 1; style LB_Clean_outline } }
    }

    // Save button (bottom-right, green)
    ButtonWidgetClass btnSaveSettings {
      position 5 5    size 200 25    halign right_ref    valign bottom_ref
      hexactpos 1    vexactpos 1    hexactsize 1    vexactsize 1
      style Empty
      { PanelWidgetClass { color 0 1 0 1; style LB_Clean_outline } }
    }
  }
}
```

### Panel Layout (2x2 Grid)
Each panel uses **exact pixel positioning**:
```xml
PanelWidgetClass somePanel {
  ignorepointer 1
  position X Y      // grid position
  size 480 260      // fixed panel size
  hexactpos 1    vexactpos 1    hexactsize 1    vexactsize 1
  style LB_Clean_outline          // 1px border
  { ... }
}
```

**Grid positions:**
| Slot | Position | Size |
|------|----------|------|
| Top-left | `10 40` | `480 260` |
| Top-right | `500 40` | `480 260` |
| Bottom-left | `10 310` | `480 260` |
| Bottom-right | `500 310` | `480 260` |

### Panel Internal Layout
```xml
// Section header — centered, top of panel
TextWidgetClass lblSection {
  position 0 5    size 480 25    hexactpos 1    vexactpos 1    hexactsize 1    vexactsize 1
  font "gui/fonts/sdf_MetronBook72"
  color 1 1 1 1
  "text halign" center
}

// Checkbox — left-aligned below header
CheckBoxWidgetClass chkOption {
  position 10 35    size 460 20    hexactpos 1    vexactpos 1    hexactsize 1    vexactsize 1
}

// Label + Slider — right-aligned label, full-width slider
TextWidgetClass TextWidget_SomeLabel {
  position 10 70    size 340 20    hexactpos 1    vexactpos 1    hexactsize 1    vexactsize 1
  font "gui/fonts/sdf_MetronBook72"    color 0.8 0.8 0.8 1
  "text halign" right
}

SliderWidgetClass sldSomething {
  color 0 1 0 1                      // colored fill (R G B A)
  position 10 95    size 340 20      // below label
  hexactpos 1    vexactpos 1    hexactsize 1    vexactsize 1
  maximum 255    current 100
  "fill in" 1                        // fill from left
}

// Edit box — next to slider for numeric input
EditBoxWidgetClass editSomething {
  position 360 95    size 110 20     // right of slider
  hexactpos 1    vexactpos 1    hexactsize 1    vexactsize 1
}
```

### Critical: Exact Position Flags

**ALL** widgets in client settings panels MUST have these flags:
```
hexactpos 1    vexactpos 1    hexactsize 1    vexactsize 1
```

Without them, the layout engine interprets positions as relative (0.0-1.0) and the UI collapses into a pile. This is the #1 cause of broken layouts — forgetting these flags on even ONE widget causes overlapping text and misaligned elements.

### Font Rule
Client settings use `gui/fonts/sdf_MetronBook72` for ALL text (headers, labels, values). Admin menu shell uses `gui/fonts/Metron14`. Do NOT mix.

### Color Palette (LBmaster Reference)
| Element | RGBA | Notes |
|---------|------|-------|
| Background | `0.506 0.506 0.506 0.392` | Semi-transparent dark gray |
| Close button | `1 0.196 0.196 1` | Red border |
| Save button | `0 1 0 1` | Green border |
| Label text | `0.8 0.8 0.8 1` | Light gray |
| Slider Red | `1 0 0 1` | Pure red |
| Slider Green | `0 1 0 1` | Pure green |
| Slider Blue | `0 0 1 1` | Pure blue |
| Slider Orange | `1 0.5 0 1` | Orange for neutral sliders |
| Panel border | via `LB_Clean_outline` | Automatic 1px


## VPPMap Settings & Input


Complete pattern for building a DayZ mod UI framework with proper input handling, settings persistence, and VPP-like menu layout.

## 1. LBMenuPopulator (Global Widget Initializer)

```c
// The LBMenuPopulator script initializes all global widgets by walking through
// all ScriptParams children and calling OnWidgetInitRecieved on each.
// Use it on the root PanelWidgetClass of your layout.

// Layout pattern:
PanelWidgetClass {
  scriptclass "LBMenuPopulator"
  ScriptParamsClass {
    widgetType WidgetType
    widgetName "MyWidgetName"  // Maps to ScriptParam targetName
  }
}

// Code: The existing LayoutHandler classes handle the actual init via InitWidgets()
```

## 2. DayZ Enforce Script Syntax (CRITICAL)

```c
// WRONG - causes compile errors:
int[] arr = {1, 2, 3};           // No array literals
ref PlayerIdentity id;           // ref doesn't exist
switch (x) { case 1: ... }       // No switch statements

// CORRECT:
array<int> arr = new array<int>;
arr.Insert(1);
PlayerIdentity id;               // Class is a ref by default
if (x == 1) { ... } else if (x == 2) { ... }
```

## 3. Input Flow Architecture

```
Gamepad Input
    ↓
MenuBase.OnGamepadPress() → Sets m_InputAction, updates context
    ↓
MenuBase.ProcessInput() → MenuInputHandler
    ↓
MenuInputHandler() → Builds CommandDelegate + CommandArgs
    ↓
PlayerBase.OnInput() → menuRoot.GetCurrentMenu().Input()
    ↓
YourMenu.Input()
```

**Critical pattern for OnInput():**
```c
override bool OnInput(UAInput input, int actionType) {
    // PROTECT: Check if controller is active to prevent script errors
    GetGame().GetInput().HasGamepad(INPUT_DEVICE_CONTROLLER);
    
    int action = input.ID();
    bool hasParams = input.IsPress() || input.IsHoldStart() || input.IsHoldAbort() || input.IsRelease();
    
    // Always forward to UI first - returns true if focused widget consumed
    if (hasParams && menuRoot && menuRoot.OnInput(input, GetGame().GetInput().GetUsedDevice())) {
        return true;
    }
    
    // Only handle input when no text input is focused
    bool forward = menuRoot && menuRoot.GetFocusedWidget() && menuRoot.GetFocusedWidget().CanHandleFocus();
    
    if (action == UANextAction && !forward) {
        if (actionType == UA_PRESS) { /* LEFT */ }
        if (actionType == UA_RELEASE) { /* LEFT_RELEASE */ }
    }
}
```

## 4. Global Actions Setup

```c
// MenuBase subclass setup:
void ConfigureGlobalActions() {
    // Inventory blocking
    UAInput inp = GetUApi().GetInputByName("UAInventory");
    inp.AddAlternative(GetUApi().GetInputByName("UADefaultAction"), 0, true);
    
    // Map key combos (alternative gives priority)
    GetUApi().GetInputByName("UAFireMode").AddAlternative(
        GetUApi().GetInputByName("UABuildMod"), 0, false);
    GetUApi().GetInputByName("UABuildMod").AddAlternative(
        GetUApi().GetInputByName("UAFireMode"), 0, false);
    
    // Control hints with placeholder images
    GetGame().GetMission().GetHud()
        .ShowActionInventory(MBIMapKey, "#action_firemode" + " (Map)");
}
```

## 5. Full-Screen Settings Menu (UIControllerExtension)

```c
// Settings menu shown at root level (not inside sidebar)
void ShowConfig() {
    panel_settings_root.Show(true);
    panel_list_frame.Show(false);  // Hide sidebar content
    // Sidebar stays visible - user can click Back to return
}
```

**Layout pattern:**
```xml
PanelWidgetClass {
  visible 0  // Hidden by default
  position 0 0
  size 1 1  // FULL SCREEN
  halign center_ref
  valign center_ref
}
```

## 6. 4-Panel Settings Layout (Quadrant Pattern)

```xml
<!-- Top-left: Colors -->
PanelWidgetClass colorSettingsPanel {
  position 0.025 0.025
  size 0.475 0.475
  style LB_Clean_outline
}

<!-- Top-right: Positions -->
PanelWidgetClass layoutPositions {
  position 0.5 0.025
  size 0.475 0.475
  style LB_Clean_outline
}

<!-- Bottom-left: Styles -->
PanelWidgetClass layoutSettingsPanel {
  position 0.025 0.525
  size 0.475 0.45
  style LB_Clean_outline
}

<!-- Bottom-right: Misc -->
PanelWidgetClass miscPanel {
  position 0.5 0.525
  size 0.475 0.45
  style LB_Clean_outline
}
```

## 7. Settings Panel Widget Pattern

```xml
<!-- Title -->
TextWidgetClass {
  ignorepointer 1 position 0 10 size 0.9 40 halign center_ref
  font "gui/fonts/MetronBold16" color 1 0.6 0.1 1 text "Title"
  "text halign" center "text valign" center
}

<!-- Slider + Edit Box (LBmaster pattern) -->
SliderWidgetClass sliderR {
  color 1 0 0 1 position 5 100 size 0.7 20
  maximum 255 current 255 "fill in" 1
}
EditBoxWidgetClass editR {
  position 0.75 100 size 0.2 20
  font "gui/fonts/Metron14" text "255"
}

<!-- Reset buttons (LBmaster pattern) -->
PanelWidgetClass resetButtons {
  size 1 0.12 valign bottom_ref scriptclass "LBGapHandler" style blank
  {
    ButtonWidgetClass btnResetAll {
      position 0 5 size 0.32 0.3 valign bottom_ref text "Reset All"
      { PanelWidgetClass { color 1 0.196 0.196 1 size 1 1 style LB_Clean_outline } }
    }
    ButtonWidgetClass btnSave {
      position 0 5 size 0.32 0.3 halign right_ref valign bottom_ref text "Save"
      { PanelWidgetClass { color 0 1 0 1 size 1 1 style LB_Clean_outline } }
    }
  }
}
```

## 8. Controller Check Pattern

```c
// Check if controller is active before handling input
private bool m_UsesController = false;

override bool OnInput(UAInput input, int actionType) {
    // This check prevents script errors when no controller is connected
    m_UsesController = GetGame().GetInput().HasGamepad(INPUT_DEVICE_CONTROLLER);
    // ... rest of handler
}
```

## 9. Settings Persistence

```c
void ApplyAndSaveSettings() {
    VPPClientSettings settings = VPPClientManager.GetInstance().GetClientSettings();
    // Read from UI widgets
    if (sliderX) settings.m_ChatX = sliderX.GetCurrent();
    if (chkCompass) settings.CompassEnabled = chkCompass.IsChecked();
    // Apply + Save
    VPPClientManager.GetInstance().ApplyClientSettings();
    VPPClientManager.GetInstance().SaveClientSettings();
}
```

## 10. Server-Authoritative Settings Architecture (Complete Flow)

**Pattern**: Client is a DUMB PUPPET. Server owns all settings. Client receives, applies, and saves to server only on explicit Save button.

```
Client (dumb puppet)                Server (authoritative)
─────────────────────               ─────────────────────
On Connect:
  │                                 GetOrCreateForPlayer(steamId)
  │    ◄── VPP_SETTINGS_SYNC ◄────    ValidateSettings() + JSON serialize
  HandleSettingsSync()
  Apply to widgets

Slider moves:
  OnChange() → ApplyPositionLocal()  (widget moves, NO save, NO server)

Save button:
  ApplyAndSaveSettings()
  │    ─── VPP_CLIENT_SETTINGS_SAVE ──►  HandleSave()
  │                                    ValidateSettings()
  │                                    SavePlayerSettings()
  │                                    SyncToClient()
  │    ◄── VPP_CLIENT_SETTINGS_SYNC ◄── (echo back validated)
  HandleSettingsSync()
  Apply to widgets
```

**Server-side: VPPClientSettingsManager**
```c
class VPPClientSettingsManager {
    protected string m_SettingsDir = "$profile:VPPMap_Groups/ClientSettings/";
    protected ref map<string, ref VPPClientSettings> m_SettingsCache;

    // Called once at server start — loads default, broadcasts to all
    void Init() {
        m_SettingsCache = new map<string, ref VPPClientSettings>;
        m_SettingsDir = "$profile:VPPMap_Groups/ClientSettings/";
        MakeDirectory(m_SettingsDir);
    }

    VPPClientSettings GetOrCreateForPlayer(string steamId) {
        if (m_SettingsCache.Contains(steamId)) return m_SettingsCache.Get(steamId);

        string path = m_SettingsDir + steamId + ".json";
        VPPClientSettings settings = new VPPClientSettings();

        if (FileExist(path)) {
            settings = new VPPClientSettings();
            JsonFileLoader<VPPClientSettings>.JsonLoadFile(path, settings);
            ValidateSettings(settings);
        }

        // Set available options (defined by SERVER, not client)
        SetAvailableOptions(settings);

        if (!m_SettingsCache.Contains(steamId)) m_SettingsCache.Insert(steamId, settings);
        return settings;
    }

    // Available options come from server — client shouldn't list what it can't have
    void SetAvailableOptions(VPPClientSettings s) {
        // If you add a feature later, just add its options here
        // e.g., s.available_MarkerStyles = {"default", "small", "tiny", "cross"};
    }

    // Validate before save — clamp ranges, force valid values
    void ValidateSettings(VPPClientSettings s) {
        s.pos_ChatX = Math.ClampFloat(s.pos_ChatX, 0, 1);
        s.pos_ChatY = Math.ClampFloat(s.pos_ChatY, 0, 1);
        s.m_ChatWidth = Math.ClampFloat(s.m_ChatWidth, 0.1, 1);
        s.m_ChatSize = Math.ClampInt(s.m_ChatSize, 10, 30);
        s.m_ChatFadeDelay = Math.ClampInt(s.m_ChatFadeDelay, 5, 120);
        s.style_PlayerList = Math.ClampInt(s.style_PlayerList, 0, 3);
        s.style_MarkerPos = Math.ClampInt(s.style_MarkerPos, 0, 2);
    }

    void SavePlayerSettings(string steamId, VPPClientSettings settings) {
        if (!settings) return;
        string path = m_SettingsDir + steamId + ".json";
        VPPClientSettings copy = new VPPClientSettings();
        // Copy all fields...
        JsonFileLoader<VPPClientSettings>.JsonSaveFile(path, copy);
        if (m_SettingsCache.Contains(steamId)) m_SettingsCache.Set(steamId, settings);
        Print("[VPPClientSettingsManager] Saved settings for " + steamId);
    }
}
```

**Client-side: VPPClientSettings (data object, no logic)**
```c
// NO SaveToFile, NO LoadFromFile, NO JsonFileLoader
// Pure data class that gets serialized over RPC
class VPPClientSettings {
    // Positions (0-1 normalized)
    float pos_ChatX, pos_ChatY;
    float pos_PlayerListX, pos_PlayerListY;
    float pos_MinimapX, pos_MinimapY;

    // Colors (ARGB ints)
    int col_Player3DMarker = ARGB(255,255,255,255);
    int col_OwnMapMarker = ARGB(255,255,0,0);
    // ... more color fields

    // Styles
    int style_PlayerList = 0;
    int style_MarkerPos = 0;
    bool style_MarkerIcon = true;
    bool style_MarkerName = true;
    bool style_MarkerDistance = true;

    // Toggles
    bool ShowGroupTag = true;
    bool UseCustomTextures = true;
    bool StreamerMode = false;
    bool ShowNoBuildZones = true;

    // Chat
    float m_ChatWidth = 0.4;
    int m_ChatSize = 15;
    int m_ChatFadeDelay = 20;
}
```

**Client-side: RPC handler (receives validated settings from server)**
```c
void HandleSettingsSync(PlayerIdentity sender, Object target, int rpc_type, ParamsReadContext ctx) {
    m_ClientSettings = new VPPClientSettings();
    if (!m_ClientSettings.ReadFromCtx(ctx)) {
        Print("[VPPClientSettings] Failed to read synced settings!");
        return;
    }
    ApplyClientSettings();
}
```

**Client-side: Live preview vs Save (two methods)**
```c
// Live preview - apply to widget only, NO save, NO server
void ApplyPositionLocal(string elementName, float x, float y) {
    if (elementName == "Chat" && m_ChatRoot) {
        m_ChatRoot.SetPos(x * 1000.0, y * 1000.0);
    }
}

// Save button - write to settings AND send to server
void SetWidgetPos(string elementName, float x, float y) {
    VPPClientSettings s = VPPClientManager.GetInstance().GetClientSettings();
    if (!s) return;
    s.pos_ChatX = x; s.pos_ChatY = y;
    if (m_ChatRoot) m_ChatRoot.SetPos(x * 1000.0, y * 1000.0);
}

void OnChange(Widget w, int x, int y, bool finished) {
    if (w == sliderX || w == sliderY) {
        // Live preview ONLY — no save, no server sync
        if (sliderX && sliderY) {
            VPPHUDManager.Get().ApplyPositionLocal("Chat", sliderX.GetCurrent(), sliderY.GetCurrent());
        }
        return true;
    }
    return false;
}
```

## 11. MessageQueue for Server-Pushed Chat Messages

**Problem**: Server pushes messages to client via RPC. Chat must auto-fade, limited to N messages, newest on top.

**Solution**: Each new message at top, message lifetime tracked, auto-delete after fade delay.

```c
// ChatManager (client-side)
static const int MAX_CHAT_MESSAGES = 25;

void OnReceiveChatMessage(string sender, string text, int channelColor) {
    Widget msg = GetGame().GetWorkspace().CreateWidgets("VanillaPPMap/GUI/Layouts/Client/VPPChatItem.layout", m_ChatRoot);
    TextWidget senderLabel = TextWidget.Cast(msg.FindAnyWidget("SenderLabel"));
    TextWidget messageLabel = TextWidget.Cast(msg.FindAnyWidget("MessageLabel"));
    senderLabel.SetText(sender + ":");
    senderLabel.SetColor(channelColor);
    messageLabel.SetText(text);

    // Newest at top — push all existing down
    foreach (auto existing : m_Messages) existing.SetPos(0, existing.GetPos()[1] + 30);
    m_Messages.InsertAt(msg, 0);

    // Delete oldest if over limit
    if (m_Messages.Count() > MAX_CHAT_MESSAGES) {
        Widget old = m_Messages.Get(m_Messages.Count() - 1);
        old.Unlink();
        m_Messages.Remove(m_Messages.Count() - 1);
    }

    // Schedule fade/delete
    m_Timers[msg] = GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(FadeAndDelete, m_ChatFadeDelay * 1000, false, msg);
}
```

## 12. Simple File Verification for Layout Files

```python
# Check braces match, widget names consistent
import re
with open("layout.layout") as f:
    layout = f.read()
with open("script.c") as f:
    code = f.read()

code_names = set(re.findall(r'FindAnyWidget\("(\w+)"\)', code))
layout_names = set(re.findall(r'Class (\w+)', layout))
missing = code_names - layout_names
print(f"Missing: {missing if missing else 'NONE'}")
print(f"Braces: {layout.count('{')}/{layout.count('}')}")
```

## 13. VPPMap Render Root Widget Hierarchy

```xml
<!-- The 3 HUD widgets (PlayerList, Minimap, Chat) are attached here -->
<!-- They are NOT inside the menu itself — they're on the render root -->
<!-- The menu only CREATES and MANAGES them, but doesn't contain them -->

<!-- PlayerList: size 0.366 1.026, pos 0 0 -->
<!-- Minimap: size 0.1584 0.282, pos 0.4324 0 -->
<!-- Chat: size 0.4926 0.276, pos 0.0061 0.724 -->
```

## 14. Simple OOP Symlink Patterns

```bash
# DayZ classes use symlinks — these are simple OneClassPerFile classes
# e.g., VPPClientSettingsManager.c → contains only VPPClientSettingsManager class
# No complex logic, just serialize/deserialize/validate
```

## Pitfalls

1. **`UAInput` doesn't have `.GetHTML()`** - Use `img=` placeholder syntax instead
2. **`root` can be null** - Always check before using `root.FindAnyWidget()` in init methods
3. **Input delegation must return true** - If you handle input and want to stop propagation
4. **Slider + Edit Box sync** - Must manually update edit box text when slider changes via OnChange
5. **Full-screen menus need `position 0 0 size 1 1`** - Not just `size 1 1`
6. **Controller check is critical** - `HasGamepad()` must be called before using controller-specific methods
7. **`JsonFileLoader.JsonLoadFile` needs 2 params** - Path AND reference object: `JsonFileLoader<T>.JsonLoadFile(path, settings)`
8. **Client settings don't live on disk** - They live in memory, server owns persistence. Client is dumb puppet.
9. **Live preview vs Save** - OnChange should ONLY apply to widget, not write to settings or send to server. Save button does that.
10. **Only show settings for features that exist** - Don't create UI controls for minimap/compass/GPS if those widgets aren't implemented yet. Server defines available options.
11. **NULL player in OnKeyPress** - BaseBuildingPlus crashes on NULL player during loading — this is their mod, not ours.
12. **Extreme root syntax `@root^^^`** - CharToKeyCode uses this to walk up to root. Used in `OnKeyDown(KeyCode kc)` for focused widget menu switching.

## VPP Client Settings UI Pattern


## When to use
Building any VPP UI panel that must match LBmaster's visual/structural conventions.

## LBmaster Design Patterns (Reference)

### Layout Structure
- `size 1 1` root panel, `halign center_ref` + `valign center_ref` for fullscreen centering
- `hexactpos 1 vexactpos 1` for pixel positioning, `hexactsize 0 vexactsize 0` for relative sizing
- Style: `rover_sim_colorable` for colored backgrounds, `LB_Clean_outline` for bordered panels

### Widget Conventions
- `ignorepointer 1` on all non-interactive text/panels
- Font hierarchy: `gui/fonts/MetronBold16` (titles), `gui/fonts/Metron14` (labels/buttons)
- Labels: `"text halign" right` or `"text halign" center`, `color 0.8 0.8 0.8 1`
- Titles: `color 1 0.6 0.1 1` (orange)
- Sliders: `step 0.001` + `"fill in" 1` for continuous fill + `current` for initial value
- TextListbox: `lines 20` for scrollable selection
- XComboBox: `items "item1;item2;..."` on same line
- Checkboxes: `checked 1` or `checked 0`, `color 0.2 0.8 0.2 1` for enabled state
- Buttons: `font "gui/fonts/Metron14"`, `{ PanelWidgetClass p { ... style LB_Clean_outline } }` child for outline

### Button Colors (child panel)
- Red (reset/danger): `color 1 0.196 0.196 1`
- Orange (reload/warn): `color 1 0.5 0 1`
- Green (save/confirm): `color 0 1 0 1`

### Color Picker Pattern (LBmaster style)
- Left panel: TextListboxWidgetClass for available colors
- Right panel: 4 SliderWidgets (Alpha/Red/Green/Blue), each `maximum 255`, colored sliders (`color 1 0 0 1` for red, etc)
- Preview panel: `style rover_sim_colorable` with dynamically set color
- Default button: resets to default RGBA value

### Layout Position Pattern (LBmaster style)
- Left panel: TextListboxWidgetClass for available elements (PlayerList, Minimap, Chat)
- Right panel: Preview panel with movable icon, X/Y EditBox + Slider, Invert X/Y checkboxes, Default button
- Sliders: `maximum 1 step 0.001` for 0-1 normalized positions
- Preview icon: `style rover_sim_colorable color 0.2 0.8 0.2 1`

### 4-Quadrant Grid (typical LBmaster panel)
- Q1: Top-left (position 0 30, size 480 420) — primary settings
- Q2: Top-right (position 490 30, size 480 420) — secondary settings
- Q3: Bottom-left (position 0 460, size 480 490) — tertiary settings
- Q4: Bottom-right (position 490 460, size 480 490) — misc/actions
- Close button: `position 2 2 size 80 22 halign right_ref`

## Settings Architecture

### Field Naming Convention (Enforce Script)
- Boolean toggles: `camelCase` (e.g., `GPSEnabled`, `StreamerMode`)
- Color fields: `col_Prefix` (e.g., `col_Player3DMarker`, `col_Compass`)
- Position fields: `pos_Prefix` + `invert_Prefix` (e.g., `pos_ChatX`, `pos_ChatY`, `invert_ChatX`)
- Style fields: `style_Prefix` (e.g., `style_PlayerList`, `style_GPS`)
- Numeric config: `m_Prefix` (e.g., `m_ChatSize`, `m_LerpFactor`)

### VPPClientSettings Pattern
1. Declare all fields with defaults in constructor
2. `WriteToCtx(ParamsWriteContext ctx)` — sequential Write() calls
3. `ReadFromCtx(ParamsReadContext ctx)` — sequential Read() calls with fallback defaults
4. Server-side must match client-side field names exactly

### Handler Class Pattern (VPPClientSettingsMenu)
1. `Init()` — find all widgets, populate lists, load settings to UI
2. `PopulateColorList()` — build m_ColorNames + m_ColorValues arrays, add to TextListbox
3. `LoadSettingsToUI()` — read VPPClientSettings fields, set widget states
4. `UpdateColorPicker()` — extract RGBA from int, set 4 sliders + preview
5. `UpdatePositionFields()` — read position/invert fields, set sliders + checkboxes
6. `ApplyAndSaveSettings()` — write widget states back to VPPClientSettings fields, call ApplyClientSettings() + SaveClientSettings()
7. `ResetAllSettings()` — restore defaults, rebuild lists, call ApplyAndSaveSettings()

### VPPMapMenu Wiring
1. Initialize handler in `OnCreate()` AFTER `super.OnCreate()`
2. Create layout: `m_ClientSettingsUI = new VPPClientSettingsMenu(); m_ClientSettingsUI.Init(GetLayoutRoot().FindAnyWidget("panelClientSettings"), GetLayoutRoot());`
3. Get/Set menu reference: `VPPMapMenu.Cast(GetGame().GetUIManager().FindMenu(VPP_MENU_MAP))`

### INI Config Pattern
- Section headers: `[SectionName]`
- Key-value pairs: `key=value`
- Server reads with `GetGame().ServerConfigParser()`
- Use constant keys: `static const string INI_SECTION = "ClientSettings";`

## Pitfalls
- Field name changes in VPPClientSettings require updating ALL references (VPPChatWidget, settings menus, server-side handler)
- When renaming fields, search for `settings.oldField` AND `settings.newField` across all script files
- `max 1 step 0.001` for sliders — larger step values feel unresponsive
- `maximum 255` for color sliders (ARGB integer, not 0-1 float)
- SliderWidget `GetCurrent()` returns float, cast to int for colors

