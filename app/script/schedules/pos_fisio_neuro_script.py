"""
Script de áudios — Pós-Graduação em Fisioterapia Neurofuncional.

Baseado no script de vendas oficial (10 blocos).

Como usar:
  1. Grave os áudios conforme as descrições abaixo e coloque em audios/pos_fisio_neuro/
  2. Faça upload: make upload-audios
  3. Substitua os valores MEDIA_ID_* pelos IDs reais gerados no upload

Status dos áudios:
  01_boas_vindas.opus         → ⚠️  FALTA GRAVAR — BLOCO 1: apresentação + qualificação (35s)
  02_amplificacao_dor.opus    → ✅  GRAVADO — BLOCO 3: dor + oportunidade de mercado
  03_mercado_dados.opus       → ✅  GRAVADO — BLOCO 3: dados IBGE + home care
  04_transicao.opus           → ✅  GRAVADO — BLOCO 4: urgência + decisão
  05_visao_geral.opus         → ⚠️  FALTA GRAVAR — BLOCO 5: visão geral da pós (60s)
  06_detalhes_parte1.opus     → ✅  GRAVADO — BLOCO 6: prática clínica + módulos
  07_detalhes_parte2.opus     → ✅  GRAVADO — BLOCO 6: professores + tutorias + marketing
  08_pitch_valor.opus         → ✅  GRAVADO — BLOCO 7: por que essa pós
  09_preco_urgencia.opus      → ✅  GRAVADO — BLOCO 8: oferta + bolsas + urgência
  10_followup_silencio_1.opus → ⚠️  FALTA GRAVAR — FOLLOW-UP após silêncio pós-preço (35s)
  11_followup_silencio_2.opus → ⚠️  FALTA GRAVAR — FOLLOW-UP decisão em 12 meses (40s)
  12_followup_silencio_4.opus → ⚠️  FALTA GRAVAR — FOLLOW-UP custo de não fazer (50s)
"""

