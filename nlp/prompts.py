"""Gerência central de prompts.

Os prompts vivem na tabela `prompts` (editáveis em runtime, com histórico em
`prompt_versions`). Os valores em DEFAULT_PROMPTS servem como:
  1. semente inicial do banco (`seed_prompts`)
  2. fallback de segurança caso o banco falhe ou o prompt não exista

Precedência em runtime: valor do banco > DEFAULT_PROMPTS.
"""
from datetime import datetime

DEFAULT_PROMPTS: dict[str, str] = {
    "summary.intro": (
        "Você é um jornalista que escreve resumos diários de notícias {about}. "
        "Com base nas manchetes e trechos de vídeos abaixo, escreva um parágrafo conciso (4 a 6 frases) "
        "resumindo os principais acontecimentos. "
        "{topic_filter}{temporal}{regras_comuns}\n\n"
        "Fontes:\n{headlines}"
    ),
    "summary.topic_filter": (
        "FOCO EXCLUSIVO NO TEMA '{topic_name}': inclua APENAS conteúdo diretamente "
        "relacionado a {topic_name}. Conteúdo sobre outros temas pode ter sido classificado "
        "erroneamente — IGNORE esses itens mesmo que estejam na lista. "
        "Se não houver conteúdo suficiente sobre {topic_name}, "
        "escreva apenas sobre o que realmente pertence ao tema. "
    ),
    "summary.temporal.dashboard": (
        "Este resumo é exibido em tempo real e reúne as notícias coletadas hoje ({date_str}). "
        "Descreva cada acontecimento com o tempo verbal que corresponde ao momento REAL do evento: "
        "— Use PASSADO apenas se a notícia descreve o evento como já ocorrido ANTES de hoje "
        "(palavras como 'ocorreu ontem', 'foi realizado', 'aconteceu na semana passada'). "
        "— Use PRESENTE ou FUTURO se a notícia indica que o evento é de hoje ou de data posterior "
        "('hoje', 'neste sábado', 'neste fim de semana', 'amanhã', 'nesta semana'): "
        "nesses casos NUNCA use passado, mesmo que o anúncio do evento use 'ganhou' ou 'terá'. "
        "— Uma notícia de hoje pode relatar evento de ontem: use passado e 'ontem' quando isso estiver claro. "
        "Não use frases de abertura genéricas como 'Hoje foi um dia movimentado' — "
        "comece direto com o fato mais relevante. "
    ),
    "summary.temporal.email": (
        "Este é um boletim enviado na manhã seguinte, recapitulando as notícias publicadas ontem ({date_str}). "
        "Descreva cada acontecimento com o tempo verbal que corresponde ao momento REAL do evento, "
        "e não à data de publicação da notícia: passado para o que já ocorreu, "
        "presente para serviços ou situações contínuas, e FUTURO para o que foi apenas anunciado "
        "e ainda vai acontecer depois daquela data — por exemplo, um feriado, evento ou serviço "
        "programado para os dias seguintes (use 'vai manter', 'ocorrerá', 'está previsto'). "
        "Não force tudo para o passado nem use 'ontem' em fatos que se referem ao futuro. "
        "Não use frases de abertura genéricas como 'Ontem foi um dia movimentado' — "
        "comece direto com o fato mais relevante. "
        "IMPORTANTE: NÃO inicie o parágrafo com a palavra 'Ontem'. Comece pelo sujeito da notícia "
        "(o órgão, a pessoa, o evento) — por exemplo 'A Prefeitura de Manaus inaugurou...' ou "
        "'Uma operação da Polícia Civil resultou em...'. O contexto temporal (ontem) deve aparecer "
        "naturalmente ao longo do texto quando necessário, não como primeira palavra. "
    ),
    "summary.common_rules": (
        "Inclua apenas fatos que dizem respeito à cidade de Manaus — ignore notícias "
        "de outros municípios do Amazonas ou de outros estados. "
        "IGNORE notícias de repercussão nacional sem ligação direta com Manaus, mesmo que publicadas "
        "por veículos locais — por exemplo, casos criminais, judiciais ou políticos de outros estados "
        "(como o Caso Henry Borel, do Rio de Janeiro). Um portal amazonense republicar uma notícia "
        "nacional NÃO a torna local. "
        "NÃO cite as fontes/veículos dentro do texto: nunca escreva 'segundo o portal X', "
        "'conforme noticiado por', 'de acordo com a fonte Y' ou similares. O resumo deve ser um texto "
        "jornalístico fluido, narrando os fatos diretamente, sem atribuir cada frase a um veículo. "
        "Preserve os nomes completos de pessoas, órgãos e locais mencionados. "
        "Ao mencionar pessoas, use apenas o nome e o cargo exatamente como aparecem nas fontes. "
        "NUNCA atribua a uma pessoa um cargo, ação ou acusação que as fontes associam a OUTRA pessoa — "
        "não funda duas pessoas nem duas histórias diferentes em uma só. Se uma fonte menciona alguém "
        "apenas pelo nome ou apelido, sem informar o cargo, NÃO complete o cargo a partir de outra "
        "notícia: escreva somente o nome. "
        "Se uma fonte menciona apenas uma instituição (como 'Prefeitura de Manaus', 'Governo do Estado') "
        "sem citar nenhum representante pelo nome, NÃO adicione nomes de pessoas nesse contexto — "
        "escreva apenas o nome da instituição, mesmo que você associe uma pessoa a ela. "
        "Ao mencionar instituições, campanhas ou programas (hospitais, escolas, órgãos, campanhas), "
        "sempre identifique o nome completo — nunca escreva apenas 'uma campanha' ou 'o programa' sem nomear. "
        "Inclua apenas fatos com contexto suficiente para o leitor entender — "
        "ignore manchetes que pareçam fragmentos sem contexto claro. "
        "DEDUPLICAÇÃO: várias manchetes podem cobrir o MESMO acontecimento (de fontes diferentes). "
        "Trate cada acontecimento UMA ÚNICA VEZ — nunca escreva duas frases sobre o mesmo evento, "
        "mesmo que apareça repetido em várias fontes. Reúna as informações e mencione o fato apenas uma vez. "
        "NÃO invente precisão temporal: só diga 'pela manhã', 'à tarde', 'à noite' ou um horário "
        "se isso estiver EXPLÍCITO nas fontes. Se as fontes não indicam a hora do evento, não a mencione. "
        "Da mesma forma, não afirme que algo aconteceu hoje se as fontes não confirmam a data — "
        "uma notícia publicada hoje pode relatar um evento de um dia anterior. Na dúvida, não atribua data nem hora. "
        "PROIBIDO usar frases de encerramento genéricas como 'Esses foram alguns dos principais acontecimentos', "
        "'Esses são os destaques' ou similares — termine no último fato relevante. "
        "Escreva em português, de forma clara e objetiva, sem usar bullet points."
    ),
    "crime.extract": (
        "Você é um extrator de dados para um observatório de mídia. Leia a matéria "
        "jornalística abaixo e identifique QUAIS CRIMES ela noticia.\n\n"

        "PRINCÍPIO QUE GOVERNA TODAS AS DEMAIS REGRAS: esta base prioriza PRECISÃO "
        "sobre cobertura. Deixar um crime de fora custa pouco; registrar um crime "
        "errado corrompe a série e é pior do que não registrar nada. Portanto, "
        "sempre que houver dúvida:\n"
        "- na dúvida se é crime → is_crime = false;\n"
        "- na dúvida sobre qual figura penal → use a mais geral compatível, ou "
        "'outro';\n"
        "- na dúvida sobre data, local, número de envolvidos ou tentativa → deixe "
        "null.\n"
        "Não preencha campo por plausibilidade. Abster-se é resposta correta.\n\n"

        "O QUE NÃO CONTA COMO CRIME NOTICIADO (responda is_crime = false):\n"
        "- Ocorrência sem crime: incêndio acidental, acidente de trânsito sem indício "
        "de crime, afogamento, desabamento, resgate, simulado ou treinamento de "
        "bombeiros, pessoa desaparecida que foi encontrada.\n"
        "- Matéria institucional: nota de gabinete, release de órgão, seminário, posse, "
        "entrevista, balanço estatístico, campanha educativa.\n"
        "- Política pública ou tramitação legislativa: projeto de lei, votação, mudança "
        "de regra sobre algum crime. Falar SOBRE um tipo de crime não é noticiar uma "
        "ocorrência dele.\n"
        "- BALANÇO OU RELATÓRIO ESTATÍSTICO: matéria que apresenta totais de um "
        "período ('registrou queda de 32%', '1.628 vítimas em 2025', 'relatório aponta "
        "X casos'). Os números ali são agregados, NÃO pessoas de uma ocorrência. Uma "
        "matéria dessas não gera nenhum registro, por mais crimes que cite.\n"
        "- Referência histórica: matéria sobre um crime antigo que não noticia fato "
        "novo — venda do imóvel onde ocorreu um crime, aniversário de um caso, "
        "retrospectiva.\n"
        "- Cumprimento de mandado sem crime informado: 'preso por mandado em aberto' "
        "sem dizer de que crime. Não invente a figura que originou o mandado.\n"
        "- CRIME OCORRIDO FORA DO AMAZONAS. Esta base cobre crimes acontecidos no "
        "estado do Amazonas. Se o fato ocorreu em outro estado ou em outro país, "
        "responda is_crime = false — mesmo que a vítima seja amazonense, mesmo que a "
        "família more em Manaus, mesmo que o veículo que publicou seja daqui. O que "
        "importa é ONDE O CRIME ACONTECEU.\n\n"

        "DUAS ARMADILHAS:\n"
        "1. Nome de repartição não é fato. 'Delegacia Especializada em Roubos, Furtos e "
        "Defraudações' é o nome do órgão — não conclua que houve roubo ou furto por "
        "causa disso. Considere apenas o fato narrado.\n"
        "2. Matéria sobre desdobramento (prisão, denúncia, julgamento, condenação) de um "
        "crime ANTIGO é cobertura de hoje sobre fato antigo. Preencha occurred_on com a "
        "data do FATO, não a da publicação, e ajuste stage.\n\n"

        "REGRA DE CONTAGEM: um item por FIGURA PENAL, nunca por pessoa. Uma operação com "
        "12 presos por tráfico é UM item, com count_people = 12. Só gere mais de um item "
        "se a matéria noticiar crimes de TIPOS DIFERENTES.\n\n"

        "PREFIRA SEMPRE A FIGURA AUTÔNOMA E MAIS ESPECÍFICA, nunca a genérica:\n"
        "- morte de mulher por razões da condição do sexo feminino → feminicidio "
        "(não homicidio_doloso);\n"
        "- roubo seguido de morte → latrocinio (não roubo, não homicidio_doloso);\n"
        "- vítima menor de 14 anos ou incapaz de consentir → estupro_vulneravel "
        "(não estupro);\n"
        "- agressão praticada por cônjuge, ex-companheiro, familiar ou pessoa que "
        "coabita → lesao_corporal_domestica. Se a matéria NÃO indica vínculo "
        "doméstico ou familiar, é 'lesao_corporal' simples — professor que agride "
        "aluno, vizinho, colega de trabalho e desconhecido não configuram o §9º;\n"
        "- ameaça reiterada que perturba a liberdade da vítima → perseguicao "
        "(não ameaca).\n"
        "Use 'secondary_types' para registrar as outras figuras que o MESMO fato "
        "também configure — por exemplo, um latrocínio também é roubo.\n\n"

        "FEMINICÍDIO: morte de mulher praticada por companheiro, ex-companheiro ou "
        "familiar, ou em contexto de violência doméstica, ou por menosprezo à condição "
        "de mulher, é 'feminicidio' — nunca 'homicidio_doloso'. Na dúvida entre os "
        "dois, quando a vítima é mulher e há indício de contexto doméstico ou de "
        "gênero, use 'feminicidio' e registre 'homicidio_doloso' em secondary_types.\n\n"

        "CRIME-FIM ANTES DE CRIME-MEIO. Quando a violência serve a outro crime, o "
        "principal é o crime que a violência serviu, e a violência vai em "
        "secondary_types: assalto com agressão é 'roubo' com 'lesao_corporal' "
        "secundária, não o contrário. Vale para qualquer meio — invasão, ameaça, "
        "restrição de liberdade — quando instrumental a um fim.\n\n"

        "IDADE DA VÍTIMA MANDA NO CRIME SEXUAL. Vítima menor de 14 anos, ou incapaz "
        "de consentir, é SEMPRE 'estupro_vulneravel' (art. 217-A), nunca 'estupro'. "
        "Se a matéria informa idades como 4, 6 ou 7 anos, a figura é vulnerável — "
        "não há exceção.\n\n"

        "NÃO AFIRME TIPIFICAÇÃO QUE A MATÉRIA NÃO SUSTENTA. Se ela noticia um fato "
        "SOB APURAÇÃO sem indicar o enquadramento, não escolha a figura por "
        "suposição:\n"
        "- morte sem causa estabelecida, ainda em investigação → 'morte_a_esclarecer', "
        "nunca 'homicidio_culposo' ou 'homicidio_doloso';\n"
        "- mandado ou prisão descritos genericamente ('por violência doméstica', 'por "
        "crimes sexuais') sem dizer a conduta → use a figura mais geral compatível, ou "
        "'outro'; não escolha uma figura específica como violência psicológica só "
        "porque é plausível.\n\n"

        "AÇÃO CÍVEL OU TRABALHISTA NÃO É CRIME. Condenação a indenizar, processo em "
        "Juizado Especial Cível, reclamação trabalhista, assédio moral no trabalho, "
        "decisão de TRT — nada disso é matéria criminal, mesmo quando a conduta é "
        "grave e mesmo quando há condenação. Responda is_crime = false.\n\n"

        "NA AUSÊNCIA DE FIGURA ADEQUADA, USE 'outro'. Nunca escolha uma figura por "
        "semelhança superficial de palavras: moto sem placa e sem chassi NÃO é crime "
        "contra a fauna. 'outro' é resposta correta e útil — figura errada corrompe a "
        "série e é pior do que não classificar.\n\n"

        "O CRIME É O FATO NOVO QUE A MATÉRIA NOTICIA. Se ela menciona outro crime "
        "apenas como antecedente ou pano de fundo, 'type' recebe o fato NOVO e o "
        "antecedente vai em 'secondary_types'. Exemplo: em 'Acusado de feminicídio é "
        "espancado e morto por populares', o fato noticiado é o linchamento — um "
        "homicídio doloso; o feminicídio é o antecedente.\n\n"

        "DATA DO FATO — esta matéria foi publicada em {data_publicacao}. Resolva as "
        "datas relativas ('ontem', 'na noite de terça (2)', 'neste sábado') tomando "
        "essa data de publicação como referência.\n"
        "Informe SEMPRE 'occurred_precision', que diz até onde a matéria permite "
        "datar o fato:\n"
        "  'dia'          = dá para determinar dia, mês e ano;\n"
        "  'mes'          = só mês e ano ('em junho de 2023');\n"
        "  'ano'          = só o ano ('um crime de 2023');\n"
        "  'desconhecida' = a matéria não permite datar.\n"
        "Preencha occurred_on com a melhor data possível, mas seja honesto na "
        "precisão — o sistema descarta a data quando a precisão não for 'dia'.\n\n"

        "VOCABULÁRIO — use exatamente um destes identificadores em 'type':\n"
        "{vocabulario}\n\n"

        "Responda SOMENTE com JSON neste formato:\n"
        "{{\n"
        '  "is_crime": true,\n'
        '  "crimes": [\n'
        "    {{\n"
        '      "type": "identificador do vocabulário",\n'
        '      "secondary_types": ["outras figuras que o MESMO fato configure"],\n'
        '      "stage": "fato|investigacao|prisao|julgamento|condenacao",\n'
        '      "tentativa": false,\n'
        '      "occurred_on": "AAAA-MM-DD ou null se a matéria não informar",\n'
        '      "occurred_precision": "dia|mes|ano|desconhecida",\n'
        '      "municipio": "Manaus, Parintins, ... ou null",\n'
        '      "bairro": "bairro citado ou null",\n'
        '      "location_text": "trecho curto indicando o local ou null",\n'
        '      "count_people": "número de pessoas envolvidas (presas, vítimas) ou null",\n'
        '      "description": "1 a 2 frases sobre o fato, SEM nomes próprios",\n'
        '      "entities": ["nomes próprios de pessoas citadas na matéria"],\n'
        '      "legal_cited_by_source": true,\n'
        '      "legal_text_source": "trecho em que a matéria cita o enquadramento, ou null",\n'
        '      "confidence": 0.9\n'
        "    }}\n"
        "  ]\n"
        "}}\n\n"

        "Se is_crime for false, 'crimes' deve ser lista vazia.\n"
        "'tentativa' é true quando o crime NÃO se consumou por circunstâncias alheias "
        "à vontade do agente (CP art. 14, II): 'tentou matar', 'tentativa de "
        "feminicídio', 'a vítima sobreviveu'. Use a MESMA figura penal do crime "
        "consumado e marque tentativa = true — não existe figura separada para "
        "tentativa.\n"
        "NUNCA escreva nomes próprios de pessoas em 'description' — eles vão apenas em "
        "'entities'.\n"
        "NÃO invente data nem local: o que a matéria não informa vai como null.\n"
        "legal_cited_by_source é true SOMENTE se a matéria nomear a figura penal ou "
        "citar o dispositivo — 'responderá por latrocínio', 'crime de estelionato', "
        "'art. 157'. O vocabulário corriqueiro do noticiário policial NÃO conta: "
        "'preso', 'acusado', 'investigado', 'condenação', 'suspeito' são termos "
        "genéricos, não enquadramento jurídico.\n\n"

        "MATÉRIA:\n{texto}"
    ),
    "is_local": (
        "Você é um classificador de notícias. Responda apenas 'sim' ou 'não'.\n\n"
        "A notícia abaixo é sobre a cidade de Manaus ou o estado do Amazonas "
        "(inclui fatos que ocorrem lá, pessoas, instituições ou eventos locais)?\n\n"
        "Notícia: {text}"
    ),
}


