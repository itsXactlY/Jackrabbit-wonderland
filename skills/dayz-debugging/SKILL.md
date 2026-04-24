---
name: dayz-debugging
version: 1.0.0
category: dayz
description: Complete DayZ debugging guide — compilation errors, crash analysis, undefined methods, layout crashes, HUD timing, widget sync, and recovery strategies.
tags: [dayz, debugging, compilation, crash, undefined-methods, hud]
---

# DayZ Debugging — Complete Guide


## Compilation Debug Workflow


# DayZ Mod Compilation Debug

Systematic approach for debugging and fixing DayZ mod compilation errors, particularly for EnforceScript-based UI mods like VanillaPPMap.

## When to Use
- DayZ mod fails to compile with "Can't compile Mission script module!" errors
- EnforceScript syntax errors in .c files or .layout files
- Missing function references or undefined method errors
- Layout syntax issues causing UI initialization failures

## Step-by-Step Process

### 1. Extract Error Details from Crash Log
```bash
# Look for specific error messages in the crash log
grep -A5 -B5 "Can't compile" /home/alca/games/DayZ/Server/profile/crash_*.log
# Extract file, line number, and error type
# Example: VanillaPPMap/scripts/5_Mission/gui\vppmapmenu.c(105): Broken expression (missing ';'?)
```

### 2. Initial Assessment & Quick Fixes
Check for these common EnforceScript issues:
- **GetType() calls**: Remove - doesn't exist in EnforceScript
- **Layout keywords**: vextpos → vexactpos (DayZ-specific syntax)  
- **Missing semicolons**: Check lines before/after reported error
- **Invalid widget types**: MapWidgetPointer doesn't exist - use proper widget casting

### 3. Systematic File Inspection
```bash
# Check layout file syntax
grep -n "vextpos" /path/to/mod/GUI/Layouts/*.layout

# Check for missing functions referenced elsewhere
grep -r "RefreshGroupUI\|SetMapNeedsUpdate" /path/to/mod/scripts/

# Check for invalid widget declarations
grep -n "MapWidgetPointer\|CreateWidget.*MapWidget" /path/to/mod/scripts/5_Mission/gui/*.c
```

### 4. Safe Fix Application Procedure
To avoid corrupting files during editing (LEARNED FROM EXPERIENCE):

**A. Backup Original**
```bash
cp file.c file.c.backup
```

**B. Apply Fixes Individually**
1. **Layout syntax**: `sed -i 's/vextpos/vexactpos/g' file.layout`
2. **Remove GetType()**: `sed -i 's/GetType()/""/g' file.c` (or remove line entirely)
3. **Remove invalid widget code**: Delete blocks creating non-existent widgets
4. **Add missing functions**: Insert before first major function after Init()

**C. Safe Function Addition Method**
Instead of risky line-number insertion that can corrupt files:
```bash
# Find reliable anchor point (e.g., EditMarkerVisibility function)
LINE_BEFORE_EDIT=$(grep -n "EditMarkerVisibility" file.c | cut -d: -f1)
INSERT_POINT=$((LINE_BEFORE_EDIT - 1))

# Insert missing functions safely
sed -i "${INSERT_POINT}i\\
\\
    void RefreshGroupUI() {\\
        if (m_GroupMenu) m_GroupMenu.RefreshGroupData();\\
        if (m_GroupAdmin) m_GroupAdmin.Refresh();\\
        if (m_AdminHandler) m_AdminHandler.LoadSettingsToUI(VPPClientManager.GetInstance().GetServerSettings());\\
    }\\
\\
    void SetMapNeedsUpdate(bool state) {\\
        m_MapNeedsUpdate = state;\\
    }" file.c
```

