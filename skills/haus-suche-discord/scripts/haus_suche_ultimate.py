#!/usr/bin/env python3
"""
Haus-Suche ULTIMATE: Camoufox + ImmobilienScout24 + Kleinanzeigen
"""
import json, subprocess, re, time, sys
sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1164313161093103716/swOaRW2QRNf82uZxIHtcONb15zizkfhmgITeSFINAJaWgLGl0i-GPvKAaoBz6Z2VWvs7"
BUDGET = 1300

REGIONS = [
    ('MeckPomm', 'mecklenburg-vorpommern', 'l4276'),
    ('Thüringen', 'thueringen', 'l9684'),
    ('Sachsen', 'sachsen', 'l4711'),
    ('Sachsen-Anhalt', 'sachsen-anhalt', 'l8646'),
    ('Hessen', 'hessen', 'l4279'),
]

def price_num(s):
    nums = re.findall(r'[\d]+', str(s).replace('.','').replace(',',''))
    return int(nums[0]) if nums else 0

def haustier_ok(d):
    t = f"{d.get('title','')} {d.get('description','')}".lower()
    if any(v in t for v in ['keine haustiere','haustiere nicht','haustiere verboten']): return 'verboten'
    if any(e in t for e in ['haustiere erlaubt','haustiere willkommen','haustiere möglich','hunde erlaubt','haustiere jeder art','haustiere aller art','haustiere kein problem','haustiere nach vereinbarung']): return 'ok'
    return 'unbekannt'

def alleinlage_score(d):
    t = f"{d.get('title','')} {d.get('description','')}".lower()
    score = 0
    for kw in ['alleinlage','einzellage','alleinstehend','keine nachbarn','ohne nachbarn','waldrand','waldhaus','im wald','waldnähe','eigener feldweg','abgelegen','abgeschieden','einsam','außerhalb','naturgrundstück','kein direkter nachbar']:
        if kw in t: score += 2
    for kw in ['freistehend','bungalow','landhaus','bauernhaus','gehöft','fachwerkhaus']:
        if kw in t: score += 1
    for kw in ['ortslage','ortsmitte','zentrum','hauptstraße','reihenhaus','doppelhaus']:
        if kw in t: score -= 3
    return max(0, score)

def post_discord(msgs):
    for m in msgs:
        subprocess.run(["curl","-s","-X","POST",WEBHOOK_URL,"-H","Content-Type: application/json","-d",json.dumps({"content":m})], capture_output=True, timeout=15)
        time.sleep(1)

# Listing-level kill keywords (title + card text)
LISTING_KILLWORDS = ['suche','gesucht','sucht','suchen','reihenhaus','reihenendhaus',
                     'doppelhaushälfte','doppelhaus','wohnung','apartment','mehrfamilien',
                     'urlaub','ferien','gewerbe']

HARD_KILLS = ['reihenhaus','reihenmittelhaus','reiheneckhaus','reihenendhaus',
              'doppelhaushälfte','doppelhaus','doppel-haus',
              'mehrfamilienhaus','mehrfamilien','mfh',
              'wohnung','apartment','dachgeschosswohnung',
              'ortslage','ortsmitte','zentrum','stadtteil','stadtmitte',
              'hauptstraße','durchgangsstraße',
              'suche','gesucht','urlaub','ferien',
              'galerie','werkskantine','bahnhofshotel','sanierungsobjekt',
              'pflegeheim','gewerbe','büro','praxis',
              'siedlung','dorfzentrum','dorfmitte',
              'in der stadt','stadtbus','innenstadt']

