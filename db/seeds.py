from db.connection import get_session
from db.models import Source, Topic

TOPICS = [
    {
        "name": "Saúde",
        "slug": "saude",
        "color": "#e74c3c",
        "display_order": 1,
        "keywords": [
            "saúde", "hospital", "ubs", "sus", "médico", "enfermeiro", "dengue",
            "vacina", "vacinação", "epidemia", "pandemia", "doença", "paciente",
            "internação", "pronto-socorro", "fhaj", "fcecon", "hps", "caps",
            "secretaria de saúde", "semsa"
        ],
    },
    {
        "name": "Segurança Pública",
        "slug": "seguranca-publica",
        "color": "#c0392b",
        "display_order": 2,
        "keywords": [
            "crime", "polícia", "homicídio", "assassinato", "tráfico", "bope",
            "pm", "policia militar", "policia civil", "ssp", "segurança pública",
            "preso", "prisão", "furto", "roubo", "violência", "operação policial",
            "feminicídio", "latrocínio", "delegacia", "penal"
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
            "poluição", "resíduo", "lixo", "manancial", "igarapé"
        ],
    },
    {
        "name": "Política e Governo",
        "slug": "politica-governo",
        "color": "#2980b9",
        "display_order": 4,
        "keywords": [
            "prefeito", "governador", "vereador", "deputado", "senador", "câmara",
            "assembleia legislativa", "eleição", "partido", "política", "governo",
            "prefeitura", "estado do amazonas", "semcom", "licitação", "concurso público",
            "decreto", "lei municipal", "gestão pública", "david almeida", "wilson lima"
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
            "empreendedor", "startup", "negócio", "renda"
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
            "ensino médio", "bolsa", "fies", "prouni", "alfabetização"
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
            "semsa", "energia elétrica", "água", "esgoto", "manaus ambiental",
            "brt", "via", "rodovia", "aeroporto", "porto"
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
            "parque", "lazer", "música", "dança"
        ],
    },
    {
        "name": "Esporte",
        "slug": "esporte",
        "color": "#1abc9c",
        "display_order": 9,
        "keywords": [
            "esporte", "futebol", "amazonas fc", "nacional", "fast clube",
            "campeonato", "atleta", "competição", "jogos", "olimpíada", "natação",
            "basquete", "vôlei", "maratona", "arena da amazônia", "goleiro",
            "técnico", "jogo", "partida", "gol", "copa"
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
            "transformação digital", "inteligência de dados"
        ],
    },
    {
        "name": "Outros",
        "slug": "outros",
        "color": "#95a5a6",
        "display_order": 11,
        "keywords": [],
    },
]

SOURCES = [
    # Portais locais de Manaus
    {"name": "A Crítica",            "url": "https://www.acritica.com",          "rss_url": "https://www.acritica.com/feed",                                 "type": "portal"},
    {"name": "Em Tempo",             "url": "https://emtempo.com.br",            "rss_url": "https://emtempo.com.br/feed",                                   "type": "portal"},
    {"name": "D24am",                "url": "https://www.d24am.com",             "rss_url": "https://www.d24am.com/feed",                                    "type": "portal"},
    {"name": "Portal do Holanda",    "url": "https://portaldoholanda.com.br",    "rss_url": "https://portaldoholanda.com.br/feed",                           "type": "portal"},
    {"name": "Amazonas Atual",       "url": "https://amazonasatual.com.br",      "rss_url": "https://amazonasatual.com.br/feed",                             "type": "portal"},
    {"name": "A Gazeta do Amazonas", "url": "https://agazetadoamazonas.com",     "rss_url": "https://agazetadoamazonas.com/feed",                            "type": "portal"},
    {"name": "Amazonas 1",           "url": "https://amazonas1.com.br",          "rss_url": "https://amazonas1.com.br/feed",                                 "type": "portal"},
    {"name": "AM POST",              "url": "https://ampost.com.br",             "rss_url": "https://ampost.com.br/feed",                                    "type": "portal"},
    {"name": "Norte em Foco",        "url": "https://norteemfoco.com.br",        "rss_url": "https://norteemfoco.com.br/feed",                               "type": "portal"},
    {"name": "Correio da Amazônia",  "url": "https://correiodaamazonia.com",     "rss_url": "https://correiodaamazonia.com/feed",                            "type": "portal"},
    {"name": "Rede Amazônica",       "url": "https://redeamazonica.com.br",      "rss_url": "https://redeamazonica.com.br/feed",                             "type": "portal"},
    # Blogs
    {"name": "Blog do Holanda",      "url": "https://blogdoholanda.com",         "rss_url": "https://blogdoholanda.com/feed",                                "type": "blog"},
    {"name": "Blog do Hiel Levy",    "url": "https://blogdohiellevy.com.br",     "rss_url": "https://blogdohiellevy.com.br/feed",                            "type": "blog"},
    {"name": "Portal Marcos Santos", "url": "https://portalmarcossantos.com.br", "rss_url": "https://portalmarcossantos.com.br/feed",                        "type": "blog"},
    {"name": "I9 Brasil",            "url": "https://i9brasil.com.br",           "rss_url": "https://i9brasil.com.br/feed",                                  "type": "portal"},
    {"name": "Fato Amazônico",       "url": "https://fatoamazonico.com",         "rss_url": "https://fatoamazonico.com/feed",                                "type": "portal"},
    {"name": "Radar Amazônico",      "url": "https://radaramazonico.com.br",     "rss_url": "https://radaramazonico.com.br/feed",                            "type": "portal"},
    {"name": "BNC Amazonas",         "url": "https://bncamazonas.com.br",        "rss_url": "https://bncamazonas.com.br/feed",                               "type": "portal"},
    {"name": "Realtime",             "url": "https://realtime1.com.br",          "rss_url": "https://realtime1.com.br/feed",                                 "type": "portal"},
    {"name": "Portal Único",         "url": "https://portalunico.com",           "rss_url": "https://portalunico.com/feed",                                  "type": "portal"},
    # Cobertura regional e ambiental
    {"name": "G1 Amazonas",          "url": "https://g1.globo.com/am/amazonas",  "rss_url": "https://g1.globo.com/rss/g1/am/amazonas/",                      "type": "portal"},
    {"name": "Agência Brasil",       "url": "https://agenciabrasil.ebc.com.br",  "rss_url": "https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml",  "type": "portal"},
    {"name": "Mongabay Brasil",      "url": "https://brasil.mongabay.com",       "rss_url": "https://brasil.mongabay.com/feed/",                             "type": "portal"},
]


def seed_all():
    session = get_session()
    try:
        for t in TOPICS:
            if not session.query(Topic).filter_by(slug=t["slug"]).first():
                session.add(Topic(**t))

        for s in SOURCES:
            if not session.query(Source).filter_by(url=s["url"]).first():
                session.add(Source(**s))

        session.commit()
        print("Seeds aplicados com sucesso.")
    finally:
        session.close()
