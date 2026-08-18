import os
import re
import unicodedata
from db.connection import get_session
from db.models import Article

LOCAL_TERMS = {
    "cidade_estado": [
        "manaus", "amazonas", "manauara", "manauaras", "manauense",
        "manauenses", "capital amazonense", "capital do amazonas",
        "estado do amazonas", "interior do amazonas",
        "região metropolitana de manaus", "rmm", "grande manaus",
        "amazonia ocidental", "amazônia ocidental", "amazônia brasileira",
        "amazonia brasileira", "alto solimões", "baixo amazonas",
        "médio amazonas", "calha do madeira", "calha do purus",
        "calha do juruá", "calha do rio negro", "sul do amazonas",
    ],
    "zonas_de_manaus": [
        "zona norte", "zona sul", "zona leste", "zona oeste",
        "zona centro-sul", "zona centro-oeste", "zona rural de manaus",
        "área rural de manaus", "area rural de manaus",
        "distrito industrial", "distrito industrial de manaus",
        "polo industrial de manaus", "pim",
    ],
    "bairros_de_manaus": [
        # Bug 2: removidos bairros cujo nome colide com palavras comuns ou com
        # lugares de outros estados (geravam falso positivo):
        #   centro, flores, planalto, alvorada, glória, raiz, chapada, betânia,
        #   "da paz", redenção, "cidade de deus" (RJ), petrópolis (RJ),
        #   "são francisco", "são josé".
        # Notícias que só tenham esses termos caem no fallback do LLM.
        "adrianópolis", "adrianopolis", "aleixo",
        "armando mendes", "cachoeirinha", "cidade nova",
        "colônia antônio aleixo", "colonia antonio aleixo",
        "colônia oliveira machado", "colonia oliveira machado",
        "compensa", "coroado", "crespo", "dom pedro",
        "educandos", "gilberto mestrinho",
        "japiim", "jorge teixeira", "lírio do vale", "lirio do vale",
        "mauazinho", "monte das oliveiras", "morro da liberdade",
        "nova cidade", "nova esperança", "nova esperanca", "novo aleixo",
        "parque 10", "parque dez",
        "ponta negra", "praça 14", "praca 14", "praça 14 de janeiro",
        "praca 14 de janeiro", "presidente vargas", "puraquequara",
        "santa etelvina", "santa luzia",
        "santo agostinho", "santo antônio", "santo antonio",
        "são geraldo", "sao geraldo", "são jorge", "sao jorge",
        "são josé operário", "sao jose operario", "tancredo neves",
        "tarumã", "taruma", "tarumã-açu", "taruma-acu",
        "vila buriti", "zumbi", "zumbi dos palmares",
    ],
    "comunidades_conjuntos_e_loteamentos": [
        "viver melhor", "viver melhor 1", "viver melhor 2",
        "conjunto cidadão", "conjunto cidadao", "conjunto ajuricaba",
        "conjunto eldorado", "conjunto hiléia", "conjunto hileia",
        "conjunto vieiralves", "vieiralves", "conjunto beija-flor",
        "conjunto nova república", "conjunto nova republica",
        "conjunto habitacional manauara", "comunidade parque das tribos",
        "parque das tribos", "comunidade sharp", "comunidade da sharp",
        "comunidade coliseu", "comunidade jesus me deu",
        "comunidade monte horebe", "monte horebe",
        "comunidade parque são pedro", "parque são pedro",
        "parque sao pedro", "comunidade bela vista",
        "comunidade união da vitória", "uniao da vitoria",
        "comunidade ribeirinha", "comunidades ribeirinhas",
    ],
    "municipios_do_amazonas": [
        "alvarães", "alvaraes", "amaturá", "amatura", "anamã", "anama",
        "anori", "apuí", "apui", "atalaia do norte", "autazes",
        "barcelos", "barreirinha", "benjamin constant", "beruri",
        "boa vista do ramos", "boca do acre", "borba", "caapiranga",
        "canutama", "carauari", "careiro", "careiro da várzea",
        "careiro da varzea", "coari", "codajás", "codajas",
        "eirunepé", "eirunepe", "envira", "fonte boa", "guajará",
        "guajara", "humaitá", "humaita", "ipixuna", "iranduba",
        "itacoatiara", "itamarati", "itapiranga", "japurá", "japura",
        "juruá", "jurua", "jutaí", "jutai", "lábrea", "labrea",
        "manacapuru", "manaquiri", "manicoré", "manicore", "maraã",
        "maraa", "maués", "maues", "nhamundá", "nhamunda",
        "nova olinda do norte", "nova aripuanã", "nova aripuana",
        "parintins", "pauini", "presidente figueiredo",
        "rio preto da eva", "santa isabel do rio negro",
        "santo antônio do içá", "santo antonio do ica",
        "são gabriel da cachoeira", "sao gabriel da cachoeira",
        "são paulo de olivença", "sao paulo de olivenca",
        "são sebastião do uatumã", "sao sebastiao do uatuma",
        "silves", "tabatinga", "tapauá", "tapaua", "tefé", "tefe",
        "tonantins", "uarini", "urucará", "urucara", "urucurituba",
    ],
    "rios_geografia_e_ambiente": [
        "rio amazonas", "rio negro", "rio solimões", "rio solimoes",
        "rio madeira", "rio purus", "rio juruá", "rio jurua",
        "rio japurá", "rio japura", "rio uatumã", "rio uatuma",
        "rio tarumã", "rio taruma", "rio tarumã-açu", "rio taruma-acu",
        "igarapé", "igarape", "igarapés", "igarapes",
        "igarapé do mindu", "igarape do mindu",
        "igarapé do quarenta", "igarape do quarenta",
        "igarapé do educandos", "igarape do educandos",
        "igarapé do passarinho", "igarape do passarinho",
        "encontro das águas", "encontro das aguas",
        "arquipélago de anavilhanas", "arquipelago de anavilhanas",
        "anavilhanas", "ilha do careiro", "lago janauari",
        "lago de janeiro", "praia da ponta negra",
        "praia do tupé", "praia do tupe", "catalão", "catalao",
        "reserva ducke", "musa", "museu da amazônia",
        "museu da amazonia", "jardim botânico de manaus",
        "jardim botanico de manaus", "parque do mindu",
        "parque sumaúma", "parque sumauma",
        "parque estadual sumaúma", "parque estadual sumauma",
        "floresta amazônica", "floresta amazonica",
        "cheia dos rios", "vazante dos rios", "seca no amazonas",
        "estiagem no amazonas", "fumaça em manaus", "fumaca em manaus",
        "queimadas no amazonas",
    ],
    "infraestrutura_pontos_referencia": [
        "arena da amazônia", "arena da amazonia", "ponte rio negro",
        "ponte jornalista phelippe daou", "aeroporto eduardo gomes",
        "aeroporto internacional eduardo gomes", "porto de manaus",
        "porto da ceasa", "porto do são raimundo",
        "porto do sao raimundo", "mercado adolpho lisboa",
        "mercadão", "mercadao", "teatro amazonas",
        "largo de são sebastião", "largo de sao sebastiao",
        "palácio rio negro", "palacio rio negro",
        "palácio da justiça", "palacio da justica",
        "palácio do governo", "palacio do governo",
        "centro histórico de manaus", "centro historico de manaus",
        "relógio municipal", "relogio municipal",
        "alfândega de manaus", "alfandega de manaus",
        "rodoviária de manaus", "rodoviaria de manaus",
        "terminal rodoviário de manaus", "terminal rodoviario de manaus",
        "terminal de integração", "terminal de integracao",
        "terminal 1", "terminal 2", "terminal 3", "terminal 4",
        "terminal 5", "t1", "t2", "t3", "t4", "t5",
        "complexo viário", "complexo viario",
        "avenida torquato tapajós", "avenida torquato tapajos",
        "avenida constantino nery", "avenida das torres",
        "avenida brasil", "avenida djalma batista",
        "avenida ephigênio salles", "avenida efigenio salles",
        "avenida andré araújo", "avenida andre araujo",
        "avenida autaz mirim", "grande circular",
        "avenida grande circular", "avenida coronel teixeira",
        "avenida do turismo", "avenida sete de setembro",
        "avenida getúlio vargas", "avenida getulio vargas",
        "avenida mario ypiranga", "avenida mário ypiranga",
        "avenida recife", "avenida nilton lins",
        "shopping manauara", "manauara shopping",
        "shopping sumaúma", "shopping sumauma",
        "sumaúma park shopping", "sumauma park shopping",
        "boulevard shopping", "amazonas shopping",
        "shopping ponta negra", "manaus plaza shopping",
        "studio 5", "studio 5 centro de convenções",
        "studio 5 centro de convencoes",
        "centro de convenções do amazonas",
        "centro de convencoes do amazonas", "vasco vasques",
    ],
    "instituicoes_orgaos": [
        "prefeitura de manaus", "governo do amazonas",
        "governo do estado do amazonas", "câmara municipal de manaus",
        "camara municipal de manaus", "cmm",
        "assembleia legislativa do amazonas", "aleam",
        "tribunal de justiça do amazonas",
        "tribunal de justica do amazonas", "tjam",
        "tribunal de contas do amazonas", "tce-am", "tce/am",
        "tce amazonas", "ministério público do amazonas",
        "ministerio publico do amazonas", "mpam",
        "defensoria pública do amazonas",
        "defensoria publica do amazonas", "dpe-am", "dpe/am",
        "procuradoria geral do estado do amazonas", "pge-am", "pge/am",
        "ufam", "universidade federal do amazonas", "uea",
        "universidade do estado do amazonas", "ifam",
        "instituto federal do amazonas", "inpa",
        "instituto nacional de pesquisas da amazônia",
        "instituto nacional de pesquisas da amazonia", "fapeam",
        "fcecon", "fundação cecon", "fundacao cecon", "fhaj",
        "fundação hospital adriano jorge",
        "fundacao hospital adriano jorge", "hps", "hps 28 de agosto",
        "hospital 28 de agosto", "hospital joão lúcio",
        "hospital joao lucio",
        "hospital e pronto-socorro joão lúcio",
        "hospital e pronto-socorro joao lucio",
        "hospital platão araújo", "hospital platao araujo",
        "hospital delphina aziz", "delphina aziz",
        "maternidade ana braga", "maternidade balbina mestrinho",
        "fundação de medicina tropical",
        "fundacao de medicina tropical", "fmt-hvd",
        "semsa", "secretaria municipal de saúde",
        "secretaria municipal de saude", "semed",
        "secretaria municipal de educação",
        "secretaria municipal de educacao", "seminf",
        "secretaria municipal de infraestrutura", "semulsp",
        "secretaria municipal de limpeza urbana", "semacc",
        "semcom", "semtepi", "semmas", "semmasclima", "semob",
        "instituto municipal de mobilidade urbana", "immu",
        "manaustrans", "manaus ambiental", "águas de manaus",
        "aguas de manaus", "suframa", "zona franca de manaus",
        "sine manaus", "sine amazonas", "detran-am", "detran amazonas",
        "ssp-am", "secretaria de segurança pública do amazonas",
        "secretaria de seguranca publica do amazonas",
        "pm do amazonas", "polícia militar do amazonas",
        "policia militar do amazonas", "pmam",
        "polícia civil do amazonas", "policia civil do amazonas",
        "pc-am", "pcam", "corpo de bombeiros do amazonas", "cbmam",
        "ipaam", "instituto de proteção ambiental do amazonas",
        "instituto de protecao ambiental do amazonas",
        "ads amazonas", "agência de desenvolvimento sustentável do amazonas",
        "agencia de desenvolvimento sustentavel do amazonas",
        "procon-am", "procon amazonas", "jucea",
        "junta comercial do estado do amazonas", "sefaz-am",
        "secretaria de fazenda do amazonas", "seduc-am",
        "secretaria de educação do amazonas",
        "secretaria de educacao do amazonas", "ses-am",
        "secretaria de saúde do amazonas",
        "secretaria de saude do amazonas",
        "funati", "idam", "sepror", "amazonastur",
        "secretaria de cultura do amazonas", "cultura am", "amazonprev",
    ],
    "programas_servicos_e_politicas_locais": [
        "prato cheio", "auxílio estadual", "auxilio estadual",
        "cartão estadual", "cartao estadual", "castramóvel",
        "castramovel", "asfalta manaus", "manaus mais verde",
        "vacina manaus", "imuniza manaus", "samu manaus",
        "zona azul manaus", "tarifa de ônibus", "tarifa de onibus",
        "transporte coletivo de manaus", "ônibus em manaus",
        "onibus em manaus", "linhas de ônibus", "linhas de onibus",
        "faixa azul", "boto-cinza",
        "programa social e ambiental dos igarapés de manaus",
        "prosamim", "pontos de vacinação", "pontos de vacinacao",
        "mutirão de saúde", "mutirao de saude", "feira da ads",
        "feira de produtos regionais", "feira do produtor",
    ],
    "cultura_turismo_eventos": [
        "festival de parintins", "festival folclórico de parintins",
        "festival folclorico de parintins", "boi garantido",
        "boi caprichoso", "caprichoso", "garantido",
        "bumbódromo", "bumbodromo", "carnaval de manaus",
        "boi manaus", "passo a paço", "passo a paco",
        "sou manaus", "sou manaus passagem",
        "festival de ópera do amazonas",
        "festival de opera do amazonas",
        "amazonas green jazz festival", "amazonas film festival",
        "faaf", "festival amazonas de artes visuais",
        "teatro amazonas", "teatro da instalação",
        "teatro da instalacao", "palacete provincial",
        "centro cultural palácio da justiça",
        "centro cultural palacio da justica",
        "centro cultural povoados da amazônia",
        "centro cultural povoados da amazonia",
        "museu do seringal", "museu da cidade de manaus",
        "manaus moderna", "feira da manaús moderna",
        "feira da manaus moderna", "feira do peixe",
        "feira da banana", "feira da panair", "ponta negra",
        "praia da ponta negra", "turismo no amazonas",
        "turismo em manaus",
    ],
    "times_esporte_local": [
        "amazonas fc", "amazonas futebol clube",
        "onça-pintada", "onca-pintada", "onça pintada", "onca pintada",
        "nacional fc", "nacional futebol clube", "naça", "naca",
        "fast clube", "fast club", "tricolor de aço", "tricolor de aco",
        "são raimundo", "sao raimundo", "tufão da colina",
        "tufao da colina", "rio negro clube",
        "atlético rio negro clube", "atletico rio negro clube",
        "manaus fc", "manaus futebol clube", "gavião do norte",
        "gaviao do norte", "princesa do solimões",
        "princesa do solimoes", "operário-am", "operario-am",
        "penarol atlético clube", "penarol atletico clube",
        "penarol-am", "instituto 3b", "3b da amazônia",
        "3b da amazonia", "iranduba", "hulk da amazônia",
        "hulk da amazonia", "campeonato amazonense",
        "barezão", "barezao", "amazonense de futebol",
    ],
    "pessoas_publicas_locais": [
        "david almeida", "wilson lima", "roberto cidade",
        "amazonino mendes", "arthur virgílio", "arthur virgilio",
        "omar aziz", "eduardo braga", "plínio valério",
        "plinio valerio", "marcelo ramos", "amom mandel",
        "capitão alberto neto", "capitao alberto neto",
        "sidney leite", "saullo vianna", "fausto júnior",
        "fausto junior", "josué neto", "josue neto",
        "serafim corrêa", "serafim correa", "hissa abrahão",
        "hissa abrahao", "ricardo nicolau", "josé ricardo",
        "jose ricardo", "marcos rotta", "tadeu de souza",
        "sabá reis", "saba reis", "elizabeth valeiko",
        "neuton corrêa", "neuton correa",
    ],
    # "veiculos_locais" removido (Bug 1): muitos portais embutem o próprio nome
    # no summary do RSS, então qualquer notícia — inclusive nacional — que citasse
    # o veículo virava "local". Sem essa categoria, esses casos caem no fallback
    # do LLM (_groq_classify), que lê o contexto em vez de casar o nome do portal.
    "gentilicos_regionais": [
        "amazonense", "amazonenses", "parintinense",
        "itacoatiarense", "manacapuruense", "coariense",
        "tefeense", "tabatinguense", "humaitaense",
        "mauesense", "borbense", "irandubense", "autazense",
        "barcelense",
    ],
}

