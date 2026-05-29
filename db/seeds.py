from db.connection import get_session
from db.models import Source, Topic

TOPICS = [
    {
        "name": "Saúde",
        "slug": "saude",
        "color": "#e74c3c",
        "display_order": 1,
        "keywords": [
            "saúde", "hospital", "ubs", "sus", "médico", "médica", "enfermeiro", "enfermagem",
            "dengue", "vacina", "vacinação", "epidemia", "pandemia", "doença", "paciente",
            "internação", "pronto-socorro", "fhaj", "fcecon", "hps", "caps", "upa",
            "secretaria de saúde", "semsa", "leito", "cirurgia", "tratamento", "remédio",
            "medicamento", "febre", "vírus", "infecção", "malária", "tuberculose", "aids",
            "câncer", "obesidade", "hipertensão", "diabetes", "saúde mental", "ambulância",
            "samu", "emergência médica", "clínica", "posto de saúde", "agente de saúde",
            "farmácia", "nutrição", "pediatria", "maternidade", "parto", "gestante",
            "zika", "chikungunya", "leptospirose"
        ],
    },
    {
        "name": "Segurança Pública",
        "slug": "seguranca-publica",
        "color": "#c0392b",
        "display_order": 2,
        "keywords": [
            "crime", "polícia", "homicídio", "assassinato", "assassinado", "tráfico",
            "bope", "polícia militar", "policia militar", "polícia civil", "policia civil",
            "ssp", "segurança pública", "preso", "prisão", "furto", "roubo", "violência",
            "operação policial", "feminicídio", "latrocínio", "delegacia", "penal",
            "morte", "morto", "vítima", "suspeito", "arma", "tiro", "bala", "disparo",
            "droga", "cocaína", "crack", "maconha", "apreensão", "flagrante", "mandado",
            "inquérito", "acusado", "criminoso", "gangue", "milícia", "sequestro",
            "estupro", "abuso", "violência doméstica", "feminicídio", "ameaça",
            "acidente de trânsito", "batida", "atropelamento", "colisão", "capotamento",
            "bombeiros", "corpo de bombeiros", "cbm", "resgate", "incêndio", "fogo",
            "desaparecido", "foragido", "procurado", "investigação criminal"
        ],
    },
    {
        "name": "Meio Ambiente",
        "slug": "meio-ambiente",
        "color": "#27ae60",
        "display_order": 3,
        "keywords": [
            "meio ambiente", "amazônia", "desmatamento", "queimada", "incêndio florestal",
            "rio negro", "solimões", "peixe", "ibama", "sema", "enchente", "cheia",
            "seca", "biodiversidade", "floresta", "sustentabilidade", "carbono",
            "poluição", "resíduo", "lixo", "manancial", "igarapé",
            "fauna", "flora", "animal silvestre", "reserva ambiental", "área de preservação",
            "reflorestamento", "desmatamento ilegal", "garimpo", "mineração ilegal",
            "clima", "temperatura", "chuva", "estiagem", "nível do rio",
            "ipaam", "arboviroses", "mosquito", "dengue ambiental", "saneamento básico",
            "reciclagem", "coleta seletiva", "compostagem", "agrotóxico",
            "poluição do ar", "poluição da água", "derramamento", "vazamento"
        ],
    },
    {
        "name": "Política e Governo",
        "slug": "politica-governo",
        "color": "#2980b9",
        "display_order": 4,
        "keywords": [
            "prefeito", "governador", "vereador", "deputado", "senador", "câmara",
            "assembleia legislativa", "aleam", "eleição", "eleições", "partido",
            "política", "governo", "prefeitura", "estado do amazonas", "semcom",
            "licitação", "concurso público", "decreto", "lei municipal", "gestão pública",
            "david almeida", "wilson lima", "roberto cidade", "gestão",
            "secretaria", "secretário", "secretária", "ministério", "ministro",
            "orçamento", "emenda", "pec", "projeto de lei", "votação", "sessão",
            "plenário", "comissão parlamentar", "cpi", "mandato", "posse",
            "campanha eleitoral", "candidato", "urna", "eleitorado", "coligação",
            "improbidade", "corrupto", "corrupção", "denúncia política",
            "transparência", "prestação de contas", "licitação pública",
            "contrato público", "concurso público", "edital"
        ],
    },
    {
        "name": "Economia e Negócios",
        "slug": "economia-negocios",
        "color": "#f39c12",
        "display_order": 5,
        "keywords": [
            "economia", "emprego", "desemprego", "salário", "pib", "zona franca",
            "suframa", "indústria", "comércio", "empresa", "investimento", "inflação",
            "mercado", "exportação", "importação", "produto", "serviço", "polo industrial",
            "empreendedor", "startup", "negócio", "renda",
            "salário mínimo", "crédito", "financiamento", "banco", "dívida",
            "imposto", "tributo", "icms", "receita", "arrecadação",
            "auxílio", "benefício social", "bolsa família", "bpc", "cad único",
            "sine", "vaga de emprego", "contratação", "demissão", "rescisão",
            "faturamento", "lucro", "prejuízo", "falência", "concordata",
            "loja", "supermercado", "shopping", "preço", "custo de vida",
            "turismo econômico", "feira", "mercado municipal", "produtor rural",
            "agronegócio", "pesca", "agricultura familiar"
        ],
    },
    {
        "name": "Educação",
        "slug": "educacao",
        "color": "#8e44ad",
        "display_order": 6,
        "keywords": [
            "educação", "escola", "aluno", "professor", "universidade", "uea", "ufam",
            "enem", "vestibular", "graduação", "pós-graduação", "pesquisa", "ciência",
            "secretaria de educação", "semed", "creche", "ensino fundamental",
            "ensino médio", "bolsa", "fies", "prouni", "alfabetização",
            "estudante", "acadêmico", "acadêmica", "ifam", "instituto federal",
            "escola pública", "escola particular", "colégio", "turma", "aula",
            "aprovação", "reprovação", "evasão escolar", "analfabetismo",
            "educação infantil", "berçário", "pré-escola", "eja",
            "projeto pedagógico", "currículo", "formação", "capacitação",
            "bolsista", "monitoria", "iniciação científica", "tcc",
            "congresso acadêmico", "seminário científico", "publicação científica"
        ],
    },
    {
        "name": "Infraestrutura e Mobilidade",
        "slug": "infraestrutura-mobilidade",
        "color": "#7f8c8d",
        "display_order": 7,
        "keywords": [
            "trânsito", "obra", "ônibus", "transporte", "ponte", "saneamento",
            "asfalto", "pavimentação", "semob", "manaustrans", "congestionamento",
            "energia elétrica", "água", "esgoto", "manaus ambiental",
            "brt", "via", "rodovia", "aeroporto", "porto",
            "calçada", "ciclovia", "iluminação pública", "poste",
            "abastecimento de água", "falta de água", "falta de luz", "blecaute",
            "interrupção", "manutenção", "reforma", "reconstrução", "demolição",
            "habitação", "moradia", "conjunto habitacional", "minha casa minha vida",
            "urbanização", "regularização fundiária", "reassentamento",
            "bueiro", "alagamento", "drenagem", "canal", "galeria",
            "semulsp", "implanturb", "detran", "vias expressas",
            "teleférico", "hidrovia", "balsa", "ferry", "lancha"
        ],
    },
    {
        "name": "Cultura e Lazer",
        "slug": "cultura-lazer",
        "color": "#e67e22",
        "display_order": 8,
        "keywords": [
            "cultura", "festival", "teatro", "show", "turismo", "festa junina",
            "festival de parintins", "boi bumbá", "folclore", "museu", "cinema",
            "arte", "exposição", "gastronomia", "evento", "carnaval", "réveillon",
            "parque", "lazer", "música", "dança",
            "teatro amazonas", "espetáculo", "peça teatral", "ópera", "ballet",
            "artista", "cantor", "banda", "forró", "funk", "pagode", "axé",
            "literatura", "livro", "escritor", "biblioteca", "leitura",
            "fotografia", "pintura", "escultura", "artesanato", "patrimônio",
            "festa popular", "arraial", "quadrilha", "bumba meu boi",
            "parque do mindú", "bosque da ciência", "jardim botânico",
            "praia", "balneário", "piscina", "recreação", "passeio",
            "restaurante", "bar", "culinária", "prato típico", "tacacá",
            "religiosa", "festejo", "procissão", "quermesse"
        ],
    },
    {
        "name": "Esporte",
        "slug": "esporte",
        "color": "#1abc9c",
        "display_order": 9,
        "keywords": [
            "esporte", "futebol", "amazonas fc", "nacional fc", "fast clube",
            "são raimundo", "rio negro clube",
            "campeonato", "atleta", "competição", "jogos", "olimpíada", "natação",
            "basquete", "vôlei", "maratona", "arena da amazônia", "goleiro",
            "técnico", "jogo", "partida", "gol", "copa",
            "campeonato brasileiro", "série a", "série b", "série c",
            "campeonato amazonense", "estadual", "copa do brasil",
            "treinamento", "treino", "preparação física", "lesão",
            "transferência", "contratação", "reforço", "torcida", "torcedor",
            "esporte amador", "escolinha", "peneira", "categoria de base",
            "judô", "karatê", "boxe", "MMA", "luta", "ciclismo",
            "corrida de rua", "triathlon", "remo", "canoagem", "surfe",
            "tênis", "golfe", "hipismo", "atletismo", "ginástica"
        ],
    },
    {
        "name": "Tecnologia e Inovação",
        "slug": "tecnologia-inovacao",
        "color": "#3498db",
        "display_order": 10,
        "keywords": [
            "tecnologia", "inovação", "aplicativo", "digital", "inteligência artificial",
            "software", "startup", "ciência de dados", "programação",
            "internet", "5g", "blockchain", "robótica", "automação", "hackathon",
            "fapeam", "cnpq", "pesquisa tecnológica", "desenvolvimento de software",
            "transformação digital", "inteligência de dados",
            "smartphone", "celular", "app", "plataforma digital", "e-commerce",
            "cibersegurança", "hacker", "golpe digital", "fraude online",
            "computador", "servidor", "nuvem", "cloud", "dados",
            "telemedicina", "educação digital", "governo digital",
            "inclusão digital", "conectividade", "wifi", "fibra óptica",
            "satélite", "starlink", "4g", "rede móvel"
        ],
    },
    {
        "name": "Justiça e Direito",
        "slug": "justica-direito",
        "color": "#6c3483",
        "display_order": 11,
        "keywords": [
            "tribunal", "tjam", "stj", "stf", "trf", "tce", "mpam", "ministério público",
            "juiz", "juíza", "promotor", "promotora", "defensor", "defensoria",
            "advogado", "advogada", "processo judicial", "ação judicial",
            "sentença", "condenação", "absolvição", "julgamento", "audiência",
            "habeas corpus", "liminar", "recurso", "apelação", "decisão judicial",
            "vara", "fórum", "comarca", "juizado especial",
            "preso", "prisão preventiva", "prisão domiciliar", "liberdade",
            "extradição", "mandado de prisão", "operação judicial",
            "improbidade administrativa", "peculato", "desvio de verbas",
            "lava jato", "investigação", "inquérito policial", "denúncia",
            "vítima", "réu", "acusado", "testemunho", "perícia",
            "conciliação", "mediação", "acordo judicial", "indenização",
            "dano moral", "pensão alimentícia", "guarda", "adoção", "divórcio",
            "direito do consumidor", "procon", "multa judicial"
        ],
    },
    {
        "name": "Social e Cidadania",
        "slug": "social-cidadania",
        "color": "#e91e63",
        "display_order": 12,
        "keywords": [
            "assistência social", "cras", "creas", "família", "criança",
            "idoso", "pessoa idosa", "adolescente", "jovem", "juventude",
            "comunidade", "bairro", "morador", "vizinhança",
            "voluntário", "doação", "campanha solidária", "ação social",
            "vulnerabilidade", "pobreza", "exclusão social", "desigualdade",
            "habitação social", "sem teto", "sem casa", "ocupação",
            "mulher", "gênero", "feminismo", "violência contra a mulher",
            "lgbtqia", "diversidade", "inclusão", "preconceito", "discriminação",
            "pessoa com deficiência", "acessibilidade", "inclusão social",
            "indígena", "quilombola", "ribeirinho", "comunidade tradicional",
            "migrante", "refugiado", "imigrante",
            "direitos humanos", "cidadania", "participação popular",
            "conselho municipal", "conferência", "audiência pública",
            "proteção animal", "abandono animal", "maus tratos",
            "criança desaparecida", "menor abandonado", "abrigo"
        ],
    },
    {
        "name": "Outros",
        "slug": "outros",
        "color": "#95a5a6",
        "display_order": 13,
        "keywords": [],
    },
]

