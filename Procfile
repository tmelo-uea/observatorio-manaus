web: streamlit run "dashboard/0_Visão_Geral.py" --server.port=$PORT --server.address=0.0.0.0
worker: python collector/runner.py
bot: uvicorn bot.main:app --host 0.0.0.0 --port $PORT