**D. File Reconstruction Method (when sed gets complex)**
For complex insertions that keep corrupting:
```bash
# 1. Get everything BEFORE the insertion point
head -n $INSERT_POINT file.c > /tmp/part1.c

# 2. Add the new content
cat >> /tmp/part1.c << 'EOF'

    void RefreshGroupUI() {
        if (m_GroupMenu) m_GroupMenu.RefreshGroupData();
        if (m_GroupAdmin) m_GroupAdmin.Refresh();
        if (m_AdminHandler) m_AdminHandler.LoadSettingsToUI(VPPClientManager.GetInstance().GetServerSettings());
    }

    void SetMapNeedsUpdate(bool state) {
        m_MapNeedsUpdate = state;
    }
EOF

# 3. Add everything AFTER the insertion point
tail -n +$INSERT_POINT file.c >> /tmp/part1.c

# 4. Replace original
mv /tmp/part1.c file.c
```

### 5. Verification Checklist
After each fix round:
- [ ] No `GetType()` calls remain
- [ ] No `vextpos` in layout files (only `vexactpos`)
- [ ] No `MapWidgetPointer` or invalid `CreateWidget` usage
- [ ] Missing functions present and correctly formatted
- [ ] Braces balanced (check with IDE or manual inspection)
- [ ] PBOs build without errors
- [ ] Server progresses past script compilation

### 6. Build & Test
```bash
# Build PBOs
./build_and_start_vanillappmap.sh

# Check for success indicators:
# - "✓ Client PBO gebaut"
# - "✓ Server PBO gebaut" 
# - "Starte DayZServer_x64..."
# - "fsync: up and running."

# Verify PBOs created
ls -lh /home/alca/games/DayZ/Mods/@VanillaPPMap/addons/VanillaPPMap.pbo
ls -lh /home/alca/games/DayZ/Mods/@VanillaPPMap_Server/addons/VanillaPPMap_Server.pbo
```

### Common Pitfalls & Solutions
- **File corruption during editing**: Always work from git backup or make backups before sed operations. Learned this the hard way when multiple sed commands corrupted the file structure.
- **Misplaced function insertion**: Use anchor points (like `EditMarkerVisibility`) instead of line numbers to avoid putting code in wrong locations.
- **Missing braces**: Verify each added function has proper opening/closing braces - unbalanced braces cause cascade errors.
- **Layout vs script confusion**: Layout files use different syntax (.layout) than script files (.c) - don't mix them up.
- **Assuming missing functions**: Always verify functions are actually referenced before adding them - don't guess.
- **Iterative fixing**: Fix one error at a time - fixing early errors often reveals later ones that were masked.

### Recovery Strategy
If file becomes corrupted during editing:
```bash
# Reset to known good state
git checkout HEAD -- path/to/mod/GUI/Layouts/VPPMapMenu.layout
git checkout HEAD -- path/to/mod/scripts/5_Mission/GUI/VPPMapMenu.c

# Then re-apply fixes carefully one by one
```

### Verification Commands
```bash
# Check fixes are applied
! grep -q vextpos /path/to/mod/GUI/Layouts/VPPMapMenu.layout && echo "✅ Layout fixed"
! grep -q GetType /path/to/mod/scripts/5_Mission/GUI/VPPMapMenu.c && echo "✅ GetType removed"
! grep -q MapWidgetPointer /path/to/mod/scripts/5_Mission/GUI/VPPMapMenu.c && echo "✅ Widget fix"
grep -q "RefreshGroupUI" /path/to/mod/scripts/5_Mission/GUI/VPPMapMenu.c && echo "✅ Function 1"
grep -q "SetMapNeedsUpdate" /path/to/mod/scripts/5_Mission/GUI/VPPMapMenu.c && echo "✅ Function 2"
```

## Expected Outcome
- Server progresses past "Can't compile Mission script module!" error
- PBOs build successfully without compilation errors
- Server reaches fsync initialization stage
- Map functionality works when client connects and presses 'M'

## Prerequisites
- DayZ mod development tools installed
- Access to mod source files
- Understanding of EnforceScript limitations vs standard scripting
- Basic sed/grep proficiency for file manipulation
- Patience for iterative debugging process

