---
name: dayz-enforce-script
version: 1.0.0
category: dayz
description: Complete DayZ Enforce Script reference — syntax rules, cross-module compilation, UI/UX design principles, error table, and debugging workflow.
tags: [dayz, enforce-script, syntax, compiler, ui-ux]
---

# DayZ Enforce Script — Complete Reference

## 1. Syntax Rules


DayZ Enforce Script syntax constraints caught by the compiler. Follow these to avoid build failures.

## Trigger
When writing or editing `.c` files for DayZ mods (client or server PBOs).

## Rules

### 1. No C-style array declarations
```c
// WRONG — compiler error
int[] vals = {1, 2, 3};
string[] names = {"a", "b"};

// RIGHT
ref array<int> vals = new array<int>;
vals.Insert(1); vals.Insert(2); vals.Insert(3);

ref array<string> names = new array<string>;
names.Insert("a"); names.Insert("b");
```

### 2. No bracket indexing — use Get/Set
```c
// WRONG
int v = myArray[i];
myArray[i] = 42;

// RIGHT
int v = myArray.Get(i);
myArray.Set(i, 42);
```

### 3. No duplicate class names across files
Each `class` name must be unique across the entire mod (both client and server modules). If a class like `VPPTerritoryConfig` exists in `VPPTerritoryModels.c`, you cannot redeclare it in `VPPAdminServerSettings.c` — even if the file compiles separately. Enforce merges all Game-module files at link time.

**Fix:** Remove the duplicate. Extend the existing class if you need more fields.

### 4. `int[]` literal arrays don't exist
```c
// WRONG
int[] radii = {20, 35, 50};

// RIGHT — insert one by one
ref array<int> radii = new array<int>;
radii.Insert(20); radii.Insert(35); radii.Insert(50);
```

### 5. `modded class` for extending vanilla
When extending a vanilla DayZ class, use `modded class ClassName` — do NOT redeclare it as `class`. Redeclaring causes a duplicate-class error at link time.

### 6. No ternary operator (`? :`)
Enforce Script has NO ternary operator. Using it causes `Broken expression (missing ';'?)` compile crash.
```c
// WRONG — crashes compilation
btn.SetColor(tab == 3 ? activeColor : dimColor);

// RIGHT
if (tab == 3) btn.SetColor(activeColor);
else btn.SetColor(dimColor);
```

### 7. No `ref` on types with private destructor
`PlayerIdentity` and other vanilla classes with private destructors cannot use `ref<>`.
```c
// WRONG — won't compile
void GetPlayer(ref PlayerIdentity id) { ... }

// RIGHT
void GetPlayer(PlayerIdentity id) { ... }
```

### 8. `Substring()` requires both start AND length
```c
// WRONG — only start param doesn't exist
string s = full.Substring(4);

// RIGHT
string s = full.Substring(4, full.Length() - 4);
```

### 9. `switch` without `return` falls through
In Enforce, `switch` cases can fall through unexpectedly. Prefer `if/else` chains for safety.

### 10. `string.Get(i)` returns int, not string
`Get()` on a string returns the ASCII code (int), not the character as a string. Comparing its result to strings or passing it where a string is expected causes `Incompatible parameter`.
```c
// WRONG — Get() returns int (e.g. 45 for '-')
int code = myStr.Get(0);
if (code < 48) return;  // works for comparison, but fragile

// RIGHT — Substring(i, 1) returns a single-char string
string ch = myStr.Substring(0, 1);
if (ch == "-") { ... }
int digit = ch.ToInt(); // 0-9 or error
```

### 11. No string comparison with `<` / `>`
Enforce Script does not support `string < string` or `string > string` comparisons.
```c
// WRONG — Broken expression
if (a < b) { ... }

// RIGHT — convert to int first
int ai = a.ToInt();
int bi = b.ToInt();
if (ai < bi) { ... }
```

### 12. `FindFile` signature is strict
`FindFile()` in Enforce has a specific signature: `FindFileHandle FindFile(string pattern, out string filename, out FileAttr attr, FindFileFlags flags)`. You cannot pass an `array<string>` as the second argument.
```c
// WRONG — array param
FindFileHandle fh = FindFile("*.json", files, FindFileFlags.ALL);

// RIGHT — iterate with string out param
string filename;
FileAttr attr;
FindFileHandle fh = FindFile(path + "*.json", filename, attr, FindFileFlags.ALL);
if (fh) {
    do {
        if ((attr & FileAttr.DIRECTORY) == 0) { files.Insert(filename); }
    } while (FindNextFile(fh, filename, attr));
    CloseFindFile(fh);
}
```

