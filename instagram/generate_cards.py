"""Gerador determinístico de cards para Instagram a partir dos resumos diários.

Lê o resumo geral e os resumos por tema do dia (tabela ``daily_summaries``),
escolhe os temas com mais artigos (excluindo os que exigem revisão editorial
reforçada) e renderiza um carrossel de imagens 1080x1350 seguindo a
identidade visual definida em
``instagram/prototypes/manaus-em-resumo-2026-06-05.md``.

Uso:
    python instagram/generate_cards.py --date 2026-06-05
    python instagram/generate_cards.py --sample   # pré-visualização sem banco
"""
import argparse
import math
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
from PIL import Image, ImageDraw, ImageFont

from db.connection import get_session
from db.models import DailySummary, Topic

# ---------------------------------------------------------------------------
# Identidade visual (ver prototypes/manaus-em-resumo-2026-06-05.md)
# ---------------------------------------------------------------------------
NAVY = (10, 34, 56)
FOREST = (30, 57, 40)
CREAM = (243, 234, 222)
GOLD = (196, 162, 77)
TERRACOTTA = (178, 117, 79)

# Estilos de fundo dos cards de tema, um por posição no carrossel — usa as
# três cores da identidade (creme, verde-floresta, terracota) em vez de só
# alternar duas, e cada um já vem com a cor de traço da onda decorativa.
TOPIC_STYLES = [
    {"bg": CREAM, "fg": NAVY, "wave": (225, 209, 181)},
    {"bg": FOREST, "fg": CREAM, "wave": (23, 43, 31)},
    {"bg": TERRACOTTA, "fg": CREAM, "wave": (140, 88, 56)},
]

W, H = 1080, 1350
MARGIN = 90
# Região vertical onde o bloco de texto principal é centralizado — acima da
# faixa reservada para a onda decorativa e o rodapé (evita texto "flutuando"
# no topo quando o conteúdo é curto).
CONTENT_TOP, CONTENT_BOTTOM = 160, H - 260

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGOMARK_TRANSPARENT = os.path.join(ASSETS_DIR, "logomark-transparent.png")

# Temas que exigem revisão humana reforçada antes de publicação — nunca
# selecionados automaticamente para o carrossel (ver "Decisões editoriais
# do piloto" no protótipo).
EXCLUDED_TOPIC_SLUGS = {"seguranca-publica"}

MAX_CONTENT_CARDS = 3
BODY_CHAR_BUDGET = 230

_MESES_ABREV = ["jan", "fev", "mar", "abr", "mai", "jun",
                "jul", "ago", "set", "out", "nov", "dez"]
_MESES_NOMES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _data_abrev(d: date) -> str:
    return f"{d.day:02d} {_MESES_ABREV[d.month - 1]} {d.year}".upper()


def _data_extenso(d: date) -> str:
    return f"{d.day} de {_MESES_NOMES[d.month - 1]} de {d.year}"


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    base = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
    return ImageFont.truetype(os.path.join(base, name), size)


