# 🔭 Observatório de Manaus

Plataforma de monitoramento contínuo de notícias e publicações sobre a cidade de Manaus e o estado do Amazonas. O sistema coleta, classifica e exibe automaticamente o que é publicado nos principais portais, blogs, canais de YouTube e órgãos públicos da região.

Uma iniciativa do **LSI — Laboratório de Sistemas Inteligentes** da **Universidade do Estado do Amazonas (UEA)**.

🌐 **Acesso público:** https://observatorio-manaus-production.up.railway.app

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                         FONTES DE DADOS                         │
│  Portais e blogs (43+)  │  YouTube (9 canais)                   │
│  Órgãos públicos (5)    │  Cobertura regional (3)               │
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
- Coleta automática a cada **30 minutos** via RSS de portais, blogs e órgãos públicos
- Coleta de vídeos de **9 canais do YouTube** locais via RSS do YouTube
- **Transcrição automática** de vídeos: busca legendas do YouTube; usa **Groq Whisper** como fallback
- Deduplicação por URL — cada artigo é armazenado apenas uma vez
- Datas armazenadas em **UTC**; exibição convertida para horário de Manaus (UTC−4, sem horário de verão)

### Processamento de Linguagem Natural
- **Classificação temática** por palavras-chave com regex (word boundary) em 12 temas pré-definidos
- **Classificação de localidade** (`is_local`): híbrida — lista com mais de 700 palavras-chave locais primeiro; Groq LLM apenas para casos ambíguos
- **Resumos diários gerados por IA** (Groq `llama-3.1-8b-instant`): resumo geral e resumos por tema gerados automaticamente a cada ciclo de coleta

### Dashboard
- Filtros por tema, fonte, tipo de fonte, período e palavra-chave
- **Notícias locais por padrão** — exibe apenas artigos classificados como `is_local = True`; opção para incluir todas
- Gráfico de volume de notícias por dia com **rótulos em português**
- Distribuição por tema e por fonte (top 20)
- Nuvem de palavras com bigramas (título + descrição + transcrição, com limpeza de HTML e URLs)
- Card de resumo diário com IA, mostrando fontes consultadas
- Cards de resumo por tema com contadores de notícias hoje / semana / total

---

## Temas classificados

