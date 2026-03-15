"""
Script de áudios do Curso 1.

Cada passo do script é um dicionário com:
  - delay_seconds (int)  : tempo de espera ANTES de enviar este passo
  - pre_text (str|None)  : texto enviado ANTES do áudio (opcional)
  - audio (str|None)     : URL pública ou media_id do áudio na Meta (opcional)
  - post_text (str|None) : texto enviado APÓS o áudio (opcional)
  - trigger (str)        : "auto"     → dispara automaticamente após o delay
                           "response" → só dispara quando o lead responder algo

Como usar:
  1. Faça upload dos áudios (.ogg/.mp3) para a Meta via app/services/whatsapp.upload_audio()
     e substitua os valores de "audio" pelo media_id retornado.
  2. Ajuste os delay_seconds conforme sua estratégia de funil.
  3. Personalize pre_text e post_text para cada passo.
"""

CURSO_1_CONFIG: dict = {
    # Nome legível do curso — substitua quando criar o produto real
    "name": "[NOME DO CURSO 1]",

    # Palavras-chave que o router usa para identificar interesse nesse curso
    "keywords": [],  # preencha ao criar o produto real

    # Passo 2 é o de investimento/preço. IA assume a partir do passo 3.
    "price_reveal_step": 3,
    # Na 2ª insistência no preço, pula direto pro passo do preço.
    "price_skip_to_step": 2,
}

CURSO_1_SCRIPT: list[dict] = [
    # ── Passo 0 — Boas-vindas imediatas ──────────────────────────────────────
    {
        "delay_seconds": 2,
        "pre_text": "Oi! Que ótimo ter você aqui 🎉 Deixa eu te contar tudo sobre o nosso curso!",
        "audio": "MEDIA_ID_AUDIO_BOAS_VINDAS_CURSO1",   # substitua pelo media_id real
        "post_text": "Ouviu? O que achou? 😊 Pode me fazer qualquer pergunta!",
        "trigger": "auto",
    },

    # ── Passo 1 — Apresentação dos diferenciais (após resposta do lead) ──────
    {
        "delay_seconds": 0,
        "pre_text": None,
        "audio": "MEDIA_ID_AUDIO_DIFERENCIAIS_CURSO1",  # substitua pelo media_id real
        "post_text": (
            "Esses são os nossos principais diferenciais! 🚀\n"
            "Tem alguma dúvida sobre a grade ou metodologia?"
        ),
        "trigger": "response",  # só envia quando o lead responder
    },

    # ── Passo 2 — Investimento e condições (2 min após o passo anterior) ─────
    {
        "delay_seconds": 120,
        "pre_text": "Agora vou te falar sobre o investimento e nossas condições especiais 💰",
        "audio": "MEDIA_ID_AUDIO_PRECO_CURSO1",         # substitua pelo media_id real
        "post_text": (
            "Condições bem acessíveis né? 😊\n"
            "Quer que eu te envie o link de matrícula?"
        ),
        "trigger": "auto",
    },

    # ── Passo 3 — Depoimento de aluno (após resposta do lead) ────────────────
    {
        "delay_seconds": 0,
        "pre_text": "Olha o que um dos nossos alunos tem a dizer sobre o curso 👇",
        "audio": "MEDIA_ID_AUDIO_DEPOIMENTO_CURSO1",    # substitua pelo media_id real
        "post_text": None,
        "trigger": "response",
    },

    # ── Passo 4 — CTA final ───────────────────────────────────────────────────
    {
        "delay_seconds": 300,
        "pre_text": None,
        "audio": None,
        "post_text": (
            "Oi! Passando pra te lembrar que as vagas com desconto são limitadas 🔥\n"
            "Já pensou na sua decisão? Posso te ajudar com mais alguma coisa?"
        ),
        "trigger": "auto",
    },
]
