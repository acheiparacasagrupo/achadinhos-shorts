"""Montagem do Short com FFmpeg: vídeo REAL do produto (anúncio, outros
anúncios ou YouTube) em 1080x1920, narração, legendas animadas, gancho no
topo e CTA do grupo no final. Sempre < 60 s (formato Shorts)."""
import glob
import os
import random
import re
import shutil
import subprocess

from . import config as C
from .tts import _duration

HDRS = f"User-Agent: {C.USER_AGENT}\r\nReferer: https://www.mercadolivre.com.br/\r\n"

NORMALIZE = (
    "split[a][b];"
    f"[a]scale={C.W}:{C.H}:force_original_aspect_ratio=increase,crop={C.W}:{C.H},boxblur=25:2,eq=brightness=-0.10[bg];"
    f"[b]scale={C.W}:{C.H}:force_original_aspect_ratio=decrease[fg];"
    f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={C.FPS},setsar=1,format=yuv420p"
)
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(C.FPS)]


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-1500:])
    return p


# ---------------- fontes do vídeo ----------------

def _clip_from_url(url, out):
    src = url
    if url.startswith("http"):
        # 1º baixa (o ffmpeg escolhe sozinho a variante de maior resolução do HLS)
        src = out.replace(".mp4", "_raw.mp4")
        run(["ffmpeg", "-y", "-loglevel", "error", "-headers", HDRS, "-rw_timeout", "30000000",
             "-i", url, "-t", str(C.MAX_CLIP_SECONDS), "-c", "copy", "-bsf:a", "aac_adtstoasc", src])
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src,
         "-filter_complex", f"[0:v]{NORMALIZE}[v]", "-map", "[v]",
         "-map", "0:a?", "-c:a", "aac", "-ar", "44100", "-ac", "2", *ENC, out])
    return _duration(out)


def _yt_dlp_base():
    cmd = ["yt-dlp", "-q", "--no-warnings", "--no-playlist"]
    if os.path.exists(C.YT_COOKIES_FILE):
        cmd += ["--cookies", C.YT_COOKIES_FILE]
    return cmd


def _clip_from_youtube(ref, out, tmp):
    """ref = id do vídeo ou URL. Baixa (máx. 1080p) e normaliza."""
    if not shutil.which("yt-dlp"):
        raise RuntimeError("yt-dlp não instalado")
    url = ref if ref.startswith("http") else f"https://www.youtube.com/watch?v={ref}"
    raw = os.path.join(tmp, "yt_" + re.sub(r"[^A-Za-z0-9_-]", "", url)[-15:] + ".mp4")
    run([*_yt_dlp_base(), "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b",
         "--merge-output-format", "mp4", "--download-sections", f"*0-{int(C.MAX_CLIP_SECONDS)+1}",
         "-o", raw, url])
    return _clip_from_url(raw, out)


def youtube_search(query, n=8):
    """Busca vídeos curtos do produto no YouTube (Shorts/reviews) e devolve URLs."""
    if not shutil.which("yt-dlp") or not query:
        return []
    p = subprocess.run([*_yt_dlp_base(), "--flat-playlist", "--print", "%(id)s|%(duration)s|%(title)s",
                        f"ytsearch{n}:{query}"], capture_output=True, text=True, timeout=120)
    out = []
    for line in p.stdout.splitlines():
        try:
            vid, dur, title = line.split("|", 2)
            dur = float(dur) if dur not in ("NA", "None", "") else 0
        except ValueError:
            continue
        if 5 <= dur <= 120:  # vídeos curtos de demonstração
            out.append(f"https://www.youtube.com/watch?v={vid}")
    if p.returncode and not out:
        print("  busca no YouTube falhou:", p.stderr[-200:])
    return out


def _concat(parts, out, tmp):
    lst = os.path.join(tmp, "concat.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])


def _ensure_audio(path, tmp):
    """Garante trilha de áudio (clips sem som quebram o concat)."""
    has = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    if has:
        return path
    fixed = path.replace(".mp4", "_a.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", fixed])
    return fixed


class NoVideo(Exception):
    pass


def _collect(urls, tmp, parts, prefix, loader):
    for i, url in enumerate(urls):
        if len(parts) >= max(C.MAX_CLIPS, 1):
            break
        seg = os.path.join(tmp, f"{prefix}{i}.mp4")
        try:
            d = loader(url, seg)
            if d >= 2.5:
                parts.append(_ensure_audio(seg, tmp))
                print(f"  clip ok ({d:.1f}s): {url[:80]}")
        except Exception as e:  # noqa: BLE001
            print("  clip falhou:", str(e)[:200])


