"""Mapa bairro → zona administrativa de Manaus.

Serve para densificar a dimensão geográfica da série de cobertura criminal.
Bairro é preciso mas esparso (60+ unidades, menos de um caso/dia cada); zona
tem 6 valores e recebe volume suficiente para série temporal já no primeiro mês.

O LLM extrai o BAIRRO do texto da matéria; a zona é derivada aqui, de forma
determinística. Bairro desconhecido → zona None (não chuta).

⚠️ CONFERIR COM QUEM CONHECE A CIDADE. Este mapa foi compilado sem consulta à
divisão oficial da Prefeitura de Manaus. Erros de zona não quebram nada, mas
enviesam silenciosamente a análise geográfica.
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
        "Chapada", "Parque 10 de Novembro", "Adrianópolis",
        "Nossa Senhora das Graças", "Aleixo", "São Geraldo", "Flores",
    ],
    "Centro-Oeste": [
        "Alvorada", "Dom Pedro", "Planalto", "São Jorge", "Vila da Prata",
        "Santo Agostinho", "Redenção", "Da Paz", "Lírio do Vale",
    ],
    "Oeste": [
        "Compensa", "Santo Antônio", "São Raimundo", "Glória",
        "Nova Esperança", "Ponta Negra", "Tarumã", "Tarumã-Açu",
    ],
    "Norte": [
        "Cidade Nova", "Novo Israel", "Monte das Oliveiras", "Santa Etelvina",
        "Cidade de Deus", "Nova Cidade", "Colônia Terra Nova", "Lago Azul",
        "Amazonino Mendes", "Novo Aleixo",
    ],
    "Leste": [
        "Jorge Teixeira", "São José Operário", "Tancredo Neves", "Coroado",
        "Distrito Industrial II", "Zumbi dos Palmares", "Puraquequara",
        "Mauazinho", "Armando Mendes", "Gilberto Mestrinho",
        "Colônia Antônio Aleixo", "São José",
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

# apelidos e grafias que aparecem na imprensa mas não são o nome oficial
ALIASES = {
    "parque 10": "Parque 10 de Novembro",
    "parque dez": "Parque 10 de Novembro",
    "praca 14": "Praça 14 de Janeiro",
    "sao jose": "São José Operário",
    "colonia antonio aleixo": "Colônia Antônio Aleixo",
    "zumbi": "Zumbi dos Palmares",
    "taruma acu": "Tarumã-Açu",
    "distrito industrial": "Distrito Industrial I",
    "novo aleixo": "Novo Aleixo",
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