### 13. `JsonFileLoader` availability depends on module
`JsonFileLoader` from JM_CF_Scripts is available in `3_Game` (both client+server). In `4_World` server-side, it may fail with `Bad type 'JsonFileLoader'` if the CF module hasn't loaded by the time your script compiles. Use manual file I/O as fallback:
```c
// Fallback — manual JSON array read
FileHandle fh = OpenFile(path, FileMode.READ);
if (fh) {
    string line;
    while (FGets(fh, line) >= 0) {
        line.Trim();
        if (line == "[" || line == "]" || line == "") continue;
        line.Replace("\"", "");
        line.Replace(",", "");
        line.Trim();
        if (line != "") array.Insert(line);
    }
    CloseFile(fh);
}
```

### 14. `ShowInput` missing — modded class lifecycle
When a `modded class` calls methods on custom types, the custom type must compile in the same module. If `ShowInput()` is called on `VPPChatWidget` from `ChatInputMenu.c` but `VPPChatWidget` doesn't declare `ShowInput`, you get `Undefined function`. Always verify method signatures match across modded classes.

### 15. `FindFile` may not work in 4_World server module
Even with correct signature, `FindFile()` can return null in `4_World` server scripts. **Workaround:** maintain an index file alongside data files:
```c
// When saving, write tag to _index.json
// When loading, read _index.json to enumerate known files
// When deleting, remove tag from _index.json
FileHandle fh = OpenFile(dataPath + "_index.json", FileMode.READ);
if (fh) {
    string line;
    while (FGets(fh, line) >= 0) {
        line.Trim();
        line.Replace("\"", ""); line.Replace(",", ""); line.Trim();
        if (line != "" && line != "[" && line != "]") {
            LoadGroupFromFile(dataPath + line + ".json");
        }
    }
    CloseFile(fh);
}
```

### 16. Brace counting is unreliable with string literals
Naive `{`/`}` counting gives false positives when `{` and `}` appear inside string literals (e.g., `if (block.Substring(i, 1) == "{")`). Always track `in_string` state when debugging brace mismatches:
```c
bool in_string = false;
for (int j = 0; j < line.Length(); j++) {
    if (line.Substring(j, 1) == "\"" && (j == 0 || line.Substring(j-1, 1) != "\\")) {
        in_string = !in_string;
    }
    if (!in_string) {
        if (line.Substring(j, 1) == "{") depth++;
        else if (line.Substring(j, 1) == "}") depth--;
    }
}
```

### 17. `foreach` works but has quirks
Enforce Script supports `foreach` on arrays:
```c
for (int i = 0; i < arr.Count(); i++) {
    MyType item = arr.Get(i);
    // use item
}
```
`foreach` is available in newer Enforce versions but older ones may not support it. For maximum compatibility, use `for` + `Get()`.

### 18. `MakeDirectory` is idempotent
`MakeDirectory(path)` creates directory if missing, does nothing if it exists. Safe to call unconditionally — no `FileExist` check needed. Prefer:
```c
MakeDirectory("$profile:MyMod");
MakeDirectory("$profile:MyMod/Data");
```
Over:
```c
if (!FileExist("$profile:MyMod")) MakeDirectory("$profile:MyMod");
```
`FileExist` on directory paths is unreliable in DayZ.

### 19. foreach with maps does NOT work
DayZ Enforce Script does NOT support `foreach (key, value : map)` syntax. You must use indexed iteration:

```c
// WRONG - Enforce Script doesn't support this:
foreach (string key, MyType val : myMap) { ... }

// CORRECT - indexed loop:
for (int i = 0; i < myMap.Count(); i++) {
    MyType val = myMap.GetElement(i);  // value only
    string key = myMap.GetKey(i);      // key only
}
```

For arrays:
```c
// Both work in Enforce Script:
for (int i = 0; i < arr.Count(); i++) { MyType item = arr.Get(i); }
// Some versions support: foreach (MyType item : arr) { ... }
```

### 20. Maps API
```c
// Declare
ref map<string, ref MyType> m_Map = new map<string, ref MyType>;

// Operations
m_Map.Insert(key, val);
bool found = m_Map.Find(key, val);  // returns bool, val is out param
bool exists = m_Map.Contains(key);
int count = m_Map.Count();
MyType val = m_Map.GetElement(i);   // value by index
string key = m_Map.GetKey(i);       // key by index
m_Map.Remove(key);
```