def build_base(product, tmp):
    """O vídeo REAL do produto é obrigatório. Ordem de busca:
    1) vídeos do anúncio escolhido (vendedor + avaliações)
    2) vídeos de OUTROS anúncios do mesmo produto no Mercado Livre
    3) vídeo do YouTube embutido no anúncio
    4) busca no YouTube pelo nome do produto
    Se nada der certo -> NoVideo (o fluxo pula para o próximo produto)."""
    from . import mercadolivre as ml
    parts = []
    _collect(product.get("videos", []), tmp, parts, "clip", _clip_from_url)
    source = "anuncio"
    if not parts:
        print("  sem vídeo no anúncio -> procurando em outros anúncios do mesmo produto...")
        _collect(ml.find_videos_other_listings(product["title"], product.get("id")), tmp, parts, "alt", _clip_from_url)
        source = "outro-anuncio"
    if not parts and product.get("youtube_ids"):
        _collect(product["youtube_ids"][:2], tmp, parts, "yt", lambda u, o: _clip_from_youtube(u, o, tmp))
        source = "youtube-anuncio"
    if not parts and C.ALLOW_YOUTUBE_SEARCH:
        q = ml.search_query(product["title"], 6)
        print(f"  procurando no YouTube: '{q}'...")
        urls = youtube_search(q + " shorts") or youtube_search(q)
        _collect(urls[:5], tmp, parts, "yts", lambda u, o: _clip_from_youtube(u, o, tmp))
        source = "youtube-busca"
    if not parts:
        raise NoVideo("nenhum vídeo real do produto encontrado")
    base = os.path.join(tmp, "base.mp4")
    _concat(parts, base, tmp)
    return base, source


# ---------------- legendas (ASS) ----------------

def _ts(t):
    t = max(t, 0)
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(s):
    return s.replace("\\", "/").replace("{", "(").replace("}", ")").replace("\n", " ")


def _chunks(words, max_words=3):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or w["text"].rstrip().endswith((".", "!", "?", ",")):
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def make_ass(words, hook, total, path):
    f = C.FONT_NAME
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {C.W}
PlayResY: {C.H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{f},104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,7,4,2,60,60,560,1
Style: Hook,{f},84,&H00FFFFFF,&H00FFFFFF,&H001B1BE0,&H001B1BE0,-1,0,0,0,100,100,1,0,3,18,0,8,70,70,250,1
Style: Cta,{f},78,&H00000000,&H00000000,&H0000E5FF,&H0000E5FF,-1,0,0,0,100,100,1,0,3,20,0,8,70,70,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    cta_start = max(total - 4.5, total * 0.7)
    ev.append(f"Dialogue: 1,{_ts(0)},{_ts(cta_start)},Hook,,0,0,0,,{{\\fad(150,150)}}{_esc(hook.upper())}")
    ev.append(f"Dialogue: 1,{_ts(cta_start)},{_ts(total)},Cta,,0,0,0,,{{\\fad(150,0)}}ENTRE NO GRUPO VIP\\NLINK NA DESCRIÇÃO")
    ch = _chunks(words)
    for i, c in enumerate(ch):
        st = c[0]["start"]
        en = ch[i + 1][0]["start"] if i + 1 < len(ch) else min(c[-1]["end"] + 0.4, total)
        txt = " ".join(w["text"] for w in c).upper().rstrip(",;")
        color = "&H0000E5FF&" if i % 2 == 0 else "&H00FFFFFF&"  # alterna amarelo / branco
        ev.append(f"Dialogue: 0,{_ts(st)},{_ts(en)},Cap,,0,0,0,,"
                  f"{{\\c{color}\\fscx78\\fscy78\\t(0,90,\\fscx104\\fscy104)\\t(90,150,\\fscx100\\fscy100)}}{_esc(txt)}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(head + "\n".join(ev) + "\n")


# ---------------- render final ----------------

def render(base, narration_mp3, narration_dur, words, hook, out_path, tmp):
    total = min(narration_dur + 0.8, C.MAX_SHORT_SECONDS)
    ass = os.path.join(tmp, "subs.ass")
    make_ass(words, hook, total, ass)

    music = sorted(glob.glob(str(C.MUSIC_DIR / "*.mp3")))
    inputs = ["-stream_loop", "-1", "-i", base, "-i", narration_mp3]
    amix = ["[1:a]volume=1.0[nar]"]
    mix_in = "[nar]"
    n = 1
    if music:
        inputs += ["-stream_loop", "-1", "-i", random.choice(music)]
        amix.append(f"[2:a]volume={C.MUSIC_VOLUME}[mus]"); mix_in += "[mus]"; n += 1
    if C.KEEP_ORIGINAL_AUDIO:
        amix.append("[0:a]volume=0.15[orig]"); mix_in += "[orig]"; n += 1
    if n > 1:
        amix.append(f"{mix_in}amix=inputs={n}:duration=first:dropout_transition=0:normalize=0,"
                    f"loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    else:
        amix.append("[nar]loudnorm=I=-14:TP=-1.5:LRA=11[aout]")

    ass_esc = ass.replace("\\", "/").replace(":", "\\:")
    fonts = str(C.FONTS_DIR).replace("\\", "/").replace(":", "\\:")
    vf = f"[0:v]ass='{ass_esc}':fontsdir='{fonts}',fade=t=out:st={total-0.35:.2f}:d=0.35[vout]"
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", ";".join([vf] + amix),
         "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
         *ENC, "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", out_path])
    return out_path, total
