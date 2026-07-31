"""Taxonomia de tipos penais usada pela extração de cobertura criminal.

A categoria da série É a figura penal. Isso tem uma consequência importante:
o dispositivo legal (`ref`) NÃO é gerado pelo LLM — ele vem deste mapa, escrito
à mão e determinístico. O modelo só escolhe um slug da lista fechada; a
tipificação é consultada aqui. Elimina o risco de artigo de lei alucinado.

Dois níveis, e o segundo vem de graça da estrutura do próprio Código Penal:

  nível 1  `group`  — bem jurídico tutelado (Títulos do CP e leis especiais).
                      ~13 grupos. É a série DENSA, boa para gráfico temporal.
  nível 2  `slug`   — a figura penal em si. ~50 tipos. Preciso, mas esparso:
                      com ~30 casos/dia, muitas figuras rendem menos de um
                      registro por semana. Serve para consulta e drill-down,
                      não para série temporal isolada.

⚠️ REVISÃO JURÍDICA PENDENTE. As referências abaixo foram compiladas sem
parecer de alguém com formação em Direito. Antes de qualquer publicação que
exiba o dispositivo legal, pedir revisão — sobretudo nos pontos que mudaram
por leis recentes (feminicídio autônomo, perseguição, violência psicológica).
"""

# slug -> (rótulo legível, dispositivo legal, grupo)
CRIME_TYPES = {
    # ------------------------------------------------------------------
    # Crimes contra a vida — CP, Título I, Capítulo I
    # ------------------------------------------------------------------
    "homicidio_doloso":        ("Homicídio doloso",              "CP art. 121",            "vida"),
    "homicidio_culposo":       ("Homicídio culposo",             "CP art. 121, §3º",       "vida"),
    "feminicidio":             ("Feminicídio",                   "CP art. 121-A",          "vida"),
    "infanticidio":            ("Infanticídio",                  "CP art. 123",            "vida"),
    "aborto":                  ("Aborto",                        "CP arts. 124 a 128",     "vida"),
    # Acrescentado depois que o modelo inventou este identificador sozinho ao
    # classificar "matar e ocultar cadáver do próprio pai" — sinal de lacuna.
    "ocultacao_cadaver":       ("Ocultação de cadáver",          "CP art. 211",            "vida"),

    # ------------------------------------------------------------------
    # Lesão e liberdade pessoal — CP, Títulos I e I-A
    # ------------------------------------------------------------------
    "lesao_corporal":          ("Lesão corporal",                "CP art. 129",            "integridade"),
    "lesao_corporal_domestica":("Lesão corporal — violência doméstica", "CP art. 129, §9º", "integridade"),
    "ameaca":                  ("Ameaça",                        "CP art. 147",            "integridade"),
    "perseguicao":             ("Perseguição (stalking)",        "CP art. 147-A",          "integridade"),
    "violencia_psicologica":   ("Violência psicológica contra a mulher", "CP art. 147-B",   "integridade"),
    "maus_tratos":             ("Maus-tratos",                   "CP art. 136",            "integridade"),

    "sequestro_carcere":       ("Sequestro e cárcere privado",   "CP art. 148",            "liberdade"),
    "trafico_pessoas":         ("Tráfico de pessoas",            "CP art. 149-A",          "liberdade"),
    "trabalho_escravo":        ("Redução a condição análoga à de escravo", "CP art. 149",  "liberdade"),
    "violacao_domicilio":      ("Violação de domicílio",         "CP art. 150",            "liberdade"),

    # ------------------------------------------------------------------
    # Crimes contra o patrimônio — CP, Título II
    # ------------------------------------------------------------------
    "furto":                   ("Furto",                         "CP art. 155",            "patrimonio"),
    "roubo":                   ("Roubo",                         "CP art. 157",            "patrimonio"),
    "latrocinio":              ("Latrocínio (roubo seguido de morte)", "CP art. 157, §3º, II", "patrimonio"),
    "extorsao":                ("Extorsão",                      "CP art. 158",            "patrimonio"),
    "extorsao_sequestro":      ("Extorsão mediante sequestro",   "CP art. 159",            "patrimonio"),
    "dano":                    ("Dano",                          "CP art. 163",            "patrimonio"),
    "apropriacao_indebita":    ("Apropriação indébita",          "CP art. 168",            "patrimonio"),
    "estelionato":             ("Estelionato",                   "CP art. 171",            "patrimonio"),
    "receptacao":              ("Receptação",                    "CP art. 180",            "patrimonio"),

    # ------------------------------------------------------------------
    # Crimes contra a dignidade sexual — CP, Título VI (e ECA)
    # ------------------------------------------------------------------
    "estupro":                 ("Estupro",                       "CP art. 213",            "dignidade_sexual"),
    "estupro_vulneravel":      ("Estupro de vulnerável",         "CP art. 217-A",          "dignidade_sexual"),
    "importunacao_sexual":     ("Importunação sexual",           "CP art. 215-A",          "dignidade_sexual"),
    # Idem: inventado pelo modelo num caso de estupro de vulnerável.
    "exploracao_sexual":       ("Exploração sexual de vulnerável", "CP art. 218-B",        "dignidade_sexual"),
    "assedio_sexual":          ("Assédio sexual",                "CP art. 216-A",          "dignidade_sexual"),
    "pornografia_infantil":    ("Pornografia infantil",          "ECA arts. 241 a 241-B",  "dignidade_sexual"),

    # ------------------------------------------------------------------
    # Crimes contra a paz pública — CP, Título IX / Lei 12.850
    # ------------------------------------------------------------------
    "associacao_criminosa":    ("Associação criminosa",          "CP art. 288",            "paz_publica"),
    "organizacao_criminosa":   ("Organização criminosa",         "Lei 12.850/2013, art. 2º", "paz_publica"),
    "milicia":                 ("Constituição de milícia privada", "CP art. 288-A",        "paz_publica"),

    # ------------------------------------------------------------------
    # Fé pública — CP, Título X
    # ------------------------------------------------------------------
    "falsidade_ideologica":    ("Falsidade ideológica",          "CP art. 299",            "fe_publica"),
    "falsificacao_documento":  ("Falsificação de documento",     "CP arts. 297 e 298",     "fe_publica"),
    "moeda_falsa":             ("Moeda falsa",                   "CP art. 289",            "fe_publica"),

    # ------------------------------------------------------------------
    # Administração pública — CP, Título XI
    # ------------------------------------------------------------------
    "peculato":                ("Peculato",                      "CP art. 312",            "administracao_publica"),
    "concussao":               ("Concussão",                     "CP art. 316",            "administracao_publica"),
    "corrupcao_passiva":       ("Corrupção passiva",             "CP art. 317",            "administracao_publica"),
    "prevaricacao":            ("Prevaricação",                  "CP art. 319",            "administracao_publica"),
    "corrupcao_ativa":         ("Corrupção ativa",               "CP art. 333",            "administracao_publica"),
    "contrabando":             ("Contrabando",                   "CP art. 334-A",          "administracao_publica"),
    "descaminho":              ("Descaminho",                    "CP art. 334",            "administracao_publica"),

    # ------------------------------------------------------------------
    # Drogas — Lei 11.343/2006
    # ------------------------------------------------------------------
    "trafico_drogas":          ("Tráfico de drogas",             "Lei 11.343/2006, art. 33", "drogas"),
    "associacao_trafico":      ("Associação para o tráfico",     "Lei 11.343/2006, art. 35", "drogas"),

    # ------------------------------------------------------------------
    # Armas — Lei 10.826/2003
    # ------------------------------------------------------------------
    "posse_ilegal_arma":       ("Posse ilegal de arma de fogo",  "Lei 10.826/2003, art. 12", "armas"),
    "porte_ilegal_arma":       ("Porte ilegal de arma de fogo",  "Lei 10.826/2003, art. 14", "armas"),
    "arma_uso_restrito":       ("Arma de fogo de uso restrito",  "Lei 10.826/2003, art. 16", "armas"),

    # ------------------------------------------------------------------
    # Ambientais — Lei 9.605/1998 (relevante para a Amazônia)
    # ------------------------------------------------------------------
    # Rótulos deliberadamente explícitos: com "Crime contra a fauna" x "Maus-tratos
    # a animais" o modelo classificava rinha de galos como art. 29 (fauna silvestre),
    # quando galo doméstico é art. 32.
    "crime_fauna":             ("Caça, pesca ou tráfico de fauna SILVESTRE", "Lei 9.605/1998, art. 29", "ambiental"),
    "maus_tratos_animais":     ("Maus-tratos a animais (incl. rinhas e animais domésticos)", "Lei 9.605/1998, art. 32", "ambiental"),
    "desmatamento":            ("Destruição de vegetação/desmatamento", "Lei 9.605/1998, arts. 38 e 50", "ambiental"),
    "poluicao":                ("Poluição",                      "Lei 9.605/1998, art. 54", "ambiental"),
    "garimpo_ilegal":          ("Extração mineral ilegal (garimpo)", "Lei 9.605/1998, art. 55", "ambiental"),
    "pesca_ilegal":            ("Pesca ilegal",                  "Lei 9.605/1998, arts. 34 e 35", "ambiental"),

    # ------------------------------------------------------------------
    # Trânsito — Lei 9.503/1997 (CTB)
    # ------------------------------------------------------------------
    "homicidio_transito":      ("Homicídio culposo na direção",  "CTB art. 302",           "transito"),
    "lesao_transito":          ("Lesão corporal culposa na direção", "CTB art. 303",       "transito"),
    "embriaguez_volante":      ("Embriaguez ao volante",         "CTB art. 306",           "transito"),

    # ------------------------------------------------------------------
    # Outras leis especiais
    # ------------------------------------------------------------------
    "lavagem_dinheiro":        ("Lavagem de dinheiro",           "Lei 9.613/1998, art. 1º", "outras_leis"),
    "medida_protetiva":        ("Descumprimento de medida protetiva", "Lei 11.340/2006, art. 24-A", "outras_leis"),
    "tortura":                 ("Tortura",                       "Lei 9.455/1997, art. 1º", "outras_leis"),
    "crime_eleitoral":         ("Crime eleitoral",               "Lei 4.737/1965 (Código Eleitoral)", "outras_leis"),

    # ------------------------------------------------------------------
    # Escape. Usado quando há crime noticiado sem figura identificável.
    # Se este slug crescer demais na série, é sinal de lacuna na taxonomia.
    # ------------------------------------------------------------------
    "outro":                   ("Outro crime",                   None,                      "outros"),
}