## Related Skills
- dayz-mod-ui-dev: For broader DayZ UI development patterns
- enforce-script-syntax: For EnforceScript-specific rules
- dayz-layout-crash-debug: For GUI layout file issues

## Compilation Fix Workflow

# DayZ Mod Compilation Fix Workflow

## When to Use
Use this workflow when a DayZ mod fails to compile and prevents server startup, showing errors like:
- "Can't compile \"Mission\" script module!"
- "Undefined function 'X'" 
- "Broken expression"
- "Missing ';'"
- Invalid layout keywords
- Class/method not found errors

## Workflow Steps

### 1. Log-First Investigation
- Examine the latest crash log in `/home/alca/games/DayZ/Server/profile/`
- Identify the specific error messages, file names, and line numbers
- Look for patterns: multiple errors often indicate related issues

#### Commands:
```bash
# Get latest crash log
ls -lt /home/alca/games/DayZ/Server/profile/ | grep log | head -1

# Examine specific error
grep -A5 -B5 "Broken expression\|Undefined function" /home/alca/games/DayZ/Server/profile/crash_*.log
```

### 2. Systematic Error-by-Error Fixing
Address each compiler error in the order they appear, as later errors may be caused by earlier ones.

#### Common Fix Patterns:
- **GetType() calls**: Remove - doesn't exist in EnforceScript
- **Invalid layout keywords**: Fix `vextpos` → `vexactpos`, check all layout syntax
- **Missing functions**: Check if function existed in original git version, restore if missing
- **Invalid widget creation**: Remove attempts to CreateWidget MapWidgets - use layout-defined widgets only
- **Pointer errors**: Remove invalid pointer types like `MapWidgetPointer`

#### Verification After Each Fix:
```bash
# Check fix was applied correctly
grep -n "GetType()" file.c   # Should return nothing
grep -n "vextpos" file.layout # Should return nothing  
grep -n "MapWidgetPointer" file.c # Should return nothing
```

### 3. Build Verification
After applying fixes, test that the mod builds successfully.

#### Commands:
```bash
# From mod working directory
./build_and_start_vanillappmap.sh  # Or your mod's build script

# Or manually:
# cd /path/to/mod
# ./Build.bat  # Windows
# ./Build.sh   # Linux (if available)

# Check PBOs were created
ls -la @ModName/addons/ModName.pbo
ls -la @ModName_Server/addons/ModName_Server.pbo
```

### 4. Iterative Refinement
If build succeeds but server still fails to start:
- Check new crash log for next set of errors
- Repeat from Step 1
- Common pattern: fixing compilation errors reveals runtime initialization issues

#### Signs of Progress:
- Server gets further in startup (check log timestamps)
- Different error messages appear
- PBOs build without compilation errors
- Server reaches "fsync: up and running" or similar initialization message

### 5. Principle Application (DayZ Enforce Script)
Throughout the process, apply these principles:
- **Existing infra first**: Use layout-defined widgets, don't create manually
- **No ternary operators**: Use if/else instead
- **Proper array handling**: Use ref array<T> + Insert/Get/Set, not int[] syntax
- **No switch statements**: Use if/else chains
- **No {} literals**: Construct objects properly

## DayZ-Specific Notes
- **VPPMaps**: Root size is `1 1`, quadrants use `0.49 0.46` 
- **Fonts**: Use Chat/PuristaMedium/PuristaBold outside VPPAdminTools
- **Layout textures**: Use forward slashes
- **GUI Separation**: UIScriptedMenu for open/close, plain widgets+VPPHUDManager for always-visible
- **Admin Checks**: VPPAdminTools GetPermissionManager() can return NULL - need fallback

## Example Fix Sequence
For errors like:
1. `GetType()` call → Remove it
2. `vextpos` in layout → Change to `vexactpos`  
3. `MapWidgetPointer` → Remove manual widget creation
4. `Undefined function RefreshGroupUI` → Restore function
5. `Undefined function SetMapNeedsUpdate` → Add function

