"""Agrupamento de menções que falam do mesmo caso. CAMADA DERIVADA.

Por que existe: a série de menções sozinha não distingue "20 crimes noticiados
uma vez cada" de "1 crime noticiado 20 vezes" — e são afirmações opostas sobre
a imprensa. Medido no acervo, a razão menções/caso varia de 1x a 5x conforme o
tipo de crime (um latrocínio rendeu 5 matérias; a maioria dos casos, 1). Essa
razão é o achado sobre prioridade editorial.

Por que é derivada: se o limiar estiver mal calibrado, basta zerar event_id e
rodar de novo. A série primária (crime_mentions) nunca é tocada. Foi o ajuste
que tirou o componente mais arriscado do caminho crítico.

O agrupamento é DETERMINÍSTICO — sem chamada de LLM. Cada fusão grava
cluster_score, então a decisão fica auditável e o limiar pode ser revisto com
dados reais em vez de palpite.
"""
import re
import unicodedata
from datetime import timedelta

from db.connection import get_session
from db.models import Article, CrimeEvent, CrimeMention

# Janela do bloco de candidatos: mesmo tipo, mesmo município, datas próximas.
JANELA_DIAS = 3

# Acima de FUNDE, é o mesmo caso. Abaixo, caso novo. A faixa entre os dois é
# ambígua: por ora vira caso novo (erra para o lado de separar demais, que é o
# erro reversível), mas fica marcada pelo score para revisão no painel.
LIMIAR_FUNDE = 0.60
LIMIAR_AMBIGUO = 0.35

_STOP = {
    "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas", "o", "a",
    "os", "as", "um", "uma", "para", "por", "com", "que", "se", "foi", "ser", "sao",
    "apos", "ate", "sobre", "entre", "anos", "ano", "homem", "mulher", "pessoa",
    "policia", "policial", "policiais", "suspeito", "suspeita", "vitima", "caso",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9\s]", " ", s)


def _tokens(s: str) -> set[str]:
    return {t for t in _norm(s).split() if len(t) > 3 and t not in _STOP}


def _nomes(entities) -> set[str]:
    """Nomes próprios normalizados. É o sinal mais forte de que é o mesmo caso."""
    if not entities:
        return set()
    return {_norm(e).strip() for e in entities if isinstance(e, str) and len(e.strip()) > 3}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _data_ref(mention: CrimeMention):
    return mention.occurred_on or mention.reported_on


def similaridade(m: CrimeMention, outras: list[CrimeMention]) -> float:
    """Score de 0 a 1 entre uma menção e as já agrupadas num evento.

    Compara contra a melhor correspondência do grupo, não contra a média: uma
    matéria de desdobramento pode parecer pouco com a primeira cobertura e muito
    com a mais recente.
    """
    melhor = 0.0
    nomes_m = _nomes(m.entities)
    toks_m = _tokens(m.description)

    for o in outras:
        # Base: o bloco de candidatos já garante mesmo tipo penal, mesmo
        # município e datas próximas. Sem esta base, uma matéria que não nomeia
        # ninguém teria teto de 0,45 e JAMAIS alcançaria o limiar — ou seja,
        # criaria caso novo por construção, não por evidência.
        score = 0.10

        # Nome próprio compartilhado é quase decisivo: foi "Evilázio" que uniu
        # as 5 matérias do mesmo latrocínio no acervo.
        nomes_o = _nomes(o.entities)
        if nomes_m and nomes_o and (nomes_m & nomes_o):
            score += 0.45

        # Bairro igual reforça; bairros diferentes e ambos conhecidos derrubam.
        if m.bairro and o.bairro:
            score += 0.15 if _norm(m.bairro) == _norm(o.bairro) else -0.25

        # Número de envolvidos igual (e não trivial) é sinal razoável.
        if m.count_people and o.count_people and m.count_people == o.count_people:
            score += 0.08

        # Sobreposição de conteúdo da descrição.
        score += 0.42 * _jaccard(toks_m, _tokens(o.description))

        melhor = max(melhor, min(1.0, max(0.0, score)))

    return melhor


