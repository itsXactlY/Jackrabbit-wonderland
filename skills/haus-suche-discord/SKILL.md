---
name: haus-suche-discord
description: Stündliche Suche nach freistehenden Häusern zur Miete via Camoufox + Immoscout + Kleinanzeigen → Discord
category: productivity
---

# Haus-Suche: Häuser zur Miete (Alleinlage)

Sucht automatisch nach freistehenden Häusern zur Miete und postet an Discord.

## Suchkriterien (STRENG!)
- **Budget:** IDEAL unter 1.000€ warm, MAXIMAL 1.300€ warm (oberste Schmerzgrenze)
- **Typ:** NUR freistehendes Einfamilienhaus, Bungalow, Landhaus, Bauernhaus, Fachwerkhaus
- **STRENGE KILLS:** Reihenhaus, DHH, Doppelhaus, MFH, Mehrfamilienhaus, Wohnung, Stadthaus, Ortszentrum, "suche/gesucht", Urlaub/Ferien, "Reserviert • Gelöscht"
- **Alleinlage:** Freistehend, keine direkten Nachbarn, ab vom Schuss
- **Haustiere:** User hat GROSSER RUDEL CHIHUAHUAS + Lou Trompetenkopf. "Keine Haustiere" = KILL. "Unbekannt" = posten aber markieren.
- **Haushalt:** 2 Personen, 2-3 Zimmer reichen, ab 70m²
- **Regionen (Priorität):** MeckPomm > Thüringen > Sachsen > Sachsen-Anhalt > Hessen
- **Mietkauf:** Bevorzugt, aber nicht Pflicht
- **Posting-Regel:** ALLES posten was potentiell passt — User schaut selbst!

## Tool: Camoufox (Anti-Detection Browser)

Venv: `~/.venvs/camoufox/`
Haupt-Script: `~/.hermes/skills/haus-suche-discord/scripts/haus_suche_ultimate.py`

### Camoufox Quick-Reference:
```python
from camoufox.sync_api import Camoufox
with Camoufox(headless=True) as browser:
    page = browser.new_page()
    page.goto('URL', timeout=30000)
    # Cookie-Dialog:
    try:
        btn = page.locator('button:has-text("Alle akzeptieren")')
        if btn.is_visible(timeout=3000): btn.click(); time.sleep(1)
    except: pass
    data = page.evaluate('JS_CODE')
    page.close()
```

## Quellen

### ✅ ImmobilienScout24 (Camoufox)
**Funktioniert!** Kein CAPTCHA mit Camoufox. ABER: IP kann temporär blockiert werden bei zu vielen Requests. Pausen einhalten!

Such-URL-Format:
```
https://www.immobilienscout24.de/Suche/de/{region}/haus-mieten?price=-1350.0&buildingfreestanding=1
```
Region-Slugs: `mecklenburg-vorpommern`, `thueringen`, `sachsen`, `sachsen-anhalt`, `hessen`

### ✅ Kleinanzeigen.de (Camoufox)
Zuverlässig. Cookie-Dialog + JS-Extraktion funktioniert.

### ❌ Nicht funktionierend (zu viele Requests von IP):
- Google, Bing, DuckDuckGo → CAPTCHA
- Immowelt → DataDome
- Startpage → teilweise OK für Dork-Suche

## Alternative Quellen (entdeckt via DDG/Startpage)

### Spezialisierte Alleinlage-Portale:
- `https://www.alleinlage-immobilien.de/` — hat "Mieten" Kategorie (aber oft leer)
- `https://www.alleinlage-immo.de/` — FUXGRUPPE Spezialportal
- `https://www.immokralle.com/immobilien/de/alleinlage` — 800+ Alleinlage, meist KAUF
- `https://www.ohne-makler.net/themen/besondere-lage/alleinlage/` — provisionsfrei

### Immobilien-Suchmaschinen:
- `https://www.immosuchmaschine.de/b/{region}/haus-mieten` — Cookie-Akzeptanz nötig!
- `https://immosurf.de/mieten/haus/{region}` — hat "Pet Friendly" Filter!
- `https://www.immobilo.de/mieten/haus/{region}` — 105+ Ergebnisse MP
- `https://de.trovit.com/immobilien/mieten-haus-alleinlage-land-{region}` — Aggregator
- `https://www.nestoria.de/haus/mieten/{region}`

### Zwischenmiete/Übergang:
- `https://wunderflats.com` — Zwischenmiete, auch Alleinlage (Rügen gefunden!)