def get_template(name: str) -> str:
    """Retorna o template ativo do banco; cai no DEFAULT se ausente ou em erro."""
    try:
        from db.connection import get_session
        from db.models import Prompt
        session = get_session()
        try:
            row = session.query(Prompt).filter_by(name=name).first()
            if row and row.template:
                return row.template
        finally:
            session.close()
    except Exception as e:
        print(f"  [prompts] Falha ao buscar '{name}', usando default: {e}")
    return DEFAULT_PROMPTS.get(name, "")


def render(name: str, **kwargs) -> str:
    """Busca o template e aplica .format(**kwargs); cai no default em erro."""
    template = get_template(name)
    try:
        return template.format(**kwargs)
    except Exception as e:
        print(f"  [prompts] Falha ao formatar '{name}', usando default: {e}")
        return DEFAULT_PROMPTS.get(name, "").format(**kwargs)


def set_prompt(name: str, template: str, description: str | None = None) -> int:
    """Atualiza (ou cria) o prompt e registra a nova versão no histórico.

    Retorna o número da versão gravada.
    """
    from db.connection import get_session
    from db.models import Prompt, PromptVersion
    session = get_session()
    try:
        now = datetime.utcnow()
        row = session.query(Prompt).filter_by(name=name).first()
        if row:
            row.version += 1
            row.template = template
            row.updated_at = now
            if description is not None:
                row.description = description
            version = row.version
        else:
            row = Prompt(name=name, template=template, description=description,
                         version=1, updated_at=now)
            session.add(row)
            version = 1
        session.add(PromptVersion(name=name, template=template, version=version, created_at=now))
        session.commit()
        return version
    finally:
        session.close()


def seed_prompts() -> int:
    """Insere ou atualiza no banco os prompts default. Retorna quantos foram alterados."""
    from db.connection import get_session
    from db.models import Prompt
    session = get_session()
    changes = 0
    try:
        existing = {p.name: p.template for p in session.query(Prompt).all()}
    finally:
        session.close()
    for name, template in DEFAULT_PROMPTS.items():
        if name not in existing:
            set_prompt(name, template, description="Seed inicial (default do código)")
            changes += 1
        elif existing[name] != template:
            set_prompt(name, template, description="Atualizado pelo seed do código")
            changes += 1
    if changes:
        print(f"  [prompts] Seed: {changes} prompts inseridos/atualizados no banco.")
    return changes
