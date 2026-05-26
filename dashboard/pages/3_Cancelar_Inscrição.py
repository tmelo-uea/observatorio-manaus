import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from notifications.email_sender import unsubscribe_by_token

st.set_page_config(page_title="Cancelar inscrição — Observatório de Manaus", page_icon="🔭", layout="centered")

st.title("🔭 Observatório de Manaus")
st.subheader("Cancelar inscrição no digest")

token = st.query_params.get("token", "")

if not token:
    st.info("Acesse este link a partir do botão de cancelamento no e-mail recebido.")
else:
    success, message = unsubscribe_by_token(token)
    if success:
        st.success(message)
    else:
        st.error(message)

st.markdown("---")
st.markdown("[← Voltar ao Observatório](/)")