| Tema | Cor |
|---|---|
| Saúde | ![#e74c3c](https://placehold.co/12x12/e74c3c/e74c3c.png) `#e74c3c` |
| Segurança Pública | ![#c0392b](https://placehold.co/12x12/c0392b/c0392b.png) `#c0392b` |
| Meio Ambiente | ![#27ae60](https://placehold.co/12x12/27ae60/27ae60.png) `#27ae60` |
| Política e Governo | ![#2980b9](https://placehold.co/12x12/2980b9/2980b9.png) `#2980b9` |
| Economia e Negócios | ![#f39c12](https://placehold.co/12x12/f39c12/f39c12.png) `#f39c12` |
| Educação | ![#8e44ad](https://placehold.co/12x12/8e44ad/8e44ad.png) `#8e44ad` |
| Infraestrutura e Mobilidade | ![#7f8c8d](https://placehold.co/12x12/7f8c8d/7f8c8d.png) `#7f8c8d` |
| Cultura e Lazer | ![#e67e22](https://placehold.co/12x12/e67e22/e67e22.png) `#e67e22` |
| Esporte | ![#1abc9c](https://placehold.co/12x12/1abc9c/1abc9c.png) `#1abc9c` |
| Tecnologia e Inovação | ![#3498db](https://placehold.co/12x12/3498db/3498db.png) `#3498db` |
| Justiça e Direito | ![#6c3483](https://placehold.co/12x12/6c3483/6c3483.png) `#6c3483` |
| Social e Cidadania | ![#e91e63](https://placehold.co/12x12/e91e63/e91e63.png) `#e91e63` |
| Outros | ![#95a5a6](https://placehold.co/12x12/95a5a6/95a5a6.png) `#95a5a6` |

---

## Fontes monitoradas

### Portais de notícias (Manaus/Amazonas)
Em Tempo, D24am, Portal do Holanda, Amazonas Atual, Amazonas 1, AM POST, Norte em Foco, Correio da Amazônia, I9 Brasil, Fato Amazônico, Radar Amazônico, BNC Amazonas, Realtime, Portal Único, Portal Manaus Alerta, CM7 Brasil, Manaus 360, Vocativo, Chumbo Grosso Manaus, Tribuna Amazonas, Tribuna de Manaus, Tribuna do Amazonas, Igarapé News, Rios de Notícias, Portal da Floresta, Portal Norte, Portal O Poder, Agência Amazonas, Portal AM 24h, Portal Amazôn Online, Portal R5, Portal Regional AM, Portal Tambaqui, Portal do Amazonas AM, No Ar Portal, Nosso Show AM, Comunica AM, Menezes Virtual Eye, Canal 92, ALEAM

### Blogs
Blog do Holanda, Blog do Hiel Levy, Portal Marcos Santos

### Cobertura regional e ambiental
G1 Amazonas, Agência Brasil, Mongabay Brasil

### Órgãos públicos
Prefeitura de Manaus, SSP-AM, DETRAN-AM, IPAAM, Cultura AM

### Universidades
UFAM, UniNorte

### Canais do YouTube
TV Norte Amazonas, Jovem Pan Manaus, Portal do Holanda, Rede Amazônica, TV CM7, Record Manaus, Band Amazonas, Amazonas Atual, ALEAM

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
│   ├── local_classifier.py  # Classificador de localidade (700+ keywords + Groq)
│   └── summarizer.py        # Geração de resumos diários via Groq
├── scripts/
│   └── backfill_transcripts.py  # Preenche transcrições retroativas (limit por ciclo)
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
| type | VARCHAR(50) | `portal`, `blog`, `youtube` ou `orgao_publico` |
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
| published_at | DATETIME | Data de publicação **em UTC** |
| collected_at | DATETIME | Data de coleta **em UTC** |
| source_id | INT | FK → sources |
| topic_id | INT | FK → topics |
| topic_score | FLOAT | Confiança da classificação |
| is_local | TINYINT(1) | 1 = sobre Manaus/AM, 0 = não-local |

### `daily_summaries`
| Campo | Tipo | Descrição |
|---|---|---|
| id | INT | Chave primária |
| date | DATE | Data do resumo (horário de Manaus) |
| topic_id | INT | FK → topics (NULL = resumo geral) |
| summary | TEXT | Texto gerado pelo Groq |
| article_ids | JSON | IDs dos artigos usados |
| article_count | INT | Quantidade de artigos locais (`is_local = 1`) |
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
| NLP / IA | Groq (`llama-3.1-8b-instant`) |
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

## Digest diário por e-mail

O Observatório envia automaticamente um resumo das notícias do dia anterior para assinantes.

### Configuração

No arquivo `.env`, adicione:
```env
# Brevo SMTP (para envio de emails)
BREVO_API_KEY=sua_chave_api_brevo
BREVO_SMTP_LOGIN=seu@email.com
BREVO_SENDER_EMAIL=seu@email.com
BREVO_SENDER_NAME=Observatório de Manaus

# Senha do painel admin (para disparar testes)
ADMIN_PASSWORD=sua_senha_secreta
```

**Obtendo a chave Brevo:**
1. Crie uma conta em [Brevo](https://www.brevo.com/)
2. Vá para **SMTP** nas configurações
3. Crie um login SMTP e copie a senha (chave API)

### Funcionamento

- **Horário de disparo:** 7:00 (horário de Manaus, UTC-4)
- **Frequência:** Uma vez por dia
- **Conteúdo:** Resumos por tema gerados por IA (Groq) + contagem de artigos por tema
- **Inscrição:** Disponível no formulário lateral do dashboard
- **Cancelamento:** Link "Cancelar inscrição" no rodapé do email

### Testando o digest

**Localmente:**
```bash
python scripts/test_digest.py
```

**Pelo dashboard:**
1. Abra http://localhost:8501
2. Clique em "⚙️ Admin" na barra lateral
3. Informe a senha (`ADMIN_PASSWORD`)
4. Clique em "📤 Disparar digest agora (teste)"

**Via Railway (serviço Web):**
1. Acesse o dashboard em produção
2. Verifique que `BREVO_API_KEY` está configurada
3. Use o botão de teste no painel admin

### Troubleshooting

| Problema | Solução |
|----------|---------|
| "BREVO_API_KEY não configurada" | Adicione a variável de ambiente em `.env` ou no Railway |
| Email não chegou | Verifique spam, confirme remetente (`BREVO_SENDER_EMAIL`) é autorizado no Brevo |
| "Apenas N resumos disponíveis — sem envio" | Aguarde o coletor executar (a cada 30 min) e gerar resumos |
| Erro SMTP no log | Verifique credenciais SMTP (`BREVO_SMTP_LOGIN` e `BREVO_API_KEY`) |

---

## Deploy no Railway

O projeto usa dois serviços no Railway:

- **Web** (`Procfile`): `streamlit run "dashboard/0_Visão_Geral.py"`
- **Worker**: `python collector/runner.py`

Variáveis de ambiente necessárias em **ambos os serviços**:

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | Fornecida automaticamente pelo plugin MySQL do Railway |
| `GROQ_API_KEY` | Chave da API do Groq (necessária para resumos por IA) |
| `BREVO_API_KEY` | Senha SMTP do Brevo (para envio de emails) |
| `BREVO_SMTP_LOGIN` | Login SMTP do Brevo (ex: seu@email.com) |
| `BREVO_SENDER_EMAIL` | Email remetente dos digests (ex: seu@email.com) |
| `BREVO_SENDER_NAME` | Nome exibido no "De:" dos emails |
| `ADMIN_PASSWORD` | Senha para acessar o painel admin do dashboard |

O deploy é automático a cada push no branch `main`.

---

## Equipe

Iniciativa do **LSI — Laboratório de Sistemas Inteligentes**  
**Universidade do Estado do Amazonas (UEA)**

**Coordenação:** Tiago Eugenio de Melo  
**Equipe:** Elloá Guedes, Carlos Maurício, Fábio Santos  
**Contato:** tmelo@uea.edu.br
