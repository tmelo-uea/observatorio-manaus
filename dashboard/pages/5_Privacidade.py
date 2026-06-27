import streamlit as st

st.set_page_config(
    page_title="Política de Privacidade — Observatório de Manaus",
    page_icon="🔒",
    layout="centered",
)

st.markdown("## Política de Privacidade")
st.caption("Última atualização: junho de 2026")

st.divider()

st.markdown("""
**Responsável pelo tratamento de dados**

Tiago Eugenio de Melo — OpinionBotz Tecnologia
Contato: [tmelo@uea.edu.br](mailto:tmelo@uea.edu.br)

---

### 1. O que é o Observatório de Manaus

O Observatório de Manaus é uma plataforma de monitoramento de notícias sobre a cidade de
Manaus e o estado do Amazonas. Coleta, organiza e disponibiliza publicamente informações
provenientes de portais e blogs da região. Não é necessário criar conta para acessar o
painel de notícias.

---

### 2. Dados coletados

**Painel de notícias (site)**

Não coletamos dados pessoais identificáveis de visitantes. Logs de acesso padrão (endereço
IP, data/hora, páginas visitadas) podem ser gerados pela infraestrutura de hospedagem
(Railway) exclusivamente para fins operacionais e de segurança, sem armazenamento ativo
pela plataforma.

**Boletim por e-mail**

Para os assinantes do boletim diário, coletamos apenas o **endereço de e-mail** fornecido
voluntariamente no formulário de cadastro. Esse e-mail é usado exclusivamente para o envio
do boletim. O cancelamento pode ser feito a qualquer momento pelo link presente em cada
mensagem.

**Chatbot WhatsApp**

Para os usuários do chatbot, coletamos:

- **Número de telefone WhatsApp** (fornecido automaticamente pelo sistema Twilio ao
  interagir com o serviço)
- **Histórico de interações** com o bot (comandos enviados e respostas recebidas)

Esses dados são usados exclusivamente para operar o serviço de consulta de resumos de
notícias. O cancelamento pode ser feito a qualquer momento enviando a palavra **parar**
para o chatbot.

---

### 3. Base legal e finalidade

O tratamento dos dados acima tem como base o **legítimo interesse** na operação do serviço
e o **consentimento** expresso pelo usuário ao se cadastrar ou interagir com o chatbot. Os
dados são usados exclusivamente para:

- Enviar o boletim diário aos assinantes
- Responder às consultas feitas via WhatsApp

Não utilizamos os dados para publicidade, perfilagem ou compartilhamento com terceiros,
exceto os provedores de infraestrutura listados abaixo.

---

### 4. Compartilhamento com terceiros

Os dados transitam pelos seguintes provedores de infraestrutura, estritamente necessários
para a operação do serviço:

| Serviço | Finalidade |
|---|---|
| Railway | Hospedagem da aplicação e banco de dados |
| Twilio | Intermediação das mensagens WhatsApp |
| Brevo | Envio do boletim por e-mail |
| OpenAI | Geração de resumos de notícias (dados de artigos, não dados de usuários) |
| Groq | Classificação e transcrição (dados de artigos, não dados de usuários) |

Nenhum dado pessoal de usuários é enviado a modelos de linguagem (LLMs).

---

### 5. Retenção

- **E-mail:** mantido enquanto o assinante não cancelar.
- **WhatsApp:** mantido enquanto o usuário não enviar o comando **parar**. Após o
  cancelamento, o registro é marcado como inativo e não é usado para nenhuma comunicação.

---

### 6. Seus direitos (LGPD)

Conforme a Lei Geral de Proteção de Dados (Lei nº 13.709/2018), você tem direito a:

- Confirmar a existência de tratamento dos seus dados
- Acessar os dados que temos sobre você
- Solicitar a correção ou exclusão
- Revogar o consentimento a qualquer momento

Para exercer qualquer desses direitos, envie um e-mail para
[tmelo@uea.edu.br](mailto:tmelo@uea.edu.br) informando seu pedido.

---

### 7. Alterações nesta política

Eventuais atualizações serão publicadas nesta página com a data de revisão atualizada.
O uso continuado do serviço após qualquer alteração implica concordância com a versão
vigente.
""")

st.divider()
st.caption("Observatório de Manaus — LSI/UEA · [tmelo@uea.edu.br](mailto:tmelo@uea.edu.br)")