## Success Criteria
- Mod PBOs build without compilation errors
- Server progresses past script compilation phase
- No more "Can't compile Mission script module!" errors
- Server reaches further initialization stages (check logs)

## Estimated Time
- Single error fix: 5-15 minutes
- Multiple related errors: 20-45 minutes
- Complex interdependent issues: 1-2 hours

## Skill Maintenance
After using this workflow, update this skill with:
- New error patterns encountered
- Additional fix patterns discovered
- DayZ version-specific considerations
- Tool chain updates that affect the process

## Fix Undefined Methods


# DayZ Enforce Script: Fix Undefined Methods in Custom Classes

## Problem
When developing DayZ mods with Enforce Script, accessing undefined methods on custom classes results in compilation errors. Commonly occurs when classes have private member variables but lack corresponding public getter/setter methods.

## Detection
- Compiler error: "Undefined function 'ClassName.MethodName'"
- Error occurs when trying to access methods like `IsMenuOpen()`, `GetVariable()` on custom classes
- The class typically has the backing private member variable but lacks the accessor methods
- Multiple files may attempt to call the same missing method

## Solution
1. Locate the class definition that's missing the method
2. Verify the backing private member variable exists
3. Add the missing getter and/or setter methods to the class
4. For boolean flags: add `GetFlagName()` returning the variable and `SetFlagName(bool)` setting it
5. Place methods near the end of the class definition before the closing brace

## Example Fix
For a class with `private bool m_IsMenuOpen;` missing `IsMenuOpen()`:
```c
bool IsMenuOpen() {
    return m_IsMenuOpen;
}

void SetMenuOpen(bool state) {
    m_IsMenuOpen = state;
}
```

## Prevention
- When adding private member variables that need external access, immediately add corresponding getter/setter methods
- Use consistent naming: `GetVariableName()` and `SetVariableName(type)`
- Review all files that instantiate the class to ensure they use the proper accessors
- Consider creating a template for common UI menu classes that need open/close state tracking

## Verification
- Recompile the mod to ensure no more undefined function errors
- Verify all call sites now work correctly
- Test the functionality that was previously broken due to the missing access

## DayZ Enforce Script Specifics
- Applies to classes extending `UIScriptedMenu` or other custom DayZ classes
- Commonly needed for menu state tracking, visibility flags, and UI interaction states
- Methods should be simple wrappers around member variables without additional logic

## Fix Undefined Methods (Enhanced)


# DayZ Enforce Script: Enhanced Fix for Undefined Methods in Custom Classes

## Problem
When developing DayZ mods with Enforce Script, accessing undefined methods on custom classes results in compilation errors like "Undefined function 'ClassName.MethodName'". This commonly occurs when classes have private member variables but lack corresponding public getter/setter methods.

## Enhanced Solution Approach

### Phase 1: Discovery and Verification
1. **Identify the error location**: Note the file and line number from the compiler error
2. **Check filename casing**: DayZ file references may have different casing than expected (e.g., ClientManager.c vs clientmanager.c)
3. **Locate the class definition**: Find the class that's missing the method
4. **Verify member variable exists**: Confirm the backing private member variable is present
5. **Check all call sites**: Search for all occurrences of the missing method call to understand scope

### Phase 2: Apply DayZ Enforce Script Patterns
Following the `dayz-enforce-script-fix-undefined-methods` skill:
1. **Getter method**: For `private bool m_IsMenuOpen;` add `bool IsMenuOpen() { return m_IsMenuOpen; }`
2. **Setter method**: For `private bool m_IsMenuOpen;` add `void SetMenuOpen(bool state) { m_IsMenuOpen = state; }`
3. **Placement**: Add methods near the end of the class before the closing brace
4. **Naming convention**: Use `GetVariableName()` and `SetVariableName(type)` pattern

