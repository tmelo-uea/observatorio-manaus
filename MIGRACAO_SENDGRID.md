# 🚀 Migração Brevo → Sendgrid

Guia rápido para migrar o sistema de digest do Brevo para Sendgrid.

## Por quê?

Brevo apresentou:
- ❌ Timeouts em Railway (mesmo com 30s + retries)
- ❌ Warning de "Freemail não recomendado" para Gmail
- ❌ Requisitos rígidos de DKIM/DMARC

Sendgrid:
- ✅ API mais rápida e confiável
- ✅ Plano gratuito: **100 emails/dia**
- ✅ Não exige DKIM/DMARC para começar
- ✅ Funciona nativamente em Railway

---

## 📋 Passo 1: Criar conta no Sendgrid

1. Acesse: https://signup.sendgrid.com
2. Preencha o formulário
3. Verifique seu email

---

## 📋 Passo 2: Verificar remetente (Single Sender Verification)

1. Acesse: https://app.sendgrid.com/settings/sender_auth/senders
2. Clique em **"Create New Sender"**
3. Preencha:
   - **From Name:** `Observatório de Manaus`
   - **From Email:** `tiagoeugeniodemelo@gmail.com`
   - **Reply To:** mesmo email
   - **Company Address:** endereço da UEA (qualquer endereço válido)
   - **City, State, ZIP, Country:** Manaus, AM, 69050-000, Brazil
4. Clique em **"Create"**
5. **VERIFIQUE seu email** — clique no link de confirmação que o Sendgrid enviou
6. Status deve mudar para **"Verified"** ✅

---

## 📋 Passo 3: Criar API Key

1. Acesse: https://app.sendgrid.com/settings/api_keys
2. Clique em **"Create API Key"**
3. **Name:** `observatorio-manaus`
4. **Permissions:** selecione **"Full Access"**
5. Clique em **"Create & View"**
6. **COPIE A CHAVE** — começa com `SG.xxxxx...`
   ⚠️ **A chave só aparece UMA VEZ!**

---

## 📋 Passo 4: Configurar no Railway

1. Acesse seu projeto Railway
2. Vá para **Variables**
3. Adicione (em **ambos os serviços** — Web e Worker):
   ```
   SENDGRID_API_KEY = SG.xxxxx...
   SENDGRID_FROM_EMAIL = tiagoeugeniodemelo@gmail.com
   SENDGRID_FROM_NAME = Observatório de Manaus
   ```
4. **Opcional:** Remova as variáveis do Brevo:
   - `BREVO_API_KEY`
   - `BREVO_SENDER_EMAIL`
   - `BREVO_SENDER_NAME`

5. Railway fará redeploy automático

---

## 📋 Passo 5: Testar

Após o deploy terminar (~2-3 min):

1. Abra: https://observatorio-manaus-production.up.railway.app
2. Clique em **⚙️ Admin** (sidebar)
3. Informe a senha
4. Clique em **📤 Disparar digest agora (teste)**
5. Deve aparecer: `📧 Provedor: Sendgrid | De: tiagoeugeniodemelo@gmail.com`
6. Status: `✓ Digest enviado para X assinante(s)` ✅
7. Verifique seu email

---

## 🐛 Troubleshooting

### Erro 401: Unauthorized
- Chave inválida — gere uma nova em [API Keys](https://app.sendgrid.com/settings/api_keys)

### Erro 403: Forbidden
- Remetente não verificado — verifique em [Senders](https://app.sendgrid.com/settings/sender_auth/senders)

### Status 202 mas email não chega
- Verifique spam
- Verifique logs em [Activity](https://app.sendgrid.com/email_activity)

---

## 🔧 Teste manual da API

Localmente, para testar antes do deploy:

```bash
export SENDGRID_API_KEY="SG.xxxxx..."
export SENDGRID_FROM_EMAIL="tiagoeugeniodemelo@gmail.com"
python3 scripts/test_sendgrid_simple.py
```

Deve retornar **status 202** em menos de 2 segundos.
