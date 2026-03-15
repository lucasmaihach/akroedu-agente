# 🎙️ Guia de Setup dos Áudios

Este arquivo descreve como preparar, fazer upload e configurar os áudios do seu script de vendas.

---

## 📋 Passo 1: Crie os Áudios

Você precisa gravar **5 áudios para cada curso**:

### Para Curso 1:
1. **Boas-vindas** (30-60s) — Apresentação inicial do curso
2. **Diferenciais** (45-90s) — O que torna o curso especial
3. **Investimento** (30-60s) — Preço, parcelamento, formas de pagamento
4. **Depoimento** (30-45s) — Relato de um aluno satisfeito
5. **CTA Final** (20-30s) — Chamada para ação / urgência

### Para Curso 2:
Mesma estrutura acima, mas adaptado para o Curso 2.

**Dicas de gravação:**
- ✅ Use uma voz clara e profissional (pode ser IA com Natural Reader, ElevenLabs, etc.)
- ✅ Fundo silencioso (sem ruídos)
- ✅ Tom conversacional, não robótico
- ✅ Formato: MP3 ou OGG (Meta suporta ambos)
- ✅ Bitrate recomendado: 128 kbps

---

## 📁 Passo 2: Organize os Arquivos

Crie a estrutura de pastas:

```
projeto-raiz/
└── audios/
    ├── curso_1/
    │   ├── 01_boas_vindas.mp3
    │   ├── 02_diferenciais.mp3
    │   ├── 03_preco.mp3
    │   ├── 04_depoimento.mp3
    │   └── 05_cta_final.mp3
    └── curso_2/
        ├── 01_boas_vindas.mp3
        ├── 02_mercado.mp3
        ├── 03_grade.mp3
        ├── 04_preco.mp3
        └── 05_depoimento.mp3
```

---

## 🚀 Passo 3: Faça Upload para a Meta

Você tem **2 opções**:

### Opção A: Upload via Script Python (Recomendado)

Crie um arquivo `upload_audios.py` na raiz do projeto:

```python
import asyncio
from app.services.whatsapp import upload_audio
from app.config import settings
from pathlib import Path

async def upload_all_audios():
    """Faz upload de todos os áudios e exibe os media_ids."""
    audios_dir = Path("audios")
    
    for course_dir in audios_dir.iterdir():
        if not course_dir.is_dir():
            continue
        
        course_name = course_dir.name
        print(f"\n{'='*60}")
        print(f"Fazendo upload dos áudios de {course_name}")
        print(f"{'='*60}\n")
        
        for audio_file in sorted(course_dir.glob("*.mp3")):
            try:
                media_id = await upload_audio(str(audio_file))
                print(f"✅ {audio_file.name}")
                print(f"   Media ID: {media_id}\n")
            except Exception as e:
                print(f"❌ Erro ao fazer upload de {audio_file.name}: {e}\n")

if __name__ == "__main__":
    asyncio.run(upload_all_audios())
```

Rode:

```bash
python upload_audios.py
```

**Salve os media_ids retornados!** Você vai precisar deles no próximo passo.

### Opção B: Upload Manual via Meta API

Usando `curl`:

```bash
AUDIO_FILE="audios/curso_1/01_boas_vindas.mp3"
ACCESS_TOKEN="seu-token-aqui"
PHONE_NUMBER_ID="seu-phone-number-id"
API_VERSION="v20.0"

curl -X POST "https://graph.facebook.com/$API_VERSION/$PHONE_NUMBER_ID/media" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "messaging_product=whatsapp" \
  -F "file=@$AUDIO_FILE"
```

Resposta esperada:

```json
{
  "id": "123456789abcdef"
}
```

Salve o `id` — esse é o media_id!

---

## 🎯 Passo 4: Atualize o Script

Agora que tem os media_ids, atualize os scripts:

### Arquivo: `app/script/schedules/curso_1_script.py`

```python
CURSO_1_SCRIPT: list[dict] = [
    # ── Passo 0 — Boas-vindas ────────────────────
    {
        "delay_seconds": 2,
        "pre_text": "Oi! Que ótimo ter você aqui 🎉 Deixa eu te contar tudo sobre o nosso curso!",
        "audio": "MEDIA_ID_DO_AUDIO_01_BOAS_VINDAS",  # <- Cole aqui!
        "post_text": "Ouviu? O que achou? 😊 Pode me fazer qualquer pergunta!",
        "trigger": "auto",
    },

    # ── Passo 1 — Diferenciais ────────────────────
    {
        "delay_seconds": 0,
        "pre_text": None,
        "audio": "MEDIA_ID_DO_AUDIO_02_DIFERENCIAIS",  # <- Cole aqui!
        "post_text": "Esses são os nossos principais diferenciais! 🚀\nTem alguma dúvida?",
        "trigger": "response",
    },

    # ── Passo 2 — Investimento ────────────────────
    {
        "delay_seconds": 120,
        "pre_text": "Agora vou te falar sobre o investimento e nossas condições especiais 💰",
        "audio": "MEDIA_ID_DO_AUDIO_03_PRECO",  # <- Cole aqui!
        "post_text": "Condições bem acessíveis né? 😊\nQuer que eu te envie o link de matrícula?",
        "trigger": "auto",
    },

    # ── Passo 3 — Depoimento ──────────────────────
    {
        "delay_seconds": 0,
        "pre_text": "Olha o que um dos nossos alunos tem a dizer sobre o curso 👇",
        "audio": "MEDIA_ID_DO_AUDIO_04_DEPOIMENTO",  # <- Cole aqui!
        "post_text": None,
        "trigger": "response",
    },

    # ── Passo 4 — CTA Final ────────────────────────
    {
        "delay_seconds": 300,
        "pre_text": None,
        "audio": None,  # Apenas texto, sem áudio
        "post_text": (
            "Oi! Passando pra te lembrar que as vagas com desconto são limitadas 🔥\n"
            "Já pensou na sua decisão? Posso te ajudar com mais alguma coisa?"
        ),
        "trigger": "auto",
    },
]
```

