#!/usr/bin/env python3
"""Haus-Suche: Search via Camoufox, post via curl subprocess"""
import json, time, re, os, subprocess, traceback
from datetime import datetime

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1164313161093103716/swOaRW2QRNf82uZxIHtcONb15zizkfhmgITeSFINAJaWgLGl0i-GPvKAaoBz6Z2VWvs7"
MAX_PRICE = 1350
SEEN_IDS_FILE = os.path.expanduser('~/.hermes/skills/haus-suche-discord/seen_ids.json')

try:
    with open(SEEN_IDS_FILE) as f:
        seen_ids = set(json.load(f))
except:
    seen_ids = set()

KILL_TERMS = [
    'reihenhaus', 'doppelhaus', 'dhh', 'doppelhaushälfte', 'mfh', 'mehrfamilienhaus',
    'wohnung', 'stadthaus', 'suche', 'gesucht', 'urlaub', 'ferien', 'reserviert',
    'gelöscht', 'geloescht'
]

def is_kill_listing(title, loc="", desc=""):
    combined = (title + " " + loc + " " + desc).lower()
    for k in KILL_TERMS:
        if k in combined: return True
    return False

def extract_price_num(price_str):
    if not price_str: return None
    nums = re.findall(r'[\d.,]+', price_str.replace('.', '').replace(',', '.'))
    for n in nums:
        val = float(n)
        if 100 < val < 5000: return val
    return None

def send_discord_curl(title, price, location, size, rooms, url, extra_info=""):
    price_str = str(price) if price else "unbekannt"
    msg = f"**{title} — {price_str}**\n📍 {location or 'unbekannt'}\n"
    if size: msg += f"📐 {size}"
    if rooms: msg += f" | 🛏 {rooms}"
    msg += f"\n🔗 {url}"
    if extra_info: msg += f"\n⚠️ {extra_info}"
    msg = msg[:2000]
    data = json.dumps({"content": msg})
    result = subprocess.run(
        ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}',
         '-X', 'POST', DISCORD_WEBHOOK,
         '-H', 'Content-Type: application/json',
         '-d', data],
        capture_output=True, text=True, timeout=15
    )
    code = result.stdout.strip()
    if code in ('200', '204'):
        print(f"  ✅ Discord: {title[:60]}")
        return True
    else:
        print(f"  ❌ Discord HTTP {code}: {title[:40]}")
        return False

def accept_cookies(page):
    try:
        btn = page.locator('button:has-text("Alle akzeptieren"), button:has-text("Akzeptieren")')
        if btn.first.is_visible(timeout=3000):
            btn.first.click(); time.sleep(1)
    except: pass

def search_immoscout():
    print("\n=== IMMOBILIENSCOUT24 ===")
    results = []
    from camoufox.sync_api import Camoufox
    regions = [
        ('mecklenburg-vorpommern', 'MeckPomm'),
        ('thueringen', 'Thüringen'),
        ('sachsen', 'Sachsen'),
        ('sachsen-anhalt', 'Sachsen-Anhalt'),
        ('hessen', 'Hessen'),
    ]
    with Camoufox(headless=True) as browser:
        for region_slug, region_name in regions:
            print(f"\n  📍 {region_name}...")
            page = browser.new_page()
            url = f"https://www.immobilienscout24.de/Suche/de/{region_slug}/haus-mieten?price=-1350.0&buildingfreestanding=1"
            try:
                page.goto(url, timeout=30000)
                time.sleep(2)
                accept_cookies(page)
                listings = page.evaluate('''() => {
                    const items = [];
                    document.querySelectorAll('.listing-card').forEach(card => {
                        const id = card.getAttribute('data-obid');
                        const title = card.querySelector('h3,h2')?.textContent?.trim()||'';
                        const dds = Array.from(card.querySelectorAll('dd')).map(d=>d.textContent.trim());
                        const loc = card.querySelector('[class*=address],[class*=locality]')?.textContent?.trim()||'';
                        if (id && title) items.push({id,title,location:loc,price:dds[0]||'',sqm:dds[1]||'',rooms:dds[2]||''});
                    });
                    return items;
                }''')
                print(f"  Found {len(listings)} listings")
                for item in listings:
                    if item['id'] in seen_ids: continue
                    if is_kill_listing(item['title'], item.get('location','')): continue
                    price_num = extract_price_num(item['price'])
                    if price_num and price_num > MAX_PRICE: continue
                    results.append({
                        'id': item['id'], 'title': item['title'],
                        'price': item['price'], 'price_num': price_num,
                        'location': item['location'], 'sqm': item['sqm'],
                        'rooms': item['rooms'],
                        'url': f"https://www.immobilienscout24.de/expose/{item['id']}",
                        'source': 'Immoscout', 'region': region_name, 'extra': ''
                    })
                page.close()
                time.sleep(1.5)
            except Exception as e:
                print(f"  ⚠️ Error: {e}")
                try: page.close()
                except: pass
    return results

