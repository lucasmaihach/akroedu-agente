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
        "acolhimento_variations": [
            "Obrigada por compartilhar isso, [nome]. Você não está sozinho(a) nessa — a maioria dos fisioterapeutas que atende neuro sente exatamente o que você descreveu. Deixa eu te mostrar como essa realidade pode mudar:",
            "Faz todo sentido, [nome]. Insegurança técnica sem formação específica em neuro é esperada — e totalmente resolvível. Olha só o que acontece quando você não resolve isso logo:",
            "Que bom que você trouxe isso, [nome]! Porque é exatamente sobre esses pontos que eu quero te falar algo que vai fazer muito sentido. Presta atenção nesse áudio:",
            "[nome], o que você descreveu é sério. Cada mês sem resolver isso é um mês a mais perdendo pacientes e confiança técnica. Quero que você entenda o tamanho disso:",
            "Muito obrigada por ser tão honesta, [nome]. Essa coragem de reconhecer os próprios pontos de melhora é o primeiro passo pra mudar de patamar. E eu tenho algo importante pra te mostrar sobre isso:",
            "Perfeito, [nome]. Você descreveu o perfil de quem mais se transforma com essa formação. Mas antes de te mostrar a solução, quero que você entenda o custo de continuar assim:",
            "[nome], você acabou de descrever o que trava a carreira de 90% dos fisioterapeutas que não têm pós em neuro. E quanto mais tempo passa, mais difícil fica de mudar isso. Deixa eu te mostrar por quê:",
            "Uau, [nome]! Você resumiu muito bem. É exatamente sobre isso que eu quero conversar com você hoje. Manda ouvir esse áudio que vai fazer sentido:",
            "[nome], você acabou de descrever o que praticamente todo fisioterapeuta que me procura sente. Você não está atrasado(a) — está no momento certo de mudar isso. Quero que você veja o cenário completo antes de continuar:",
            "Interessante, [nome]. O que você descreveu não é falta de capacidade — é falta de formação específica. São coisas muito diferentes. E isso tem solução. Vou te mostrar o que muda quando você resolve isso de verdade:",
        ],
        "pre_text": None,
        "audio": "pos_fisio_neuro/02_amplificacao_dor.opus",
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
        "acolhimento_variations": [
            "Fico feliz que percebe isso, [nome]! Quem enxerga essa oportunidade cedo já sai na frente da maioria. Agora deixa eu te mostrar como transformar isso em realidade:",
            "Exato, [nome]. E o mercado não vai esperar — quem se especializar primeiro vai ocupar esse espaço. Vou te mostrar o próximo passo pra você ser essa profissional:",
            "Que bom, [nome]! Profissionais que chegam até mim com essa visão são exatamente os que mais crescem depois da pós. E é por isso que quero que você ouça isso:",
            "Isso mesmo, [nome]. Os dados são claros — e você acabou de conectar os pontos que a maioria demora anos pra entender. Agora vou te mostrar como agir a partir disso:",
            "[nome], o que você percebeu agora é só a ponta do iceberg. Tem muito mais oportunidade nesse mercado do que parece. Pra aproveitar isso, você precisa tomar uma decisão. Deixa eu te explicar:",
            "Consegue sim, [nome]! E sabe o que mais? Muitas alunas nossas pensavam exatamente assim antes de entrar na pós — e hoje estão colhendo exatamente esses resultados. Quer saber como chegar lá?",
            "Perfeito, [nome]. Você já tem a visão certa. Agora é sobre ter a formação que vai sustentar essa visão na prática. Vou te mostrar como isso funciona:",
            "Fico muito feliz que enxerga isso, [nome]. Agora imagina continuar mais um ano sem agir em cima disso — outros profissionais estão se especializando agora. É por isso que o momento de decidir é esse:",
            "Ótimo, [nome]! Então você já tem a mentalidade certa. Agora deixa eu te mostrar o que diferencia quem só enxerga a oportunidade de quem realmente aproveita ela:",
            "[nome], você acabou de confirmar o que os dados mostram. Profissionais com essa visão e com a formação certa são os que realmente dominam o mercado de neuro. Agora deixa eu te mostrar o que precisa fazer pra chegar lá:",
        ],
        "pre_text": None,
        "audio": "pos_fisio_neuro/04_transicao.opus",
        "post_text": "Quer que eu te mostre como nossa pós-graduação pode te ajudar a alcançar isso?",
        "trigger": "response",
    },

    # ── BLOCO 5 — Visão Geral da Pós ─────────────────────────────────────────
    {
        "delay_seconds": 0,
        "acolhimento_variations": [
            "Ótimo, [nome]! Você vai adorar o que vou te mostrar 😊",
            "Boa escolha, [nome]. Essa é a parte onde tudo começa a fazer sentido 😊",
            "Perfeito, [nome]. Então vamos lá — sem enrolação 😊",
            "Que bom, [nome]! Adoro quando o profissional tá aberto pra entender de verdade. Fica muito mais fácil de ajudar 😊",
            "Haha, [nome], essa é a melhor parte! Presta atenção que você vai gostar 😄",
            "[nome], o que você vai ouvir agora pode mudar a forma como você enxerga sua carreira nos próximos anos. Fica atento(a) 😊",
            "Ótimo, [nome]. Então sem perder tempo — deixa eu te mostrar o que essa pós entrega 😊",
            "Boa, [nome]! Muitas alunas disseram que esse foi o momento em que tudo ficou claro pra elas. Acho que vai ser assim com você também 😊",
            "[nome], tenho certeza que você vai sair dessa conversa com uma visão completamente diferente sobre o que é possível na sua carreira 😊",
            "Que ótimo, [nome]! Essa abertura pra aprender é o que diferencia os profissionais que realmente evoluem. Vou te mostrar tudo com cuidado 😊",
        ],
        "pre_text": None,
        "audio": "pos_fisio_neuro/05_visao_geral.opus",
        "post_text": "Isso faz sentido pro que você está buscando?",
        "trigger": "response",
    },

    # ── BLOCO 6 — Detalhamento Técnico ───────────────────────────────────────
    {
        "delay_seconds": 0,
        "acolhimento_variations": [
            "Que bom, [nome]! Fico feliz que você vê isso. Agora deixa eu te mostrar como funciona na prática — que é onde a diferença aparece de verdade 😊",
            "Perfeito, [nome]. Então agora você vai ver como isso funciona na prática — que é onde a coisa fica realmente interessante 😊",
            "Fico muito feliz que faz sentido, [nome]! Você descreveu exatamente o que nossas alunas mais valorizam na pós. Agora deixa eu te detalhar como tudo isso se aplica no dia a dia 😊",
            "Exato, [nome]. É uma abordagem que não existe em nenhuma outra pós do mercado com esse nível de profundidade. Vou te mostrar como isso funciona na prática clínica real 😊",
            "[nome], o que você acabou de ouvir é só a estrutura. O que realmente impressiona é ver como cada módulo se aplica no atendimento do dia a dia. Ouve esse próximo áudio que vai ficar mais claro 😊",
            "Boa, [nome]! E o melhor ainda tá por vir — agora vou te mostrar como tudo isso vira prática clínica real 😄",
            "Ótimo, [nome]. Então sem enrolar — deixa eu te mostrar como cada módulo se aplica em casos reais que você já pode estar enfrentando hoje 😊",
            "[nome], você vai amar o próximo áudio! Aqui é onde as alunas geralmente falam 'é exatamente isso que eu precisava' 😄",
            "Que bom, [nome]! Quando o conteúdo se encaixa com o que você busca, o aprendizado é muito mais rápido e consistente. Agora vou te mostrar a fundo como cada módulo funciona 😊",
            "Perfeito, [nome]. Agora imagina ver isso sendo aplicado em um paciente pós-AVE na prática — é onde a diferença fica evidente. Ouve 😊",
        ],
        "pre_text": None,
        "audio": "pos_fisio_neuro/06_detalhes_parte1.opus",
        "post_text": None,
        "trigger": "response",
    },
    {
        "delay_seconds": 5,
        "pre_text": None,
        "audio": "pos_fisio_neuro/07_detalhes_parte2.opus",
        "mid_text": (
            "Você vai aprender a usar esse conteúdo para criar um posicionamento online, "
            "construir presença digital, atrair mais pacientes e cobrar preços mais altos. 💡"
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
            "Haha, já tô vendo seu nome aí também, [nome]! 😄 Esse diploma vai representar muito na sua carreira. Agora vou te falar sobre o investimento pra chegar até ele:",
            "Que bom, [nome]! Esse momento — quando o profissional se vê no diploma — é quando a decisão começa a ficar mais clara. Agora deixa eu te mostrar o valor real dessa formação:",
            "Ótimo, [nome]. Então vamos falar sobre o que precisa acontecer pra esse diploma sair do imaginário e ir pra sua parede:",
            "[nome], esse diploma é reconhecido pelo MEC e vai abrir portas que hoje estão fechadas pra você. Faz todo sentido se ver nele. Agora vou te explicar o que você está investindo pra conquistar isso:",
            "[nome], pensa comigo: daqui 12 meses, esse diploma vai representar não só um título — mas uma carreira completamente diferente. Vale a reflexão. Deixa eu te mostrar o que está por trás desse investimento:",
            "Boa, [nome]! Esse diploma já tem seu nome escrito. Agora é só você confirmar 😊 Vou te explicar o investimento:",
            "[nome], as alunas que mais cresceram com a pós disseram a mesma coisa que você quando viram o diploma. É um sinal positivo! 😄 Agora vamos falar sobre o investimento:",
            "Ótimo, [nome]. Esse diploma é emitido pela Anhanguera — uma das maiores instituições do país. Ter ele no currículo é diferencial real no mercado. Agora deixa eu te falar sobre o investimento:",
            "Fico feliz que consegue se ver nele, [nome]! E quanto mais cedo você começar, mais cedo esse diploma vai estar na sua mão — e na sua carreira. Vou te apresentar o investimento agora:",
            "[nome], já tô vendo seu nome nele também! 😍 Agora deixa eu te mostrar o que é preciso pra tornar isso real:",
        ],
        "pre_text": None,
        "audio": "pos_fisio_neuro/08_pitch_valor.opus",
        "post_text": "Quando você compara a qualidade com o investimento, consegue ver o valor?",
        "trigger": "response",
    },

    # ── BLOCO 8 — Oferta de Preço + Urgência ─────────────────────────────────
    {
        "delay_seconds": 0,
        "acolhimento_variations": [
            "Ótimo, [nome]! Quem entende o que está comprando toma a melhor decisão. Agora vou te apresentar o investimento com todos os detalhes:",
            "Perfeito, [nome]. Então sem enrolar — deixa eu te mostrar o investimento e as condições que tenho disponíveis só até hoje:",
            "Que bom, [nome]! Você acabou de enxergar o que separa quem investe no crescimento de quem fica esperando o momento certo. Agora vem a parte prática:",
            "Fico feliz que consegue ver isso, [nome]. Profissionais que enxergam valor antes de ver o preço são os que mais se comprometem com o processo. Agora deixa eu te apresentar o investimento:",
            "[nome], o que você acabou de confirmar é a parte mais importante de qualquer decisão de investimento: saber o que está recebendo antes de olhar o número. Agora vamos ao número:",
            "Ótimo, [nome]. Você pensou exatamente como as profissionais que mais se desenvolvem com a pós pensam. Agora vem o investimento:",
            "[nome], perfeito. E o valor que vou te apresentar agora é uma condição que temos disponível só por hoje — então presta atenção:",
            "Consegue sim, [nome]! 😊 Ótimo. Agora vem a melhor parte — as condições que eu tenho pra você hoje:",
            "[nome], boa! Você passou pelo filtro que a maioria das pessoas trava. Agora deixa eu te mostrar o investimento — acho que vai surpreender 😊",
            "Que bom, [nome]. Quando a pessoa enxerga o valor real de uma formação, ela toma decisões com muito mais clareza e segurança. Agora vou te apresentar o investimento:",
        ],
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