### 21. Variable scope: function-level, NOT block-level
Enforce Script uses **function-level variable scope**. You cannot redeclare the same variable name in nested blocks (if/foreach/while) within the same function:

```c
// WRONG — "Multiple declaration of variable 'year'"
void MyFunc() {
    if (condition1) {
        int year, month;  // first declaration
    }
    if (condition2) {
        int year, month;  // COMPILER ERROR: already declared above
    }
}

// CORRECT — hoist to top of function
void MyFunc() {
    int year, month;  // once, at function top
    if (condition1) {
        // use year, month
    }
    if (condition2) {
        // reuse year, month
    }
}
```

This applies to ALL local variables — not just function params. Common victims: `year, month, day, hour, minute` in time-getting code, loop indices, temp strings.

### 22. OnClick handler in ScriptedWidgetEventHandler
DayZ `ScriptedWidgetEventHandler` expects `void OnClick(Widget w)`. If you register via `RegisterOnButton(widget, handler, "OnClick")`, your callback takes `(Widget w, int x, int y, int button)` — and must return `bool`. Do NOT use `override void` — just declare `bool OnClick(Widget, int, int, int)`:

```c
// WRONG — causes "Overloaded function 'OnClick' not compatible"
override void OnClick(Widget w, int x, int y, int button) {
    super.OnClick(w, x, y, button);  // also wrong signature
}

// CORRECT — just a method, not an override
bool OnClick(Widget w, int x, int y, int button) {
    // handle click
    return true;
}
```

### 23. WidgetEventHandler button registration
The correct DayZ API for registering button click handlers on dynamically created widgets:
```c
// RegisterOnButton is the correct method (NOT RegisterOnDoubleClick, NOT RegisterOnButton for generic)
WidgetEventHandler.GetInstance().RegisterOnButton(widget, this, "ButtonClicked");

void ButtonClicked(Widget w, int x, int y, int button) {
    // handle click
}
```

### 24. Cross-Module Visibility Rules (CRITICAL)
DayZ script modules load in strict order: **3_Game → 4_World → 5_Mission**. Each module can ONLY see classes from **previous** modules, NOT from later ones:

```
3_Game  →  can see: vanilla game classes only
4_World →  can see: vanilla + 3_Game classes
5_Mission → can see: vanilla + 3_Game + 4_World classes
```

**NEVER reference 5_Mission classes from 3_Game or 4_World** — compiler error: "Can't find variable 'SomeMissionClass'".

**NEVER access `private` or `protected` members of a class from a different class** — even within the same module, Enforce Script won't let you read private members of another class. You'll get "Variable 'm_FieldName' is private".

**Fix patterns for private member issues:**
- Add setter methods: `void SetUse3DMarkers(bool v) { m_Use3DMarkers = v; }`
- Make members package-public (no modifier): `bool m_Use3DMarkers = true;`
- Pass data through method params instead of direct field access

**Fix patterns when 3_Game needs settings from 5_Mission:**
- Use hardcoded constants in 3_Game instead of reading from settings
- Store settings in a shared 3_Game singleton (e.g., DayZGame subclass)
- Pass settings via method params at runtime (e.g., VPPCompassWidget applies colors in 5_Mission, passes them down)

**NEVER use `modded class` to modify a class defined in an earlier module of your OWN mod** — the compiler can't see the base class yet. Just inline the full implementation into the base class file.

Example that crashes:
```c
// 3_Game/Base.c
class ServerMarkersCache {
    void LoadCache() { /* stub */ }  // empty stub
}

// 4_World/ServerMarkersCache.c  — COMPILER ERROR: "Unknown type 'ServerMarkersCache'"
modded class ServerMarkersCache {
    override void LoadCache() { /* real impl */ }  // 4_World can't see 3_Game classes in own mod
}
```
**Fix:** Inline the 4_World implementation into the 3_Game base class. Delete the `modded class` file.

**REAL-WORLD EXAMPLE (ClientMarkersCache / ServerMarkersCache):**
A common pattern found in many DayZ mods is splitting cache logic: 3_Game has the base class with stub methods ("moved to 5_Mission"), and 5_Mission has `modded class` providing the real implementation. **This does NOT compile** — the Mission module can't "see" the 3_Game type when resolving `modded class`.

**Correct approach:** Put the FULL implementation in the 3_Game file. Both stubs AND modded implementations get inlined together. Delete all modded class files for these caches from 4_World and 5_Mission.