def search_kleinanzeigen():
    print("\n=== KLEINANZEIGEN ===")
    results = []
    from camoufox.sync_api import Camoufox
    queries = [
        'freistehendes+haus+mieten+alleinlage',
        'bungalow+mieten+alleinlage',
        'bauernhaus+mieten',
        'landhaus+mieten',
        'fachwerkhaus+mieten',
    ]
    with Camoufox(headless=True) as browser:
        for query in queries:
            print(f"\n  🔍 {query}...")
            page = browser.new_page()
            url = f"https://www.kleinanzeigen.de/s-haus-mieten/{query}/k0c203"
            try:
                page.goto(url, timeout=30000)
                time.sleep(2)
                accept_cookies(page)
                listings = page.evaluate('''() => {
                    const items = [];
                    document.querySelectorAll('article[class*=aditem]').forEach(card => {
                        const linkEl = card.querySelector('a[class*=ellipsis],.aditem-main--middle--title a');
                        const priceEl = card.querySelector('[class*=price]');
                        const locEl = card.querySelector('[class*=top--left],.aditem-main--top--left');
                        if (linkEl && linkEl.href) {
                            items.push({
                                id: card.getAttribute('data-adid')||linkEl.href.split('/').pop(),
                                title: linkEl.textContent?.trim()||'',
                                url: linkEl.href,
                                price: priceEl?.textContent?.trim()||'',
                                location: locEl?.textContent?.trim()||''
                            });
                        }
                    });
                    return items;
                }''')
                print(f"  Found {len(listings)} listings")
                for item in listings:
                    lid = item.get('id','')
                    if lid in seen_ids: continue
                    if not item.get('url','').startswith('http'): continue
                    if is_kill_listing(item['title'], item.get('location','')): continue
                    price_num = extract_price_num(item['price'])
                    if price_num and price_num > MAX_PRICE: continue
                    results.append({
                        'id': lid, 'title': item['title'],
                        'price': item['price'], 'price_num': price_num,
                        'location': item['location'], 'sqm': '', 'rooms': '',
                        'url': item['url'], 'source': 'Kleinanzeigen',
                        'region': '', 'extra': ''
                    })
                page.close()
                time.sleep(0.5)
            except Exception as e:
                print(f"  ⚠️ Error: {e}")
                try: page.close()
                except: pass
    return results

def main():
    print(f"🏠 Haus-Suche: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Gesehene IDs: {len(seen_ids)}")
    all_results = []
    try:
        all_results.extend(search_immoscout())
    except Exception as e:
        print(f"❌ Immoscout: {e}"); traceback.print_exc()
    try:
        all_results.extend(search_kleinanzeigen())
    except Exception as e:
        print(f"❌ Kleinanzeigen: {e}"); traceback.print_exc()

    # Dedup + sort
    unique = {}
    for r in all_results:
        if r['id'] not in unique: unique[r['id']] = r
    all_results = list(unique.values())
    all_results.sort(key=lambda x: x.get('price_num') or 99999)

    print(f"\n📊 Total unique after dedup+filter: {len(all_results)}")

    # Post new ones
    posted = 0
    new_seen = set(seen_ids)
    for r in all_results:
        rid = str(r['id'])
        if rid in seen_ids: continue
        src_tag = f"{r['source']}" + (f"/{r['region']}" if r.get('region') else '')
        success = send_discord_curl(
            r['title'][:200], r['price'], r['location'],
            r.get('sqm',''), r.get('rooms',''), r['url'],
            r.get('extra','') + f" [{src_tag}]"
        )
        if success:
            posted += 1
            new_seen.add(rid)
        time.sleep(0.8)  # Discord rate limit

    with open(SEEN_IDS_FILE, 'w') as f:
        json.dump(list(new_seen), f)

    print(f"\n{'='*50}")
    print(f"📊 {len(all_results)} unique, {posted} neu gepostet")
    print(f"{'='*50}")
    if posted == 0:
        print("ℹ️ Keine neuen Treffer — Alleinlage-Häuser zur Miete sind selten.")

if __name__ == '__main__':
    main()