### Phase 3: Constraint Compliance Verification
Verify the fix adheres to DayZ Enforce Script constraints:
- ✅ **No switch statements**: Replace with if/else chains
- ✅ **No ternary operators**: Replace with if/else  
- ✅ **No array literals**: Use `ref array<T>` + Insert/Get/Set/.Count()
- ✅ **Proper foreach**: Avoid `foreach(key, value : map)` syntax
- ✅ **Function-level variable scope**: No redeclaring variables in nested blocks
- ✅ **Widget event handlers**: Proper `bool OnClick(Widget, int, int, int)` signatures

### Phase 4: Dupication Prevention
After applying the fix:
1. **Check for duplicates**: Search the file to ensure methods weren't accidentally duplicated
2. **Validate placement**: Ensure methods are in the correct location (after other methods, before closing brace)
3. **Verify naming consistency**: Confirm method names match the expected getter/setter pattern

### Phase 5: Multi-Call Site Validation
Test that all call sites now work:
1. **ClientManager.c**: `mapMenu.IsMenuOpen()` calls
2. **missionGameplay.c**: `m_VPPMapMenu.IsMenuOpen()` calls  
3. **Any other files**: Search for additional usages of the method
4. **Setter usage**: Verify `SetMenuOpen(bool)` calls work if applicable

## Example Fix Workflow
For the specific case of `VPPMapMenu.IsMenuOpen()`:

**Before:**
```c
class VPPMapMenu extends UIScriptedMenu {
    private bool m_IsMenuOpen;
    // ... other members and methods ...
    // MISSING: IsMenuOpen() and SetMenuOpen(bool) methods
}
```

**After applying fix:**
```c
class VPPMapMenu extends UIScriptedMenu {
    private bool m_IsMenuOpen;
    // ... other members and methods ...
    
    bool IsMenuOpen() {
        return m_IsMenuOpen;
    }

    void SetMenuOpen(bool state) {
        m_IsMenuOpen = state;
    }
}
```

## Prevention Strategies
1. **Immediate implementation**: When adding private member variables requiring external access, immediately add corresponding getter/setter methods
2. **Consistent naming**: Always use `GetVariableName()` and `SetVariableName(type)` patterns
3. **Module awareness**: Remember DayZ module load order (3_Game → 4_World → 5_Mission) and cross-visibility rules
4. **Template creation**: Create templates for common UI menu classes needing state tracking

## Verification Checklist
- [ ] Compiler error "Undefined function 'ClassName.MethodName'" resolved
- [ ] Getter method returns correct member variable type and value
- [ ] Setter method correctly assigns to member variable
- [ ] No switch statements, ternary operators, or array literals introduced
- [ ] Methods placed correctly in class definition (before closing brace)
- [ ] No duplicate methods created
- [ ] All call sites accessing the method now compile successfully
- [ ] Follows function-level variable scope rules
- [ ] Complies with DayZ module cross-visibility constraints

## DayZ-Specific Considerations
- **UIScriptedMenu classes**: Commonly need open/close state tracking for menus
- **Cross-module access**: Ensure calling module can see the class definition (based on load order)
- **Private member access**: Other classes cannot access private members directly - must use getters/setters
- **Method simplicity**: Keep getters/setters as simple wrappers without additional business logic

## Layout Crash Debug


# DayZ Layout Crash Debugging

**Trigger**: DayZ crashes with `SEH exception 0x80000101` in `CreateWidgets()` or during widget init, especially when layout braces appear balanced.

## Diagnosis Steps

1. **Check binary layout file** — read as bytes, check for BOM, null bytes, encoding issues
2. **Verify braces match** — `{` count must equal `}` count
3. **Check `size` + `hexactsize` pairs** — the #1 hidden cause of crashes:
   - `hexactsize 1` means EXACT PIXEL size — value is in pixels, not relative 0-1
   - Large pixel values (e.g., `size 1104 25`) with `hexactsize 1` can overflow the parent container and crash `CreateWidgets`
   - **Fix**: Either reduce the pixel value to screen width (≤980 for typical 1080p), OR change to `hexactsize 0` + `size 1 25` (relative width)
4. **Check `hexactpos`** — same principle, exact pixel positioning can place widgets off-screen

