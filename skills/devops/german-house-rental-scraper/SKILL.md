---
name: german-house-rental-scraper
title: German House Rental Scraper
description: Search for freestanding houses for rent in Germany, filter by criteria, post to Discord webhook. Hourly cron capable.
---

# German House Rental Scraper

Search for houses (Haus mieten) across German real estate portals with specific criteria, post results to Discord.

## Trigger
When user wants: Haus mieten, freistehendes Haus, house rental Germany, ländliches Haus mieten.

## Portal Landscape (tested 2026-04-08)

### WORKING Portals
1. **Kleinanzeigen.de** ✅ — best source, no bot detection, curl works fine
   - URL pattern: `https://www.kleinanzeigen.de/s-haus-mieten/{region-slug}/preis::{max-price}/c203`
   - Region slugs: `mecklenburg-vorpommern`, `thueringen`, `sachsen`, `sachsen-anhalt`, `hessen`
   - Category `c203` = Immobilien/Mieten (NOT house-specific — must filter post-scrape)
   - Parse with: `re.findall(r'<article[^>]*class="[^"]*aditem[^"]*"[^>]*>(.*?)</article>', html, re.DOTALL)`

2. **Browser-based** (ImmobilienScout24, Immowelt) — can work via browser_navigate but:
   - ImmobilienScout24: CAPTCHA blocks curl; browser_navigate hits CAPTCHA too
   - Immowelt: returns 410 Gone on most URLs; Thüringen sometimes works
   - Immonet: redirects to Immowelt

### BLOCKED Portals
- ImmobilienScout24 — aggressive CAPTCHA, no residential proxies
- Immowelt — 410 Gone / 403 on most region URLs
- Immonet — redirects to Immowelt
- immobilien.de — 404 on all tested paths
- wohnungsbörse.de — connection refused

## Scraping Approach

### Step 1: Fetch Kleinanzeigen per region
```python
import subprocess, re, json

regions = {
    "MeckPomm": "mecklenburg-vorpommern",
    "Thueringen": "thueringen",
    "Sachsen": "sachsen",
    "SachsenAnhalt": "sachsen-anhalt",
    "Hessen": "hessen"
}

for name, slug in regions.items():
    url = f"https://www.kleinanzeigen.de/s-haus-mieten/{slug}/preis::1100/c203"
    result = subprocess.run(
        ["curl", "-s", "-L", "--max-time", "15",
         "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
         "-H", "Accept-Language: de-DE,de;q=0.9", url],
        capture_output=True, text=True, timeout=20)
    html = result.stdout
```

### Step 2: Parse articles
```python
articles = re.findall(
    r'<article[^>]*class="[^"]*aditem[^"]*"[^>]*>(.*?)</article>',
    html, re.DOTALL)
```

### Step 3: Extract fields per article
```python
title_match = re.search(r'<a[^>]*class="[^"]*ellipsis[^"]*"[^>]*>([^<]+)</a>', article)
link_match = re.search(r'href="(/s-anzeige/[^"]+)"', article)
price_match = re.search(r'<[^>]*class="[^"]*aditem-main--middle--price[^"]*"[^>]*>([^<]+)</[^>]+>', article)
location_match = re.search(r'<[^>]*class="[^"]*aditem-main--top--left[^"]*"[^>]*>([^<]+)</[^>]+>', article)
```

### Step 4: Filter for houses
Kleinanzeigen c203 includes ALL rentals (apartments too). Must filter by keywords:
```python
house_keywords = ['haus', 'freistehend', 'einfamilien', 'alleinlage', 'bauernhof',
                  'landhaus', 'mietkauf', 'doppelhaus', 'reihenhaus',
                  'hof', 'gut', 'villa', 'landanwesen', 'forsthaus', 'mühle']
if any(kw in title.lower() for kw in house_keywords):
    results.append({...})
```

### Step 5: Also search with specific keywords
```
https://www.kleinanzeigen.de/s-alleinlage/{slug}/preis::1100/c203
https://www.kleinanzeigen.de/s-freistehend/{slug}/preis::1100/c203
https://www.kleinanzeigen.de/s-einfamilienhaus-mieten/{slug}/preis::1100/c203
```

## Discord Webhook Posting

```python
import json, subprocess

WEBHOOK_URL = "https://discord.com/api/webhooks/..."

def post_to_discord(title, description, url):
    payload = json.dumps({
        "embeds": [{
            "title": title,
            "description": description,
            "url": url,
            "color": 5814783  # purple
        }]
    })
    subprocess.run([
        "curl", "-X", "POST", "-H", "Content-Type: application/json",
        "-d", payload, WEBHOOK_URL
    ], capture_output=True)
```

## Cron Setup

```python
cronjob(action='create',
    name='haus-suche-deutschland',
    schedule='1h',
    deliver='local',
    prompt='Search Kleinanzeigen.de for freistehende Häuser zur Miete in MeckPomm, Thüringen, Sachsen, Sachsen-Anhalt, Hessen (max 1100€ warm, prefer Mietkauf). Post new finds to Discord webhook. See skill: german-house-rental-scraper.')
```

## Deduplication
Store seen URLs in a file (`~/.hermes/haus-suche/seen_urls.json`) to avoid reposting.

## Pitfalls
- Kleinanzeigen c203 is NOT house-specific — heavy filtering needed
- Many results are sponsored/promoted (TOP tags) — may not be relevant
- Immowelt/Immonet unreliable via curl — use browser_navigate as fallback but expect bot detection
- Title parsing may miss entries with unconventional formatting
- "Maisonette" in title is usually an apartment, not a house — filter carefully