def font_bold(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSans-Bold.ttf", size)


def font_regular(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSans.ttf", size)


# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------

def _manaus_today() -> date:
    return (datetime.utcnow() - timedelta(hours=4)).date()


def fetch_card_data(ref_date: date) -> dict:
    """Busca o resumo geral e os melhores resumos por tema para ref_date."""
    session = get_session()
    try:
        general = session.query(DailySummary).filter_by(date=ref_date, topic_id=None).first()
        topic_rows = (
            session.query(DailySummary)
            .join(Topic)
            .filter(DailySummary.date == ref_date, DailySummary.topic_id.isnot(None))
            .filter(~Topic.slug.in_(EXCLUDED_TOPIC_SLUGS))
            .order_by(DailySummary.article_count.desc())
            .limit(MAX_CONTENT_CARDS)
            .all()
        )
        topics = [
            {"name": row.topic.name, "summary": row.summary, "article_count": row.article_count}
            for row in topic_rows
        ]
        return {
            "date": ref_date,
            "general_summary": general.summary if general else None,
            "topics": topics,
        }
    finally:
        session.close()


def _select_topics(topics: list[dict]) -> list[dict]:
    """Aplica a mesma regra de exclusão/ranking de fetch_card_data, mas em
    memória — usado pelo caminho --from-json, quando os dados já vieram de
    fora (ex.: uma consulta rodada via `railway ssh` no worker, para os casos
    em que o banco de produção não está acessível diretamente daqui)."""
    eligible = [t for t in topics if t.get("slug") not in EXCLUDED_TOPIC_SLUGS]
    eligible.sort(key=lambda t: t["article_count"], reverse=True)
    return eligible[:MAX_CONTENT_CARDS]


def load_card_data_from_json(path: str) -> dict:
    import json
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        "date": date.fromisoformat(raw["date"]),
        "general_summary": raw.get("general_summary"),
        "topics": _select_topics(raw["topics"]),
    }


# Dados de amostra para pré-visualizar o template sem acesso ao banco de
# produção (baseados no piloto editorial de 2026-06-05).
SAMPLE_DATA = {
    "date": date(2026, 6, 5),
    "general_summary": (
        "O Teatro Amazonas celebrou o bicentenário das relações diplomáticas entre Brasil "
        "e Suécia com iluminação especial; uma comunidade da zona Leste se mobilizou diante "
        "do desaparecimento de um menino de 10 anos; e uma iniciativa escolar uniu Libras e "
        "cultura regional ao ensinar uma toada do Caprichoso em língua de sinais."
    ),
    "topics": [
        {
            "name": "Cultura e Lazer",
            "summary": "O Teatro Amazonas recebeu iluminação especial pelo bicentenário das relações diplomáticas entre Brasil e Suécia.",
            "article_count": 6,
        },
        {
            "name": "Social e Cidadania",
            "summary": "Um professor de Manaus ensinou uma toada do Caprichoso em Libras, ampliando o acesso dos alunos à cultura regional.",
            "article_count": 4,
        },
        {
            "name": "Educação",
            "summary": "Escolas municipais de Manaus promovem atividades de inclusão para alunos surdos com apoio de intérpretes de Libras.",
            "article_count": 3,
        },
    ],
}


# ---------------------------------------------------------------------------
# Desenho
# ---------------------------------------------------------------------------

def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _truncate(text: str, budget: int) -> str:
    if len(text) <= budget:
        return text
    cut = text[:budget]
    last_boundary = max(cut.rfind(". "), cut.rfind("; "))
    if last_boundary > budget * 0.4:
        return cut[: last_boundary + 1]
    last_space = cut.rfind(" ")
    return cut[:last_space].rstrip(",;: ") + "…"


def _wave(draw: ImageDraw.ImageDraw, y_base: float, color: tuple, amplitude: float = 26, phase: float = 0.0):
    points = [(0, H)]
    for x in range(0, W + 1, 20):
        y = y_base + amplitude * math.sin((x / W) * math.pi * 2 + phase)
        points.append((x, y))
    points.append((W, H))
    draw.polygon(points, fill=color)


def _paste_logomark(canvas: Image.Image, size: int, xy: tuple):
    logo = Image.open(LOGOMARK_TRANSPARENT).convert("RGBA")
    logo = logo.resize((size, size), Image.LANCZOS)
    canvas.paste(logo, xy, logo)


def _wordmark(draw: ImageDraw.ImageDraw, xy: tuple, color: tuple):
    draw.multiline_text(xy, "Observatório\nde Manaus", font=font_bold(30), fill=color, spacing=4)


def _vcenter_start(block_height: float) -> float:
    """Y inicial para centralizar um bloco de `block_height` px entre
    CONTENT_TOP e CONTENT_BOTTOM (nunca acima de CONTENT_TOP, mesmo se o
    bloco for maior que a região — nesse caso ele só cresce para baixo)."""
    slack = (CONTENT_BOTTOM - CONTENT_TOP) - block_height
    return CONTENT_TOP + max(0, slack / 2)


def render_cover(ref_date: date) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)
    _wave(draw, H - 140, (16, 46, 70), amplitude=22, phase=0.3)

    title_font = font_bold(96)
    date_font = font_bold(40)
    tagline_font = font_regular(34)
    TAGLINE_GAP, TAGLINE_LH = 50, 46

    title = "OBSERVATÓRIO\nMANAUS"
    title_box = draw.multiline_textbbox((0, 0), title, font=title_font, spacing=14)
    title_h = title_box[3] - title_box[1]
    date_box = draw.textbbox((0, 0), _data_abrev(ref_date), font=date_font)
    date_h = date_box[3] - date_box[1]
    tagline_lines = _wrap_text(
        draw, "Cobertura diária de notícias sobre Manaus e o Amazonas.", tagline_font, W - 2 * MARGIN
    )

    RULE_GAP, RULE_H = 30, 10
    total_h = (title_h + RULE_GAP + RULE_H + RULE_GAP + date_h
               + TAGLINE_GAP + len(tagline_lines) * TAGLINE_LH)
    y = _vcenter_start(total_h)

    draw.multiline_text((MARGIN, y), title, font=title_font, fill=CREAM, spacing=14)
    y += title_h + RULE_GAP
    draw.rectangle([MARGIN, y, MARGIN + 140, y + RULE_H], fill=GOLD)
    y += RULE_H + RULE_GAP
    draw.text((MARGIN, y), _data_abrev(ref_date), font=date_font, fill=GOLD)
    y += date_h + TAGLINE_GAP
    for line in tagline_lines:
        draw.text((MARGIN, y), line, font=tagline_font, fill=CREAM)
        y += TAGLINE_LH

    _paste_logomark(img, 64, (MARGIN, H - 110))
    _wordmark(draw, (MARGIN + 80, H - 104), CREAM)
    return img


