# 🏠 Achadinhos Shorts — piloto automático 100% grátis

Esse fluxo roda sozinho no **GitHub Actions** (sem n8n, sem servidor), 3 vezes por dia:

```
Mercado Livre (mais vendidos de Casa + buscas virais)
      │  Gemini sugere termos virais e escolhe os produtos que RESOLVEM DORES
      ▼
VÍDEO REAL DO PRODUTO é obrigatório. Ordem de busca:
      │  1) vídeos do anúncio escolhido (vendedor + avaliações)
      │  2) vídeos de OUTROS anúncios do mesmo produto no Mercado Livre
      │  3) vídeo do YouTube embutido no anúncio
      │  4) busca no YouTube pelo nome do produto
      │  sem vídeo em nenhum lugar → pula para o próximo produto
      ▼
Gemini escreve: gancho com a DOR → solução → benefícios → CTA do grupo do WhatsApp
      ▼
edge-tts (voz neural pt-BR grátis) + legendas animadas sincronizadas
      ▼
FFmpeg monta o SHORT 1080x1920, sempre < 60 s
      ▼
YouTube Data API → publica com título, descrição e tags no modelo do canal de referência
```

| Peça | Serviço grátis | Limite grátis |
|---|---|---|
| Execução / agendamento | GitHub Actions | ilimitado em repo **público** · 2.000 min/mês em privado (cada Short ≈ 4–6 min) |
| Busca dos produtos | Raspagem das páginas públicas do Mercado Livre | — |
| Inteligência | Gemini API (Google AI Studio) | 3 chamadas por vídeo, sobra muito no free tier |
| Voz | edge-tts (Microsoft, sem chave) · plano B: Gemini TTS | — |
| Edição | FFmpeg | — |
| Upload | YouTube Data API v3 | 10.000 unidades/dia ≈ **6 uploads/dia** |

---

## Passo a passo de configuração (≈ 20 min, uma vez só)

### 1. Criar o repositório
1. No GitHub: **New repository** → nome `achadinhos-shorts` → de preferência **Public** (minutos ilimitados; os segredos ficam protegidos mesmo em repo público).
2. Envie todos os arquivos desta pasta (arraste no navegador em *Add file → Upload files*, ou `git push`).
   ⚠️ A pasta `.github/workflows` precisa ir junto (no Windows ela pode ficar oculta).

### 2. Chave do Gemini
1. Acesse <https://aistudio.google.com/apikey> → **Create API key**.
2. No repo: **Settings → Secrets and variables → Actions → New repository secret**
   - `GEMINI_API_KEY` = sua chave

### 3. Acesso ao canal do YouTube
1. <https://console.cloud.google.com> → crie um projeto (ex.: `achadinhos-shorts`).
2. **APIs e serviços → Biblioteca** → ative **YouTube Data API v3**.
3. **Tela de consentimento OAuth** → tipo *Externo* → preencha nome/e-mail → em *Usuários de teste* adicione o e-mail do canal.
   Depois clique em **PUBLICAR APLICATIVO** (status "Em produção").
   > Se ficar em "Teste", o token expira a cada 7 dias e o fluxo para.
4. **Credenciais → Criar credenciais → ID do cliente OAuth → App para computador** → baixe o JSON e renomeie para `client_secret.json`.
5. No seu PC (com Python):
   ```bash
   pip install google-auth-oauthlib
   python scripts/gerar_token_youtube.py client_secret.json
   ```
   Abre o navegador → escolha o **canal** → aparece "app não verificado" → *Avançado → Acessar* → permitir.
6. Crie 3 secrets no GitHub com o que foi impresso: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
   (Nunca suba o `client_secret.json` para o repo.)

> **Importante — vídeos travados como privados:** o YouTube pode bloquear como *privado* os vídeos enviados por projetos de API que ainda não passaram pela auditoria. Se isso acontecer, preencha o formulário grátis **"YouTube API Services – Audit and Quota Extension Form"** (no Google, busque por esse nome) explicando que é uma ferramenta própria para publicar no seu canal. Enquanto não for aprovado, use `YT_PRIVACY=private`/`DRY_RUN=true` e publique manualmente os vídeos gerados.

### 4. Variáveis do canal
**Settings → Secrets and variables → Actions → aba Variables → New repository variable**

| Variável | Exemplo | Obrigatória |
|---|---|---|
| `WHATSAPP_LINK` | já vem configurado com o seu grupo; só crie se quiser trocar | |
| `TITLE_HASHTAGS` | `#achadinhos #mercadolivre #dicas` (o `#shorts` entra sozinho) | |
| `DESC_HASHTAGS` | `#achadinhos #compras #mercadolivre #donadecasa` | |
| `LINK_TEMPLATE` | `{url}` ou modelo com seu link de afiliado, ex.: `https://seusite.com/r?u={url}` | |
| `TTS_VOICE` | `pt-BR-AntonioNeural` · `pt-BR-FranciscaNeural` · `pt-BR-ThalitaMultilingualNeural` | |
| `YT_PRIVACY` | `public` / `unlisted` / `private` | |
| `VIDEOS_PER_RUN` | `1` | |
| `DRY_RUN` | `true` = só gera, não publica | |
| `GEMINI_MODELS` | lista de modelos em ordem, se o padrão mudar | |
| `ALLOW_YOUTUBE_SEARCH` | `true` (padrão) / `false` = não buscar vídeo no YouTube | |