### Arquivo: `app/script/schedules/curso_2_script.py`

Faça o mesmo, substituindo os media_ids pelos do Curso 2.

---

## 🔄 Passo 5: Teste os Áudios

### Teste Local

1. Inicie a aplicação:
```bash
docker-compose up -d
```

2. Envie uma mensagem de teste (via WhatsApp no número configurado ou via curl)

3. Verifique os logs:
```bash
docker-compose logs -f api | grep -i audio
```

Você deve ver:
```
🔊 Áudio enviado por media_id. to=5511999999999 media_id=123456789
```

### Teste Manual no WhatsApp

1. Mande "Oi" para o seu número de WhatsApp
2. Aguarde o agente responder
3. Aguarde o delay (2 segundos no passo 0)
4. O áudio deve chegar automaticamente
5. Responda algo
6. O próximo áudio deve chegar conforme o trigger (auto ou response)

---

## ⏱️ Entendendo o Fluxo de Delays

```
Lead manda mensagem
        ↓
delay_seconds = 2
        ↓ (aguarda 2 segundos)
        ↓
Envia pre_text (opcional)
        ↓
Aguarda 1.5s
        ↓
Envia áudio
        ↓
Aguarda 1.5s
        ↓
Envia post_text (opcional)
```

### Exemplo de Passo com Trigger "auto":

```python
{
    "delay_seconds": 120,  # ← Aguarda 2 minutos após o passo anterior
    "pre_text": "Deixa eu te contar sobre o preço...",
    "audio": "MEDIA_ID_PRECO",
    "post_text": "Ficou claro? Tem dúvida?",
    "trigger": "auto",  # ← Dispara automaticamente após o delay
}
```

### Exemplo de Passo com Trigger "response":

```python
{
    "delay_seconds": 0,  # ← Sem delay, dispara imediatamente
    "pre_text": None,
    "audio": "MEDIA_ID_DIFERENCIAIS",
    "post_text": "Tem interesse em algum dos diferenciais?",
    "trigger": "response",  # ← Só dispara quando o lead responder
}
```

---

## 🐛 Troubleshooting

### "Erro ao fazer upload: 400 Bad Request"

✅ Verifique que o arquivo é MP3 ou OGG
✅ Verifique que o arquivo não está corrompido
✅ Tente usar um arquivo de exemplo conhecidamente funcionando

### "Áudio enviado mas lead não ouve nada"

✅ Verifique que o media_id é válido
✅ Cheque se o format é suportado (MP3/OGG)
✅ Verifique logs: `docker-compose logs -f api | grep audio`

### "Script está enviando áudios duplicados"

✅ Isso pode acontecer se houver erro de retry
✅ O Redis lock deveria prevenir isso — cheque se está funcionando
✅ Reinicie: `docker-compose restart api`

### "Lead está vendo texto do pre_text mas não áudio"

✅ Pode ser timeout da Meta API — tente aumentar delay_seconds
✅ Verifique conectividade da VPS com a API da Meta
✅ Cheque os logs da API

---

## 📊 Exemplo de Script Completo (Curso 1)

```python
CURSO_1_SCRIPT = [
    {
        "delay_seconds": 2,
        "pre_text": "Oi! 👋 Bem-vindo ao nosso MBA em Gestão!",
        "audio": "5102376458926",  # Áudio: Boas-vindas
        "post_text": "Legal né? Quer saber mais?",
        "trigger": "auto",
    },
    {
        "delay_seconds": 0,
        "pre_text": None,
        "audio": "5103456234987",  # Áudio: Diferenciais
        "post_text": "Essas são nossas forças 💪",
        "trigger": "response",
    },
    {
        "delay_seconds": 120,
        "pre_text": "Agora sobre o investimento...",
        "audio": "5104567345098",  # Áudio: Preço
        "post_text": "Acessível certo? 😊",
        "trigger": "auto",
    },
    {
        "delay_seconds": 0,
        "pre_text": "Escuta esse depoimento 👇",
        "audio": "5105678456109",  # Áudio: Depoimento
        "post_text": None,
        "trigger": "response",
    },
    {
        "delay_seconds": 300,
        "pre_text": None,
        "audio": None,  # Sem áudio, só texto
        "post_text": "As vagas estão acabando! 🔥 Quer se inscrever?",
        "trigger": "auto",
    },
]
```

---

## ✅ Checklist Final

- [ ] Áudios gravados (5 para cada curso)
- [ ] Arquivos em formato MP3/OGG
- [ ] Áudios organizados em `audios/curso_1/` e `audios/curso_2/`
- [ ] Upload realizado via script ou curl
- [ ] Media IDs salvos com segurança
- [ ] Script atualizado com media IDs
- [ ] Testado localmente com ngrok
- [ ] Lead recebeu todos os áudios corretamente
- [ ] Agente respondeu além dos áudios
- [ ] Transição entre áudios foi natural (não pareceu robótico)

---

**Pronto! Seus áudios estão configurados e rodando! 🎉**

Se tiver dúvidas, verifique a seção de Troubleshooting ou veja os logs: `docker-compose logs -f api`
