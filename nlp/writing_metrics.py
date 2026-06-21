"""Métricas de escrita agregadas por fonte (e, futuramente, por tema).

Mede o estilo da *chamada* (título + resumo) de cada fonte, pois é o texto
uniformemente disponível para todas as notícias — o corpo completo só existe
para parte dos artigos e enviesaria a comparação entre fontes.

Como os resumos individuais são curtos demais para métricas estáveis, medimos
sobre o **pool** de todas as notícias locais da fonte nos últimos 30 dias.
Roda 1x/dia no ciclo do worker e grava um snapshot diário em `writing_metrics`.

Métricas (todas robustas ao tamanho do texto):
  - lexical_density        densidade lexical: palavras de conteúdo / palavras totais
  - mtld                   diversidade lexical (Measure of Textual Lexical Diversity)
  - lexical_sophistication proporção de palavras de conteúdo raras (wordfreq pt)
  - nominalization_rate    substantivos nominalizados por 100 palavras (heurística de sufixos)
"""
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import text
from db.connection import get_engine

logger = logging.getLogger(__name__)

PERIOD_DAYS = 30
BATCH       = 256

# Pool mínimo de palavras para a métrica ser estável; abaixo disso a fonte é omitida.
MIN_TOKENS = 500

# Palavra é "rara/sofisticada" se sua frequência Zipf no português for menor que isto.
# Zipf 3.0 ≈ 1 ocorrência por milhão de palavras. Limiar relativo: o que importa é
# a comparação entre fontes, não o valor absoluto.
RARE_ZIPF = 3.0

# Para sofisticação, nomes próprios são "raros" mas não sofisticados — ficam de fora.
SOPHIST_POS = {"NOUN", "VERB", "ADJ", "ADV"}

# Sufixos nominalizadores do português (conjunto conservador, evita os mais ruidosos
# como -ura). Heurística: contam substantivos cujo lema termina nestes sufixos.
NOMINAL_SUFFIXES = (
    "ção", "ções", "são", "sões", "mento", "mentos", "dade", "dades",
    "agem", "agens", "ância", "âncias", "ência", "ências", "ismo", "ismos",
)


def _load_spacy():
    import spacy
    try:
        return spacy.load("pt_core_news_sm", disable=["parser", "ner", "senter"])
    except OSError:
        logger.info("Baixando modelo spaCy pt_core_news_sm...")
        from spacy.cli import download
        download("pt_core_news_sm")
        return spacy.load("pt_core_news_sm", disable=["parser", "ner", "senter"])


def _is_nominalization(lemma: str) -> bool:
    return lemma.endswith(NOMINAL_SUFFIXES) and len(lemma) > 5


def _compute_pool(texts: list[str], nlp) -> dict | None:
    """Calcula as 3 métricas de estilo sobre o pool de textos de um grupo.

    - lexical_sophistication: proporção de palavras de conteúdo raras (wordfreq)
    - nominalization_rate:    substantivos nominalizados por 100 palavras
    - word_length:            comprimento médio das palavras (letras/palavra)

    Retorna None se o pool não atingir MIN_TOKENS.
    """
    from wordfreq import zipf_frequency

    total_words   = 0   # palavras (tokens alfabéticos)
    total_chars   = 0   # letras somadas (para o comprimento médio)
    nominalizations = 0
    sophist_total = 0   # palavras de conteúdo elegíveis à sofisticação
    sophist_rare  = 0

    for doc in nlp.pipe(texts, batch_size=BATCH):
        for token in doc:
            if not token.is_alpha:
                continue
            total_words += 1
            total_chars += len(token.text)
            pos = token.pos_
            if pos == "NOUN" and _is_nominalization(token.lemma_.lower()):
                nominalizations += 1
            if pos in SOPHIST_POS:
                sophist_total += 1
                if zipf_frequency(token.text.lower(), "pt") < RARE_ZIPF:
                    sophist_rare += 1

    if total_words < MIN_TOKENS:
        return None

    return {
        "lexical_sophistication": (sophist_rare / sophist_total) if sophist_total else 0.0,
        "nominalization_rate":    nominalizations / total_words * 100,
        "word_length":            total_chars / total_words,
        "n_tokens":               total_words,
    }


# Coluna de agrupamento por lente. O texto medido (título+resumo) é o mesmo;
# muda apenas a chave que define o pool.
_GROUP_COLUMN = {"source": "source_id", "topic": "topic_id"}

# Métrica que só existe no conjunto atual; sua presença marca "já computado hoje".
# Permite recomputar quando o conjunto de métricas muda (ex.: troca de MTLD por word_length).
_CURRENT_MARKER = "word_length"


