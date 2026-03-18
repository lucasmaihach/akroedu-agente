"""
Script de áudios do Curso 2.

Cada passo do script é um dicionário com:
  - delay_seconds (int)  : tempo de espera ANTES de enviar este passo
  - pre_text (str|None)  : texto enviado ANTES do áudio (opcional)
  - audio (str|None)     : URL pública ou media_id do áudio na Meta (opcional)
  - post_text (str|None) : texto enviado APÓS o áudio (opcional)
  - trigger (str)        : "auto"     → dispara automaticamente após o delay
                           "response" → só dispara quando o lead responder algo
"""

CURSO_2_CONFIG: dict = {
    # Nome legível do curso — substitua quando criar o produto real
    "name": "Pós-Graduação em Marketing Digital e E-commerce",

    # Palavras-chave que o router usa para identificar interesse nesse curso
    "keywords": [
        "marketing", "digital", "e-commerce", "ecommerce",
        "seo", "sem", "facebook", "instagram", "google ads",
        "vendas online", "loja virtual", "shopify", "publicidade",
        "influencer", "inbound", "email", "social media",
    ],

    # Passo 3 é o de investimento/preço. IA assume a partir do passo 4.
    "price_reveal_step": 4,
    # Na 2ª insistência no preço, pula direto pro passo do preço.
    "price_skip_to_step": 3,

    # Passo específico onde o bloco de preço é enviado.
    "price_offer_step": 3,
}

CURSO_2_SCRIPT: list[dict] = [
    # ── Passo 0 — Boas-vindas imediatas ──────────────────────────────────────
    {
        "delay_seconds": 2,
        "pre_text": "Olá! Que bom te ver por aqui 😊 Vou te apresentar tudo sobre o nosso curso!",
        "audio": "MEDIA_ID_AUDIO_BOAS_VINDAS_CURSO2",   # substitua pelo media_id real
        "post_text": "O que achou da apresentação? Tem alguma pergunta?",
        "trigger": "auto",
    },

    # ── Passo 1 — Mercado de trabalho e ROI (após resposta do lead) ──────────
    {
        "delay_seconds": 0,
        "pre_text": None,
        "audio": "MEDIA_ID_AUDIO_MERCADO_CURSO2",       # substitua pelo media_id real
        "post_text": (
            "Números impressionantes né? 📈\n"
            "Profissionais com essa especialização estão muito valorizados no mercado!\n"
            "Quer saber mais sobre a grade curricular?"
        ),
        "trigger": "response",
    },

    # ── Passo 2 — Grade e metodologia (2 min após o passo anterior) ──────────
    {
        "delay_seconds": 120,
        "pre_text": "Deixa eu te mostrar como o curso é estruturado 📚",
        "audio": "MEDIA_ID_AUDIO_GRADE_CURSO2",         # substitua pelo media_id real
        "post_text": (
            "Metodologia 100% focada no mercado real!\n"
            "Agora vou te falar sobre o investimento 💰"
        ),
        "trigger": "auto",
    },

    # ── Passo 3 — Condições de pagamento (após resposta do lead) ─────────────
    {
        "delay_seconds": 0,
        "pre_text": "Sobre o investimento, temos condições especiais essa semana 👇",
        "audio": "MEDIA_ID_AUDIO_PRECO_CURSO2",         # substitua pelo media_id real
        "post_text": (
            "Ficou alguma dúvida sobre os valores?\n"
            "Posso calcular a melhor condição pra você! 😊"
        ),
        "trigger": "response",
    },

    # ── Passo 4 — Depoimento (5 min após o passo anterior) ───────────────────
    {
        "delay_seconds": 300,
        "pre_text": "Olha o que nossos alunos falam sobre a transformação na carreira deles 🎯",
        "audio": "MEDIA_ID_AUDIO_DEPOIMENTO_CURSO2",    # substitua pelo media_id real
        "post_text": None,
        "trigger": "auto",
    },

    # ── Passo 5 — CTA final ───────────────────────────────────────────────────
    {
        "delay_seconds": 600,
        "pre_text": None,
        "audio": None,
        "post_text": (
            "Oi! Não quero ser chato, mas as vagas realmente são limitadas 🔥\n"
            "Você já tomou sua decisão? Posso te ajudar com alguma dúvida final?"
        ),
        "trigger": "auto",
    },
]
