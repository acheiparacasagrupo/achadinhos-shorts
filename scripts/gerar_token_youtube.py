"""Rode UMA vez no seu PC para autorizar o canal e pegar o YT_REFRESH_TOKEN.

  pip install google-auth-oauthlib
  python scripts/gerar_token_youtube.py client_secret.json

Abre o navegador -> escolha a conta/canal do YouTube -> autorize.
Copie os 3 valores impressos para os Secrets do GitHub.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"]

path = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
flow = InstalledAppFlow.from_client_secrets_file(path, SCOPES)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
info = json.load(open(path))
info = info.get("installed") or info.get("web")
print("\n===== COLE NOS SECRETS DO GITHUB =====")
print("YT_CLIENT_ID     =", info["client_id"])
print("YT_CLIENT_SECRET =", info["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