def render_topic_card(topic: dict, index: int) -> Image.Image:
    style = TOPIC_STYLES[index % len(TOPIC_STYLES)]
    bg, fg, wave_color = style["bg"], style["fg"], style["wave"]

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    _wave(draw, H - 200, wave_color, amplitude=30, phase=index * 0.7)

    headline_font = font_bold(58)
    body_font = font_regular(42)
    HEADLINE_LH, RULE_GAP_TOP, RULE_H, RULE_GAP_BOTTOM, BODY_LH = 70, 10, 10, 50, 58

    headline_lines = _wrap_text(draw, topic["name"].upper(), headline_font, W - 2 * MARGIN)
    body_text = _truncate(topic["summary"].strip(), BODY_CHAR_BUDGET)
    body_lines = _wrap_text(draw, body_text, body_font, W - 2 * MARGIN)

    total_h = (len(headline_lines) * HEADLINE_LH + RULE_GAP_TOP + RULE_H + RULE_GAP_BOTTOM
               + len(body_lines) * BODY_LH)
    y = _vcenter_start(total_h)

    for line in headline_lines:
        draw.text((MARGIN, y), line, font=headline_font, fill=fg)
        y += HEADLINE_LH

    y += RULE_GAP_TOP
    draw.rectangle([MARGIN, y, MARGIN + 110, y + RULE_H], fill=GOLD)
    y += RULE_H + RULE_GAP_BOTTOM

    for line in body_lines:
        draw.text((MARGIN, y), line, font=body_font, fill=fg)
        y += BODY_LH

    return img


def render_closing(ref_date: date) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)
    _wave(draw, H - 260, (16, 46, 70), amplitude=24, phase=1.1)

    headline_font = font_bold(52)
    body_font = font_regular(40)
    cta_label_font = font_regular(40)
    cta_url_font = font_bold(42)
    HEADLINE_LH, RULE_GAP_TOP, RULE_H, RULE_GAP_BOTTOM, BODY_LH, CTA_GAP, CTA_LH = (
        66, 10, 10, 40, 56, 40, 56)

    headline_lines = ["A COBERTURA DO DIA,", "EM PERSPECTIVA"]
    disclaimer = (
        "Síntese automática da cobertura jornalística monitorada pelo Observatório "
        "de Manaus. Representa o que foi publicado pelas fontes acompanhadas, não "
        "a totalidade dos acontecimentos."
    )
    body_lines = _wrap_text(draw, disclaimer, body_font, W - 2 * MARGIN)

    total_h = (len(headline_lines) * HEADLINE_LH + RULE_GAP_TOP + RULE_H + RULE_GAP_BOTTOM
               + len(body_lines) * BODY_LH + CTA_GAP + 2 * CTA_LH)
    y = _vcenter_start(total_h)

    for line in headline_lines:
        draw.text((MARGIN, y), line, font=headline_font, fill=CREAM)
        y += HEADLINE_LH

    y += RULE_GAP_TOP
    draw.rectangle([MARGIN, y, MARGIN + 110, y + RULE_H], fill=GOLD)
    y += RULE_H + RULE_GAP_BOTTOM

    for line in body_lines:
        draw.text((MARGIN, y), line, font=body_font, fill=CREAM)
        y += BODY_LH

    y += CTA_GAP
    draw.text((MARGIN, y), "Leia as fontes originais em", font=cta_label_font, fill=CREAM)
    y += CTA_LH
    draw.text((MARGIN, y), "observatorio.manaus.br", font=cta_url_font, fill=GOLD)

    _paste_logomark(img, 64, (MARGIN, H - 110))
    _wordmark(draw, (MARGIN + 80, H - 104), CREAM)
    return img


