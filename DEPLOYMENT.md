# 🚀 Guia de Deployment no Railway

## Configuração Inicial

### 1. Criar Conta no Railway
- Acesse [railway.app](https://railway.app)
- Faça login com GitHub
- Crie um novo projeto

### 2. Conectar Repositório
1. Clique em "+ New" → "Database" e escolha "MySQL"
2. Clique em "+ New" → "GitHub Repo" e selecione este repositório
3. Railway criará automaticamente dois serviços baseados no `Procfile`

### 3. Variáveis de Ambiente

Configure estas variáveis **em ambos os serviços** (Web e Worker):

#### Banco de Dados (automático)
- `DATABASE_URL` — Gerada automaticamente pelo plugin MySQL

#### NLP / IA (necessário para resumos)
```
GROQ_API_KEY = sua_chave_groq
```
Obtenha em: https://console.groq.com/

#### Email / Digest (Escolha uma opção)

**Opção A: Sendgrid** (Recomendado — nunca bloqueado por Railway)
```
SENDGRID_API_KEY = SG.xxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL = seu@email.com
SENDGRID_FROM_NAME = Observatório de Manaus
```
Obtenha em: https://sendgrid.com/ → Settings → API Keys

**Opção B: Brevo** (Fallback)
```
BREVO_API_KEY = sua_chave_api_brevo
BREVO_SENDER_EMAIL = seu@email.com
BREVO_SENDER_NAME = Observatório de Manaus
```
Obtenha em: https://www.brevo.com/ → Settings → SMTP & API

#### Admin Dashboard
```
ADMIN_PASSWORD = sua_senha_secreta
```

## Serviços

### Web (Streamlit Dashboard)
- **Comando:** `streamlit run "dashboard/0_Visão_Geral.py" --server.port=$PORT --server.address=0.0.0.0`
- **Porta:** Atribuída pelo Railway
- **URL Pública:** Gerada automaticamente

### Worker (Coletor + NLP)
- **Comando:** `python collector/runner.py`
- **Tipo:** Background Worker
- **Executa a cada 30 minutos:**
  - Coleta RSS de portais e blogs
  - Coleta YouTube + transcrições
  - Classificação temática
  - Classificação de localidade
  - Backfill de transcrições
  - Geração de resumos diários
  - **Envio do digest (após 7:00 Manaus)**

## Checklist de Deploy

- [ ] Criada conta Brevo e obtidas credenciais SMTP
- [ ] Obtida chave Groq API
- [ ] Todas as 9 variáveis de ambiente configuradas em ambos serviços
- [ ] Worker iniciou com sucesso (ver logs)
- [ ] Dashboard acessível em produção
- [ ] Botão admin funcionando (com password)
- [ ] Teste de digest disparado (ao menos 1 email enviado)
- [ ] Assinante cadastrado no formulário lateral

## Monitoramento

### Logs do Worker (Coletor)
```
Railway > seu-projeto > Worker > Logs
```
Procure por:
- `--- Iniciando coleta ---` (ciclo de 30 min)
- `[Resumos por tema]` (geração de resumos)
- `[Digest]` (envio de emails)

### Teste Manual do Digest
1. Acesse dashboard em produção
2. Clique ⚙️ Admin
3. Informe `ADMIN_PASSWORD`
4. Clique "📤 Disparar digest agora (teste)"
5. Verifique se emails chegaram em Brevo → [Emails](https://app.brevo.com/smtp/)

## Troubleshooting

| Problema | Solução |
|----------|---------|
| Worker não inicia | Verifique `DATABASE_URL` e `GROQ_API_KEY` |
| "BREVO_API_KEY não configurada" | Adicione em ambos os serviços, não apenas um |
| Emails não enviados | Verifique credenciais Brevo, confirme remetente autorizado |
| Resumos não gerados | Aguarde 30+ min para coletor executar |

## Atualizar Código

Simplesmente faça push para `main`:
```bash
git push origin main
```

Railway fará deploy automaticamente de ambos os serviços.