def _run_group(engine, today, start_utc, group_type: str, nlp) -> int:
    """Computa e grava as métricas de um tipo de agrupamento. Idempotente por dia.

    Retorna o nº de grupos gravados (0 se já calculado hoje ou sem dados).
    """
    with engine.connect() as conn:
        already = conn.execute(
            text("SELECT 1 FROM writing_metrics "
                 "WHERE computed_date = :d AND group_type = :g AND metric = :m LIMIT 1"),
            {"d": today, "g": group_type, "m": _CURRENT_MARKER},
        ).fetchone()
    if already:
        return 0

    col = _GROUP_COLUMN[group_type]
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT
                a.{col} AS gid,
                CONCAT(COALESCE(a.title, ''), ' ', COALESCE(a.summary, '')) AS texto
            FROM articles a
            WHERE a.published_at >= :start
              AND a.is_local = 1
              AND a.{col} IS NOT NULL
        """), {"start": start_utc}).fetchall()

    pools: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        texto = (row.texto or "").strip()
        if texto:
            pools[row.gid].append(texto)
    if not pools:
        return 0

    records = []
    for gid, texts in pools.items():
        metrics = _compute_pool(texts, nlp)
        if metrics is None:
            continue
        n_tokens = metrics.pop("n_tokens")
        for metric, value in metrics.items():
            records.append({
                "computed_date": today,
                "group_type":    group_type,
                "group_id":      gid,
                "metric":        metric,
                "value":         float(value),
                "n_articles":    len(texts),
                "n_tokens":      n_tokens,
            })

    if not records:
        return 0

    with engine.begin() as conn:
        # Remove qualquer linha antiga do dia (ex.: conjunto de métricas anterior) antes de gravar.
        conn.execute(text("DELETE FROM writing_metrics "
                          "WHERE computed_date = :d AND group_type = :g"),
                     {"d": today, "g": group_type})
        conn.execute(text("""
            INSERT INTO writing_metrics
                (computed_date, group_type, group_id, metric, value, n_articles, n_tokens)
            VALUES
                (:computed_date, :group_type, :group_id, :metric, :value, :n_articles, :n_tokens)
        """), records)
    return len({r["group_id"] for r in records})


def run_writing_metrics():
    """Computa métricas de escrita por fonte e por tema, gravando snapshot diário.

    Roda 1x/dia. Carrega o spaCy apenas se houver alguma lente pendente.
    """
    engine = get_engine()
    today = (datetime.utcnow() - timedelta(hours=4)).date()

    with engine.connect() as conn:
        done = {
            r.group_type for r in conn.execute(
                text("SELECT DISTINCT group_type FROM writing_metrics "
                     "WHERE computed_date = :d AND metric = :m"),
                {"d": today, "m": _CURRENT_MARKER},
            ).fetchall()
        }
    pending = [g for g in _GROUP_COLUMN if g not in done]
    if not pending:
        return

    logger.info(f"Computando métricas de escrita: {', '.join(pending)}...")
    start_utc = datetime.utcnow() - timedelta(days=PERIOD_DAYS)
    nlp = _load_spacy()

    for group_type in pending:
        n = _run_group(engine, today, start_utc, group_type, nlp)
        if n:
            logger.info(f"Métricas de escrita salvas: {n} {group_type}(s) para {today}.")


# ── Análise interpretativa por IA (lente de fontes) ──────────────────────────

INSIGHT_MODEL = "gpt-4o-mini"

# Rótulos legíveis das métricas para a tabela enviada ao modelo.
_METRIC_LABELS = {
    "lexical_sophistication": "Sofisticação (% de palavras raras)",
    "nominalization_rate":    "Nominalização (substantivos derivados de verbos por 100 palavras)",
    "word_length":            "Comprimento médio das palavras (letras)",
}

# Configuração por lente: tabela de nomes, substantivo e rótulo do bloco no prompt.
_INSIGHT_CFG = {
    "source": {"table": "sources", "sing": "veículo", "plur": "veículos", "header": "POR FONTE"},
    "topic":  {"table": "topics",  "sing": "tema",    "plur": "temas",    "header": "POR TEMA"},
}


def _insight_system(group_type: str) -> str:
    cfg = _INSIGHT_CFG[group_type]
    sing, plur = cfg["sing"], cfg["plur"]
    return (
        "Você é um analista de dados de mídia. Recebe métricas linguísticas agregadas "
        "da imprensa de Manaus/Amazonas e escreve uma análise curta e DESCRITIVA em português.\n\n"
        "REGRAS OBRIGATÓRIAS:\n"
        f"1. É descrição de ESTILO, nunca de QUALIDADE. Jamais classifique um {sing} como "
        "escrevendo melhor, pior, de forma mais confiável ou mais profissional. Não há juízo de valor.\n"
        "2. Use APENAS os números fornecidos. Não invente dados, causas, contexto histórico "
        "ou informações ausentes.\n"
        f"3. SINTETIZE o quadro geral em vez de listar os {plur} um a um: identifique os {plur} "
        f"de escrita mais formal/elaborada e os mais enxutos, e o contraste entre eles. Cite no "
        f"máximo 2 ou 3 {plur} como exemplos ilustrativos — NÃO faça uma chamada de todos nem "
        "recite o ranking completo de números.\n"
        "4. Foque nos padrões GRANDES E ESTÁVEIS (contrastes nítidos, extremos claros). NÃO "
        "comente diferenças minúsculas nem o ordenamento fino do meio da tabela (são instáveis "
        "e mudam a cada semana).\n"
        "5. Inclua, em uma frase, a ressalva de que isto reflete os últimos 30 dias e mede apenas "
        "o título e o resumo (a chamada) das notícias, não o corpo da matéria.\n"
        "6. Seja conciso: 2 a 4 frases, um único parágrafo corrido. Sem listas, sem títulos."
    )


def _build_metric_table(engine, today, group_type: str = "source"):
    """Monta a tabela texto (grupo × métrica) e as médias do corpus para o prompt."""
    cfg = _INSIGHT_CFG[group_type]
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT g.name AS nome, wm.metric, wm.value, wm.n_articles
            FROM writing_metrics wm
            JOIN {cfg['table']} g ON wm.group_id = g.id
            WHERE wm.group_type = :g AND wm.computed_date = :d
        """), {"g": group_type, "d": today}).fetchall()
    if not rows:
        return None, None

    by_source: dict = defaultdict(dict)
    arts: dict = {}
    sums: dict = defaultdict(float)
    counts: dict = defaultdict(int)
    for r in rows:
        by_source[r.nome][r.metric] = r.value
        arts[r.nome] = r.n_articles
        sums[r.metric] += r.value
        counts[r.metric] += 1

    metrics = list(_METRIC_LABELS)
    avgs = {m: (sums[m] / counts[m] if counts[m] else 0.0) for m in metrics}

    def _fmt(metric, v):
        if metric == "lexical_sophistication":
            return f"{v * 100:.1f}%"
        if metric == "word_length":
            return f"{v:.2f}"
        return f"{v:.1f}"

    lines = ["MÉDIA DA IMPRENSA LOCAL: " + " | ".join(
        f"{_METRIC_LABELS[m]}: {_fmt(m, avgs[m])}" for m in metrics)]
    lines.append("")
    lines.append(f"{cfg['header']} (nº de notícias no período entre parênteses):")
    # ordena por volume para dar contexto de confiabilidade
    for nome in sorted(by_source, key=lambda n: -arts.get(n, 0)):
        vals = " | ".join(f"{_METRIC_LABELS[m]}: {_fmt(m, by_source[nome].get(m, 0))}"
                          for m in metrics)
        lines.append(f"- {nome} ({arts.get(nome, 0)} notícias): {vals}")
    return "\n".join(lines), avgs


