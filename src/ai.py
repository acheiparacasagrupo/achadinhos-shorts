"""Gemini (free tier): sugere termos virais, escolhe os produtos que resolvem
dores e escreve narração + título + tags no padrão do canal."""
import json
import re
import time

from google import genai
from google.genai import types

from . import config as C

_client = None


def client():
    global _client
    if _client is None:
        if not C.GEMINI_API_KEY:
            raise RuntimeError("Falta o secret GEMINI_API_KEY")
        _client = genai.Client(api_key=C.GEMINI_API_KEY)
    return _client


def _json(prompt, schema=None, temperature=0.9):
    """Chama o Gemini pedindo JSON, com fallback de modelo e retry em limite de cota."""
    last = None
    for model in C.GEMINI_MODELS:
        for attempt in range(3):
            try:
                cfg = types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=schema,
                )
                r = client().models.generate_content(model=model, contents=prompt, config=cfg)
                txt = (r.text or "").strip()
                txt = re.sub(r"^```(?:json)?|```$", "", txt).strip()
                return json.loads(txt)
            except Exception as e:  # noqa: BLE001
                last = e
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg or "UNAVAILABLE" in msg:
                    time.sleep(20 * (attempt + 1))
                    continue
                if "404" in msg or "NOT_FOUND" in msg or "not found" in msg.lower():
                    break  # modelo não existe mais -> próximo
                time.sleep(3)
        print(f"  Gemini: modelo {model} falhou ({str(last)[:120]}), tentando o próximo...")
    raise RuntimeError(f"Gemini falhou em todos os modelos: {last}")


# ---------------- 1) termos virais ----------------

def viral_terms(n=6):
    prompt = f"""Você é um caçador de "achadinhos para casa" virais no TikTok, Reels e Shorts do Brasil.
Liste {n} termos de busca CURTOS (2 a 4 palavras, sem acento, minúsculas) de produtos baratos para casa
(cozinha, limpeza, organização, banheiro, lavanderia, quarto) que viralizam porque RESOLVEM UMA DOR clara
do dia a dia (ex.: "mini triturador eletrico", "rodo magico", "veda porta").
Varie as categorias. Não repita: {", ".join(C.SEED_TERMS[:20])}.
Responda em JSON: {{"terms": ["..."]}}"""
    try:
        return _json(prompt).get("terms", [])[:n]
    except Exception as e:  # noqa: BLE001
        print("  aviso: não consegui termos do Gemini:", e)
        return []


# ---------------- 2) ranking de produtos ----------------

def rank_products(cands, k=10):
    lines = [
        f'{i}. {c["title"]} | R$ {c["price"]} | nota {c["rating"]} | {c["reviews"]} avaliações | {c["source"]}'
        for i, c in enumerate(cands)
    ]
    prompt = f"""Você escolhe produtos para vídeos curtos de "achadinhos para casa" que vendem muito.
Critérios (do mais importante ao menos):
1. Resolve uma DOR clara e visual do dia a dia (sujeira, bagunça, falta de espaço, perda de tempo, cheiro, choro ao cortar cebola...).
2. Tem "efeito uau" em vídeo (dá pra mostrar o antes/depois ou o uso em segundos).
3. Preço de impulso (idealmente até R$ 150) e boa nota.
4. Já é vendido em volume / tem cara de viral.
DESCARTE: itens commodity sem graça (papel higiênico, sabão, detergente comum, colchão, móveis grandes, lâmpada comum),
itens de marca famosa sem diferencial, adulto/medicamentos/armas.

Produtos:
{chr(10).join(lines)}

Devolva os {k} melhores em ordem, em JSON:
{{"ranking": [{{"index": 0, "dor": "dor que resolve em poucas palavras", "nota": 0-10}}]}}"""
    data = _json(prompt, temperature=0.3)
    out = []
    for r in data.get("ranking", []):
        try:
            i = int(r["index"])
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= i < len(cands):
            c = dict(cands[i])
            c["dor"] = r.get("dor", "")
            c["score"] = r.get("nota", 0)
            out.append(c)
    return out


# ---------------- 3) roteiro + metadados ----------------

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "hook_overlay": {"type": "string"},
        "narration": {"type": "string"},
        "title_hook": {"type": "string"},
        "product_label": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["hook_overlay", "narration", "title_hook", "product_label", "tags"],
}

EXAMPLE = {
    "title": "PARE DE CHORAR PRA CORTAR CEBOLA   #achadinhos #shopee #dicas",
    "label": "MINI TRITURADOR ELETRICO",
    "tags": ["achadinhos", "achadinhos para casa", "como cortar cebola sem chorar", "como picar alho rapido",
             "compras para casa", "cozinha", "mini processador eletrico", "mini triturador usb",
             "processador de tempero", "triturador de alho", "utensilios de cozinha"],
}


def write_script(p, video_seconds_hint=30):
    prompt = f"""Você é um copywriter brasileiro especialista em vídeos curtos virais de achadinhos (Shorts/Reels/TikTok).
Escreva o roteiro de NARRAÇÃO (voz em off) para o produto abaixo. O vídeo mostra o produto real em uso.

PRODUTO: {p["title"]}
Preço: R$ {p.get("price","")} | Vendidos: {p.get("sold","")}
Dor que resolve (pista): {p.get("dor","")}
Características: {p.get("features","")}
Descrição do vendedor: {p.get("description","")[:900]}

REGRAS DA NARRAÇÃO (campo "narration"):
- Português do Brasil, tom de amiga/amigo empolgado contando um achado, frases curtas, fala natural.
- Entre 65 e 85 palavras (≈ {video_seconds_hint} segundos).
- Estrutura OBRIGATÓRIA:
  1) GANCHO com a DOR nos 2 primeiros segundos (pergunta ou afirmação que a pessoa se identifica). Ex.: "Você ainda chora toda vez que corta cebola?"
  2) Agitar a dor em 1 frase.
  3) Apresentar o produto como a solução e mostrar 2 ou 3 benefícios concretos e visuais.
  4) Prova social/urgência leve (ex.: "tá vendendo muito", "preço tá ótimo hoje") SEM inventar números ou preços exatos.
  5) CTA final: chamar para entrar no {C.GROUP_NAME}, onde tem achadinhos assim com desconto para casa todos os dias; o link está na descrição.
- NÃO cite a marca, NÃO prometa nada que o produto não faz, NÃO use emojis, hashtags, nem parênteses, nem indicações de cena.
- Escreva números por extenso quando for falado.

OUTROS CAMPOS:
- "hook_overlay": texto curto (máx. 6 palavras, MAIÚSCULAS) que aparece no topo do vídeo, a dor/benefício. Ex.: "CHEGA DE CHORAR COM CEBOLA".
- "title_hook": título em MAIÚSCULAS, sem acento obrigatório, máx. 55 caracteres, focado na DOR, no estilo: "{EXAMPLE["title"].split("   ")[0]}". Sem hashtags.
- "product_label": nome curto genérico do produto em MAIÚSCULAS sem acento (2 a 4 palavras), estilo "{EXAMPLE["label"]}".
- "tags": 10 a 13 tags de busca em minúsculas sem acento, no estilo: {json.dumps(EXAMPLE["tags"], ensure_ascii=False)}
  (sempre inclua "achadinhos", "achadinhos para casa" e "compras para casa"; o resto específico do produto e das dores que ele resolve).
Responda só o JSON."""
    d = _json(prompt, schema=SCRIPT_SCHEMA, temperature=0.95)
    d["narration"] = re.sub(r"[\(\)\*#\[\]]", "", d["narration"]).strip()
    return d
