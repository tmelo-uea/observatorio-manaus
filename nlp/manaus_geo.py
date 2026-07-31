"""Mapa bairro → zona administrativa de Manaus.

Serve para densificar a dimensão geográfica da série de cobertura criminal.
Bairro é preciso mas esparso (60+ unidades, menos de um caso/dia cada); zona
tem 6 valores e recebe volume suficiente para série temporal já no primeiro mês.

O LLM extrai o BAIRRO do texto da matéria; a zona é derivada aqui, de forma
determinística. Bairro desconhecido → zona None (não chuta).

FONTE: divisão oficial da Lei Municipal nº 1.401/2010, com a inclusão de
Colônia Japonesa (oficializada em 22/12/2025). São 64 bairros em 6 zonas
administrativas — a zona rural não é dividida em bairros e não entra aqui.

Obtida via verbete consolidado que cita a lei, não do PDF do IMPLURB
diretamente; se for publicar análise geográfica, vale confirmar na fonte
primária (implurbatende.manaus.am.gov.br).
"""
import re
import unicodedata

# zona -> bairros
ZONAS = {
    "Sul": [
        "Centro", "Praça 14 de Janeiro", "Cachoeirinha", "Presidente Vargas",
        "Educandos", "Santa Luzia", "Colônia Oliveira Machado", "Crespo",
        "Morro da Liberdade", "São Lázaro", "Petrópolis", "Vila Buriti",
        "Betânia", "São Francisco", "Distrito Industrial I", "Japiim",
        "Raiz", "Nossa Senhora Aparecida",
    ],
    "Centro-Sul": [
        "Adrianópolis", "Aleixo", "Chapada", "Colônia Japonesa", "Flores",
        "Nossa Senhora das Graças", "Parque 10 de Novembro", "São Geraldo",
    ],
    "Centro-Oeste": [
        "Alvorada", "Da Paz", "Dom Pedro", "Planalto", "Redenção",
    ],
    "Oeste": [
        "Compensa", "Glória", "Lírio do Vale", "Nova Esperança", "Ponta Negra",
        "Santo Agostinho", "Santo Antônio", "São Jorge", "São Raimundo",
        "Tarumã", "Tarumã-Açu", "Vila da Prata",
    ],
    "Norte": [
        "Cidade de Deus", "Cidade Nova", "Colônia Santo Antônio",
        "Colônia Terra Nova", "Lago Azul", "Monte das Oliveiras",
        "Nova Cidade", "Novo Aleixo", "Novo Israel", "Santa Etelvina",
    ],
    "Leste": [
        "Armando Mendes", "Colônia Antônio Aleixo", "Coroado",
        "Distrito Industrial II", "Gilberto Mestrinho", "Jorge Teixeira",
        "Mauazinho", "Puraquequara", "São José Operário", "Tancredo Neves",
        "Zumbi dos Palmares",
    ],
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


# índice normalizado: "cidade nova" -> ("Cidade Nova", "Norte")
_INDEX = {}
for _zona, _bairros in ZONAS.items():
    for _b in _bairros:
        _INDEX[_norm(_b)] = (_b, _zona)

# Apelidos e grafias que a imprensa usa mas não são o nome oficial do bairro.
# "São José" é o caso mais comum: as matérias quase nunca escrevem "Operário".
ALIASES = {
    "parque 10": "Parque 10 de Novembro",
    "parque dez": "Parque 10 de Novembro",
    "parque 10 de novembro": "Parque 10 de Novembro",
    "praca 14": "Praça 14 de Janeiro",
    "sao jose": "São José Operário",
    "zumbi": "Zumbi dos Palmares",
    "taruma acu": "Tarumã-Açu",
    "distrito industrial": "Distrito Industrial I",
    "nossa senhora das gracas": "Nossa Senhora das Graças",
    "gracas": "Nossa Senhora das Graças",
    "colonia oliveira machado": "Colônia Oliveira Machado",
    "sao raimundo": "São Raimundo",
}


def resolve(bairro: str | None) -> tuple[str | None, str | None]:
    """Normaliza o bairro e devolve (bairro_oficial, zona).

    Devolve (bairro_como_veio, None) se o bairro não estiver no mapa — melhor
    preservar o texto original do que descartar a informação.
    """
    if not bairro:
        return None, None
    key = _norm(bairro)
    if key in ALIASES:
        key = _norm(ALIASES[key])
    hit = _INDEX.get(key)
    if hit:
        return hit[0], hit[1]
    return bairro.strip()[:80], None


ALL_BAIRROS = sorted({b for bs in ZONAS.values() for b in bs})
