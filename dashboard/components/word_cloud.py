import re

import streamlit as st
import matplotlib.pyplot as plt
from wordcloud import WordCloud

STOPWORDS = {
    # artigos e preposições
    "de", "da", "do", "dos", "das", "em", "no", "na", "nos", "nas",
    "e", "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "com", "por", "para", "que", "se", "ao", "aos", "à", "às",
    "pelo", "pela", "pelos", "pelas", "neste", "nesta", "nestes", "nestas",
    "deste", "desta", "destes", "destas", "nesse", "nessa", "nesses", "nessas",
    "desse", "dessa", "desses", "dessas", "num", "numa",
    # pronomes
    "são", "foi", "será", "ser", "tem", "ter", "seus", "sua", "seu", "suas",
    "isso", "este", "esta", "esse", "essa", "esses", "essas",
    "ele", "ela", "eles", "elas", "nós", "eu", "você", "vocês",
    "mais", "já", "ainda", "também", "sobre", "entre", "após", "até", "como",
    "quando", "onde", "porque", "mas", "ou", "nem", "não", "sim",
    "muito", "bem", "aqui", "lá", "agora", "então", "assim", "tudo",
    "todos", "todas", "outro", "outra", "outros", "outras", "mesmo",
    # verbos jornalísticos genéricos
    "disse", "diz", "afirmou", "segundo", "conforme", "durante",
    "foi", "são", "está", "vai", "teve", "teve", "foram", "seja",
    "pode", "podem", "deve", "devem", "quer", "faz", "fez", "ter",
    "ocorreu", "realiza", "realizada", "realizado", "realizou",
    # conjunções e advérbios genéricos
    "apenas", "desde", "através", "partir", "dentro", "fora", "sem",
    "caso", "vez", "vezes", "além", "contra", "ante", "perante",
    # substantivos genéricos sem valor informativo
    "dia", "dias", "ano", "anos", "mês", "meses", "semana", "semanas",
    "manhã", "tarde", "noite", "hoje", "ontem", "amanhã",
    "meio", "nova", "novo", "novos", "novas", "grande", "grandes",
    "pais", "país", "área", "áreas", "grupo", "grupos", "equipe",
    "momento", "parte", "local", "região", "vez", "total",
    "acordo", "apoio", "agenda", "projeto", "ação", "iniciativa",
    "serviço", "serviços", "encontro", "debate", "proposta",
    "edição", "escala", "volta", "interior", "capital",
    # boilerplate de portais e redes sociais
    "http", "https", "br", "href", "src", "img", "bit", "www",
    "instagram", "facebook", "tiktok", "youtube", "twitter", "whatsapp",
    "redes", "sociais", "canal", "site", "post", "vivo",
    "notificações", "conteúdo", "conteúdos", "exclusivos", "informações",
    "apareceu", "acompanhe", "inscreva", "leia", "veja", "segue", "acesse",
    "notícia", "notícias", "noticias", "noticia", "últimas", "ultimas",
    "portais", "atual", "visita",
    # dias da semana
    "segunda", "terça", "terca", "quarta", "quinta", "sexta",
    "sábado", "sabado", "domingo", "feira",
    # palavras em inglês que escapam
    "the", "and", "for", "this", "that", "with",
    # referências de localização/transmissão genéricas
    "horário", "horario", "brasília", "brasilia",
    "primeiro", "segunda", "terceiro",
    # nomes de fontes que aparecem no próprio conteúdo
    "critica", "crítica", "radar", "holanda",
    # termos onipresentes no observatório — não distinguem nada
    "Manaus", "manaus", "Manau", "manau",
    "Amazonas", "amazonas", "Amazona", "amazona",
    "Amazônia", "amazônia", "amazonia", "Amazônico", "amazônico", "Amazônica", "amazônica",
    "amazonense", "Amazonense", "Amazon", "amazon",
}


def clean_text(series):
    def clean(t):
        t = re.sub(r"<[^>]+>", " ", t)           # remove tags HTML
        t = re.sub(r"https?://\S+", " ", t)       # remove URLs completas
        t = re.sub(r"\bhttps?\b", " ", t)         # remove http/https soltos
        t = re.sub(r"\b\w*\d\w*\b", " ", t)       # remove tokens com números
        t = re.sub(r"\b\w{1,2}\b", " ", t)        # remove palavras de 1-2 letras
        return t
    return series.dropna().apply(clean).str.cat(sep=" ")


def render_word_cloud(df, columns=("title", "summary")):
    """Renderiza a nuvem de palavras a partir das colunas de texto do dataframe."""
    texts = [clean_text(df[col]) for col in columns if col in df.columns]
    all_text = " ".join(t for t in texts if t.strip())
    if not all_text.strip():
        return
    wc = WordCloud(
        width=1600, height=500, background_color="white",
        collocations=True, max_words=120, stopwords=STOPWORDS,
        regexp=r"\b[^\W\d_]{3,}\b",
        margin=6, max_font_size=120,
    ).generate(all_text)
    fig, ax = plt.subplots(figsize=(16, 5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout(pad=0.5)
    st.pyplot(fig)
    plt.close(fig)