**Secret opcional `YT_COOKIES`:** o YouTube às vezes bloqueia downloads vindos dos servidores do GitHub ("confirme que você não é um robô"). Se aparecer isso no log, exporte os cookies do YouTube de uma conta **secundária** com a extensão "Get cookies.txt LOCALLY" e cole o conteúdo no secret `YT_COOKIES`.

### 5. Primeiro teste
1. Aba **Actions** → *Achadinhos Shorts (automático)* → **Run workflow** → `dry_run = true` → Run.
2. Ao terminar, abra a execução → **Artifacts** → baixe o `.mp4` e o `.txt` (título, descrição, tags e narração).
3. Gostou? Rode com `dry_run = false`. Daí em diante ele roda sozinho às **11:17, 17:17 e 21:17** (horário de Brasília). Mude em `.github/workflows/shorts.yml`, linha `cron`.

### 6. Música de fundo (opcional)
Coloque arquivos `.mp3` **livres de direitos** (ex.: Biblioteca de Áudio do YouTube Studio) em `assets/music/`. O fluxo sorteia uma e deixa baixinha embaixo da voz.

---

## Como o título/descrição ficam (modelo do vídeo de referência)

**Título:** `PARE DE CHORAR PRA CORTAR CEBOLA   #achadinhos #mercadolivre #dicas #shorts`

**Descrição:**
```
🛍️ LINK DO PRODUTO AQUI

🔴GRUPO VIP DE PROMOÇÕES NO WHATSAPP🔴
https://chat.whatsapp.com/Dm1Mv7qgbPRDNZN1zvLZRz

🛍️MINI TRITURADOR ELETRICO
https://www.mercadolivre.com.br/.../p/MLB29050257

🟢GRUPO DE OFERTAS E CUPONS DE DESCONTO🟢
https://chat.whatsapp.com/Dm1Mv7qgbPRDNZN1zvLZRz
O grupo é somente de postagem de produtos, sem chat.
Nele você encontra achadinhos para casa com cupons de desconto todos os dias!

#achadinhos #compras #mercadolivre #donadecasa #shorts
```
**Tags:** 10–13 tags específicas do produto e da dor (ex.: `como cortar cebola sem chorar`, `triturador de alho`...).

Para mudar o texto fixo, edite `build_description()` em `src/main.py`. Para mudar o estilo da narração, edite o prompt em `src/ai.py → write_script()`.

---

## Problemas comuns

| Sintoma no log | Causa / solução |
|---|---|
| `Nenhum candidato` / `HTTP 403` no Mercado Livre | O ML bloqueou o IP do servidor do GitHub naquele horário. Tente de novo; se for frequente, use um **runner no seu próprio PC** (grátis): *Settings → Actions → Runners → New self-hosted runner* e troque `runs-on: ubuntu-latest` por `runs-on: self-hosted`. |
| `nenhum vídeo real do produto encontrado` | Normal de vez em quando: o fluxo pula para o próximo produto do ranking. |
| `Sign in to confirm you're not a bot` (yt-dlp) | Configure o secret `YT_COOKIES` (veja passo 4). |
| `edge-tts falhou` | Usa o Gemini TTS sozinho como plano B. |
| `Gemini: modelo X falhou` | Modelo descontinuado ou cota do minuto; ele tenta o próximo da lista `GEMINI_MODELS`. |
| `invalid_grant` no upload | Token expirou: o app ficou em "Teste". Publique o app (passo 3.3) e gere o token de novo. |
| `quotaExceeded` | Passou de ~6 uploads/dia. Reduza agendamentos ou `VIDEOS_PER_RUN`. |
| Vídeo "Bloqueado como privado" | Veja o aviso de auditoria no passo 3. |

O arquivo `data/history.json` guarda tudo que já foi publicado (o fluxo não repete produto por 90 dias).

## ⚠️ Direitos de imagem
Os vídeos vêm dos anúncios (vendedores), de avaliações de compradores e, em último caso, do YouTube. É prática comum em perfis de achadinhos, mas o dono do vídeo pode reivindicar ou pedir remoção — o risco é maior com vídeos do YouTube (Content ID). Para reduzir, o fluxo usa trechos curtos, reenquadra, tira o áudio original e põe narração e legendas próprias. Se quiser evitar vídeos do YouTube, use `ALLOW_YOUTUBE_SEARCH=false`.

## Estrutura
```
.github/workflows/shorts.yml   agendamento + execução
src/main.py                    orquestrador
src/mercadolivre.py            busca de produtos + vídeos/fotos do anúncio
src/ai.py                      Gemini (termos virais, ranking por dor, roteiro, título, tags)
src/tts.py                     narração (edge-tts / Gemini TTS) + tempos das palavras
src/video.py                   montagem do Short no FFmpeg (legendas, gancho, CTA)
src/youtube.py                 upload no YouTube
scripts/gerar_token_youtube.py autorização do canal (rodar 1 vez no PC)
assets/fonts/Anton-Regular.ttf fonte das legendas (licença OFL)
```