## Common Pitfalls

| Pattern | Problem | Fix |
|---------|---------|-----|
| `size 1104 25 hexactsize 1` | 1104px wide exceeds container | `size 1 25 hexactsize 0` |
| `size 1920 1080 hexactsize 1` | Full screen exact pixels | `size 1 1 hexactsize 0` |
| `.edds` referenced but only `.png` exists | Missing texture file | Change path to actual format |
| Non-existent font in `font` attribute | Crash on widget init | Replace with valid DayZ font |
| Brace count mismatch | Structural corruption | Rebuild from backup |

## Font-Related Crashes

Non-existent fonts cause **SEH exception 0x80000101** on startup when the engine tries to create text widgets. Common culprits from VPPAdminTools/other mods:

| Bad Font | DayZ Replacement |
|----------|-----------------|
| `gui/fonts/sdf_MetronBook72` | `gui/fonts/Chat` |
| `gui/fonts/sdf_MetronLight24` | `gui/fonts/PuristaMedium` |
| `gui/fonts/sdf_MetronBold16` | `gui/fonts/PuristaBold` |

**Scan command**: `grep -r "sdf_Metron" GUI/Layouts/` then bulk-replace with sed or script. These fonts are from VPPAdminTools - if that mod isn't loaded, the references break.

## Key Insight

A layout file can be **structurally valid** (braces balanced, no corruption) but still crash the engine if **pixel dimensions exceed container bounds** or **referenced textures don't exist**. Always verify `hexactsize` values against screen dimensions and texture file existence.


## HUD Init & Timing


# DayZ MissionGameplay HUD Widget Initialization

## When to initialize HUD widgets

**Never** create HUD widgets in the `MissionGameplay` constructor or via `CallLater` with short delays. During construction, the loading screen is still active, the world isn't spawned, and `GetGame().GetPlayer()` returns null. Widgets that query settings, register with managers, or access the world will hang or crash the connection handshake — causing infinite loading.

**Correct pattern:** Override `OnInit()` and defer with a short CallLater:

```enforce
override void OnInit() {
    super.OnInit();
    GetGame().GetCallQueue(CALL_CATEGORY_GUI).CallLater(this.InitializeHUDWidgets, 1000, false);
}
```

This fires after the world is fully loaded and the player exists.

## WidgetEventHandler API — correct calls

Widget events MUST use the specific typed registration methods. Generic `Register()` does not work for button clicks.

```enforce
// CORRECT — button click handler
WidgetEventHandler.GetInstance().RegisterOnClick(widget, this, "OnButtonClicked");

// WRONG — these don't exist or have wrong signatures
WidgetEventHandler.GetInstance().RegisterOnButton(...);  // DOES NOT EXIST
WidgetEventHandler.GetInstance().Register(widget, ...);  // doesn't register click
```

Handler signature — must be `bool` return type, NOT `void`:
```enforce
bool OnButtonClicked(Widget w, int x, int y, int button) {
    Print("clicked: " + w.GetName());
    return true;  // consume event
}
```

**Do NOT call `super.OnClick()`** unless the class you're extending overrides `OnClick` with the exact same 5-param signature. `ScriptedWidgetEventHandler` has `void OnClick(Widget w)` — calling `super.OnClick(w,x,y,button)` will crash.

## Enforce Script variable scoping

Enforce Script uses **function-level** variable scope. Declaring the same variable name twice in different `if` blocks within the same function is a compile error:

```enforce
// WRONG — 'year' declared twice
void UpdateInfo() {
    if (m_ServerTime) {
        int year, month, day, hour, minute;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
    }
    if (m_InGameTime) {
        int year, month, day, hour, minute;  // ERROR: Multiple declaration
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
    }
}

// CORRECT — declare once at function top
void UpdateInfo() {
    int year, month, day, hour, minute;
    if (m_ServerTime) {
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
    }
    if (m_InGameTime) {
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
    }
}
```

## File corruption recovery

