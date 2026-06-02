# WhatsApp Cloud API — Roteiro de Implantação

Documento de acompanhamento da implantação do canal WhatsApp para o boletim diário do Observatório de Manaus. Inicialmente como pessoa física, com possível migração futura para o CNPJ da UEA.

---

## Fase 1 — Setup burocrático na Meta

### 1.1 — Conta Meta Business
- [ ] Acessar https://business.facebook.com
- [ ] Criar conta usando seu Facebook pessoal (`tiagoeugeniodemelo@gmail.com`)
- [ ] Nome do negócio: `Observatório de Manaus`
- [ ] Categoria: `Mídia / Jornalismo / Notícias`
- [ ] País: Brasil
- [ ] Anotar o ID da conta Meta Business: __________________

### 1.2 — Número de telefone dedicado
- [ ] Adquirir um chip novo (não pode ser número que já tenha WhatsApp ativo)
- [ ] Operadora recomendada: qualquer pré-pago serve (Vivo, Claro, TIM)
- [ ] Anotar o número: __________________
- [ ] Verificar que o chip recebe SMS e ligações (necessário para validação)

### 1.3 — Criar WhatsApp Business Account (WABA)
- [ ] Em business.facebook.com → Configurações da empresa → Contas → Contas do WhatsApp
- [ ] Criar nova WABA
- [ ] Adicionar o número adquirido
- [ ] Validar via SMS ou ligação
- [ ] Anotar Phone Number ID: __________________
- [ ] Anotar WABA ID: __________________

### 1.4 — Configurar perfil business do número
- [ ] Nome de exibição: `Observatório de Manaus`
- [ ] Descrição: "Boletim diário automatizado de notícias sobre Manaus e o Amazonas. Iniciativa do LSI/UEA."
- [ ] Categoria: Notícias
- [ ] Email: tiagoeugeniodemelo@gmail.com
- [ ] Site: https://www.observatorio.manaus.br
- [ ] Foto de perfil: usar o logo do Observatório

### 1.5 — Obter credenciais de API
- [ ] Acessar https://developers.facebook.com
- [ ] Criar um App (tipo "Business")
- [ ] Adicionar o produto "WhatsApp" ao app
- [ ] Vincular o app à WABA criada
- [ ] Gerar um **Access Token permanente** (System User token)
- [ ] Anotar Access Token: __________________
- [ ] Anotar App ID: __________________

---

## Fase 2 — Aprovação de templates

### 2.1 — Criar template do boletim diário
- [ ] Acessar a WABA → Templates de mensagem
- [ ] Nome do template: `boletim_diario`
- [ ] Categoria: **Marketing** (ou Utility se for tratado como utilidade pública)
- [ ] Idioma: Português (Brasil)
- [ ] Corpo da mensagem (rascunho):
  ```
  Bom dia! Aqui está o resumo do dia anterior do Observatório de Manaus.

  {{1}}

  Leia mais: {{2}}
  ```
- [ ] Botão "Cancelar inscrição" com link para o site
- [ ] Submeter para aprovação

### 2.2 — Acompanhar aprovação
- [ ] Status atual: _________________ (Pendente / Aprovado / Rejeitado)
- [ ] Se rejeitado, motivo: _________________
- [ ] Ajustar e ressubmeter se necessário

---

## Fase 3 — Mudanças no banco e dashboard

### 3.1 — Modelo de dados
- [ ] Criar tabela `whatsapp_subscriptions` em `db/models.py`:
  - id, telefone (E.164), nome, ativo, opt_in_at, opt_in_ip, unsubscribe_token, created_at
- [ ] Adicionar migração em `db/connection.py` (auto-migrate na partida)

### 3.2 — Formulário de inscrição
- [ ] Adicionar formulário no sidebar ou página dedicada
- [ ] Campos: nome, telefone (com máscara), checkbox de consentimento LGPD
- [ ] Validação de telefone brasileiro (formato E.164: +5592XXXXXXXXX)
- [ ] Salvar opt_in_at (timestamp) e opt_in_ip (do request) como prova de consentimento

### 3.3 — Descadastro
- [ ] Endpoint/rota para descadastro via token
- [ ] Link incluído em todas as mensagens

---

## Fase 4 — Integração técnica

### 4.1 — Módulo de envio
- [ ] Criar `notifications/whatsapp_sender.py`
- [ ] Função `send_whatsapp_digest(force=False)` análoga a `run_digest()`
- [ ] Usar `requests` para chamar a Cloud API:
  - Endpoint: `https://graph.facebook.com/v18.0/{phone_number_id}/messages`
  - Auth: Bearer token
  - Body: template com parâmetros

### 4.2 — Variáveis de ambiente no Railway
- [ ] `WHATSAPP_PHONE_NUMBER_ID`
- [ ] `WHATSAPP_ACCESS_TOKEN`
- [ ] `WHATSAPP_TEMPLATE_NAME=boletim_diario`

### 4.3 — Integrar ao runner
- [ ] Chamar `send_whatsapp_digest()` no `runner.py` junto com `run_digest()`
- [ ] Criar tabela `whatsapp_digest_log` para histórico de envios

### 4.4 — Painel admin
- [ ] Botão "Disparar WhatsApp agora (teste)" no painel admin do dashboard
- [ ] Métrica de assinantes WhatsApp ativos

---

## Fase 5 — Operação

### 5.1 — Monitoramento
- [ ] Verificar taxa de entrega diariamente nas primeiras semanas
- [ ] Monitorar descadastros e marcações como spam
- [ ] Status do número (Green/Yellow/Red) no Meta Business

### 5.2 — Custos
- [ ] Verificar plano gratuito (1.000 conversas/mês)
- [ ] Configurar alerta de faturamento se passar do gratuito
- [ ] Custo atual estimado: ______________

### 5.3 — Migração para CNPJ da UEA (futuro)
- [ ] Conversar com administração/jurídico da UEA
- [ ] Obter autorização para uso do CNPJ
- [ ] Transferir WABA para nova Meta Business (mantém número, histórico e templates)
- [ ] Atualizar perfil business com dados institucionais

---

## Decisões e notas

Use este espaço para registrar decisões importantes durante a implantação:

- Data de início: 2026-06-01
- Decisão sobre PF vs CNPJ: começar como PF, migrar depois
- Template categoria escolhida: ______________
- Outros: ______________

---

## Referências úteis

- WhatsApp Cloud API: https://developers.facebook.com/docs/whatsapp/cloud-api
- Diretrizes de templates: https://developers.facebook.com/docs/whatsapp/message-templates/guidelines
- LGPD para WhatsApp: https://www.gov.br/anpd/pt-br
- Pricing: https://developers.facebook.com/docs/whatsapp/pricing
