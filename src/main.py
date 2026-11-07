"""Orquestrador: descobre -> escolhe -> roteiriza -> narra -> monta -> publica."""
import json
import re
import shutil
import sys
import tempfile
import time
import traceback
import unicodedata
from datetime import datetime, timedelta, timezone

from . import ai, config as C, mercadolivre as ml, tts, video

NOW = datetime.now(timezone.utc)


# ---------------- histórico (evita repetir produto) ----------------

def load_history():
    try:
        return json.loads(C.HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def save_history(h):
    C.DATA_DIR.mkdir(exist_ok=True)
    C.HISTORY_FILE.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding="utf-8")


def recently_used(history):
    lim = NOW - timedelta(days=C.DAYS_BEFORE_REPEAT)
    ids, titles = set(), []
    for h in history:
        try:
            if datetime.fromisoformat(h["date"]) >= lim:
                ids.add(h["id"]); titles.append(_norm(h.get("label", "")))
        except Exception:  # noqa: BLE001
            ids.add(h.get("id"))
    return ids, titles


def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


# ---------------- textos do YouTube (mesmo modelo do vídeo de referência) ----------------

def build_title(meta):
    hook = _norm(meta["title_hook"]).upper() or meta["title_hook"].upper()
    tags = C.TITLE_HASHTAGS
    if "#shorts" not in tags.lower():
        tags += " #shorts"
    room = 100 - len(tags) - 3
    return f"{hook[:room].strip()}   {tags}"


def build_description(meta, product):
    link = C.LINK_TEMPLATE.format(url=product["url"])
    label = _norm(meta["product_label"]).upper() or meta["product_label"].upper()
    tags = C.DESC_HASHTAGS
    if "#shorts" not in tags.lower():
        tags += " #shorts"
    return (
        "🛍️ LINK DO PRODUTO AQUI\n\n"
        "🔴GRUPO VIP DE PROMOÇÕES NO WHATSAPP🔴\n"
        f"{C.WHATSAPP_LINK}\n\n"
        f"🛍️{label}\n{link}\n\n"
        "🟢GRUPO DE OFERTAS E CUPONS DE DESCONTO🟢\n"
        f"{C.WHATSAPP_LINK}\n"
        "O grupo é somente de postagem de produtos, sem chat.\n"
        "Nele você encontra achadinhos para casa com cupons de desconto todos os dias!\n\n"
        f"{tags}"
    )


# ---------------- pipeline ----------------

def pick_products(history, n):
    used_ids, used_labels = recently_used(history)
    print("1) Buscando termos virais com o Gemini...")
    terms = ai.viral_terms()
    print("   termos:", terms)
    print("2) Coletando candidatos no Mercado Livre...")
    cands = [c for c in ml.collect_candidates(terms) if c["id"] not in used_ids and c["title"]]
    print(f"   {len(cands)} candidatos novos")
    if not cands:
        raise RuntimeError("Nenhum candidato (Mercado Livre pode ter bloqueado o IP do runner — veja o README).")
    cands = cands[: C.MAX_CANDIDATES]
    print("3) Gemini escolhendo os que mais resolvem dores...")
    ranked = ai.rank_products(cands, k=max(6, n * 4))
    for r in ranked[:8]:
        print(f"   [{r['score']}] {r['title'][:70]} — {r['dor']}")
    return ranked


def process(cand, history):
    print(f"\n=== {cand['title'][:90]}")
    p = ml.product_details(cand["url"])
    p["dor"] = cand.get("dor", "")
    p["title"] = p["title"] or cand["title"]
    p["price"] = p["price"] or cand.get("price", "")
    print(f"   {len(p['videos'])} vídeos reais, {len(p['images'])} fotos, vendidos: {p['sold'] or '?'}")
    if not p["videos"] and len(p["images"]) < 3:
        raise RuntimeError("produto sem vídeo e com poucas fotos — pulando")

    meta = ai.write_script(p)
    print("   narração:", meta["narration"])

    tmp = tempfile.mkdtemp(prefix="short_")
    try:
        mp3, dur, words = tts.synthesize(meta["narration"], f"{tmp}/narracao")
        print(f"   narração: {dur:.1f}s")
        if dur > C.MAX_SHORT_SECONDS - 1:
            raise RuntimeError("narração longa demais para Short")
        C.OUT_DIR.mkdir(exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", _norm(meta["product_label"]))[:40].strip("-")
        out = str(C.OUT_DIR / f"{NOW:%Y%m%d-%H%M}-{slug}.mp4")
        out, kind, total = video.render(p, mp3, dur, words, meta["hook_overlay"], out, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    title, desc = build_title(meta), build_description(meta, p)
    print("   título:", title)
    (C.OUT_DIR / (out.rsplit("/", 1)[-1] + ".txt")).write_text(
        f"{title}\n\n{desc}\n\nTAGS: {', '.join(meta['tags'])}\n\nNARRAÇÃO: {meta['narration']}", encoding="utf-8")

    vid = None
    if C.DRY_RUN:
        print("   DRY_RUN=true -> não publicado (baixe o vídeo nos Artifacts da execução)")
    else:
        from . import youtube
        vid = youtube.upload(out, title, desc, meta["tags"])

    history.append({"id": p["id"], "url": p["url"], "label": meta["product_label"], "title": title,
                    "youtube_id": vid, "base": kind, "seconds": round(total, 1),
                    "date": NOW.isoformat(timespec="seconds")})
    save_history(history)
    return vid


def main():
    history = load_history()
    ranked = pick_products(history, C.VIDEOS_PER_RUN)
    done = 0
    for cand in ranked:
        if done >= C.VIDEOS_PER_RUN:
            break
        try:
            process(cand, history)
            done += 1
            time.sleep(5)
        except Exception as e:  # noqa: BLE001
            print("   ERRO:", e)
            traceback.print_exc(limit=2)
    print(f"\nFinalizado: {done}/{C.VIDEOS_PER_RUN} vídeos.")
    if done == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