If a file gets corrupted (e.g. triple column numbering like `1|     1|     1|class` caused by a bad `write_file`), don't try to patch it. Just:

```bash
cd /path/to/mod && git checkout -- path/to/file.ext
```

Then use small targeted `sed -i '/PATTERN/d'` commands or targeted `patch` with unique surrounding context instead of rewriting the entire file.

## Working directory verification

Always run `pwd` at the start of any file-editing session. Never assume the working directory based on conversation context. Use absolute paths.

## Crash Log Analysis


# DayZ Crash Log Analysis

Diagnose DayZ client/server crashes from `.log` files, PBO-deployed mod sources, and Wine/Proton SEH exceptions.

## When to use
- User shares a DayZ crash log with SEH exceptions, stack traces, or access violations
- Need to trace a crash through mod chains (VPPAdminTools -> BaseBuildingPlus -> VanillaPPMap etc.)
- Need to find the source line referenced in a crash from a deployed PBO

## Workflow

### 1. Parse the crash log
- `Class:` and `Function:` tell you which mod class/method crashed
- Stack trace shows the mod chain (e.g., `VPPAdminTools -> BaseBuildingPlus -> VanillaPPMap`)
- SEH exception code: `0xC0000005` = access violation, `0x80000101` = Wine-translated SIGSEGV

### 2. Find source code -- check in order
1. **Deployed PBO binary** (`/home/alca/games/DayZ/Mods/@<Mod>/addons/*.pbo`) -- the actual running code
2. **Workspace source** (`/home/alca/apogrps/`, `/home/alca/apogrps_qwen/`, `/home/alca/.hermes/your-workspace/apogrps/`) -- may differ from deployed
3. **Temp build output** (`~/.local/share/Steam/steamapps/compatdata/221100/pfx/.../Temp/`) -- intermediate build files

**Important**: Line numbers in crash logs match the DEPLOYED PBO, not workspace source. Always extract from PBO first.

### 3. Extract source from PBO binary
PBOs contain uncompressed script source. Extract with text scanning:

```python
pbo_path = '/home/alca/games/DayZ/Mods/@VanillaPPMap/addons/VanillaPPMap.pbo'
with open(pbo_path, 'rb') as f:
    data = f.read()
# Find class by name
idx = data.find(b'class VPPMapMenu extends')
# Extract until next class or marker
source = data[idx:end].decode('ascii', errors='replace')
```

For finding layout files inside PBOs:
```python
# Layout files are stored as readable text
idx = data.find(b'FrameWidgetClass VPPNoBuildAdminUI')
```

### 4. Understand the call chain
DayZ mod chain: multiple mods override the same methods (MissionGameplay::OnUpdate). The crash shows which mod in the chain was executing. Key patterns:
- `EnterScriptedMenu()` -> engine calls `Init()` on the menu class
- `ShowScriptedMenu()` -> calls `OnShow()`
- `OnUpdate()` runs every frame; if it re-creates menus, Init() can be called from OnUpdate context

### 5. Common crash causes on Linux/Proton
- **0x80000101**: Wine/Proton translated SIGSEGV -- native C++ crash in engine code (widget allocation, D3D calls)
- Complex widget trees in layouts can trigger Proton edge cases
- Clear shader cache: `rm -rf ~/.local/share/Steam/steamapps/shadercache/221100/`
- Check Proton version (Proton-GE handles DayZ UI better)

### 6. Fix approaches
- Add null/layout-exists guards around CreateWidgets calls
- Wrap complex UI initialization in try-catch patterns
- Simplify widget tree depth in .layout files
- Update Proton version or GPU drivers

## File locations
- Client mods: `/home/alca/games/DayZ/Mods/@<Mod>/addons/`
- Workshop PBOs: `~/.local/share/Steam/steamapps/workshop/content/221100/`
- Workspace source: `/home/alca/apogrps/` (main) or `/home/alca/apogrps_qwen/` (Qwen branch)
- Server: `/home/alca/games/DayZ/Server/`
- Proton prefix: `~/.local/share/Steam/steamapps/compatdata/221100/pfx/`