POS_FISIO_NEURO_SCRIPT: list[dict] = [

    # ── BLOCO 1 — Boas-vindas + Qualificação ─────────────────────────────────
    # Dispara imediatamente quando o lead entra no funil
    {
        "delay_seconds": 3,
        "pre_text": (
            "Olá, meu nome é Taynara 😊 Estou te mandando mensagem porque vi que você "
            "se interessou pela nossa pós-graduação em Fisioterapia Neurofuncional.\n\n"
            "Quero conhecer um pouquinho mais sobre você. Me conta: você já é formado? "
            "Há quanto tempo? Já atende em consultório ou tem clínica própria?\n\n"
            "Fique à vontade para escrever ou mandar áudio 🎤"
        ),
        "audio": None,  # TODO: gravar 01_boas_vindas.opus quando quiser personalizar com voz
        "post_text": None,
        "trigger": "auto",
    },

    # ── BLOCO 2 — Descoberta do Problema ─────────────────────────────────────
    # Dispara após o lead responder a qualificação
    {
        "delay_seconds": 0,
        "pre_text": (
            "Muito obrigado por compartilhar! 🙏\n\n"
            "Agora me fala: quais são os principais desafios no seu dia a dia "
            "que você acredita que essa pós poderia te ajudar a resolver?"
        ),
        "audio": None,
        "post_text": None,
        "trigger": "response",
    },

    # ── BLOCO 3 — Amplificação da Dor + Oportunidade de Mercado ──────────────
    # Dispara após o lead falar dos desafios
    {
        "delay_seconds": 0,
        "pre_text": None,
        "audio": "pos_fisio_neuro/02_amplificacao_dor.opus",
        "post_text": "Olha só as notícias que vou te mandar 👇",
        "trigger": "response",
    },
    # Imagens de notícias (enviadas como texto descritivo — substitua por send_image se disponível)
    {
        "delay_seconds": 3,
        "pre_text": (
            "📊 *Dados do mercado de neurorreabilitação:*\n\n"
            "• População brasileira envelhecendo rapidamente\n"
            "• Crescimento acelerado do home care no Brasil\n"
            "• Alta demanda por fisioterapeutas especializados\n"
            "• IBGE: até 225% de aumento de remuneração com pós-graduação"
        ),
        "audio": "pos_fisio_neuro/03_mercado_dados.opus",
        "post_text": (
            "Consegue perceber como se especializar nessa área pode aumentar "
            "seu reconhecimento e melhorar sua remuneração? 🚀"
        ),
        "trigger": "auto",
    },

    # ── BLOCO 4 — Transição para Apresentação da Pós ─────────────────────────
    {
        "delay_seconds": 0,
        "pre_text": None,
        "audio": "pos_fisio_neuro/04_transicao.opus",
        "post_text": "Quer que eu te mostre como nossa pós-graduação pode te ajudar a alcançar isso?",
        "trigger": "response",
    },

    # ── BLOCO 5 — Visão Geral da Pós ─────────────────────────────────────────
    {
        "delay_seconds": 0,
        "pre_text": "Bom, vamos lá! 🎯",
        "audio": "pos_fisio_neuro/05_visao_geral.opus",
        "post_text": "Isso faz sentido pro que você está buscando?",
        "trigger": "response",
    },

    # ── BLOCO 6 — Detalhamento Técnico ───────────────────────────────────────
    {
        "delay_seconds": 0,
        "pre_text": "Deixa eu te mostrar como essa pós funciona na prática 👇",
        "audio": "pos_fisio_neuro/06_detalhes_parte1.opus",
        "post_text": None,
        "trigger": "response",
    },
    {
        "delay_seconds": 5,
        "pre_text": None,
        "audio": "pos_fisio_neuro/07_detalhes_parte2.opus",
        "post_text": (
            "Você vai aprender a usar esse conteúdo para criar um posicionamento online, "
            "construir presença digital, atrair mais pacientes e cobrar preços mais altos. 💡\n\n"
            "Já consegue ver seu nome escrito nesse diploma? 🎓"
        ),
        "trigger": "auto",
    },

    # ── BLOCO 7 — Pitch de Valor ──────────────────────────────────────────────
    {
        "delay_seconds": 0,
        "pre_text": None,
        "audio": "pos_fisio_neuro/08_pitch_valor.opus",
        "post_text": "Quando você compara a qualidade com o investimento, consegue ver o valor?",
        "trigger": "response",
    },

    # ── BLOCO 8 — Oferta de Preço + Urgência ─────────────────────────────────
    {
        "delay_seconds": 0,
        "pre_text": (
            "O valor de referência dessa pós no mercado é 12x de R$ 797.\n\n"
            "Mas para você que chegou até aqui, a condição especial é *20x de R$ 257* 🎯"
        ),
        "audio": "pos_fisio_neuro/09_preco_urgencia.opus",
        "post_text": (
            "Para garantir sua vaga é só acessar o link abaixo 👇\n"
            "https://link-de-teste.com/pos-fisio-neuro\n\n"
            "Como prefere fazer: PIX ou cartão? 😊"
        ),
        "trigger": "response",
    },

    # ── FOLLOW-UP 1 — Silêncio após 2h (qualquer momento) ────────────────────
    {
        "delay_seconds": 7200,   # 2 horas
        "pre_text": "Opa, cadê você?? Tu me deixou falando sozinho 😅",
        "audio": None,
        "post_text": None,
        "trigger": "auto",
    },

    # ── FOLLOW-UP 2 — Silêncio após 4h ───────────────────────────────────────
    {
        "delay_seconds": 7200,   # +2 horas (total 4h)
        "pre_text": "Você já atende pacientes neurológicos no seu consultório?",
        "audio": None,
        "post_text": None,
        "trigger": "auto",
    },

    # ── FOLLOW-UP 3 — Dia seguinte ────────────────────────────────────────────
    {
        "delay_seconds": 57600,  # ~16h depois (dia seguinte de manhã)
        "pre_text": "Eu acabei não te perguntando, de qual cidade você é? 😄",
        "audio": None,
        "post_text": None,
        "trigger": "auto",
    },

    # ── FOLLOW-UP 4 — Após 2 dias ─────────────────────────────────────────────
    {
        "delay_seconds": 86400,  # +1 dia
        "pre_text": "Conseguiu ouvir o áudio que mandei?",
        "audio": None,
        "post_text": None,
        "trigger": "auto",
    },

    # ── FOLLOW-UP APÓS SABER O VALOR — 1h depois ─────────────────────────────
    # OBS: este bloco é controlado pelo agente quando detecta silêncio pós-preço
    {
        "delay_seconds": 3600,   # 1 hora após envio do preço
        "pre_text": None,
        "audio": None,  # TODO: gravar 10_followup_silencio_1.opus e substituir pelo media_id
        "post_text": None,
        "trigger": "auto",
    },

    # ── FOLLOW-UP APÓS SABER O VALOR — 4h depois ─────────────────────────────
    {
        "delay_seconds": 10800,  # +3 horas (total 4h)
        "pre_text": None,
        "audio": None,  # TODO: gravar 11_followup_silencio_2.opus e substituir pelo media_id
        "post_text": None,
        "trigger": "auto",
    },

    # ── FOLLOW-UP APÓS SABER O VALOR — Dia seguinte manhã ────────────────────
    {
        "delay_seconds": 57600,
        "pre_text": (
            "Bom dia! ☀️ A bolsa especial que te mostrei ontem ainda está disponível "
            "até hoje às 23h59. Depois disso volta ao valor normal. "
            "Quer garantir sua vaga com desconto?"
        ),
        "audio": None,
        "post_text": None,
        "trigger": "auto",
    },

    # ── FOLLOW-UP APÓS SABER O VALOR — Dia seguinte tarde ────────────────────
    {
        "delay_seconds": 21600,  # +6 horas (tarde)
        "pre_text": None,
        "audio": None,  # TODO: gravar 12_followup_silencio_4.opus e substituir pelo media_id
        "post_text": None,
        "trigger": "auto",
    },

    # ── FOLLOW-UP APÓS SABER O VALOR — Último aviso (noite) ──────────────────
    {
        "delay_seconds": 14400,  # +4 horas (noite)
        "pre_text": (
            "Última chance de garantir a bolsa especial. 🔥\n"
            "Depois de hoje, volta ao valor integral.\n\n"
            "Se tiver alguma dúvida que te impeça de decidir, me fala agora que eu te ajudo. "
            "Vale a pena?"
        ),
        "audio": None,
        "post_text": None,
        "trigger": "auto",
    },
]
