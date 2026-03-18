import unicodedata
from typing import Optional


FAQ_INTENTS = [
    {
        "keywords": [
            "tem aula ao vivo", "aulas ao vivo", "é gravado", "é ao vivo", "como são as aulas",
            "formato das aulas", "aula presencial", "é online", "é ead",
        ],
        "response": "As aulas são gravadas e você pode assistir no seu ritmo 🎓 Além disso, temos *tutorias online e ao vivo* em cada módulo para tirar dúvidas direto com os professores.",
    },
    {
        "keywords": ["quando começa", "início do curso", "quando as aulas começam", "data de início", "turma começa quando"],
        "response": "Assim que você realiza o pagamento da matrícula, já fica oficialmente matriculado e começa a receber o material. As aulas ficam disponíveis na plataforma logo em seguida 😊",
    },
    {
        "keywords": ["quanto tempo dura", "duração do curso", "prazo para concluir", "quantos meses", "quanto tempo tenho para terminar"],
        "response": "A pós tem *360 horas* de carga horária. O tempo de conclusão é flexível — você estuda no seu ritmo, encaixando na sua rotina de trabalho.",
    },
    {
        "keywords": ["tem tcc", "precisa fazer tcc", "tem trabalho de conclusão", "tem monografia"],
        "response": "Não tem TCC 🙌 Você conclui a pós sem precisar fazer monografia ou trabalho de conclusão de curso.",
    },
    {
        "keywords": ["é reconhecido pelo mec", "tem certificado", "o diploma é válido", "o certificado é reconhecido", "vale para o coffito", "conselho reconhece"],
        "response": "Sim, a pós é certificada pelo MEC ✅ O diploma tem validade nacional e é reconhecido pelo conselho.",
    },
    {
        "keywords": ["tenho quanto tempo para assistir", "as aulas ficam disponíveis por quanto tempo", "acesso vitalício", "acesso expira", "prazo para assistir"],
        "response": "Você tem acesso às aulas durante todo o período do curso. Pode assistir e rever o conteúdo quantas vezes precisar 😊",
    },
    {
        "keywords": ["quais são os módulos", "o que tem no curso", "o que vou aprender", "conteúdo programático", "grade curricular", "ementa"],
        "response": "A pós tem 9 módulos completos:\n\n1️⃣ Neuroanatomia do sistema nervoso\n2️⃣ Fisiopatologia do adulto (AVE, TCE, Parkinson, Lesão Medular)\n3️⃣ Fisiopatologia da criança (Paralisia Cerebral, síndromes genéticas)\n4️⃣ Cinesioterapia no adulto neurológico (FNP, Terapia do Espelho, Treino de Marcha)\n5️⃣ Cinesioterapia em neuropediatria\n6️⃣ Terapia manual no paciente neurológico\n7️⃣ Fisioterapia respiratória no neurológico\n8️⃣ Abordagem em home care\n9️⃣ Órteses e tecnologias assistivas\n\nCobre adulto, pediátrico e home care — tudo em uma única especialização 💪",
    },
    {
        "keywords": ["quem são os professores", "os professores são bons", "professores com experiência", "professores clínicos", "quem vai dar aula"],
        "response": "Os professores são fisioterapeutas *atuantes na área de neurorreabilitação* — não apenas acadêmicos. Eles dominam a prática clínica e você pode contatar diretamente para tirar dúvidas em casos reais 🤙",
    },
    {
        "keywords": ["tem suporte", "posso tirar dúvida", "tem onde perguntar", "suporte ao aluno", "como funciona o suporte"],
        "response": "Sim! Você tem dois canais:\n\n✅ *Tutorias ao vivo* em cada módulo com os professores\n✅ *Contato direto* com os docentes para dúvidas de casos clínicos\n\nNão é aquele suporte genérico de plataforma — você fala com quem ensina.",
    },
    {
        "keywords": ["tem marketing digital", "ensina a captar paciente", "ensina a vender", "gestão de consultório", "como atrair pacientes"],
        "response": "Tem sim 🎯 Além de todo o conteúdo técnico, a pós inclui *tutorias de marketing digital* para você aprender a se posicionar online, atrair pacientes e cobrar mais pelo seu trabalho. Esse é um dos nossos grandes diferenciais.",
    },
    {
        "keywords": ["precisa ser formado", "pode fazer na faculdade", "graduando pode fazer", "sou recém formado", "acabei de me formar", "tenho pouca experiência"],
        "response": "Para fazer uma pós-graduação você precisa ter o diploma de graduação em Fisioterapia. Se você acabou de se formar, já está elegível! E este é justamente o momento ideal para se especializar antes de o mercado te pegar generalista 😊",
    },
    {
        "keywords": ["precisa ter experiência", "nunca atendi neurológico", "não tenho experiência em neuro", "posso fazer sem experiência em neuro"],
        "response": "Não precisa ter experiência prévia em neurológico! A pós começa desde a base — neuroanatomia e fisiopatologia — e vai avançando até técnicas e protocolos clínicos. Você aprende do zero ao avançado 💡",
    },
    {
        "keywords": ["só trabalho com pediátrico", "trabalho só com adulto", "atendo só home care", "tenho foco em uma área só"],
        "response": "A pós cobre *adulto, pediátrico e home care* em um único curso. Você pode aprofundar a área que já atua e ainda abrir novas frentes de atendimento. Fica bem mais completo do que cursar especialidades separadas.",
    },
    {
        "keywords": ["qual o preço", "quanto custa", "valor da pós", "mensalidade", "quanto é"],
        "response": "O valor integral é *R$ 9.500*, parcelado em até *14x de R$ 794* no boleto.\n\nMas temos condições especiais de bolsa — posso te explicar melhor?",
    },
    {
        "keywords": ["aceita cartão de crédito", "pode pagar no cartão", "parcelamento no cartão", "tem opção no cartão"],
        "response": "Sim, tem opção no cartão de crédito! Me conta em qual condição você tem interesse e eu te passo os detalhes de pagamento 😊",
    },
    {
        "keywords": ["aceita pix", "pode pagar no pix", "pagar à vista", "tem desconto à vista"],
        "response": "Sim, aceitamos PIX! Se quiser pagar à vista ou tem interesse em condição especial, me fala que eu verifico o que consigo te oferecer 🙂",
    },
    {
        "keywords": ["o que é a taxa de matrícula", "precisa pagar matrícula", "a matrícula é separada", "pago matrícula e mensalidade"],
        "response": "A taxa de matrícula é um valor único pago na hora da inscrição para garantir sua vaga. A primeira mensalidade só começa no mês seguinte. Ou seja, você se matricula hoje e já tem acesso ao material — sem pagar mensalidade imediatamente 👌",
    },
    {
        "keywords": [
            "posso cancelar", "cancelar", "cancelamento", "como funciona o cancelamento",
            "tem política de reembolso", "reembolso", "tem multa", "multa",
            "e se eu quiser desistir", "desistir", "tem garantia",
        ],
        "response": "Boa pergunta! Eu vou verificar certinho pra te responder com precisão e já te respondo 😊",
        "notify_human": True,
    },
    {
        "keywords": ["tem bolsa", "tem desconto", "condição especial", "tem promoção", "tem como baixar o preço"],
        "response": "Tem sim! Temos duas condições de bolsa:\n\n🎓 *Bolsa 1* — indicando pessoas (não precisam se matricular): *12x de R$ 559* + matrícula de R$ 350\n\n🎯 *Bolsa 2* — indicando 5 pessoas + decidir hoje: *20x de R$ 257* + matrícula de R$ 197\n\nQual faz mais sentido pra você?",
    },
    {
        "keywords": ["a bolsa expira", "até quando vale a bolsa", "prazo da bolsa", "posso pegar a bolsa amanhã"],
        "response": "A Bolsa 2 (melhor condição) é *válida apenas hoje* ⏳ Depois volta ao valor integral. Se quiser garantir, é agora. Me fala e eu te passo o link!",
    },
    {
        "keywords": ["como funciona a indicação", "preciso indicar quem", "a pessoa precisa se matricular", "como faço a indicação"],
        "response": "Você só precisa me passar o contato de 5 pessoas que podem ter interesse na pós — colegas fisioterapeutas, por exemplo. Eles *não precisam se matricular*, só indicar já garante a condição da Bolsa 1. Para a Bolsa 2, a indicação de 5 + sua decisão hoje 😊",
    },
    {
        "keywords": ["qual a plataforma", "onde assistem as aulas", "tem aplicativo", "acessa pelo celular", "como acesso o curso"],
        "response": "O acesso é pela nossa plataforma de ensino online. Funciona pelo navegador, tanto no celular quanto no computador. Assim que a matrícula é confirmada você já recebe os dados de acesso 📲",
    },
    {
        "keywords": ["quando recebo o acesso", "acesso imediato", "acesso em quanto tempo", "quando começo a estudar"],
        "response": "Após confirmação do pagamento da matrícula, você já recebe o acesso. É rápido — dá pra começar no mesmo dia 🚀",
    },
    {
        "keywords": ["vou ganhar mais", "aumenta o salário", "muda o faturamento", "vale a pena financeiramente", "retorno financeiro"],
        "response": "De acordo com o IBGE, profissionais com pós-graduação aumentam sua remuneração em *cerca de 225%*. Além disso, você passa a atender casos neurológicos complexos que hoje recusa — o que significa mais pacientes, fidelização e ticket maior por sessão 💰",
    },
    {
        "keywords": ["mercado de neuro tá bom", "tem demanda", "tem paciente para atender", "vale especializar em neuro"],
        "response": "O mercado de neurorreabilitação está em expansão acelerada: população envelhecendo, mais sobreviventes de UTI com sequelas, e crescimento explosivo do home care. São áreas com *alta demanda e poucos especialistas qualificados* — cenário ideal pra quem se especializa agora 📈",
    },
    {
        "keywords": ["posso trabalhar em hospital", "posso trabalhar em clínica", "posso atender em domicílio", "onde posso atuar depois"],
        "response": "Com a pós você se habilita para atuar em *clínicas de reabilitação, hospitais, consultório particular e home care*. A abordagem cobre os três perfis de atendimento, então você escolhe onde quer atuar — ou atua em todos 😄",
    },
]


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.split())


def match_faq_response(text: str) -> tuple[Optional[str], bool]:
    """
    Retorna (resposta, notify_human).
    - resposta=None quando não encontrou intenção mapeada.
    - notify_human=True para intenções sensíveis (ex.: cancelamento/reembolso).
    """
    normalized = _normalize(text)

    for intent in FAQ_INTENTS:
        for raw_kw in intent["keywords"]:
            if _normalize(raw_kw) in normalized:
                return intent["response"], bool(intent.get("notify_human", False))

    return None, False