### 25. MissionGameplay HUD Initialization Timing
**PITFALL (verified broken):** `CallLater(this.InitHUDWidgets, 2000, false)` in the MissionGameplay constructor fires **during the loading screen** — before the world and player exist. Any HUD widget that reads settings, positions, or creates 3D markers will cause an **infinite loading hang**.

**Correct pattern — defer to OnInit():**
```c
class MissionGameplay extends MissionBase {
    void MissionGameplay() {
        // Constructor — only RPC registration, NO HUD/widget init
        Print("[VPPGroups] RPCs registered...");
        // DO NOT: GetGame().GetCallQueue(CALL_CATEGORY_GUI).CallLater(this.InitHUD, 2000, false);
    }

    override void OnInit() {
        super.OnInit();
        // HUD init AFTER world is fully loaded — not during loading screen
        GetGame().GetCallQueue(CALL_CATEGORY_GUI).CallLater(this.InitHUDWidgets, 1000, false);
    }
}
```
`OnInit()` fires after the mission is loaded and the player is in the world. The 1s CallLater gives the world a moment to finish initializing.

## Common errors and fixes

| Error message | Cause | Fix |
|---|---|---|
| `Multiple declaration of class 'X'` | Class defined in two files | Remove duplicate, extend existing |
| `Broken expression (missing ';'?)` | Ternary `? :` operator | Use `if/else` instead |
| `Broken expression (missing ';'?)` | C-style array literal `int[] x = {v}` | Use `ref array<int>` + `Insert()` |
| `Syntax error` on `int[]` declaration | C-style fixed array | Use `ref array<int>` |
| `Can't compile "Mission" script module` | Any above syntax errors | Check script.log for specific line |
| `Undefined function 'CGame.GetAdmins'` | `GetGame().GetAdmins()` doesn't exist in Enforce | Use JSON config file or VPPAdminTools integration instead |
| `Variable 'm_X' is private` | Accessing private member of another class | Add setter, make public, or pass via params |
| `Can't find variable 'X'` | Referencing a class from a later module | Move class to earlier module or restructure |
| `Unknown type 'X'` | `modded class` can't see base in own mod | Inline implementation into base class |

## Common Pitfalls
1. **Constructor adds items** — check before inserting (e.g., VPPEnhancedGroup constructor already adds leader)
2. **ref keyword** — use `ref` for class member variables of complex types
3. **Param types** — Param1<T>, Param2<T1,T2>, etc. for RPC serialization
4. **ScriptRPC** — `.Write()` to serialize, `.Read()` to deserialize, `.Send()` to transmit

## Notes
- `foreach` variable names cannot be reused in nested `foreach` in same scope — rename them
- `float` requires explicit casts (e.g., `int` → `float` with `.ToFloat()` on strings)
- Print() output goes to script.log, not .RPT — check both when debugging
- When the script compiler hits errors, it aborts the **entire module** — fix one file at a time, rebuild
- `Bool Expression` error can mean very different things — check the exact line in script.log

## Debugging workflow
1. `tail -f script*.log` for live compile feedback
2. `grep "SCRIPT.*(E)" script.log` for all errors
3. Filter for your mod: `grep "SCRIPT.*(E).*VanillaPPMap" script.log`
4. `Can't compile "X" script module` = first broken file killed the whole module
5. Fix errors from top to bottom — later errors may be cascading


## 2. Cross-Module Compilation


## Trigger Conditions
- "Can't compile" errors with "Unknown type" when a higher module (4_World, 5_Mission) defines a class that's already in a lower module (3_Game)
- `modded class X` fails because the base class X is defined in the same mod's own lower module
- Cross-module calls like 3_Game code trying to access 5_Mission classes (or vice versa)
- "Not enough parameters in function" — debug/fallback code using wrong API signatures

## Core Principles

### Module Load Order (strict, one-way)
DayZ compiles modules in sequence:
```
3_Game → 4_World → 5_Mission
```
- Lower modules **cannot** reference higher modules. `3_Game` code cannot see `5_Mission` classes.
- `modded class X` in a higher module **extends** the class from a lower module.
- BUT: you **cannot** `modded class X` in a higher module to extend a class that was **already fully defined** in your own mod's lower module — the compiler sees the same class from multiple compilation passes and gets confused.

### Consolidation Rule
If you have a pattern like:
```
3_Game/BaseClass.c    → class BaseClass { stub methods }
5_Mission/BaseClass.c → modded class BaseClass { real implementation }
```

This **will fail** because `5_Mission` can't properly extend its own mod's `3_Game` class during the Mission pass.

**Fix:** Move the full implementation into the 3_Game base class. Delete the 5_Mission `modded class` file entirely. The implementation should live in one place — always the lowest module that has access to all required dependencies.

