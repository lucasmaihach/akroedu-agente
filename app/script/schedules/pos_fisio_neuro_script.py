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
  05_visao_geral.opus         → ✅  GRAVADO — BLOCO 5: visão geral da pós (60s)
  06_detalhes_parte1.opus     → ✅  GRAVADO — BLOCO 6: prática clínica + módulos
  07_detalhes_parte2.opus     → ✅  GRAVADO — BLOCO 6: professores + tutorias + marketing
  08_pitch_valor.opus         → ✅  GRAVADO — BLOCO 7: por que essa pós
  09_preco_urgencia.opus      → ✅  GRAVADO — BLOCO 8: oferta + bolsas + urgência
  10_followup_silencio_1.opus → ⚠️  FALTA GRAVAR — FOLLOW-UP após silêncio pós-preço (35s)
  11_followup_silencio_2.opus → ⚠️  FALTA GRAVAR — FOLLOW-UP decisão em 12 meses (40s)
  12_followup_silencio_4.opus → ⚠️  FALTA GRAVAR — FOLLOW-UP custo de não fazer (50s)
"""

POS_FISIO_NEURO_CONFIG: dict = {
    # Nome legível do curso — usado no WELCOME_MESSAGE e no router
    "name": "Pós-Graduação em Fisioterapia Neurofuncional",

    # Palavras-chave que o router usa para identificar o interesse nesse curso
    "keywords": [
        "fisioterapia", "fisioterapeuta", "fisio", "neurologia",
        "neurofuncional", "neurorreabilitação", "reabilitação neurológica",
        "neuro", "home care fisio",
    ],

    # Índice do passo APÓS o áudio de preço ser enviado.
    # Antes desse passo, a IA fica em modo silencioso (não assume a conversa).
    "price_reveal_step": 10,

    # Índice para onde o script pula quando o lead insiste no preço pela 2ª vez.
    # Deve apontar para o bloco de detalhamento que encadeia automaticamente até o preço.
    "price_skip_to_step": 6,

    # Passo específico onde o bloco de preço é enviado.
    "price_offer_step": 8,
}

POS_FISIO_NEURO_SCRIPT: list[dict] = [

    # ── BLOCO 1 — Boas-vindas + Qualificação ─────────────────────────────────
    # Dispara imediatamente quando o lead entra no funil
    {
        "delay_seconds": 3,
        "pre_text": [
            "Olá, meu nome é Taynara 😊 Estou te mandando mensagem porque vi que você se interessou pela nossa pós-graduação em Fisioterapia Neurofuncional.",
            "Quero conhecer um pouquinho mais sobre você. Me conta: você já é formado? Há quanto tempo? Já atende em consultório ou tem clínica própria?",
            "Fique à vontade para escrever ou mandar áudio 🎤",
        ],
        "audio": None,  # TODO: gravar 01_boas_vindas.opus quando quiser personalizar com voz
        "post_text": None,
        "trigger": "auto",
    },

    # ── BLOCO 2 — Descoberta do Problema ─────────────────────────────────────
    # Dispara após o lead responder a qualificação
    {
        "delay_seconds": 0,
        "pre_text": [
            "Muito obrigado por compartilhar! 🙏",
            "Agora me fala: quais são os principais desafios no seu dia a dia que você acredita que essa pós poderia te ajudar a resolver?",
        ],
        "audio": None,
        "post_text": None,
        "trigger": "response",
    },

    # ── BLOCO 3 — Amplificação da Dor + Oportunidade de Mercado ──────────────
    # Dispara após o lead falar dos desafios
    {
        "delay_seconds": 0,
        "acolhimento_variations": [
            ["Obrigada por compartilhar isso, [nome] 🙏", "Você não está sozinho(a) nisso. A maioria dos fisioterapeutas que atende neuro sente exatamente o que você descreveu.", "Me deixa te mostrar como essa realidade pode mudar:"],
            ["Faz todo sentido, [nome].", "Insegurança técnica sem formação específica em neuro é esperada e totalmente resolvível.", "Olha o que acontece quando isso não é resolvido logo:"],
            ["Que bom que você trouxe isso, [nome]!", "É exatamente sobre esses pontos que eu quero conversar.", "Presta atenção nesse áudio:"],
            ["[nome], o que você descreveu é sério.", "Cada mês sem resolver isso é um mês a mais perdendo paciente e confiança técnica.", "Quero que você entenda o tamanho disso:"],
            ["Muito obrigada por ser tão honesta, [nome] 🙏", "Reconhecer o que precisa melhorar já é o primeiro passo pra mudar de patamar.", "Tenho algo importante pra te mostrar:"],
            ["Entendo, [nome].", "Você descreveu o perfil de quem mais se transforma com essa formação.", "Antes de te mostrar a solução, quero que você veja o custo de continuar assim:"],
            ["[nome], você acabou de descrever o que trava a carreira de 90% dos fisioterapeutas sem pós em neuro.", "Quanto mais tempo passa, mais difícil fica.", "Me deixa te mostrar por quê:"],
            ["Uau, [nome]! Você resumiu muito bem.", "É exatamente sobre isso que eu quero conversar hoje.", "Ouve esse áudio que vai fazer sentido:"],
            ["[nome], você acabou de descrever o que praticamente todo fisioterapeuta que me procura sente.", "Você não está atrasado(a), está no momento certo de mudar isso.", "Quero que você veja o cenário completo:"],
            ["Entende uma coisa, [nome].", "O que você descreveu não é falta de capacidade, é falta de formação específica.", "E isso tem solução. Vou te mostrar o que muda quando você resolve:"],
        ],
        "pre_text": None,
        "audio": "1463671382038744",
        "audio_duration_seconds": 82,
        "post_text": "Olha só as notícias que vou te mandar 👇",
        "trigger": "response",
    },
    # Imagens de notícias + áudio de dados de mercado
    {
        "delay_seconds": 3,
        "pre_text": None,
        "images": [
            "pos_fisio_neuro/noticia_populacao.jpg",
            "pos_fisio_neuro/noticia_home_care.jpg",
            "pos_fisio_neuro/noticia_ibge_225.jpg",
        ],
        "audio": "1619821755960042",
        "audio_duration_seconds": 48,
        "post_text": (
            "Consegue perceber como se especializar nessa área pode aumentar "
            "seu reconhecimento e melhorar sua remuneração? 🚀"
        ),
        "trigger": "auto",
    },

    # ── BLOCO 4 — Transição para Apresentação da Pós ─────────────────────────
    {
        "delay_seconds": 0,
        "acolhimento_variations": [
            ["Fico feliz que percebe isso, [nome]!", "Quem enxerga essa oportunidade cedo já sai na frente. Me deixa te mostrar como transformar isso em realidade:"],
            ["Exatamente, [nome]!", "Quem se especializar primeiro vai ocupar esse espaço, o mercado não espera. Vou te mostrar o próximo passo pra você ser essa profissional:"],
            ["Que bom, [nome]!", "Profissionais que chegam com essa visão são exatamente os que mais crescem depois da pós. Por isso quero que você ouça isso:"],
            ["Isso mesmo, [nome].", "Os dados são claros e você acabou de conectar os pontos que a maioria demora anos pra entender. Vou te mostrar como agir:"],
            ["[nome], o que você percebeu agora é só a ponta do iceberg.", "Tem muito mais oportunidade nesse mercado. Pra aproveitar, você precisa tomar uma decisão. Me deixa te explicar:"],
            ["Consegue sim, [nome]! E sabe mais?", "Muitas alunas nossas pensavam exatamente assim antes de entrar na pós e hoje estão colhendo esses resultados. Quer saber como chegar lá?"],
            ["Perfeito, [nome]!", "Você já tem a visão certa. Agora é sobre ter a formação que vai sustentar isso na prática. Vou te mostrar como funciona:"],
            ["Fico feliz que você enxerga isso, [nome].", "Imagina continuar mais um ano sem agir, enquanto outros profissionais se especializam. Por isso o momento de decidir é agora:"],
            ["Ótimo, [nome]!", "Você já tem a mentalidade certa. Me deixa te mostrar o que diferencia quem só enxerga a oportunidade de quem realmente aproveita ela:"],
            ["[nome], você acabou de confirmar o que os dados mostram.", "Profissionais com essa visão e a formação certa dominam o mercado de neuro. Me deixa te mostrar o que precisa fazer pra chegar lá:"],
        ],
        "pre_text": None,
        "audio": "1011913898678191",
        "audio_duration_seconds": 61,
        "post_text": "Quer que eu te mostre como nossa pós-graduação pode te ajudar a alcançar isso?",
        "trigger": "response",
    },

    # ── BLOCO 5 — Visão Geral da Pós ─────────────────────────────────────────
    {
        "delay_seconds": 0,
        "acolhimento_variations": [
            "Ótimo, [nome]! Você vai adorar o que vou te mostrar 😊",
            "Boa escolha, [nome]. Essa é a parte onde tudo começa a fazer sentido 😊",
            "Perfeito, [nome]! Então vamos lá, sem enrolação 😊",
            "Que bom, [nome]! Adoro quando o profissional tá aberto pra entender de verdade. Fica muito mais fácil de ajudar 😊",
            "Haha, [nome], essa é a melhor parte! Presta atenção que você vai gostar 😄",
            "[nome], o que você vai ouvir agora pode mudar a forma como você enxerga sua carreira. Fica atento(a) 😊",
            "Ótimo, [nome]! Então sem perder tempo, deixa eu te mostrar o que essa pós entrega 😊",
            "Boa, [nome]! Muitas alunas disseram que esse foi o momento em que tudo ficou claro. Acho que vai ser assim com você também 😊",
            "[nome], tenho certeza que você vai sair dessa conversa com uma visão completamente diferente sobre o que é possível na sua carreira 😊",
            "Que ótimo, [nome]! Essa abertura pra aprender é o que diferencia os profissionais que realmente evoluem. Vou te mostrar tudo 😊",
        ],
        "pre_text": None,
        "audio": "1508198587559926",
        "audio_duration_seconds": 63,
        "post_text": "Isso faz sentido pro que você está buscando?",
        "trigger": "response",
    },

    # ── BLOCO 6 — Detalhamento Técnico ───────────────────────────────────────
    {
        "delay_seconds": 0,
        "acolhimento_variations": [
            ["Que bom, [nome]! Fico feliz que vê isso 😊", "Me deixa te mostrar como funciona na prática, que é onde a diferença aparece de verdade:"],
            ["Perfeito, [nome]!", "Agora você vai ver como isso funciona na prática, que é onde a coisa fica realmente interessante 😊"],
            ["Fico muito feliz, [nome]!", "Você descreveu exatamente o que nossas alunas mais valorizam na pós. Me deixa detalhar como tudo isso se aplica no dia a dia 😊"],
            ["Exato, [nome]!", "É uma abordagem que não existe em nenhuma outra pós do mercado. Vou te mostrar como isso funciona na prática clínica 😊"],
            ["[nome], o que você acabou de ouvir é só a estrutura.", "O que realmente impressiona é ver cada módulo se aplicando no atendimento real.", "Ouve esse próximo áudio 😊"],
            ["Boa, [nome]!", "E o melhor ainda tá por vir. Agora vou te mostrar como tudo isso vira prática clínica real 😄"],
            ["Ótimo, [nome]!", "Então sem enrolar, me deixa te mostrar como cada módulo se aplica em casos reais que você já pode estar enfrentando 😊"],
            ["[nome], você vai amar o próximo áudio!", "Aqui é onde as alunas geralmente falam 'é exatamente isso que eu precisava' 😄"],
            ["Que bom, [nome]!", "Quando o conteúdo se encaixa com o que você busca, o aprendizado é muito mais rápido. Vou te mostrar como cada módulo funciona 😊"],
            ["Perfeito, [nome]!", "Imagina ver isso aplicado em um paciente pós-AVE na prática. É onde a diferença fica evidente. Ouve 😊"],
        ],
        "pre_text": None,
        "audio": "1261960869373711",
        "audio_duration_seconds": 59,
        "post_text": (
            "*Módulos da Pós-Graduação:*\n\n"
            "1️⃣ *Neuroanatomia do sistema nervoso*\n"
            "Base anatômica essencial para compreensão clínica das lesões neurológicas.\n"
            "• Organização macro e microanatômica do SNC e SNP\n"
            "• Neuroanatomia funcional: córtex, tronco encefálico, cerebelo e medula\n"
            "• Vias motoras, sensitivas, autonômicas e associativas\n"
            "• Circuitos córtico-subcorticais e cerebelares\n\n"
            "2️⃣ *Fisiopatologia clínica das neuropatologias do adulto*\n"
            "AVE, TCE, lesão medular, doenças neurodegenerativas.\n"
            "• AVC: isquêmico e hemorrágico (fases e repercussões funcionais)\n"
            "• Traumatismo cranioencefálico\n"
            "• Lesão medular (classificação ASIA e implicações funcionais)\n"
            "• Doença de Parkinson e síndromes parkinsonianas\n\n"
            "3️⃣ *Fisiopatologia clínica das neuropatologias da criança*\n"
            "Paralisia cerebral, síndromes genéticas, atrasos do desenvolvimento.\n"
            "• Neurodesenvolvimento típico e atípico\n"
            "• Paralisia cerebral (classificações e apresentações clínicas)\n"
            "• Síndromes genéticas com repercussão neuromotora\n"
            "• Epilepsia e repercussões funcionais\n\n"
            "4️⃣ *Estratégias de cinesioterapia no paciente neurológico adulto*\n"
            "Técnicas e protocolos de intervenção motora.\n"
            "• Controle motor e reaprendizado funcional\n"
            "• Princípios da Facilitação Neuromuscular Proprioceptiva (FNP / PNF)\n"
            "• Terapia do Espelho\n"
            "• Treino de Marcha Neurofuncional\n\n"
            "5️⃣ *Estratégias de cinesioterapia em neuropediatria*\n"
            "Abordagens terapêuticas para desenvolvimento infantil.\n"
            "• Intervenção precoce baseada no neurodesenvolvimento\n"
            "• Estimulação sensório-motora\n"
            "• Treino funcional lúdico e contextualizado\n"
            "• Estratégias para controle postural\n\n"
            "6️⃣ *Terapia manual no paciente neurológico*\n"
            "Fundamentos e aplicações da terapia manual.\n"
            "• Fundamentos neurofisiológicos da terapia manual\n"
            "• Mobilizações articulares e neurais\n"
            "• Liberação miofascial aplicada à neurologia\n"
            "• Terapia manual no manejo da espasticidade\n\n"
            "7️⃣ *Fisioterapia respiratória no paciente neurológico*\n"
            "Protocolos respiratórios para adultos e crianças neurológicas.\n"
            "• Avaliação da função respiratória\n"
            "• Técnicas de higiene brônquica\n"
            "• Reeducação ventilatória\n"
            "• Manejo de pacientes traqueostomizados\n\n"
            "8️⃣ *Abordagem neurofuncional em home care*\n"
            "Estratégias de atendimento domiciliar e gestão de casos complexos.\n"
            "• Avaliação funcional no ambiente domiciliar\n"
            "• Adaptação do tratamento ao contexto real do paciente\n"
            "• Planejamento terapêutico em home care\n"
            "• Continuidade do tratamento intensivo em domicílio\n\n"
            "9️⃣ *Órteses e tecnologias assistivas em reabilitação neurofuncional*\n"
            "Prescrição, indicação e aplicação de recursos tecnológicos.\n"
            "• Princípios biomecânicos das órteses\n"
            "• Órteses para membros superiores e inferiores\n"
            "• Indicações e contraindicações clínicas\n"
            "• Recursos para marcha, postura e função manual"
        ),
        "trigger": "response",
    },
    {
        "delay_seconds": 5,
        "pre_text": None,
        "audio": "1507890224019892",
        "audio_duration_seconds": 64,
        "mid_text": (
            "Com essa formação você passa a aceitar casos que hoje recusa, "
            "cobrar mais por sessão e se posicionar como referência em neuro na sua região. 💡"
        ),
        "images_post": [
            "pos_fisio_neuro/diploma.jpg",
        ],
        "post_text": "Já consegue ver seu nome escrito nesse diploma? 🎓",
        "trigger": "auto",
    },

    # ── BLOCO 7 — Pitch de Valor ──────────────────────────────────────────────
    {
        "delay_seconds": 0,
        "acolhimento_variations": [
            ["Haha, já tô vendo seu nome aí também, [nome]! 😄", "Esse diploma vai representar muito na sua carreira. Vou te falar sobre o investimento pra chegar até ele:"],
            ["Que bom, [nome]!", "Esse momento em que o profissional se vê no diploma é quando a decisão começa a ficar mais clara. Me deixa te mostrar o valor real dessa formação:"],
            ["Ótimo, [nome]!", "Então vamos falar sobre o que precisa acontecer pra esse diploma sair do imaginário e ir pra sua parede:"],
            ["[nome], esse diploma é reconhecido pelo MEC e vai abrir portas que hoje estão fechadas.", "Faz sentido se ver nele 😊 Vou te explicar o que você investe pra conquistar isso:"],
            ["[nome], pensa comigo: daqui 12 meses esse diploma vai representar não só um título, mas uma carreira completamente diferente.", "Vale a reflexão. Me deixa mostrar o que está por trás desse investimento:"],
            ["Boa, [nome]! Esse diploma já tem seu nome escrito.", "Agora é só você confirmar 😊 Vou te explicar o investimento:"],
            ["[nome], as alunas que mais cresceram com a pós disseram a mesma coisa quando viram o diploma 😄", "É um ótimo sinal! Vamos falar sobre o investimento:"],
            ["Ótimo, [nome]! Esse diploma é emitido pela Anhanguera, uma das maiores instituições do país.", "Ter ele no currículo é diferencial real. Me deixa falar sobre o investimento:"],
            ["Fico feliz que consegue se ver nele, [nome]!", "E quanto mais cedo você começar, mais cedo esse diploma vai estar na sua mão e na sua carreira. Vou te apresentar o investimento:"],
            ["[nome], já tô vendo seu nome nele também! 😍", "Me deixa te mostrar o que é preciso pra tornar isso real:"],
        ],
        "pre_text": None,
        "audio": "1235587978692569",
        "audio_duration_seconds": 65,
        "post_text": "Quando você compara a qualidade com o investimento, consegue ver o valor?",
        "trigger": "response",
    },

    # ── BLOCO 8 — Oferta de Preço + Urgência ─────────────────────────────────
    {
        "delay_seconds": 0,
        "audio": "2075466936567052",
        "audio_duration_seconds": 61,
        "post_text": [
            "Para garantir sua vaga é só acessar o link abaixo 👇\nhttps://link-de-teste.com/pos-fisio-neuro",
            "Como prefere fazer: PIX ou cartão? 😊",
        ],
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