def _candidatos(session, m: CrimeMention) -> list[CrimeEvent]:
    """Bloco de candidatos por SQL — custo zero, reduz a comparação a poucos casos."""
    ref = _data_ref(m)
    q = session.query(CrimeEvent).filter(CrimeEvent.crime_type == m.crime_type)
    if m.municipio:
        q = q.filter(CrimeEvent.municipio == m.municipio)
    if ref:
        q = q.filter(
            CrimeEvent.occurred_on.isnot(None),
            CrimeEvent.occurred_on >= ref - timedelta(days=JANELA_DIAS),
            CrimeEvent.occurred_on <= ref + timedelta(days=JANELA_DIAS),
        )
    return q.limit(25).all()


def _atualiza_evento(session, evento: CrimeEvent, m: CrimeMention, score: float):
    m.event_id = evento.id
    mencoes = session.query(CrimeMention).filter(CrimeMention.event_id == evento.id).all()
    ids = [x.article_id for x in mencoes]
    fontes = set()
    if ids:
        for (sid,) in session.query(Article.source_id).filter(Article.id.in_(ids)).all():
            fontes.add(sid)
    evento.mention_count = len(mencoes)
    evento.source_count = len(fontes) or 1
    evento.last_seen_at = m.extracted_at
    # Guarda o menor score entre as fusões: é o elo mais fraco do agrupamento,
    # que é o que interessa saber ao auditar.
    if evento.cluster_score is None or score < evento.cluster_score:
        evento.cluster_score = score
    # Preenche lacunas geográficas do evento a partir da menção mais informativa
    if not evento.bairro and m.bairro:
        evento.bairro = m.bairro
    if not evento.zona and m.zona:
        evento.zona = m.zona


def _cria_evento(session, m: CrimeMention) -> CrimeEvent:
    evento = CrimeEvent(
        crime_type=m.crime_type,
        crime_group=m.crime_group,
        occurred_on=_data_ref(m),
        municipio=m.municipio,
        zona=m.zona,
        bairro=m.bairro,
        mention_count=1,
        source_count=1,
        first_seen_at=m.extracted_at,
        last_seen_at=m.extracted_at,
        cluster_score=None,
    )
    session.add(evento)
    session.flush()
    m.event_id = evento.id
    return evento


def run_crime_clustering(limit: int = 200) -> dict:
    """Agrupa menções ainda sem evento. Devolve contagens para log.

    Idempotente: só toca em menções com event_id nulo.
    """
    session = get_session()
    stats = {"processadas": 0, "fundidas": 0, "novos": 0, "ambiguas": 0}
    try:
        pendentes = (
            session.query(CrimeMention)
            .filter(CrimeMention.event_id.is_(None))
            .order_by(CrimeMention.reported_on.asc(), CrimeMention.id.asc())
            .limit(limit)
            .all()
        )
        for m in pendentes:
            stats["processadas"] += 1
            melhor_evento, melhor_score = None, 0.0

            for evento in _candidatos(session, m):
                outras = session.query(CrimeMention).filter(
                    CrimeMention.event_id == evento.id
                ).all()
                score = similaridade(m, outras)
                if score > melhor_score:
                    melhor_evento, melhor_score = evento, score

            if melhor_evento is not None and melhor_score >= LIMIAR_FUNDE:
                _atualiza_evento(session, melhor_evento, m, melhor_score)
                stats["fundidas"] += 1
            else:
                if LIMIAR_AMBIGUO <= melhor_score < LIMIAR_FUNDE:
                    stats["ambiguas"] += 1
                novo = _cria_evento(session, m)
                # Registra o score que quase fundiu — é o material da auditoria
                if melhor_score >= LIMIAR_AMBIGUO:
                    novo.cluster_score = melhor_score
                stats["novos"] += 1

            session.commit()

        if stats["processadas"]:
            print(f"  [crimes] Agrupamento: {stats['processadas']} menções → "
                  f"{stats['fundidas']} fundidas, {stats['novos']} casos novos "
                  f"({stats['ambiguas']} na faixa ambígua).")
        return stats
    finally:
        session.close()


def reset_clustering() -> int:
    """Desfaz todo o agrupamento para recalibrar o limiar.

    Só isto: zera event_id e apaga crime_events. As menções — a série primária —
    não são tocadas. É o que torna o limiar uma decisão reversível.
    """
    session = get_session()
    try:
        n = session.query(CrimeMention).update({CrimeMention.event_id: None})
        session.query(CrimeEvent).delete()
        session.commit()
        print(f"  [crimes] Agrupamento zerado: {n} menções liberadas.")
        return n
    finally:
        session.close()