### Duplicate Class Files
NEVER have the same class name in both a lower and higher module within the same mod. Example conflicts found:
- `ServerMarkersCache` in both `3_Game/Json/ClientMarkersCache.c` and `4_World/ServerMarkersCache.c`
- `ClientMarkersCache` in both `3_Game/Json/ClientMarkersCache.c` and `5_Mission/Json/ClientMarkersCache.c`

**Fix:** Keep only the 3_Game version. Add any implementation that was in the higher module into the 3_Game base. Delete the higher-module file.

### Private Member Access
DayZ EnforceScript doesn't have friend classes or inner-class access. Private members of a class (like `VPPMapConfig.m_CanUse3DMarkers`) cannot be accessed from **any** other class, even in the same module.

**Fix:** If `VPPMapConfig` doesn't have setter methods and you need to set defaults from within `ServerMarkersCache` (which uses `VPPMapConfig`), change the member from `private` to package-private (no modifier) in the model class.

### Dead Code Patterns to Avoid
- `Widget.GetType()` — doesn't exist in EnforceScript
- `MapWidgetPointer` — doesn't exist
- `CreateWidget(Vector, Vector, WidgetType)` with only 2D vectors — `Vector()` requires 3 params (x, y, z)
- Debug code referencing non-existent API methods — remove all debug/fallback paths that don't compile

## Step-by-Step Fix Process

1. **Read the crash log** — identify the compile module (Game/Mission/World) and the error type
2. **Locate all files** defining the problematic class across all modules
3. **Check module hierarchy** — is a higher module trying to mod a class from its own mod's lower module?
4. **Consolidate** — move implementation to the lowest module, delete higher-module duplicates
5. **Remove dead code** — kill any debug/fallback paths using non-existent APIs
6. **Fix private access** — change `private` to package-private if cross-class access is needed within same module
7. **Rebuild and re-check** — compile errors may cascade; fix one at a time

## Common Pitfalls
- Stub classes with `// Implementation moved to 5_Mission modded class` — don't use this pattern, it breaks compilation
- `modded class` on your own mod's classes — only use `modded class` for engine classes, never for your own mod's classes across modules
- Leaving dead debug print lines with API methods that don't exist — they compile to zero but still cause parse errors


## 3. UI/UX & Backend Design Principles

# DayZ Enforce Script UI/UX & Backend Design Principles

## Core Philosophy

**Design for DayZ players first, technical limitations second.** A flawless DayZ interface works within Enforce Script constraints while providing instant feedback, clear information hierarchy, and rock-solid stability that doesn't break immersion or cause crashes.

---

## DayZ Enforce Script UI/UX Design Principles

### 1. Performance-First Interface (Critical for DayZ)

**Rule:** Every interaction must feel instantaneous (<16ms per frame to maintain 60FPS).

- **Minimize DOM-like operations:** Avoid expensive widget creation/destruction per frame
- **Update throttling:** Only update expensive operations every N frames (use frame counters)
- **Skeleton states:** Show immediate feedback for button presses, not delayed responses
- **Progressive loading:** Load complex UI elements lazily (tab clicks, not Init())
- **Never block the main thread:** Offload calculations to timers or spread across frames
- **Chat append-only pattern:** Create one widget per message, cap at MAX_ITEMS, remove oldest
- **DateTime caching:** Cache expensive GetGame().GetDate() calls, don't call every frame

### 2. Accessibility within DayZ Constraints

**Rule:** Work within DayZ's limited accessibility features while maximizing usability.

- **Color contrast:** Ensure 4.5:1 minimum contrast for text (use sdf_Metron* fonts with outlines/shadows)
- **Touch targets:** Minimum 24x24 pixels (DayZ guideline), prefer 44x44px when possible
- **Keyboard navigation:** Logical tab order, visible focus indicators (custom outlines)
- **Error states:** Clear, immediate feedback with specific guidance (tooltips, color changes)
- **Reduced motion:** Provide option to disable animations via settings
- **Font scaling:** Respect user font size preferences when available
- **Semantic structure:** Logical widget hierarchy even without semantic HTML

### 3. Consistency & Predictability (DayZ Patterns)

**Rule:** Players should never guess what a widget does based on position or appearance.

- **LBmaster design system:** Strict adherence when creating admin/settings panels
- **Component reuse:** Base components for buttons, inputs, panels with consistent styling
- **Interaction standards:** Hover states (color/outline changes), press states (scale/color)
- **Naming consistency:** Clear, descriptive widget names matching their function
- **Error presentation:** Uniform error handling (tooltips, status bars, not silent failures)
- **Layout standards:** Exact pixel positioning with hexactpos/vexactpos flags where needed

