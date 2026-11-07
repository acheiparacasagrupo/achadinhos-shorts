"""Coleta de produtos no Mercado Livre por raspagem das páginas públicas
(mais vendidos + busca) e extração de vídeos reais do anúncio (clips do
vendedor e vídeos de avaliações de compradores)."""
import json
import random
import re
import time

import requests
from bs4 import BeautifulSoup

from . import config as C

S = requests.Session()
S.headers.update({
    "User-Agent": C.USER_AGENT,
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})

PRODUCT_RE = re.compile(
    r"https://(?:www|produto)\.mercadolivre\.com\.br/[^\"'#?\s<>]*?(?:/p/MLB\d+|MLB-\d+[^\"'#?\s<>]*)"
)
ID_RE = re.compile(r"MLB-?(\d+)")


class Blocked(Exception):
    pass


def _get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            r = S.get(url, timeout=30)
            txt = r.text
            if r.status_code == 200 and "account-verification" not in r.url and len(txt) > 20000:
                return txt
            last = f"HTTP {r.status_code} ({len(txt)} bytes) em {r.url}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(2 + i * 3 + random.random())
    raise Blocked(f"Não consegui abrir {url}: {last}")


def product_id(url):
    m = re.search(r"/p/(MLB\d+)", url)
    if m:
        return m.group(1)
    m = ID_RE.search(url)
    return f"MLB{m.group(1)}" if m else url


