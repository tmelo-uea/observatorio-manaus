# 📧 Configuração Rápida - Sendgrid

## Por que Sendgrid?

✅ Railway **não bloqueia** HTTPS (porta 443)  
✅ Sendgrid usa **API REST** em vez de SMTP  
✅ Plano gratuito: **100 emails/dia**  
✅ Implementação: **5 minutos**

---

## 1️⃣ Criar Conta Sendgrid

1. Acesse: https://sendgrid.com
2. Clique "Sign Up Free"
3. Complete o cadastro
4. Verifique seu email

---

## 2️⃣ Obter Chave API

1. Faça login em https://app.sendgrid.com
2. Vá para **Settings** → **API Keys**
3. Clique **"Create API Key"**
4. Nome: `observatorio-manaus` (opcional)
5. Copie a chave: `SG.xxxxxxxxxxxxxxxxxxxx`

---

## 3️⃣ Verificar Domínio (Opcional mas Recomendado)

Para aumentar reputação, verifique um domínio:

1. **Sender Authentication** → **Domain Authentication**
2. Adicione domínio (ex: `observatorio-manaus.com`)
3. Siga as instruções para adicionar registros DNS

**Se não tiver domínio:** Use `noreply@observatorio-manaus.com` como remetente (será criado automaticamente)

---

## 4️⃣ Configurar Railway

Adicione estas variáveis no Railway:

```
SENDGRID_API_KEY = SG.xxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL = seu@email.com
SENDGRID_FROM_NAME = Observatório de Manaus
```

**Onde:**
- `SENDGRID_API_KEY` — Chave copiada no passo 2
- `SENDGRID_FROM_EMAIL` — Email que aparecerá como remetente
- `SENDGRID_FROM_NAME` — Nome que aparecerá no "De:"

---

## 5️⃣ Testar

1. Acesse dashboard em produção
2. Clique ⚙️ **Admin**
3. Informe `ADMIN_PASSWORD`
4. Clique **"📤 Disparar digest agora (teste)"**

Se funcionar:
- ✅ Email chega em segundos
- ✅ Dashboard mostra `✓ Digest enviado para X assinante(s)`

---

## 📊 Monitoramento

Após enviar alguns digests, acesse:
- https://app.sendgrid.com/analytics → **Stats**
- Veja emails enviados, opens, clicks

---

## 💡 Dicas

- **Plano gratuito:** 100 emails/dia (mais que suficiente para digest diário)
- **Spam:** Configure SPF/DKIM para melhorar entregabilidade
- **Unsubscribe:** Sendgrid detecta automaticamente links `List-Unsubscribe`

---

## ⚡ Próximo Passo

Depois que Sendgrid funcionar, você pode **remover Brevo** se quiser, ou mantê-lo como fallback.

Para remover:
1. Remova variáveis `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, etc do Railway
2. Código automaticamente usará apenas Sendgrid

---

**Dúvidas?** Confira logs do Worker no Railway:
```
[Email] Enviando via Sendgrid para...
[Email] ✓ Enviado com sucesso
```
