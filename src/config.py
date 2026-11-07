"""Configurações centrais. Tudo pode ser sobrescrito por variáveis de ambiente
(GitHub Secrets / Variables), sem mexer no código."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
MUSIC_DIR = ROOT / "assets" / "music"
HISTORY_FILE = DATA_DIR / "history.json"


def env(name, default=""):
    v = os.getenv(name)
    return v if v not in (None, "") else default


# ---------- Canal / textos ----------
WHATSAPP_LINK = env("WHATSAPP_LINK", "https://chat.whatsapp.com/Dm1Mv7qgbPRDNZN1zvLZRz")
TITLE_HASHTAGS = env("TITLE_HASHTAGS", "#achadinhos #mercadolivre #dicas")
DESC_HASHTAGS = env("DESC_HASHTAGS", "#achadinhos #compras #mercadolivre #donadecasa")
# Se você usa link de afiliado, cole aqui um "modelo" com {url}. Ex.: https://seu.encurtador/?u={url}
LINK_TEMPLATE = env("LINK_TEMPLATE", "{url}")
# Nome do grupo falado na narração
GROUP_NAME = env("GROUP_NAME", "nosso grupo VIP de achadinhos no WhatsApp")

# ---------- Execução ----------
VIDEOS_PER_RUN = int(env("VIDEOS_PER_RUN", "1"))
DRY_RUN = env("DRY_RUN", "false").lower() == "true"          # true = gera o vídeo mas NÃO publica
PRIVACY = env("YT_PRIVACY", "public")                            # public | unlisted | private
YT_CATEGORY = env("YT_CATEGORY", "26")                           # 26 = Guia e Estilo
DAYS_BEFORE_REPEAT = int(env("DAYS_BEFORE_REPEAT", "90"))

# ---------- Mercado Livre ----------
# Categorias "mais vendidos" de casa. MLB1574 = Casa, Móveis e Decoração (as subcategorias são descobertas sozinhas)
ML_BESTSELLER_CATEGORIES = [c.strip() for c in env("ML_CATEGORIES", "MLB1574").split(",") if c.strip()]
# Termos-semente de "achadinhos que resolvem dores" (o Gemini ainda sugere mais a cada execução)
SEED_TERMS = [t.strip() for t in env("SEED_TERMS", (
    "organizador de geladeira,mini triturador eletrico,mop giratorio,escova eletrica de limpeza,"
    "dispenser de detergente,porta temperos giratorio,rodo magico,veda porta,tapete absorvente banheiro,"
    "lixeira automatica sensor,organizador de gaveta,seladora de embalagem,cortador de legumes,"
    "removedor de bolinhas de roupa,luminaria sensor de presenca,escorredor de louca dobravel"
)).split(",") if t.strip()]
MAX_CANDIDATES = int(env("MAX_CANDIDATES", "60"))

# ---------- Gemini ----------
GEMINI_API_KEY = env("GEMINI_API_KEY")
# Lista em ordem de preferência; se um modelo não existir/estiver sem cota, tenta o próximo.
GEMINI_MODELS = [m.strip() for m in env("GEMINI_MODELS", "gemini-flash-latest,gemini-2.5-flash,gemini-flash-lite-latest,gemini-2.5-flash-lite").split(",") if m.strip()]

# ---------- Voz (edge-tts, grátis, sem chave) ----------
TTS_VOICE = env("TTS_VOICE", "pt-BR-AntonioNeural")   # ou pt-BR-FranciscaNeural / pt-BR-ThalitaMultilingualNeural
TTS_RATE = env("TTS_RATE", "+12%")
TTS_PITCH = env("TTS_PITCH", "+0Hz")

# ---------- Vídeo ----------
W, H = 1080, 1920
FPS = 30
MAX_CLIPS = int(env("MAX_CLIPS", "3"))           # quantos vídeos reais do anúncio/avaliações juntar
MAX_CLIP_SECONDS = float(env("MAX_CLIP_SECONDS", "14"))
FONT_NAME = env("FONT_NAME", "Anton")
FONTS_DIR = ROOT / "assets" / "fonts"
# Shorts: sempre vertical e abaixo de 60 s
MAX_SHORT_SECONDS = 58.0
MUSIC_VOLUME = float(env("MUSIC_VOLUME", "0.10"))
KEEP_ORIGINAL_AUDIO = env("KEEP_ORIGINAL_AUDIO", "false").lower() == "true"

# ---------- YouTube ----------
YT_CLIENT_ID = env("YT_CLIENT_ID")
YT_CLIENT_SECRET = env("YT_CLIENT_SECRET")
YT_REFRESH_TOKEN = env("YT_REFRESH_TOKEN")

USER_AGENT = env("USER_AGENT", (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
))