def _parse_cards(html, source):
    """Lê os cards (poly-card) de páginas de listagem/mais vendidos."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select(".poly-card, li.ui-search-layout__item"):
        a = card.select_one("a.poly-component__title, h3 a, a[href*='mercadolivre.com.br']")
        if not a or not a.get("href"):
            continue
        m = PRODUCT_RE.search(a["href"])
        if not m:
            continue
        url = m.group(0)
        if "click1.mercadolivre" in a["href"] and "/p/" not in url:
            continue  # anúncio patrocinado com redirect
        price = card.select_one(".poly-price__current .andes-money-amount__fraction, .andes-money-amount__fraction")
        rating = card.select_one(".poly-reviews__rating")
        total = card.select_one(".poly-reviews__total")
        out.append({
            "id": product_id(url),
            "url": url,
            "title": a.get_text(" ", strip=True),
            "price": price.get_text(strip=True) if price else "",
            "rating": rating.get_text(strip=True) if rating else "",
            "reviews": (total.get_text(strip=True) if total else "").strip("()"),
            "source": source,
        })
    if not out:  # fallback: só os links
        for url in dict.fromkeys(PRODUCT_RE.findall(html)):
            out.append({"id": product_id(url), "url": url, "title": "", "price": "",
                        "rating": "", "reviews": "", "source": source})
    return out


def bestseller_categories(root_cats):
    cats = []
    for c in root_cats:
        cats.append(c)
        try:
            html = _get(f"https://www.mercadolivre.com.br/mais-vendidos/{c}")
            cats += [x for x in dict.fromkeys(re.findall(r"mais-vendidos/(MLB\d+)", html)) if x not in cats]
        except Blocked as e:
            print("  aviso:", e)
    return cats


def collect_candidates(extra_terms=()):
    """Junta produtos dos 'mais vendidos' de casa + buscas por termos de achadinhos."""
    seen, out = set(), []

    def add(items):
        for it in items:
            if it["id"] not in seen:
                seen.add(it["id"])
                out.append(it)

    cats = bestseller_categories(C.ML_BESTSELLER_CATEGORIES)
    random.shuffle(cats)
    for c in cats[:8]:
        try:
            add(_parse_cards(_get(f"https://www.mercadolivre.com.br/mais-vendidos/{c}"), f"mais-vendidos:{c}"))
        except Blocked as e:
            print("  aviso:", e)
        time.sleep(1 + random.random())

    terms = list(dict.fromkeys(list(extra_terms) + random.sample(C.SEED_TERMS, min(6, len(C.SEED_TERMS)))))
    for t in terms:
        slug = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
        try:
            add(_parse_cards(_get(f"https://lista.mercadolivre.com.br/{slug}"), f"busca:{t}")[:8])
        except Blocked as e:
            print("  aviso:", e)
        time.sleep(1 + random.random())
    return out


# ---------------- página do produto ----------------

def _unescape(s):
    return s.replace("\\u002F", "/").replace("\\/", "/").replace("&amp;", "&")


def product_details(url):
    html = _get(url)
    soup = BeautifulSoup(html, "html.parser")
    flat = _unescape(html)

    title = (soup.select_one("h1.ui-pdp-title") or soup.select_one("h1"))
    title = title.get_text(" ", strip=True) if title else ""

    price = ""
    pm = soup.select_one('meta[itemprop="price"]')
    if pm and pm.get("content"):
        price = pm["content"]
    else:
        m = re.search(r'"price"\s*:\s*([\d.]+)', html)
        price = m.group(1) if m else ""

    sold = ""
    m = re.search(r"(\+?\s?[\d.,]+\s?(?:mil)?)\s+vendidos", flat)
    if m:
        sold = m.group(1).strip()

    # descrição + características (dão contexto ao roteiro)
    desc = soup.select_one(".ui-pdp-description__content")
    desc = desc.get_text(" ", strip=True)[:1500] if desc else ""
    feats = " | ".join(li.get_text(" ", strip=True) for li in soup.select(".ui-vpp-highlighted-specs__features-list li"))[:800]

    # imagens em alta
    imgs = list(dict.fromkeys(re.findall(r"https://http2\.mlstatic\.com/D_(?:NQ_NP_)?(?:2X_)?\d+-ML[A-Z]\d+_\d+-[A-Z]\.(?:webp|jpg)", flat)))
    imgs = [i for i in imgs if i.endswith("-O.webp") or i.endswith("-O.jpg") or "2X_" in i] or imgs
    og = soup.select_one('meta[property="og:image"]')
    if og and og.get("content") and og["content"] not in imgs:
        imgs.insert(0, og["content"])

    # vídeos reais: clips do vendedor e vídeos de avaliações (HLS ou mp4)
    vids = re.findall(r"https://video-[a-z-]+\.mms\.mlstatic\.com/[^\"'\s\\<>]+?(?:master\.m3u8|\.mp4)", flat)
    vids = list(dict.fromkeys(vids))
    # prioriza vídeo completo (m3u8) antes dos previews curtos
    vids.sort(key=lambda v: (0 if v.endswith("master.m3u8") else 1, 0 if "clips" in v else 1))
    previews = [v for v in vids if "/preview/" in v]
    full = [v for v in vids if "/preview/" not in v]
    # YouTube embutido no anúncio (campo video_id)
    yt = re.findall(r'"video_id"\s*:\s*"([A-Za-z0-9_-]{11})"', html)

    return {
        "url": url, "id": product_id(url), "title": title, "price": price, "sold": sold,
        "video_source": "anuncio" if (full or previews) else "",
        "description": desc, "features": feats,
        "images": imgs[:10], "videos": full + previews, "youtube_ids": list(dict.fromkeys(yt)),
    }


# ---------------- vídeo em outros anúncios do MESMO produto ----------------

STOP = {"kit", "com", "de", "da", "do", "para", "pra", "e", "em", "a", "o", "cor", "un", "unidades",
        "original", "novo", "promocao", "oferta", "frete", "gratis", "pecas", "pcs"}


def search_query(title, words=5):
    import unicodedata
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    toks = [w for w in re.findall(r"[a-z]+", t) if w not in STOP and len(w) > 2]
    return " ".join(toks[:words])


def find_videos_other_listings(title, exclude_id, max_pages=5):
    """Procura o mesmo produto em outros anúncios do ML e pega os vídeos deles."""
    q = search_query(title)
    if not q:
        return []
    slug = q.replace(" ", "-")
    try:
        cards = _parse_cards(_get(f"https://lista.mercadolivre.com.br/{slug}"), f"alt:{q}")
    except Blocked as e:
        print("  aviso:", e)
        return []
    vids = []
    for c in [c for c in cards if c["id"] != exclude_id][:max_pages]:
        try:
            d = product_details(c["url"])
            if d["videos"]:
                print(f"  vídeo achado em outro anúncio: {c['title'][:60]}")
                vids += d["videos"]
        except Blocked:
            continue
        if len(vids) >= C.MAX_CLIPS * 2:
            break
        time.sleep(1 + random.random())
    return vids