SOURCES = [
    # Portais locais de Manaus
    {"name": "A Crítica",            "url": "https://www.acritica.com",          "rss_url": "https://www.acritica.com/feed",                                 "type": "portal", "active": False},
    {"name": "Em Tempo",             "url": "https://emtempo.com.br",            "rss_url": "https://emtempo.com.br/feed",                                   "type": "portal"},
    {"name": "D24am",                "url": "https://www.d24am.com",             "rss_url": "https://www.d24am.com/feed",                                    "type": "portal",  "active": False},
    {"name": "Portal do Holanda",    "url": "https://portaldoholanda.com.br",    "rss_url": "https://portaldoholanda.com.br/feed",                           "type": "portal"},
    {"name": "Amazonas Atual",       "url": "https://amazonasatual.com.br",      "rss_url": "https://amazonasatual.com.br/feed/",                            "type": "portal"},
    {"name": "A Gazeta do Amazonas", "url": "https://agazetadoamazonas.com",     "rss_url": "https://agazetadoamazonas.com/feed",                            "type": "portal", "active": False},
    {"name": "Amazonas 1",           "url": "https://amazonas1.com.br",          "rss_url": "https://amazonas1.com.br/feed",                                 "type": "portal"},
    {"name": "AM POST",              "url": "https://ampost.com.br",             "rss_url": "https://ampost.com.br/feed",                                    "type": "portal"},
    {"name": "Norte em Foco",        "url": "https://norteemfoco.com.br",        "rss_url": "https://norteemfoco.com.br/feed",                               "type": "portal"},
    {"name": "Correio da Amazônia",  "url": "https://correiodaamazonia.com",     "rss_url": "https://correiodaamazonia.com/feed",                            "type": "portal"},
    {"name": "Rede Amazônica",       "url": "https://redeamazonica.com.br",      "rss_url": "https://redeamazonica.com.br/feed",                             "type": "portal", "active": False},
    # Blogs
    {"name": "Blog do Holanda",      "url": "https://blogdoholanda.com",         "rss_url": "https://blogdoholanda.com/feed",                                "type": "blog"},
    {"name": "Blog do Hiel Levy",    "url": "https://blogdohiellevy.com.br",     "rss_url": "https://blogdohiellevy.com.br/feed",                            "type": "blog"},
    {"name": "Portal Marcos Santos", "url": "https://portalmarcossantos.com.br", "rss_url": "https://portalmarcossantos.com.br/feed",                        "type": "blog"},
    {"name": "Blog do Pávulo",       "url": "https://blogdopavulo.com",          "rss_url": "https://blogdopavulo.com/feed/",                                "type": "blog"},
    {"name": "Blog do Botelho",      "url": "https://blogdobotelho.com",         "rss_url": "https://blogdobotelho.com/feed/",                               "type": "blog"},
    {"name": "Blog do Jucem",        "url": "https://www.blogdojucem.com",       "rss_url": "https://www.blogdojucem.com/feed",                              "type": "blog",   "active": False},
    {"name": "I9 Brasil",            "url": "https://i9brasil.com.br",           "rss_url": "https://i9brasil.com.br/feed",                                  "type": "portal"},
    {"name": "Fato Amazônico",        "url": "https://fatoamazonico.com",              "rss_url": "https://fatoamazonico.com/feed",                                     "type": "portal"},
    {"name": "Radar Amazônico",       "url": "https://radaramazonico.com.br",          "rss_url": "https://radaramazonico.com.br/feed",                                 "type": "portal"},
    {"name": "BNC Amazonas",          "url": "https://bncamazonas.com.br",             "rss_url": "https://bncamazonas.com.br/feed",                                    "type": "portal"},
    {"name": "Realtime",              "url": "https://realtime1.com.br",               "rss_url": "https://realtime1.com.br/feed",                                      "type": "portal"},
    {"name": "Portal Único",          "url": "https://portalunico.com",                "rss_url": "https://portalunico.com/feed",                                       "type": "portal"},
    {"name": "Portal Manaus Alerta",  "url": "https://portalmanausalerta.com.br",      "rss_url": "https://portalmanausalerta.com.br/feed",                             "type": "portal"},
    {"name": "CM7 Brasil",            "url": "https://www.cm7brasil.com",              "rss_url": "https://www.cm7brasil.com/feed",                                     "type": "portal"},
    {"name": "Manaus 360",            "url": "https://manaus360.com",                  "rss_url": "https://manaus360.com/feed",                                         "type": "portal"},
    {"name": "Vocativo",              "url": "https://vocativo.com",                   "rss_url": "https://vocativo.com/feed",                                          "type": "portal"},
    {"name": "Chumbo Grosso Manaus",  "url": "https://chumbogrossomanaus.com.br",      "rss_url": "https://chumbogrossomanaus.com.br/feed",                             "type": "portal"},
    {"name": "Tribuna Amazonas",      "url": "https://tribunaamazonas.com.br",         "rss_url": "https://tribunaamazonas.com.br/feed",                               "type": "portal"},
    {"name": "Tribuna de Manaus",     "url": "https://tribunademanaus.com.br",         "rss_url": "https://tribunademanaus.com.br/feed",                               "type": "portal"},
    {"name": "Tribuna do Amazonas",   "url": "https://tribunadoam.com",                "rss_url": "https://tribunadoam.com/feed",                                       "type": "portal"},
    {"name": "Igarapé News",          "url": "https://igarapenews.com.br",             "rss_url": "https://igarapenews.com.br/feed",                                    "type": "portal"},
    {"name": "Rios de Notícias",      "url": "https://www.riosdenoticias.com.br",      "rss_url": "https://www.riosdenoticias.com.br/feed",                             "type": "portal"},
    {"name": "Portal do Amazonas",    "url": "https://portaldoamazonas.com.br",        "rss_url": "https://portaldoamazonas.com.br/feed",                              "type": "portal", "active": False},
    {"name": "Portal da Floresta",    "url": "https://portaldafloresta.com.br",        "rss_url": "https://portaldafloresta.com.br/feed",                              "type": "portal"},
    {"name": "Portal do Zacarias",    "url": "https://portaldozacarias.com.br",        "rss_url": "https://portaldozacarias.com.br/feed",                              "type": "portal", "active": False},
    {"name": "Portal Norte",          "url": "https://portalnorte.com.br",             "rss_url": "https://portalnorte.com.br/feed",                                   "type": "portal",  "active": False},
    {"name": "Portal Manaus Notícias","url": "https://www.portalmanausnoticias.com.br","rss_url": "https://www.portalmanausnoticias.com.br/feed",                       "type": "portal", "active": False},
    {"name": "Portal O Poder",        "url": "https://portalopoder.com.br",            "rss_url": "https://portalopoder.com.br/feed",                                   "type": "portal"},
    {"name": "Agência Amazonas",      "url": "https://www.agenciaamazonas.am.gov.br",  "rss_url": "https://www.agenciaamazonas.am.gov.br/feed",                         "type": "portal"},
    # Canais do YouTube (rss_url com channel_id hardcoded para evitar resolução em runtime)
    {"name": "TV A Crítica (YouTube)",      "url": "https://www.youtube.com/channel/UCnLSKfHkgZ6ujEYCO9jq7Sw", "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCnLSKfHkgZ6ujEYCO9jq7Sw", "type": "youtube"},
    {"name": "TV Norte Amazonas (YouTube)", "url": "https://www.youtube.com/channel/UC4WNZYa1d0HVzdVWlfJEGjw", "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC4WNZYa1d0HVzdVWlfJEGjw", "type": "youtube"},
    {"name": "Jovem Pan Manaus (YouTube)",  "url": "https://www.youtube.com/channel/UCnzSEPHQ2zoaYIFo4BIv0ow", "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCnzSEPHQ2zoaYIFo4BIv0ow", "type": "youtube"},
    {"name": "Portal do Holanda (YouTube)", "url": "https://www.youtube.com/channel/UCH_iB5NZNUDT3BITtcFPFQw", "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCH_iB5NZNUDT3BITtcFPFQw", "type": "youtube"},
    {"name": "Rede Amazônica (YouTube)",    "url": "https://www.youtube.com/channel/UCIZiuY6rbu3myUQ39vYsqRw", "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCIZiuY6rbu3myUQ39vYsqRw", "type": "youtube"},
    {"name": "TV CM7 (YouTube)",            "url": "https://www.youtube.com/channel/UC880szznksA04nYdg2G-3eQ", "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UC880szznksA04nYdg2G-3eQ", "type": "youtube"},
    {"name": "Record Manaus (YouTube)",     "url": "https://www.youtube.com/channel/UClpkHFE0rwJOsA_Rzk7OK8A", "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UClpkHFE0rwJOsA_Rzk7OK8A", "type": "youtube"},
    {"name": "Band Amazonas (YouTube)",     "url": "https://www.youtube.com/channel/UCJVYVZTlMgiytKA9hjZ3ioA", "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCJVYVZTlMgiytKA9hjZ3ioA", "type": "youtube"},
    {"name": "Amazonas Atual (YouTube)",    "url": "https://www.youtube.com/channel/UCg8t9F8LXjaOURUBnMZgb5g", "rss_url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCg8t9F8LXjaOURUBnMZgb5g", "type": "youtube"},
    # Universidades e institutos de pesquisa
    {"name": "UFAM",    "url": "https://www.ufam.edu.br",    "rss_url": "https://www.ufam.edu.br/noticias.feed?type=rss",                        "type": "portal"},
    {"name": "UEA",     "url": "https://www.uea.edu.br",     "rss_url": "http://www.uea.edu.br/index.php/feed/",                                "type": "portal", "active": False},
    {"name": "INPA",    "url": "https://www.gov.br/inpa",    "rss_url": "https://www.gov.br/inpa/pt-br/assuntos/noticias/@@search?format=rss",    "type": "portal", "active": False},
    {"name": "UniNorte","url": "https://www.uninorte.com.br","rss_url": "https://www.uninorte.com.br/feed/",                                      "type": "portal"},
    # Cobertura regional e ambiental
    {"name": "G1 Amazonas",          "url": "https://g1.globo.com/am/amazonas",  "rss_url": "https://g1.globo.com/rss/g1/am/amazonas/",                      "type": "portal"},
    {"name": "Agência Brasil",       "url": "https://agenciabrasil.ebc.com.br",  "rss_url": "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml",  "type": "portal"},
    {"name": "Mongabay Brasil",      "url": "https://brasil.mongabay.com",       "rss_url": "https://brasil.mongabay.com/feed/",                             "type": "portal"},
    # Novos portais locais
    {"name": "Canal 92",             "url": "https://canal92am.com",             "rss_url": "https://canal92am.com/feed/",                                   "type": "portal"},
    {"name": "Portal Regional AM",   "url": "https://portalregionalam.com.br",   "rss_url": "https://portalregionalam.com.br/feed/",                         "type": "portal"},
    {"name": "Portal Tambaqui",      "url": "https://portaltambaqui.com.br",     "rss_url": "https://portaltambaqui.com.br/feed/",                           "type": "portal",  "active": False},
    {"name": "Portal AM 24h",        "url": "https://portalam24h.com",           "rss_url": "https://www.portalam24h.com/feed/",                             "type": "portal"},
    {"name": "Portal do Amazonas AM","url": "https://portaldoamazonas.com",      "rss_url": "https://portaldoamazonas.com/feed/",                            "type": "portal"},
    {"name": "Comunica AM",          "url": "https://comunicaam.com.br",         "rss_url": "https://comunicaam.com.br/feed",                                "type": "portal"},
    {"name": "Portal Amazôn Online", "url": "https://portalamazononline.com.br", "rss_url": "https://portalamazononline.com.br/feed/",                       "type": "portal"},
    {"name": "No Ar Portal",         "url": "https://noarportal.com.br",         "rss_url": "https://noarportal.com.br/feed/",                               "type": "portal"},
    {"name": "Menezes Virtual Eye",  "url": "https://menezesvirtualeye.com",     "rss_url": "https://menezesvirtualeye.com/feed/",                           "type": "blog"},
    {"name": "Portal R5",            "url": "https://portalr5.com.br",           "rss_url": "https://portalr5.com.br/?feed=rss2",                            "type": "portal"},
    {"name": "Nosso Show AM",        "url": "https://nossoshowam.com",           "rss_url": "https://nossoshowam.com/feed",                                  "type": "portal"},
    {"name": "TechAmazonia",         "url": "https://techamazonia.com",          "rss_url": "https://techamazonia.com/feed",                                 "type": "portal"},
    {"name": "Amazonas365",          "url": "https://amazonas365.com.br",        "rss_url": "https://amazonas365.com.br/feed/",                              "type": "portal"},
    {"name": "Portal Web Manaus",    "url": "https://portalwebmanaus.com",       "rss_url": "https://portalwebmanaus.com/feed/",                             "type": "portal"},
    {"name": "Portal Amazônia",      "url": "https://portalamazonia.com",        "rss_url": "https://portalamazonia.com/feed/",                              "type": "portal"},
    # Órgãos governamentais do Amazonas
    {"name": "Governo do Amazonas",  "url": "https://www.amazonas.am.gov.br",    "rss_url": "https://www.amazonas.am.gov.br/feed/",                          "type": "portal", "active": False},
    {"name": "ALEAM",                "url": "https://www.aleam.gov.br",          "rss_url": "https://www.aleam.gov.br/feed/",                                "type": "portal"},
    {"name": "IPAAM",                "url": "https://www.ipaam.am.gov.br",       "rss_url": "https://www.ipaam.am.gov.br/feed/",                             "type": "portal"},
    {"name": "SSP-AM",               "url": "https://www.ssp.am.gov.br",         "rss_url": "https://www.ssp.am.gov.br/feed/",                               "type": "portal"},
    {"name": "DETRAN-AM",            "url": "https://www.detran.am.gov.br",      "rss_url": "https://www.detran.am.gov.br/feed/",                            "type": "portal"},
    {"name": "Cultura AM",           "url": "https://cultura.am.gov.br",         "rss_url": "https://www.cultura.am.gov.br/feed/",                           "type": "portal", "active": False},
    {"name": "Prefeitura de Manaus", "url": "https://www.manaus.am.gov.br",      "rss_url": "https://www.manaus.am.gov.br/feed/",                            "type": "portal"},
    {"name": "PGE-AM",              "url": "https://www.pge.am.gov.br",         "rss_url": "https://www.pge.am.gov.br/feed/",                               "type": "portal"},
    {"name": "Amazonastur",         "url": "https://www.amazonastur.am.gov.br", "rss_url": "https://www.amazonastur.am.gov.br/feed/",                        "type": "portal"},
    {"name": "ARSEPAM",             "url": "https://www.arsepam.am.gov.br",     "rss_url": "https://www.arsepam.am.gov.br/feed/",                            "type": "portal"},
    {"name": "TRE-AM",              "url": "https://www.tre-am.jus.br",         "rss_url": "https://www.tre-am.jus.br/rss",                                 "type": "portal"},
]


def seed_all():
    session = get_session()
    try:
        for t in TOPICS:
            existing = session.query(Topic).filter_by(slug=t["slug"]).first()
            if existing:
                existing.keywords = t["keywords"]
                existing.display_order = t["display_order"]
            else:
                session.add(Topic(**t))

        for s in SOURCES:
            existing = session.query(Source).filter_by(url=s["url"]).first()
            if existing:
                existing.active = s.get("active", True)
                existing.rss_url = s.get("rss_url")
            else:
                session.add(Source(**s))

        session.commit()
        print("Seeds aplicados com sucesso.")
    finally:
        session.close()
