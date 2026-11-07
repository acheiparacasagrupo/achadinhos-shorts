"""Narração grátis: edge-tts (vozes neurais da Microsoft, sem chave).
Fallback: Gemini TTS (free tier). Devolve o áudio + tempos de cada palavra
para gerar legendas sincronizadas."""
import asyncio
import os
import re
import subprocess
import wave

from . import config as C


async def _edge(text, mp3):
    import edge_tts
    words = []
    kw = dict(rate=C.TTS_RATE, pitch=C.TTS_PITCH)
    try:
        com = edge_tts.Communicate(text, C.TTS_VOICE, boundary="WordBoundary", **kw)
    except TypeError:  # versões antigas
        com = edge_tts.Communicate(text, C.TTS_VOICE, **kw)
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"start": ch["offset"] / 1e7,
                              "end": (ch["offset"] + ch["duration"]) / 1e7,
                              "text": ch["text"]})
    return words


def _duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", path], capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def _estimate_words(text, total):
    """Sem tempos reais: distribui palavras pelo tamanho (com pausas em pontuação)."""
    toks = text.split()
    weights = [len(t) + (4 if re.search(r"[.!?]$", t) else 2 if t.endswith(",") else 0) + 2 for t in toks]
    k = total / max(sum(weights), 1)
    t, words = 0.0, []
    for tok, w in zip(toks, weights):
        words.append({"start": t, "end": t + w * k * 0.9, "text": tok})
        t += w * k
    return words


def _gemini_tts(text, wav_path):
    from google.genai import types
    from .ai import client
    voice = os.getenv("GEMINI_TTS_VOICE", "Puck")
    r = client().models.generate_content(
        model=os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
        contents=f"Leia em português do Brasil, com energia, ritmo rápido e tom animado de quem indica um achado: {text}",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))),
        ),
    )
    pcm = r.candidates[0].content.parts[0].inline_data.data
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)


def synthesize(text, out_base):
    """Gera out_base.mp3 e devolve (caminho, duração, palavras)."""
    mp3 = out_base + ".mp3"
    try:
        words = asyncio.run(_edge(text, mp3))
        dur = _duration(mp3)
        if dur < 2:
            raise RuntimeError("áudio vazio")
        if not words:
            words = _estimate_words(text, dur)
        return mp3, dur, words
    except Exception as e:  # noqa: BLE001
        print("  edge-tts falhou, usando Gemini TTS:", e)
    wav = out_base + ".wav"
    _gemini_tts(text, wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "192k", mp3], check=True)
    dur = _duration(mp3)
    return mp3, dur, _estimate_words(text, dur)