### Facebook Gruppen:
- `https://www.facebook.com/groups/suche.wohnung.haus.zur.miete.mecklenburgvorpomme`
- `https://www.facebook.com/groups/suche.wohnung.haus.zum.mieten.thueringen/`
- `https://www.facebook.com/groups/Ruegen.Immo/`

### Makler mit Mietangeboten:
- RTL Immobilien (Bad Lobenstein): `https://www.rtl-immobilien.de/Mietangebote.htm`
- Antaris (Erfurt): `https://www.antaris-immobilien.de/immobilien/?kategorie=vermietung`
- Anhalt-Immobilien: `https://www.anhalt-immobilien.de/immobilien/miete/`
- AW Weilburg: `https://www.aw-immobilienmakler.de/Mietangebote.htm`

## DuckDuckGo Dorking (via Camoufox — NICHT curl!)

DDG blockt curl aber funktioniert im Camoufox-Browser. Startpage auch.

```python
# DDG Suche
page.goto(f'https://duckduckgo.com/?q={encoded}&kl=de-de&ia=web', timeout=15000)
time.sleep(2)
# Links extrahieren (NICHT über article Selector — der ist kaputt!)
links = page.evaluate('''() => {
    const items = [];
    document.querySelectorAll('a').forEach(a => {
        if (a.href && !a.href.includes('duckduckgo.com') && a.textContent.trim().length > 10) {
            items.push({title: a.textContent.trim().substring(0,120), url: a.href});
        }
    });
    return items;
}''')
```

### Gute Dork-Queries:
- `freistehendes haus mieten alleinlage {region}`
- `haus mieten keine nachbarn`
- `bungalow mieten alleinlage`
- `mietkauf haus alleinlage`
- `immobilienmakler {region} haus mieten`
- `facebook gruppe haus mieten {region}`

## Immoscout Body-Text Fallback

Wenn document.querySelector für Beschreibung nicht funktioniert:
```python
body = page.inner_text('body')
desc_start = body.find('Beschreibung')
if desc_start < 0: desc_start = body.find('€\n')
desc = body[desc_start:desc_start+500] if desc_start > 0 else body[300:800]
```

## Marktlage (KRITISCH!)
**Echte Alleinlage-Häuser zur Miete unter 1.350€ existieren auf den Portalen quasi NICHT.**
Die allermeisten Alleinlage-Objekte werden VERKAUFT, nicht vermietet.
Wer ein freistehendes Haus in Alleinlage hat, vermietet es nicht über Immoscout/Kleinanzeigen.
Das bedeutet: Der Cron-Job wird selten echte Treffer finden. Das ist kein Bug — das ist der Markt.

## ImmobilienScout24 DOM-Struktur (KRITISCH!)

### Suchergebnisse:
- Container: `.listing-card` (NICHT `article` oder `[data-item-id]`)
- Expose-ID: `data-obid` Attribut auf dem Card-Element
- Expose-URL bauen: `https://www.immobilienscout24.de/expose/{data-obid}`
- Title: `h3` oder `h2` innerhalb der Card
- Preis/Fläche/Zimmer: `dd` Elemente (nacheinander)
- Location: `[class*=address]` oder `[class*=locality]`

### Listings extrahieren:
```javascript
const items = [];
document.querySelectorAll('.listing-card').forEach(card => {
    const id = card.getAttribute('data-obid');
    const title = card.querySelector('h3,h2')?.textContent?.trim();
    const dds = Array.from(card.querySelectorAll('dd')).map(d=>d.textContent.trim());
    const loc = card.querySelector('[class*=address],[class*=locality]')?.textContent?.trim()||'';
    if (id && title) items.push({
        id, title, location: loc,
        price: dds[0]||'?', sqm: dds[1]||'', rooms: dds[2]||'',
        url: 'https://www.immobilienscout24.de/expose/'+id
    });
});
```

### Detail-Seite extrahieren (Expose):
```javascript
const d = {title:'',price:'',location:'',description:'',attrs:{}};
d.title = document.querySelector('h1')?.textContent?.trim();
d.price = document.querySelector('h2[class*=price],#contactBoxTop .font-bold')?.textContent?.trim();
d.location = document.querySelector('[data-qa="locality"],[id*=locality],.zip-region-and-country')?.textContent?.trim();
d.description = document.querySelector('#viewad-description-text,[data-qa="description"] p,[class*=description] p')?.textContent?.trim()?.substring(0,600);
document.querySelectorAll('[class*=criterions] li,dl dt,dl dd,[class*=key-fact]').forEach(el => {
    d.attrs[el.className?.substring(0,30)||'x'] = el.textContent?.trim()?.substring(0,60);
});
```