def build_caption(ref_date: date, topics: list[dict]) -> str:
    """Monta a legenda só a partir dos temas já filtrados (mesmos dos cards).

    Nunca usa o resumo geral do dia (``general_summary``) diretamente: ele não
    passa pelo filtro de temas sensíveis (``EXCLUDED_TOPIC_SLUGS``) e poderia
    vazar para a legenda pública conteúdo excluído dos cards por exigir
    revisão humana reforçada (ex.: ocorrências criminais, casos envolvendo
    menores). Ver "Decisões editoriais do piloto" no protótipo.
    """
    lines = [f"Manaus em resumo — {_data_extenso(ref_date)}.", ""]
    if topics:
        resumo = " ".join(t["summary"].strip() for t in topics)
        lines.append(resumo)
    lines.append("")
    lines.append(
        "Esta é uma síntese automática da cobertura jornalística monitorada pelo "
        "Observatório de Manaus. O conteúdo representa o que foi publicado pelas "
        "fontes acompanhadas, não a totalidade dos acontecimentos. Consulte as "
        "notícias e fontes originais em observatorio.manaus.br."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------

def generate(ref_date: date | None = None, out_dir: str | None = None, use_sample: bool = False,
             from_json: str | None = None):
    if use_sample:
        data = SAMPLE_DATA
        ref_date = data["date"]
    elif from_json:
        data = load_card_data_from_json(from_json)
        ref_date = data["date"]
    else:
        ref_date = ref_date or _manaus_today()
        data = fetch_card_data(ref_date)

    if not data["topics"]:
        raise SystemExit(
            f"Nenhum tema com resumo elegível para {ref_date} (ou só há temas excluídos, "
            f"como {sorted(EXCLUDED_TOPIC_SLUGS)}). Use --sample para pré-visualizar com dados de exemplo."
        )

    out_dir = out_dir or os.path.join(os.path.dirname(__file__), "output", ref_date.isoformat())
    os.makedirs(out_dir, exist_ok=True)

    images = [render_cover(ref_date)]
    images += [render_topic_card(topic, i) for i, topic in enumerate(data["topics"])]
    images.append(render_closing(ref_date))

    paths = []
    for i, img in enumerate(images, start=1):
        path = os.path.join(out_dir, f"card_{i}.png")
        img.save(path)
        paths.append(path)

    caption_path = os.path.join(out_dir, "legenda.txt")
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(build_caption(ref_date, data["topics"]))

    if data["general_summary"]:
        print("\nResumo geral do dia (referência editorial — NÃO entra na legenda automaticamente):")
        print(" ", data["general_summary"])

    print(f"\nGerados {len(paths)} cards em {out_dir}")
    for p in paths:
        print(" -", p)
    print(" -", caption_path)
    return paths, caption_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=str, help="Data de referência (AAAA-MM-DD). Padrão: hoje (horário de Manaus).")
    parser.add_argument("--out-dir", type=str, help="Diretório de saída.")
    parser.add_argument("--sample", action="store_true", help="Usa dados de exemplo (pré-visualização sem banco).")
    parser.add_argument("--from-json", type=str,
                         help="Carrega os dados de um JSON já buscado (date, general_summary, topics) em vez de "
                              "consultar o banco diretamente — útil quando o banco de produção só é alcançável "
                              "via `railway ssh`.")
    args = parser.parse_args()

    generate(
        ref_date=date.fromisoformat(args.date) if args.date else None,
        out_dir=args.out_dir,
        use_sample=args.sample,
        from_json=args.from_json,
    )