def main():
    from camoufox.sync_api import Camoufox

    with Camoufox(headless=True) as browser:
        page = browser.new_page()
        seen = set()
        all_listings = []

        # ===== KLEINANZEIGEN =====
        print("=== KLEINANZEIGEN ===")
        ka_urls = []
        for region_name, _, loc_id in REGIONS:
            for kw in ['alleinlage','einzellage','freistehend','wald','bungalow','bauernhaus']:
                ka_urls.append((region_name, f'https://www.kleinanzeigen.de/s-{kw}/{loc_id}/preis::1350/c205{loc_id}'))
        ka_urls.append(('DE-weit', 'https://www.kleinanzeigen.de/s-alleinlage-haus/preis::1350/c205'))
        ka_urls.append(('DE-weit', 'https://www.kleinanzeigen.de/s-waldhaus/preis::1350/c205'))

        for region_name, url in ka_urls:
            try:
                page.goto(url, timeout=12000)
                try:
                    btn = page.locator('button:has-text("Alle akzeptieren")')
                    if btn.is_visible(timeout=2000): btn.click(); time.sleep(0.5)
                except: pass

                listings = page.evaluate('''() => {
                    const items = [];
                    document.querySelectorAll('article[class*=aditem]').forEach(a => {
                        const t = a.querySelector('a[class*=ellipsis]')?.textContent?.trim();
                        const l = a.querySelector('a[class*=ellipsis]')?.href;
                        const p = a.querySelector('[class*=price]')?.textContent?.trim();
                        const loc = a.querySelector('[class*=top--left]')?.textContent?.trim();
                        if (t && l) items.push({title:t,price:p||'?',location:loc||'?',url:l});
                    });
                    return items;
                }''')
                added = 0
                for l in listings:
                    if l['url'] not in seen:
                        tl = l.get('title','').lower()
                        if any(k in tl for k in LISTING_KILLWORDS):
                            continue
                        seen.add(l['url'])
                        l['source'] = 'KA'
                        l['region'] = region_name
                        all_listings.append(l)
                        added += 1
                if added > 0:
                    print(f"  {region_name}: +{added}")
                time.sleep(0.2)
            except Exception as e:
                continue

        # ===== IMMSCOUT =====
        print("\n=== IMMOSCOUT ===")
        for region_name, region_slug, _ in REGIONS:
            url = f'https://www.immobilienscout24.de/Suche/de/{region_slug}/haus-mieten?price=-1300.0&buildingfreestanding=1'
            try:
                page.goto(url, timeout=25000)
                time.sleep(2)
                try:
                    btn = page.locator('button:has-text("Alle akzeptieren")')
                    if btn.is_visible(timeout=3000): btn.click(); time.sleep(1)
                except: pass

                body_text = page.evaluate('() => document.body?.innerText?.substring(0,300) || ""')
                if 'captcha' in body_text.lower() or 'gesperrt' in body_text.lower():
                    print(f"  {region_name}: BLOCKED")
                    continue

                listings = page.evaluate('''() => {
                    const items = [];
                    document.querySelectorAll('.listing-card').forEach(card => {
                        const id = card.getAttribute('data-obid');
                        const title = card.querySelector('h3,h2')?.textContent?.trim();
                        const cardText = card.textContent?.trim()?.substring(0,300) || '';
                        const dds = Array.from(card.querySelectorAll('dd')).map(d=>d.textContent.trim());
                        const loc = card.querySelector('[class*=address],[class*=locality]')?.textContent?.trim()||'';
                        if (id && title) items.push({
                            id, title, location: loc, cardText,
                            price: dds[0]||'?', sqm: dds[1]||'', rooms: dds[2]||'',
                            url: 'https://www.immobilienscout24.de/expose/'+id
                        });
                    });
                    return items;
                }''')

                added = 0
                for l in listings:
                    if l['url'] not in seen:
                        tl = l.get('title','').lower() + ' ' + l.get('cardText','').lower()
                        if any(k in tl for k in LISTING_KILLWORDS):
                            continue
                        seen.add(l['url'])
                        l['source'] = 'Immoscout'
                        l['region'] = region_name
                        all_listings.append(l)
                        added += 1
                print(f"  {region_name}: +{added}")
                time.sleep(1)
            except Exception as e:
                print(f"  {region_name}: ERR {str(e)[:40]}")

        print(f"\nTotal filtered listings: {len(all_listings)}")

        # ===== DETAIL-SCRAPING =====
        MAX_DETAIL = 60
        scrape_list = all_listings[:MAX_DETAIL]
        print(f"\n=== DETAIL {len(scrape_list)}/{len(all_listings)} ===")
        results = []

        for i, item in enumerate(scrape_list):
            try:
                page.goto(item['url'], timeout=8000)
                time.sleep(0.3)

                detail = page.evaluate('''() => {
                    const d = {title:'',price:'',location:'',description:'',attrs:{}};
                    d.title = document.querySelector('h1')?.textContent?.trim()?.replace(/^Reserviert\\s*[•·]\\s*Gelöscht\\s*[•·]\\s*/,'');
                    d.price = document.querySelector('h2[class*=price],#contactBoxTop .font-bold,[class*=price-detail]')?.textContent?.trim();
                    d.location = document.querySelector('[data-qa="locality"],[id*=locality],.zip-region-and-country')?.textContent?.trim();
                    d.description = document.querySelector('#viewad-description-text,[data-qa="description"] p,[class*=description] p,[id*=description] p,[class*=adDescriptionText]')?.textContent?.trim()?.substring(0,800);
                    
                    document.querySelectorAll('[class*=criterions] li,dl dt,dl dd,[class*=key-fact]').forEach(el => {
                        d.attrs[el.className?.substring(0,30)||'x'] = el.textContent?.trim()?.substring(0,60);
                    });
                    document.querySelectorAll('[class*=addetailslist--detail],[class*=keyFacts--detail]').forEach(el => {
                        const parts = el.textContent.trim().split('\\n').map(s=>s.trim()).filter(Boolean);
                        if (parts.length>=2) d.attrs[parts[0]] = parts.slice(1).join(' ');
                    });
                    try { for (const s of document.querySelectorAll('script')) {
                        const t = s.textContent;
                        const hm = t.match(/"Haustyp"\\s*:\\s*"([^"]+)"/);
                        if (hm && !d.attrs['Haustyp']) d.attrs['Haustyp'] = hm[1];
                        const wm = t.match(/"Warmmiete"\\s*:\\s*"([^"]+)"/);
                        if (wm && !d.attrs['Warmmiete']) d.attrs['Warmmiete'] = wm[1]+' €';
                    }} catch(e){}
                    return d;
                }''')

                # Body fallback
                if not detail or not detail.get('title'):
                    try:
                        body = page.evaluate('() => document.body?.innerText?.substring(0,2000) || ""')
                        if len(body) > 200:
                            detail = detail or {}
                            h1 = page.evaluate('() => document.querySelector("h1")?.textContent?.trim() || ""')
                            if h1:
                                detail['title'] = h1
                                idx = body.find('€\n') if '€\n' in body else body.find('€ ')
                                detail['description'] = body[idx:idx+500].strip() if idx > 0 else body[300:800].strip()
                    except: pass

                if not detail or not detail.get('title'):
                    continue

                full = f"{detail.get('title','')} {detail.get('description','')} {str(detail.get('attrs',{}))}".lower()

                # Check Typ field specifically
                typ = detail.get('attrs',{}).get('Typ','').lower()
                if any(k in typ for k in ['doppelhaus','reihenhaus','mehrfamilien','wohnung']):
                    print(f"  [{i+1}] TYP-KILL: {typ} - {detail.get('title','')[:40]}")
                    continue

                killed = [k for k in HARD_KILLS if k in full]
                if killed:
                    print(f"  [{i+1}] KILLED: {killed[0]} - {detail.get('title','')[:40]}")
                    continue

                alleinlage_beweise = ['alleinlage','einzellage','alleinstehend',
                    'keine nachbarn','ohne nachbarn','kein direkter nachbar','nachbarfrei',
                    'keine direkten nachbarn','nachbarfreie lage',
                    'waldrand','waldhaus','waldgrundstück','im wald','waldnähe','mitten im wald',
                    'eigener feldweg','eigener zugang','eigenes grundstück',
                    'abgelegen','abgeschieden','einsam','isoliert',
                    'außerhalb','außerhalb des ortes','außerhalb der ortschaft',
                    'naturgrundstück','freie sicht','kein überblick',
                    'abseits','fernab','einzeln stehend','kein nachbar',
                    'ländlich','ruhige lage','natur']
                if not any(b in full for b in alleinlage_beweise):
                    continue

                warm = detail.get('attrs',{}).get('Warmmiete','')
                wn = price_num(warm) if warm else price_num(item.get('price',''))
                if wn > BUDGET: continue

                ht = haustier_ok(detail)
                if ht == 'verboten': continue

                score = alleinlage_score(detail)
                item['detail'] = detail
                item['haustier'] = ht
                item['score'] = score
                results.append(item)

                marker = '🌲' if score >= 4 else '🏠' if score >= 1 else '🏘️'
                print(f"  [{i+1}] {marker}[{score}] ✓ {detail['title'][:45]} | {warm or item.get('price','?')} | {ht}")
                time.sleep(0.1)
            except Exception as e:
                continue

        page.close()

    results.sort(key=lambda x: (-x.get('score',0), price_num(x.get('detail',{}).get('attrs',{}).get('Warmmiete','0'))))
    print(f"\n📊 {len(results)} Ergebnisse ({sum(1 for r in results if r.get('score',0)>=4)}🌲 / {sum(1 for r in results if 1<=r.get('score',0)<4)}🏠 / {sum(1 for r in results if r.get('score',0)==0)}🏘️)")

    if results:
        msgs = [f"""🏠🌲 **HÄUSER ZUR MIETE** 🌲🏠
*Freistehend, max {BUDGET}€ warm | Quellen: Kleinanzeigen + Immoscout*
🌲 = Alleinlage-Hinweis | 🏠 = freistehend | 🏘️ = allgemein
*{len(results)} Angebote*
━━━━━━━━━━━━━━━━━━━━━━━━"""]
        cur = ""
        for i, item in enumerate(results, 1):
            d = item.get('detail',{})
            ht = item.get('haustier','?')
            score = item.get('score',0)
            marker = '🌲' if score>=4 else '🏠' if score>=1 else '🏘️'
            ht_icon = '🐾' if ht=='ok' else '❓'
            e = f"\n{marker} **{i}. {d.get('title',item.get('title','?'))[:55]} — {item.get('price','?')}**\n"
            e += f"📍 {d.get('location',item.get('location','?'))} | {item['region']}\n"
            e += f"{ht_icon} Haustiere: {'✓' if ht=='ok' else '?'} | Score: {score}/10\n"
            a = d.get('attrs',{})
            if a.get('Warmmiete'): e += f"💰 Warm: {a['Warmmiete']}\n"
            if a.get('Wohnfläche') or a.get('Zimmer'): e += f"📐 {a.get('Wohnfläche','')} | {a.get('Zimmer','')} Zi\n"
            if d.get('description'):
                desc = d['description'].replace('\\n',' ').strip()[:150]
                e += f"📋 {desc}\n"
            e += f"🔗 {item['url']}\n"
            if len(cur)+len(e) > 1800:
                msgs.append(cur)
                cur = e
            else:
                cur += e
        if cur:
            cur += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n⏰ *Nächster Report in 1 Stunde*"
            msgs.append(cur)
        print(f"📤 Posting {len(msgs)} messages...")
        post_discord(msgs)
        print("✅ Done!")
    else:
        print("📭 Keine Treffer. Stille Meldung.")

if __name__ == "__main__":
    main()
