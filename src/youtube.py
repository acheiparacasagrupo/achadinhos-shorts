"""Upload para o YouTube (Data API v3, grátis: ~6 uploads/dia na cota padrão)."""
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from . import config as C

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]


def _service():
    if not (C.YT_CLIENT_ID and C.YT_CLIENT_SECRET and C.YT_REFRESH_TOKEN):
        raise RuntimeError("Faltam YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN")
    creds = Credentials(None, refresh_token=C.YT_REFRESH_TOKEN, client_id=C.YT_CLIENT_ID,
                        client_secret=C.YT_CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token",
                        scopes=SCOPES)
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _fit_tags(tags, limit=480):
    out, size = [], 0
    for t in dict.fromkeys(t.strip() for t in tags if t.strip()):
        cost = len(t) + (2 if " " in t else 0) + 1
        if size + cost > limit:
            break
        out.append(t); size += cost
    return out


def upload(path, title, description, tags):
    yt = _service()
    body = {
        "snippet": {"title": title[:100], "description": description[:4900],
                    "tags": _fit_tags(tags), "categoryId": C.YT_CATEGORY,
                    "defaultLanguage": "pt-BR", "defaultAudioLanguage": "pt-BR"},
        "status": {"privacyStatus": C.PRIVACY, "selfDeclaredMadeForKids": False,
                   "embeddable": True},
    }
    media = MediaFileUpload(path, mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  upload {int(status.progress() * 100)}%")
    vid = resp["id"]
    print(f"  publicado: https://www.youtube.com/shorts/{vid}")
    return vid