### 4. Cognitive Load Reduction

**Rule:** Minimize mental effort required to achieve goals in-game.

- **Progressive disclosure:** Hide advanced settings behind "Advanced" toggles
- **Smart defaults:** Remember last-used values, intelligent first-run configurations
- **Contextual help:** Tooltips appear on hover, not buried in manuals
- **Visual hierarchy:** Size, color, and positioning guide eye to important information
- **Information scent:** Icons + labels clearly communicate function (no mystery meat)
- **Workflow optimization:** Minimize clicks, remember last tab/position, bulk operations

### 5. Error Prevention & Recovery (DayZ-Specific)

**Rule:** Assume players will misclick, misconfigure, or encounter lag; design accordingly.

- **Undo/redo:** Where possible (profile changes, not world state)
- **Confirmation dialogs:** For irreversible actions (delete profile, reset all settings)
- **Input validation:** Real-time, specific guidance ("Must be 1-100", not "Invalid")
- **Empty states:** Educational empty states that teach how to use the feature
- **Error recovery:** Clear paths forward from errors, never dead ends
- **Graceful degradation:** Core features work even when advanced features fail
- **Crash prevention:** Re-entrancy guards, null-safe widget access, lazy loading

---

## DayZ Enforce Script Backend Design Principles

### 1. Reliability & Fault Tolerance (Preventing Crashes)

**Rule:** Systems must remain operational despite player actions, lag, or edge cases.

- **Re-entrancy guards:** Use layoutRoot as Init() guard, not separate bool flags
- **Null-safe widget access:** Check every FindAnyWidget() result before calling methods
- **Lazy loading:** Defer sub-layout creation to first use (Ensure*Loaded() patterns)
- **Null-safe mission/hud checks:** Always check GetMission() && GetHud() before use
- **Data validation:** Validate all inputs (player IDs, distances, counts) at entry point
- **Timeouts + retries:** For server requests, with exponential backoff and limits
- **Graceful shutdown:** Clean Up() methods that null-check everything
- **Default fallbacks:** Sensible defaults when config loading fails

### 2. Scalability & Performance (Within DayZ Limits)

**Rule:** Optimize for 50-100 player servers without FPS impact.

- **Stateless where possible:** UI state in widgets, not global variables
- **Object pooling:** Reuse ChatLine/widgets instead of constant Create/Destroy
- **Efficient data structures:** Pre-allocated arrays, ring buffers for chat history
- **Virtualization concept:** Only create/draw visible list items, not entire lists
- **Frame budgeting:** Spread expensive operations across multiple frames
- **Cache strategically:** Recently accessed player data, not everything
- **Network efficiency:** Minimize RPC calls, batch changes when possible

### 3. Security by Design (Preventing Exploits)

**Rule:** Never trust client input; validate everything server-side.

- **Input validation:** Validate all RPC parameters (ranges, types, sanity checks)
- **Sanitization:** Strip dangerous characters from text inputs
- **Rate limiting:** Prevent spam from chat/commands (per-player, global)
- **Permission checks:** Verify player has right to perform action (admin, owner, etc.)
- **Secure defaults:** Deny by default, explicitly grant permissions
- **Anti-cheat considerations:** Validate impossible values (negative health, etc.)
- **Audit logging:** Log security-relevant actions (settings changes, bans)

### 4. Observability & Debuggability

**Rule:** You cannot fix what you cannot see in player reports.

- **Structured logging:** Consistent format with timestamps, player IDs, contexts
- **Error boundaries:** Try/catch equivalent patterns for script safety
- **Debug toggles:** Console commands to enable verbose logging
- **Performance markers:** Frame timing checks for expensive operations
- **State dumps:** Commands to dump current UI/state for debugging
- **Reproduction steps:** Clear logging of actions leading to errors

### 5. Maintainability & Evolvability

**Rule:** Code should be easy for future you (or other modders) to understand.

- **Single responsibility:** Each class/file handles one concern (config, UI, logic)
- **Clear abstractions:** Hide Enforce Script quirks behind clean interfaces
- **Consistent naming:** Predictable, descriptive names for functions/variables
- **Documentation:** Complex Enforce Script workarounds explained
- **Testing strategy:** Manual test plans for critical paths, edge case lists
- **Dependency awareness:** Know what other mods you depend on/isolation
- **Versioned configs:** Schema versioning for settings persistence