# grupo -> rótulo legível (nível 1 da série, o que vai no gráfico temporal)
CRIME_GROUPS = {
    "vida":                  "Crimes contra a vida",
    "integridade":           "Lesão, ameaça e violência doméstica",
    "liberdade":             "Crimes contra a liberdade pessoal",
    "patrimonio":            "Crimes contra o patrimônio",
    "dignidade_sexual":      "Crimes contra a dignidade sexual",
    "paz_publica":           "Crimes contra a paz pública",
    "fe_publica":            "Crimes contra a fé pública",
    "administracao_publica": "Crimes contra a administração pública",
    "drogas":                "Drogas",
    "armas":                 "Armas de fogo",
    "ambiental":             "Crimes ambientais",
    "transito":              "Crimes de trânsito",
    "outras_leis":           "Outras leis especiais",
    "outros":                "Não classificado",
}

VALID_SLUGS = set(CRIME_TYPES)


def label(slug: str) -> str:
    """Rótulo legível da figura penal."""
    entry = CRIME_TYPES.get(slug)
    return entry[0] if entry else slug


def legal_ref(slug: str) -> str | None:
    """Dispositivo legal da figura. Determinístico — nunca vem do LLM."""
    entry = CRIME_TYPES.get(slug)
    return entry[1] if entry else None


def group(slug: str) -> str:
    """Grupo (bem jurídico tutelado) ao qual a figura pertence."""
    entry = CRIME_TYPES.get(slug)
    return entry[2] if entry else "outros"


def group_label(slug_or_group: str) -> str:
    """Rótulo legível do grupo. Aceita slug de figura ou de grupo."""
    if slug_or_group in CRIME_GROUPS:
        return CRIME_GROUPS[slug_or_group]
    return CRIME_GROUPS.get(group(slug_or_group), "Não classificado")


def prompt_vocabulary() -> str:
    """Vocabulário formatado para injetar no prompt do extrator.

    Agrupado por bem jurídico porque a vizinhança semântica ajuda o modelo a
    escolher entre figuras próximas (furto x roubo, roubo x latrocínio).
    """
    lines = []
    for gid, glabel in CRIME_GROUPS.items():
        slugs = [s for s, v in CRIME_TYPES.items() if v[2] == gid]
        if not slugs:
            continue
        lines.append(f"\n{glabel}:")
        for s in slugs:
            lines.append(f"  {s} = {CRIME_TYPES[s][0]}")
    return "\n".join(lines)