# Lista plana usada pelo matcher
LOCAL_KEYWORDS = [kw for terms in LOCAL_TERMS.values() for kw in terms]


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _keyword_match(text: str) -> bool | None:
    """Retorna True se local, None se incerto (sem match)."""
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
    """Usa OpenAI para classificar casos ambíguos.

    Groq descontinuou llama-3.1-8b-instant (2026-08-18, toda a família
    Llama-instant saiu da conta) — migrado para gpt-4o-mini, já usado em
    nlp/summarizer.py, que também não tem teto diário de tokens (o Groq 8b
    tinha 500k TPD, quase todo consumido pela operação normal).
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False
    try:
        from openai import OpenAI
        from nlp.prompts import render
        client = OpenAI(api_key=api_key)
        prompt = render("is_local", text=text[:500])
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0,
        )
        answer = response.choices[0].message.content.strip().lower()
        return answer.startswith("sim")
    except Exception as e:
        print(f"  [OpenAI local_classifier] Erro: {e}")
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


def backfill_local_keywords(batch_size: int = 5000) -> int:
    """Classifica artigos antigos com is_local=NULL usando só palavras-chave.

    Artigos sem nenhum match ficam marcados como False (não-local).
    Rápido e sem chamadas à API — ideal para processar o backlog histórico.
    """
    session = get_session()
    classified = 0
    try:
        pending = (
            session.query(Article)
            .filter(Article.is_local.is_(None))
            .order_by(Article.published_at.asc())
            .limit(batch_size)
            .all()
        )
        for article in pending:
            text = f"{article.title or ''} {article.summary or ''}"
            result = _keyword_match(text)
            article.is_local = result if result is not None else False
            classified += 1
        session.commit()
    finally:
        session.close()
    return classified
