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
