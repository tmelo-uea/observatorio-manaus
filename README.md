# 🔭 Observatório de Manaus

Plataforma de monitoramento contínuo de notícias e publicações sobre a cidade de Manaus e o estado do Amazonas. O sistema coleta, classifica e exibe automaticamente o que é publicado nos principais portais, blogs, canais de YouTube e instituições de ensino da região.

Uma iniciativa do **LSI — Laboratório de Sistemas Inteligentes** da **Universidade do Estado do Amazonas (UEA)**.

🌐 **Acesso público:** https://observatorio-manaus-production.up.railway.app

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                         FONTES DE DADOS                         │
│  Portais RSS (42+)  │  Blogs (4)  │  YouTube (9 canais)         │
│  Universidades (4)  │  Institutos de pesquisa                   │
└──────────────┬──────────────────────────────────────────────────┘
               │ coleta a cada 30 min
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     COLETOR (Railway Worker)                    │
│                                                                 │
│  rss_collector.py     → coleta portais e blogs via RSS          │
│  youtube_collector.py → coleta vídeos + busca transcrições      │
│                         (legendas YouTube ou Groq Whisper)      │
└──────────────┬──────────────────────────────────────────────────┘
               │ persiste artigos
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BANCO DE DADOS (MySQL / Railway)             │
│                                                                 │
│  sources         → portais, blogs e canais monitorados          │
│  articles        → notícias e vídeos coletados                  │
│  topics          → temas de classificação                       │
│  daily_summaries → resumos diários gerados por IA               │
└──────────────┬──────────────────────────────────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐  ┌─────────────────────────────────────────────┐
│  PIPELINE   │  │              DASHBOARD (Railway Web)         │
│  de NLP     │  │                                             │
│             │  │  Visão Geral  → métricas, gráficos,         │
│  classifier │  │                 nuvem de palavras,          │
│  → tema     │  │                 resumo diário IA            │
│             │  │  Temas        → detalhe por tema,           │
│  local_     │  │                 resumo por tema IA          │
│  classifier │  │  Sobre        → estatísticas e fontes       │
│  → is_local │  │                                             │
│             │  └─────────────────────────────────────────────┘
│  summarizer │
│  → resumo   │
│    diário   │
└─────────────┘
```

---

## Funcionalidades

### Coleta
- Coleta automática a cada **30 minutos** via RSS de portais, blogs e universidades
- Coleta de vídeos de **9 canais do YouTube** locais via RSS do YouTube
- **Transcrição automática** de vídeos: busca legendas do YouTube; usa **Groq Whisper** como fallback
- Deduplicação por URL — cada artigo é armazenado apenas uma vez

### Processamento de Linguagem Natural
- **Classificação temática** por palavras-chave com regex (word boundary) em 10 temas pré-definidos
- **Classificação de localidade** (`is_local`): híbrida — palavras-chave primeiro, Groq LLM para casos ambíguos
- **Resumos diários gerados por IA** (Groq `llama3-8b-8192`): resumo geral às 7h e resumos por tema sob demanda

### Dashboard
- Filtros por tema, fonte, tipo de fonte, período e palavra-chave
- Filtro **"Só notícias locais"** baseado na classificação de localidade
- Gráfico de volume de notícias por dia
- Distribuição por tema e por fonte
- Nuvem de palavras com bigramas (título + descrição + transcrição, com limpeza de HTML e URLs)
- Card de resumo diário com IA, mostrando fontes consultadas

---

## Temas classificados

| Tema | Cor |
|---|---|
| Saúde | ![#e74c3c](https://placehold.co/12x12/e74c3c/e74c3c.png) |
| Segurança Pública | ![#c0392b](https://placehold.co/12x12/c0392b/c0392b.png) |
| Meio Ambiente | ![#27ae60](https://placehold.co/12x12/27ae60/27ae60.png) |
| Política e Governo | ![#2980b9](https://placehold.co/12x12/2980b9/2980b9.png) |
| Economia e Negócios | ![#f39c12](https://placehold.co/12x12/f39c12/f39c12.png) |
| Educação | ![#8e44ad](https://placehold.co/12x12/8e44ad/8e44ad.png) |
| Infraestrutura e Mobilidade | ![#7f8c8d](https://placehold.co/12x12/7f8c8d/7f8c8d.png) |
| Cultura e Lazer | ![#e67e22](https://placehold.co/12x12/e67e22/e67e22.png) |
| Esporte | ![#1abc9c](https://placehold.co/12x12/1abc9c/1abc9c.png) |
| Tecnologia e Inovação | ![#3498db](https://placehold.co/12x12/3498db/3498db.png) |
| Outros | ![#95a5a6](https://placehold.co/12x12/95a5a6/95a5a6.png) |

---

## Fontes monitoradas

### Portais de notícias (Manaus/Amazonas)
A Crítica, Em Tempo, D24am, Portal do Holanda, Amazonas Atual, A Gazeta do Amazonas, Amazonas 1, AM POST, Norte em Foco, Correio da Amazônia, Rede Amazônica, I9 Brasil, Fato Amazônico, Radar Amazônico, BNC Amazonas, Realtime, Portal Único, Portal Manaus Alerta, CM7 Brasil, Manaus 360, Vocativo, Chumbo Grosso Manaus, Tribuna Amazonas, Tribuna de Manaus, Tribuna do Amazonas, Igarapé News, Rios de Notícias, Portal do Amazonas, Portal da Floresta, Portal do Zacarias, Portal Norte, Portal Manaus Notícias, Portal O Poder, Agência Amazonas

### Blogs
Blog do Holanda, Blog do Hiel Levy, Portal Marcos Santos, Blog do Jucem

### Cobertura regional e ambiental
G1 Amazonas, Agência Brasil, Mongabay Brasil

### Universidades e institutos
UFAM, UEA, INPA, UniNorte

### Canais do YouTube
TV A Crítica, TV Norte Amazonas, Jovem Pan Manaus, Portal do Holanda, Rede Amazônica, TV CM7, Record Manaus, Band Amazonas, Amazonas Atual

---

## Estrutura do projeto

```
observatorio-manaus/
├── collector/
│   ├── runner.py            # Orquestra coleta, NLP e agendamento (30 min)
│   ├── rss_collector.py     # Coleta RSS de portais e blogs
│   └── youtube_collector.py # Coleta YouTube + transcrição
├── dashboard/
│   ├── 0_Visão_Geral.py     # Página principal (métricas, gráficos, resumo)
│   ├── components/
│   │   └── summary_card.py  # Card visual de resumo por IA
│   └── pages/
│       ├── 1_Temas.py       # Exploração por tema com resumo IA
│       └── 2_Sobre.py       # Informações institucionais
├── db/
│   ├── connection.py        # Engine SQLAlchemy + migrações automáticas
│   ├── models.py            # Modelos ORM (Source, Topic, Article, DailySummary)
│   └── seeds.py             # Dados iniciais (temas e fontes)
├── nlp/
│   ├── classifier.py        # Classificador de temas por palavras-chave
│   ├── local_classifier.py  # Classificador de localidade (híbrido: keywords + Groq)
│   └── summarizer.py        # Geração de resumos diários via Groq
├── scripts/
│   └── backfill_transcripts.py  # Preenche transcrições retroativas
├── Procfile                 # Comando de start para Railway
├── nixpacks.toml            # Dependências de sistema (ffmpeg)
├── requirements.txt         # Dependências Python
└── .python-version          # Python 3.11
```

---

## Banco de dados

### `sources`
| Campo | Tipo | Descrição |
|---|---|---|
| id | INT | Chave primária |
| name | VARCHAR(200) | Nome da fonte |
| url | VARCHAR(500) | URL principal |
| rss_url | VARCHAR(500) | URL do feed RSS |
| type | VARCHAR(50) | `portal`, `blog` ou `youtube` |
| active | BOOL | Ativa para coleta |

### `topics`
| Campo | Tipo | Descrição |
|---|---|---|
| id | INT | Chave primária |
| name | VARCHAR(100) | Nome do tema |
| slug | VARCHAR(100) | Identificador único |
| keywords | JSON | Lista de palavras-chave |
| color | VARCHAR(20) | Cor hexadecimal |
| display_order | INT | Ordem de exibição |

### `articles`
| Campo | Tipo | Descrição |
|---|---|---|
| id | INT | Chave primária |
| title | VARCHAR(500) | Título |
| url | VARCHAR(767) | URL original (único) |
| summary | TEXT | Descrição/resumo |
| transcript | LONGTEXT | Transcrição (vídeos YouTube) |
| published_at | DATETIME | Data de publicação |
| collected_at | DATETIME | Data de coleta |
| source_id | INT | FK → sources |
| topic_id | INT | FK → topics |
| topic_score | FLOAT | Confiança da classificação |
| is_local | TINYINT(1) | 1 = sobre Manaus/AM, 0 = não-local |

### `daily_summaries`
| Campo | Tipo | Descrição |
|---|---|---|
| id | INT | Chave primária |
| date | DATE | Data do resumo |
| topic_id | INT | FK → topics (NULL = geral) |
| summary | TEXT | Texto gerado pelo Groq |
| article_ids | JSON | IDs dos artigos usados |
| article_count | INT | Quantidade de artigos |
| generated_at | DATETIME | Timestamp de geração |

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11 |
| Dashboard | Streamlit |
| Banco de dados | MySQL (Railway) |
| ORM | SQLAlchemy 2.0 |
| Coleta RSS | feedparser |
| Coleta YouTube | feedparser + youtube-transcript-api + yt-dlp |
| Transcrição | Groq Whisper (`whisper-large-v3`) |
| NLP / IA | Groq (`llama3-8b-8192`) |
| Gráficos | Plotly |
| Nuvem de palavras | WordCloud + matplotlib |
| Hospedagem | Railway (web + worker) |
| Versionamento | GitHub |

---

## Como executar localmente

### Pré-requisitos
- Python 3.11
- MySQL local ou acesso ao banco do Railway
- `ffmpeg` instalado no sistema

### Instalação

```bash
git clone https://github.com/tmelo-uea/observatorio-manaus.git
cd observatorio-manaus
pip install -r requirements.txt
```

### Configuração

Crie um arquivo `.env` na raiz:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=sua_senha
MYSQL_DATABASE=observatorio
GROQ_API_KEY=sua_chave_groq
```

### Rodar o coletor

```bash
python collector/runner.py
```

### Rodar o dashboard

```bash
streamlit run "dashboard/0_Visão_Geral.py"
```

---

## Deploy no Railway

O projeto usa dois serviços no Railway:

- **Web** (`Procfile`): `streamlit run "dashboard/0_Visão_Geral.py"`
- **Worker**: `python collector/runner.py`

Variáveis de ambiente necessárias no Railway:
- `MYSQL_URL` ou `DATABASE_URL` — fornecida automaticamente pelo plugin MySQL
- `GROQ_API_KEY` — chave da API do Groq

O deploy é automático a cada push no branch `main`.

---

## Equipe

Iniciativa do **LSI — Laboratório de Sistemas Inteligentes**  
**Universidade do Estado do Amazonas (UEA)**

**Coordenação:** *(a preencher)*  
**Equipe:** *(a preencher)*  
**Contato:** *(a preencher)*