## Pitfalls
- Multiple copies of source exist with DIFFERENT code (apogrps vs apogrps_qwen vs hermes workspace vs PBO)
- Line numbers in crash logs = deployed PBO source, NOT workspace source
- PBO may contain source that was formatted/changed during packing (different whitespace, removed comments)
- Wine exception codes don't map directly to Windows NTSTATUS codes


## Settings Widget Sync


# DayZ Settings ↔ Widget Sync Pattern

Problem: Settings UI changes (sliders, checkboxes) modify values internally but never reach the actual HUD widgets or persist.

## Root Cause
Settings UI and HUD widgets are decoupled — UI stores values locally but nothing bridges to the widget or JSON file.

## Solution: Central HUD Manager Singleton

All HUD state changes must flow through one manager that:
1. Holds `Widget` references to actual HUD elements (PlayerList, Minimap, Chat, Compass)
2. `SetWidgetPos(name, x, y)` — applies to widget live AND writes to settings struct
3. `SaveToFile()` — persists JSON after every change (not batched)
4. Widgets read initial state from saved settings on `Init()`

```c
class VPPHUDManager {
    private static ref VPPHUDManager s_Instance;
    private Widget m_PlayerListRoot;
    private Widget m_MinimapRoot;
    private Widget m_ChatRoot;

    static VPPHUDManager Get() {
        if (!s_Instance) s_Instance = new VPPHUDManager();
        return s_Instance;
    }

    void RegisterWidget(string name, Widget w) {
        if (name == "PlayerList") m_PlayerListRoot = w;
        else if (name == "Minimap") m_MinimapRoot = w;
        else if (name == "Chat") m_ChatRoot = w;
    }

    void SetWidgetPos(string name, float x, float y) {
        VPPClientSettings s = VPPClientManager.GetInstance().GetClientSettings();
        Widget w;
        if (name == "PlayerList") {
            s.pos_PlayerListX = x; s.pos_PlayerListY = y;
            w = m_PlayerListRoot;
        }
        // ... etc
        if (w) w.SetPos(x * 1000.0, y * 1000.0);
        VPPClientManager.GetInstance().SaveClientSettings();
    }
}
```

## Settings UI Integration

Override `OnChange` on sliders/editboxes to call the manager immediately:

```c
override bool OnChange(Widget w, int x, int y, bool finished) {
    if (w == sliderPX || w == sliderPY) {
        string elemName = "PlayerList"; // based on m_SelectedPos
        VPPHUDManager.Get().SetWidgetPos(elemName, sliderPX.GetCurrent(), sliderPY.GetCurrent());
        UpdatePositionPreview();
        return true;
    }
    return false;
}
```

Checkboxes (OnChanged) must also call manager for immediate visibility:
```c
if (chkCompass) { s.CompassEnabled = chkCompass.IsChecked(); VPPHUDManager.Get().SetCompassVisible(s.CompassEnabled); }
```

## Critical: No Widget Owns Its Own State
Widgets must NEVER store position/state independently. Always read from manager at init, always update through manager on change.

## DayZ Layout Crash Fixes

### Exact size overflow
`size 1104 25` with `hexactsize 1` causes engine crash on containers > screen width.
Fix: Use relative `size 1 25` with `hexactsize 0`.

### Texture path format
Layout files use backslash separators: `imageTexture "VanillaPPMap\\GUI\\Compass_slim.png"`
Must match actual file (`.png` not `.edds` unless EDDS file exists).
Always check `*.edds` files exist before referencing them.

### Widget not found crashes
`FindWidget()` returns null → crash at method call.
Always use `FindAnyWidget()` for name-based lookup, never `FindWidget()`.
Always null-check before calling methods on result.

### onChange per keystroke
DayZ fires `OnChanged` per keystroke on edit boxes, not on submit.
Guard with `if (finished)` for edit-box + slider sync to avoid infinite loops.

