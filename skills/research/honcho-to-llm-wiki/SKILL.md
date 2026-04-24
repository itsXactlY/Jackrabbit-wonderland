---
name: honcho-to-llm-wiki
description: "Migrate Honcho database exports to LLM Wiki (Karpathy pattern). Extracts personal info, projects, technical details from 250MB+ exports into structured markdown pages."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [wiki, knowledge-base, honcho, migration, data-extraction]
    category: research
---

# Honcho to LLM Wiki Migration

Migrate data from Honcho AI memory database exports into a Karpathy-style LLM Wiki with structured markdown pages and wikilinks.

## When This Skill Activates

Use this skill when the user:
- Wants to migrate Honcho data to their wiki
- Asks to extract information from honcho_export/ directory
- References prior_memory_file entries or wants to organize conversation history

## Prerequisites

- Honcho export at `/home/alca/honcho_export/` (250MB+)
  - `messages.json` (31MB) - 21,515+ messages
  - `documents.json` (656KB) - 64 documents
  - `prior_memory_file` entries embedded in messages
- LLM Wiki initialized (default: `~/llm-wiki/`)
- Python with json module

## CRITICAL FINDING: Where the Real Data Is

**The documents table (64 docs) is NOT where the valuable data lives.**

The goldmine is in `messages.json`:
- **prior_memory_file entries** (22 total): Consolidated user profiles with projects, preferences, technical details
- **497+ messages** contain personal information (favorite color, pets, projects)
- Documents table has mostly test entries and system observations

## Data Extraction Priority

1. **prior_memory_file entries** (HIGHEST PRIORITY)
   - Contains: user profile, technical skills, workflow patterns, project status, corrections
   - Search: `messages.json` for `<prior_memory_file>` tag
   - Sort by length to find most complete entry

2. **Personal information messages**
   - Keywords: "favorite", "my name", "I am", "I like", "my dog", "my pet"
   - Filter by `peer_name: alca`

3. **Project-specific messages**
   - Search for project names (BTQuant, DayZ, LBMaster, etc.)
   - Extract technical decisions and bug reports

4. **documents.json** (LOWEST PRIORITY)
   - Mostly test conclusions and system observations
   - Some user behavior patterns, but sparse

## Migration Process

### Step 1: Analyze prior_memory_file

```python
import json

with open('/home/alca/honcho_export/messages.json', 'r') as f:
    messages = json.load(f)

prior_files = [m for m in messages if '<prior_memory_file>' in m.get('content', '')]
prior_files.sort(key=lambda x: len(x['content']), reverse=True)

# Most complete entry is usually the best
best = prior_files[0]
print(best['content'])
```

### Step 2: Categorize Personal Information

```python
categories = {
    'preferences': ['favorite', 'lieblings', 'like', 'love'],
    'identity': ['my name is', 'i am', 'call me'],
    'projects': ['i work on', 'working on', 'project'],
    'pets': ['my dog', 'my pet', 'have a'],
    'technical': ['i know', 'i use', 'i develop']
}

categorized = {}
for msg in messages:
    if msg['peer_name'] != 'alca':
        continue
    content = msg['content'].lower()
    for cat, keywords in categories.items():
        if any(k in content for k in keywords):
            categorized.setdefault(cat, []).append(msg)
```

### Step 3: Create Wiki Pages

Follow LLM Wiki conventions:
- YAML frontmatter with title, created, updated, type, tags, sources
- Wikilinks `[[entity-name]]` between related pages (minimum 2 per page)
- Update `index.md` and `log.md` after each page

### Step 4: Store Raw Sources

Save complete prior_memory_file to `raw/honcho-prior-memory-file.md`

## Wiki Page Structure

```
~/llm-wiki/
├── SCHEMA.md
├── index.md
├── log.md
├── entities/
│   ├── alca.md           # User profile
│   ├── btquant.md        # Projects
│   ├── dayz-modding.md
│   ├── hermes.md         # Agent
│   ├── lbmaster.md
│   ├── ralph.md
│   ├── hotspine.md
│   └── trading-terminal.md
├── concepts/
│   └── ui-ux-design.md   # Technical concepts
└── raw/
    └── honcho-prior-memory-file.md
```

## Key Information to Extract

From prior_memory_file (typical structure):
- **User profile**: expertise level, communication style, tech stack
- **Enforce Script constraints**: language limitations and workarounds
- **Workflow patterns**: tool-first, existing-infra-first, doc-first
- **Corrections & boundaries**: security rules, bug fixes, linter configs
- **Project status**: BTQuant, DayZ, LBMaster, Ralph
- **Discord integration**: gateway config, cron jobs, API issues
- **UI/UX specifics**: DayZ font issues, widget patterns, layout coords

## Pitfalls

- **Don't just query documents table** - prior_memory_file in messages is the real data
- **Sort prior_memory_file by length** - longest entry usually has most complete profile
- **Filter by peer_name** - only extract from 'alca' for user info, not 'hermes' responses
- **Update index.md and log.md** - wiki degrades without navigation updates
- **Preserve wikilinks** - every page needs 2+ outbound links to other pages

## Example Output

After migration, the wiki should contain:
- 8-10 entity pages (user, projects, agent)
- 1-2 concept pages (UI/UX design principles)
- Complete frontmatter with sources pointing to honcho_export
- Cross-linked entities via wikilinks
- Raw source preservation for reference