## Kleinanzeigen.de DOM-Struktur

### Suchergebnisse:
- Container: `article[class*=aditem]`
- Title/Link: `a[class*=ellipsis]`
- Price: `[class*=price]`
- Location: `[class*=top--left]`

### Detail-Seite:
- Attributes: `[class*=addetailslist--detail]` oder `[class*=keyFacts--detail]`
- Fallback DFP-Targets: `"Haustyp": "einfamilienhaus"` in Page-Scripts

```javascript
// DFP Fallback für Haustyp/Warmmiete
try { for (const s of document.querySelectorAll('script')) {
    const t = s.textContent;
    const hm = t.match(/"Haustyp"\s*:\s*"([^"]+)"/);
    if (hm && !d.attrs['Haustyp']) d.attrs['Haustyp'] = hm[1];
    const wm = t.match(/"Warmmiete"\s*:\s*"([^"]+)"/);
    if (wm && !d.attrs['Warmmiete']) d.attrs['Warmmiete'] = wm[1]+' €';
}} catch(e) {}
```

## Filter-Logik

### alleinlage_score() — Score 0-10:
- +2 pro Hit: alleinlage, einzellage, alleinstehend, keine nachbarn, waldrand, waldhaus, im wald, eigener feldweg, abgelegen, abgeschieden, einsam, außerhalb, naturgrundstück
- +1 pro Hit: freistehend, bungalow, landhaus, bauernhaus, gehöft, fachwerkhaus
- -3 pro Hit: ortslage, ortsmitte, zentrum, hauptstraße, reihenhaus, doppelhaus

### haustier_check():
- VERBOTEN: "keine haustiere", "haustiere nicht", "haustiere verboten"
- OK: "haustiere erlaubt/willkommen/möglich", "hunde erlaubt", "haustiere jeder art"
- UNBEKANNT → OK (nehmen wir an)

### Preis: ideal unter 1.000€, max 1.300€ warm (Mietkauf: max 1.500€)

## Discord Webhook
```
https://discord.com/api/webhooks/1164313161093103716/swOaRW2QRNf82uZxIHtcONb15zizkfhmgITeSFINAJaWgLGl0i-GPvKAaoBz6Z2VWvs7
```

## Cron-Job
`haus-suche-stuendlich` (ID: b67413523bfa) — stündlich
```bash
cd ~/.hermes/skills/haus-suche-discord/scripts && ~/.venvs/camoufox/bin/python haus_suche_ultimate.py
```

## KRITISCHE REGELN
1. **URLs NIEMALS abschneiden!** Immer vollständige URL posten.
2. **Cookie-Dialog** muss bei jeder neuen Browser-Session akzeptiert werden.
3. **Pausen** zwischen Requests: Immoscout 1s, Kleinanzeigen 0.2s
4. **IP-Schutz:** Bei Blockierung → warten, nicht weiter bombardieren.
5. Bei Fehler mit Quelle → nächste Quelle, nicht abbrechen.
6. **ALLES posten** was potentiell interessant ist — User schaut selbst!

## Wiki-Integration

Gefundene Häuser werden als Wiki-Seiten in `~/wiki/entities/` gespeichert.
Format siehe `~/wiki/SCHEMA.md`. Status-Tracking: NEU → KONTAKTIERT → BESICHTIGT → ABGELEHNT/ZUGESAGT.

Nach jedem Cron-Lauf: Neue Treffer als Entity-Seiten anlegen, index.md updaten, log.md Eintrag.

## Gelernte Lektionen (wichtig!)
- Headless-Browser haben KEINE Cookies/Sessions — werden als Bot erkannt
- ImmobilienScout24 blockiert temporär, aber Camoufox kann es nach Wartezeit umgehen
- Echte Alleinlage-Häuser auf Kleinanzeigen sind EXTREM SELTEN
- Google/Bing/DuckDuckGo blocken Headless IPs komplett
- Residential Proxy wäre optimal (~10-50€/Monat) für Immoscout + Immowelt + Google
- Chrome Remote Debugging (`--remote-debugging-port=9222`) kann helfen, aber nur mit GUI-Chrome (nicht headless)
- Firefox Remote Debugging nutzt WebDriver BiDi, NICHT Chrome CDP — Playwright kann sich nicht per CDP mit Firefox verbinden
