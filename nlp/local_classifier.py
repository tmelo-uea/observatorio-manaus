import os
import re
import unicodedata
from db.connection import get_session
from db.models import Article

LOCAL_KEYWORDS = [
    # Cidade e estado
    "manaus", "amazonas", "manauara", "manauense",
    # Bairros de Manaus
    "aleixo", "adrianópolis", "chapada", "cidade nova", "compensa", "flores",
    "japiim", "petrópolis", "tarumã", "ponta negra", "são jorge", "coroado",
    "cachoeirinha", "santa etelvina", "monte das oliveiras", "redenção",
    "mauazinho", "puraquequara", "tancredo neves", "novo aleixo",
    "colônia antônio aleixo", "gilberto mestrinho",
    # Municípios do Amazonas
    "parintins", "itacoatiara", "manacapuru", "coari", "tefé", "tabatinga",
    "são gabriel da cachoeira", "humaitá", "maués", "borba",
    "nova olinda do norte", "careiro", "iranduba", "presidente figueiredo",
    "autazes", "benjamin constant", "fonte boa", "jutaí", "lábrea",
    "manicoré", "nhamundá", "silves", "urucará", "urucurituba", "nova aripuanã",
    # Rios e geografia
    "rio negro", "rio solimões", "encontro das águas", "arquipélago de anavilhanas",
    "ilha do careiro", "lago janauari", "lago de janeiro",
    "praia da ponta negra", "praia do tupé", "catalão",
    # Infraestrutura e pontos de referência
    "arena da amazônia", "ponte rio negro", "ponte jornalista phelippe daou",
    "aeroporto eduardo gomes", "porto de manaus", "mercado adolpho lisboa",
    "teatro amazonas", "palácio rio negro", "shopping manauara",
    "shopping sumaúma", "boulevard shopping",
    # Instituições e órgãos
    "prefeitura de manaus", "governo do amazonas", "câmara municipal de manaus",
    "assembleia legislativa do amazonas", "tribunal de justiça do amazonas",
    "ufam", "uea", "fcecon", "fhaj", "hps", "semsa", "semed", "semob",
    "semcom", "manaustrans", "manaus ambiental", "suframa", "zona franca de manaus",
    "fapeam", "sine manaus", "detran-am", "ssp-am", "pm do amazonas",
    "polícia civil do amazonas", "corpo de bombeiros do amazonas",
    # Times e esporte local
    "amazonas fc", "nacional fc", "fast clube", "são raimundo", "rio negro clube",
    # Pessoas públicas locais
    "david almeida", "wilson lima", "roberto cidade", "amazonino mendes",
    "arthur virgílio",
    # Veículos locais
    "tv a crítica", "rede amazônica", "em tempo", "d24am",
    "portal do holanda", "a crítica",
]


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def _keyword_match(text: str) -> bool | None:
    """Retorna True se local, False se claramente não-local, None se incerto."""
    normalized = _normalize(text)
    for kw in LOCAL_KEYWORDS:
        kw_norm = _normalize(kw)
        if " " in kw_norm:
            if kw_norm in normalized:
                return True
        else:
            if re.search(r"\b" + re.escape(kw_norm) + r"\b", normalized):
                return True
    return None


def _groq_classify(text: str) -> bool:
    """Usa Groq para classificar casos ambíguos."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return False
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        prompt = (
            "Você é um classificador de notícias. Responda apenas 'sim' ou 'não'.\n\n"
            "A notícia abaixo é sobre a cidade de Manaus ou o estado do Amazonas "
            "(inclui fatos que ocorrem lá, pessoas, instituições ou eventos locais)?\n\n"
            f"Notícia: {text[:500]}"
        )
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0,
        )
        answer = response.choices[0].message.content.strip().lower()
        return answer.startswith("sim")
    except Exception as e:
        print(f"  [Groq local_classifier] Erro: {e}")
        return False


def classify_local(text: str) -> bool:
    """Híbrido: palavras-chave primeiro, Groq para casos incertos."""
    result = _keyword_match(text)
    if result is not None:
        return result
    return _groq_classify(text)


def run_local_classification(batch_size: int = 200) -> int:
    session = get_session()
    classified = 0
    try:
        unclassified = (
            session.query(Article)
            .filter(Article.is_local.is_(None))
            .limit(batch_size)
            .all()
        )
        for article in unclassified:
            text = f"{article.title or ''} {article.summary or ''} {article.transcript or ''}"
            article.is_local = classify_local(text)
            classified += 1
        session.commit()
    finally:
        session.close()
    return classified