---

## DayZ Enforce Script UI/UX-Backend Integration

### 1. Contract-First Development (Within Constraints)

**Rule:** Define data flow before implementing UI or logic.

- **Data contracts:** Clear definitions of what data flows between UI/backend
- **Mock data:** Test UI with sample data before connecting to live systems
- **State synchronization:** Optimistic UI updates with server reconciliation
- **Loading states:** Clear spinners/progress for async operations (server requests)
- **Versioning:** Config/data versioning for backward compatibility

### 2. Data Flow & State Management

**Rule:** Single source of truth; avoid desync between UI and game state.

- **Owneritative source:** Server is truth for game state, UI reflects with delay
- **Client prediction:** UI shows immediate feedback, corrects when server responds
- **Interpolation:** Smooth movement/transitions between server updates
- **State reconciliation:** Correct UI when server state differs significantly
- **Dirty flags:** Only send updates when data actually changed
- **Change compression:** Batch multiple changes in single RPC when possible
- **Offline capability:** Queue local changes for sync when server connection drops

### 3. Performance Budget & Monitoring (DayZ-Specific)

**Rule:** Measure what matters to DayZ players.

- **Frame time:** Keep UI updates < 1ms to avoid FPS impact (aim for 0.1-0.5ms)
- **Widget count:** Monitor active widget count, aim for <200 complex widgets
- **Memory usage:** Watch for leaks from unreleased widgets/arrays
- **RPC frequency:** Track calls per second, keep reasonable (<10/sec per player)
- **Player feedback:** Observable smoothness, not just technical metrics
- **Server impact:** Monitor effect on server tick rate when scaling

---

## DayZ-Specific Validation Checklist

### UI/UX Validation (Enforce Script)
- [ ] All interactive widgets have clear hover/press/focus visual feedback
- [ ] Color contrast meets 4.5:1 minimum (test with sdf_Metron* + outline/shadow)
- [ ] Touch targets minimum 24x24px (prefer 44x44px for frequent use)
- [ ] Logical tab/navigation order for keyboard users
- [ ] Error messages are specific, actionable, and immediately visible
- [ ] Loading/spinner states shown for async operations (server requests)
- [ ] Empty states provide guidance, not just blank areas
- [ ] Respects `prefers-reduced-motion` equivalent (animation disable setting)
- [ ] Input validation provides real-time, specific feedback
- [ ] 404/500 equivalents show helpful navigation, not cryptic errors
- [ ] Font usage follows DayZ availability (Metron14, MetronBold16, etc.)

### Backend Validation (Enforce Script)
- [ ] All RPC handlers validate input parameters (type, range, sanity)
- [ ] Permission checks for all player-actions (not just admin functions)
- [ ] Rate limiting on chat/command inputs to prevent spam
- [ ] Data validation at all entry points (never trust client)
- [ ] Re-entrancy guards on all UI Init()/Show() methods
- [ ] Null-safe checks for all widget FindAnyWidget() results
- [ ] Lazy loading for sub-widgets (defer expensive CreateWidgets)
- [ ] Graceful shutdown with null-checks in Up()/Destroy() methods
- [ ] No hardcoded credentials/secrets in scripts
- [ ] Database/query equivalent: efficient data structures, no O(n²) loops

### Integration Validation (DayZ-Specific)
- [ ] Data contracts match between UI expectations and backend delivery
- [ ] Optimistic updates handle server corrections gracefully (no jumping)
- [ ] Loading states shown during all async server operations
- [ ] Error boundaries prevent UI crashes from backend failures
- [ ] Real-time updates work when available (RPC callbacks, not polling)
- [ ] Cache invalidation prevents stale data display (timers, version checks)
- [ ] Local queue syncs correctly when connection restored
- [ ] Feature flags allow safe rollback of problematic features
- [ ] Config/schema versioning tested for upgrades/downgrades

---

## Quick Reference: DayZ UI Patterns

### Correct UI Rendering Patterns

**Pattern 1: UIScriptedMenu + EnterScriptedMenu**
- Use for: Custom HUD overlays (compass, info panels, custom menus)
- **NOT for:** Chat display (use Pattern 2 unless you have full LBmaster infrastructure)

**Pattern 2: Modded Vanilla Classes**
- Use for: Replacing/extending existing vanilla UI (Chat, Player List)
- **Requires:** Full LBmaster infrastructure for Chat to work properly
- **Alternative:** UIScriptedMenu for chat when lacking LBmaster deps

### Layout Standards (LBmaster/Pixel-Perfect)