def run_writing_insight(group_type: str = "source"):
    """Gera (via IA) a análise interpretativa das métricas e grava. Roda 1x/dia."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY ausente — análise de escrita não gerada.")
        return

    engine = get_engine()
    today = (datetime.utcnow() - timedelta(hours=4)).date()
    with engine.connect() as conn:
        already = conn.execute(
            text("SELECT 1 FROM writing_insights "
                 "WHERE computed_date = :d AND group_type = :g LIMIT 1"),
            {"d": today, "g": group_type},
        ).fetchone()
    if already:
        return

    table, _ = _build_metric_table(engine, today, group_type)
    if not table:
        return

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=INSIGHT_MODEL,
            messages=[
                {"role": "system", "content": _insight_system(group_type)},
                {"role": "user", "content":
                    f"Analise o estilo de escrita por {_INSIGHT_CFG[group_type]['sing']} "
                    f"a partir destas métricas:\n\n" + table},
            ],
            max_tokens=400,
            temperature=0.3,
        )
        analysis = response.choices[0].message.content.strip()
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO writing_insights (computed_date, group_type, text, model, created_at)
                VALUES (:d, :g, :t, :m, :ts)
            """), {"d": today, "g": group_type, "t": analysis, "m": INSIGHT_MODEL,
                   "ts": datetime.utcnow()})
    except Exception as e:
        logger.warning(f"Falha ao gerar/gravar análise de escrita: {e}")
        return
    logger.info(f"Análise de escrita ({group_type}) gerada para {today}.")
