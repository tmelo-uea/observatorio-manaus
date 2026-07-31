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


# ---------------------------------------------------------------------------
# Municípios do Amazonas
#
# Fonte: API de localidades do IBGE, estado 13 (AM) — os 62 municípios oficiais.
# Serve de guarda contra contaminação da série de cobertura criminal: numa
# amostra de 25 matérias todas marcadas is_local=1, três noticiavam crimes de
# Medellín, São Paulo e Rio de Janeiro. O classificador is_local as deu como
# locais; o município extraído pelo modelo denuncia o engano de graça.
# ---------------------------------------------------------------------------
MUNICIPIOS_AM = [
    "Alvarães", "Amaturá", "Anamã", "Anori", "Apuí", "Atalaia do Norte",
    "Autazes", "Barcelos", "Barreirinha", "Benjamin Constant", "Beruri",
    "Boa Vista do Ramos", "Boca do Acre", "Borba", "Caapiranga", "Canutama",
    "Carauari", "Careiro", "Careiro da Várzea", "Coari", "Codajás", "Eirunepé",
    "Envira", "Fonte Boa", "Guajará", "Humaitá", "Ipixuna", "Iranduba",
    "Itacoatiara", "Itamarati", "Itapiranga", "Japurá", "Juruá", "Jutaí",
    "Lábrea", "Manacapuru", "Manaquiri", "Manaus", "Manicoré", "Maraã",
    "Maués", "Nhamundá", "Nova Olinda do Norte", "Novo Airão", "Novo Aripuanã",
    "Parintins", "Pauini", "Presidente Figueiredo", "Rio Preto da Eva",
    "Santa Isabel do Rio Negro", "Santo Antônio do Içá", "Silves",
    "São Gabriel da Cachoeira", "São Paulo de Olivença",
    "São Sebastião do Uatumã", "Tabatinga", "Tapauá", "Tefé", "Tonantins",
    "Uarini", "Urucará", "Urucurituba",
]

_MUNICIPIOS_INDEX = {_norm(m): m for m in MUNICIPIOS_AM}

# Referências ao estado inteiro, em vez de um município. Contam como locais.
_ESTADO_TOKENS = {
    "amazonas", "am", "estado do amazonas", "interior do amazonas",
    "interior do estado", "interior", "amazonia", "amazonia ocidental",
    "regiao metropolitana de manaus", "interior do am",
}

# "Manaus/AM", "Manaus (AM)", "Parintins - Amazonas" e afins
_SUFIXO_UF = re.compile(r"[\s,\-–—/()]+(am|amazonas)\s*\)?$")


def is_amazonas(municipio: str | None) -> bool | None:
    """True se o município é do Amazonas, False se não é, None se não dá para saber.

    None é resposta legítima e frequente: a maioria das matérias não nomeia o
    município. Nesse caso a menção é mantida — descartar o que não se sabe seria
    trocar uma contaminação por uma perda.
    """
    if not municipio:
        return None
    key = _norm(municipio).strip()
    # A função é pública e pode receber a saída crua do modelo, que às vezes traz
    # a STRING "null". Sem isto, "null" seria lido como município estrangeiro e
    # descartaria a menção.
    if key in {"null", "none", "nulo", "n/a", "na", "-", "desconhecido", "nao informado"}:
        return None

    # Checagem de estado ANTES de remover o sufixo de UF: o removedor come a
    # palavra "amazonas" e deixaria "interior do" ou "estado do", que não casam
    # com nada — e a menção local seria descartada.
    if key in _ESTADO_TOKENS:
        return True

    key = _SUFIXO_UF.sub("", key).strip()
    if not key:
        return None

    # O modelo às vezes devolve MAIS DE UM município quando a matéria cobre
    # vários ("Tonantins, Benjamin Constant"). Comparação exata rejeitava a
    # string inteira e descartava crime legítimo — os dois são do Amazonas.
    partes = [p.strip() for p in re.split(r"[,;/]| e ", key) if p.strip()]
    if not partes:
        return None

    conhecidos = {_norm(a) for a in ALIASES}
    for parte in partes:
        # O modelo às vezes preenche o campo com o ESTADO em vez do município
        # ("Amazonas", "interior do Amazonas"). Isso é local, não estrangeiro —
        # a guarda estava descartando crime legítimo por falta de precisão.
        if parte in _ESTADO_TOKENS:
            return True
        parte = _SUFIXO_UF.sub("", parte).strip()
        if not parte:
            continue
        # basta UM município do Amazonas para a menção ser local
        if parte in _MUNICIPIOS_INDEX or parte in _INDEX or parte in conhecidos:
            return True
    return False