**Root Container:**
```xml
PanelWidgetClass YourRoot {
    visible 1
    position 0 0
    size 1 1              /* FILL container, don't use 0.96 0.9 */
    halign center_ref
    valign center_ref
    hexactpos 1
    vexactpos 1
    hexactsize 0
    vexactsize 0
    color 0.506 0.506 0.506 0.392  /* LBmaster overlay */
    style rover_sim_colorable
}
```

**2x2 Quadrant Grid (440px sidebar):**
```xmln/* Top-left */
PanelWidgetClass quadrant1 {
    ignorepointer 1
    position 0 30
    size 0.49 0.46     /* ~49% width, ~46% height */
    hexactpos 1
    vexactpos 1
    hexactsize 0
    vexactsize 0
    style LB_Clean_outline
}
```

**Button Pattern (LBmaster style):**
```xml
ButtonWidgetClass btnClose {
    position 2 2
    size 80 22         /* sized for sidebar, not full screen */
    halign right_ref
    hexactpos 1
    vexactpos 1
    hexactsize 1
    vexactsize 1
    text "#close"
    {
        PanelWidgetClass PanelWidgetClose {
            ignorepointer 1
            color 1 0.196 0.196 1
            size 1 1
            halign center_ref
            valign center_ref
            hexactpos 1
            vexactpos 1
            hexactsize 0
            vexactsize 0
            style LB_Clean_outline
        }
    }
}
```

### Critical DayZ Enforce Script Gotchas

- **Ternary operator** (`? :`) NOT supported — use `if/else`
- **Bit shift operators** (`>>`, `<<`) NOT supported — parse as string or use VectorMath
- **`int.ToHex()`** NOT a method — write helper using string substring
- **`SetColor()`** takes ARGB int, NOT color vector — never return Vector for SetColor()
- **`ARGBToColor()`** does NOT exist — `ARGB()` returns int directly
- **`SetKeyboardBusy(true)`** breaks chat input permanently — NEVER USE
- **`foreach` variable names** must be unique within same scope — rename duplicates
- **`switch` on enums** can fail — prefer `if/else`
- **Do NOT create BOTH** UIScriptedMenu AND modded vanilla for same system

### Performance Optimization Patterns

**Frame Throttling:**
```c
private int m_FrameCounter;

override void OnUpdate(float timeslice) {
    super.OnUpdate(timeslice);
    m_FrameCounter++;
    if (m_FrameCounter % 3 == 0) {
        UpdateExpensiveOperation();  /* every 3rd frame */
    }
    if (m_FrameCounter % 3 == 0) {
        UpdateLightOperation();      /* every 10th frame */
    }
}
```

**Chat Append-Only (No Memory Leak):**
```c
/* Create one widget per message */
Widget line = CreateWidgets("ChatItem.layout", chatContainer);
/* Cap at MAX_ITEMS */
if (chatWidgets.Count() >= MAX_ITEMS) {
    chatWidgets.Get(0).Unlink();     /* remove from display */
    chatWidgets.Remove(0);           /* remove from array */
}
chatWidgets.Insert(line);           /* add new */
```

**Null-Safe Widget Access:**
```c
Widget sidebar = layoutRoot.FindAnyWidget("Sidebar_Root");
if (sidebar) {
    sidebar.Show(true);  /* SAFE - checked for null */
}
/* NEVER: layoutRoot.FindAnyWidget("missing").Show(true); */
```

---

## File Organization (DayZ Mod Standard)

```
/addons/
  /yourmodname/
    /scripts/
      /* Your Enforce Script logic */
    /gui/
      /layouts/
        /* Your .layout files */
      /styles/
        /* Custom styles if needed */
    /data/
      /* Config, defaults, etc. */
```

### Layout File Standards
- **Paths:** Use FORWARD SLASHES, never backslashes
- **Textures:** Must be included in PBO build (verify with `pbo list`)
- **Colors:** ARGB hex format (#AARRGGBB)
- **Fonts:** Stick to verified DayZ fonts (Metron14, MetronBold16, etc.)
- **Coordinates:** Pixel-based, top-left origin (0,0)

---

## Implementation Notes

These principles combine:
- DayZ Enforce Script limitations and quirks
- LBmaster proven patterns (from their source)
- DayZ-specific performance constraints
- Mod safety and crash prevention
- Player experience within Arma Engine limits

Apply these principles iteratively: test with players, measure FPS impact, improve.
Flawless DayZ UI/UX is achievable within Enforce Script constraints through
careful attention to performance, clarity, and crash prevention.
---
