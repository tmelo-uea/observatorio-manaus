"""Demonstração das três visualizações propostas para o Observatório.

Usa dados simulados realistas. Rode com:
    python scripts/demo_visualizacoes.py

Abre três gráficos no browser via Plotly.
"""
import random
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

TOPICS = ["Segurança", "Saúde", "Política", "Economia", "Esportes",
          "Cultura", "Meio Ambiente", "Educação", "Outros"]

TOPIC_COLORS = ["#e74c3c", "#2ecc71", "#3498db", "#f39c12", "#9b59b6",
                "#1abc9c", "#27ae60", "#e67e22", "#95a5a6"]

def _rgba(hex_color: str, alpha: float = 0.8) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

SOURCES = [
    "Portal do Holanda", "Em Tempo", "A Crítica", "Amazonas Atual",
    "D24am", "Portal Metrópoles AM", "Acrítica.net", "Norte Legal",
]

# --- 1. HEATMAP DE ATIVIDADE (hora × dia da semana) ---

def make_heatmap():
    days = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    hours = list(range(24))

    # Padrão realista: pico ao meio-dia e tarde; fim de semana mais fraco
    base = np.zeros((7, 24))
    for d in range(7):
        weekend = 0.4 if d >= 5 else 1.0
        for h in hours:
            if 7 <= h <= 8:
                base[d, h] = 0.5 * weekend
            elif 9 <= h <= 11:
                base[d, h] = 0.8 * weekend
            elif 12 <= h <= 14:
                base[d, h] = 1.0 * weekend
            elif 15 <= h <= 18:
                base[d, h] = 0.9 * weekend
            elif 19 <= h <= 21:
                base[d, h] = 0.6 * weekend
            else:
                base[d, h] = 0.1 * weekend

    counts = (base * 18 + np.random.poisson(2, (7, 24))).astype(int)

    fig = go.Figure(go.Heatmap(
        z=counts,
        x=[f"{h:02d}h" for h in hours],
        y=days,
        colorscale="YlOrRd",
        showscale=True,
        colorbar=dict(title="Notícias"),
        hovertemplate="<b>%{y}</b> às <b>%{x}</b><br>%{z} notícias<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="Ritmo de publicação da mídia local (por hora × dia da semana)",
                   font=dict(size=18)),
        xaxis_title="Hora do dia",
        yaxis_title="",
        height=380,
        margin=dict(l=100, r=40, t=70, b=60),
        plot_bgcolor="#fafafa",
    )
    return fig


# --- 2. EVOLUÇÃO DE TEMAS AO LONGO DO TEMPO ---

def make_topic_evolution():
    weeks = pd.date_range(end=datetime.today(), periods=20, freq="W")

    # Peso base por tema + variação semanal
    base_weights = [0.20, 0.15, 0.18, 0.10, 0.08, 0.07, 0.06, 0.06, 0.10]
    data = {}
    for i, topic in enumerate(TOPICS):
        vals = []
        for w in weeks:
            noise = np.random.normal(0, 0.03)
            # Cultura sobe em junho (Festival Folclórico)
            boost = 0.12 if (topic == "Cultura" and w.month == 6) else 0
            vals.append(max(5, int((base_weights[i] + noise + boost) * 120)))
        data[topic] = vals

    fig = go.Figure()
    for i, topic in enumerate(TOPICS):
        fig.add_trace(go.Scatter(
            x=weeks,
            y=data[topic],
            name=topic,
            mode="lines",
            stackgroup="one",
            fillcolor=_rgba(TOPIC_COLORS[i], 0.75),
            line=dict(color=TOPIC_COLORS[i], width=0.5),
            hovertemplate=f"<b>{topic}</b><br>%{{x|%d/%m}}: %{{y}} notícias<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text="Evolução dos temas na cobertura jornalística local (últimas 20 semanas)",
                   font=dict(size=18)),
        xaxis_title="",
        yaxis_title="Notícias por semana",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=450,
        hovermode="x unified",
        plot_bgcolor="#fafafa",
        margin=dict(l=60, r=40, t=100, b=50),
    )
    return fig


# --- 3. PERFIL EDITORIAL DAS FONTES (heatmap fonte × tema) ---

def make_source_profile():
    profiles = {
        "Portal do Holanda":    [0.30, 0.05, 0.35, 0.10, 0.05, 0.05, 0.05, 0.05],
        "Em Tempo":             [0.25, 0.15, 0.20, 0.15, 0.10, 0.05, 0.05, 0.05],
        "A Crítica":            [0.15, 0.20, 0.25, 0.15, 0.08, 0.07, 0.05, 0.05],
        "Amazonas Atual":       [0.20, 0.10, 0.15, 0.20, 0.05, 0.05, 0.15, 0.10],
        "D24am":                [0.35, 0.10, 0.25, 0.10, 0.08, 0.05, 0.04, 0.03],
        "Portal Metrópoles AM": [0.15, 0.25, 0.10, 0.20, 0.05, 0.10, 0.10, 0.05],
        "Acrítica.net":         [0.10, 0.15, 0.20, 0.10, 0.20, 0.15, 0.05, 0.05],
        "Norte Legal":          [0.20, 0.15, 0.10, 0.15, 0.05, 0.05, 0.20, 0.10],
    }
    topics_8 = TOPICS[:8]

    matrix = []
    for source in SOURCES:
        row = [int(v * 100) for v in profiles[source]]
        matrix.append(row)

    z = matrix
    text = [[f"{v}%" for v in row] for row in matrix]

    fig = go.Figure(go.Heatmap(
        z=z,
        x=topics_8,
        y=SOURCES,
        text=text,
        texttemplate="%{text}",
        colorscale="Blues",
        showscale=True,
        colorbar=dict(title="% da cobertura"),
        hovertemplate="<b>%{y}</b><br>%{x}: %{z}% das notícias<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="Perfil editorial por portal — distribuição de cobertura por tema",
                   font=dict(size=18)),
        xaxis_title="",
        yaxis_title="",
        height=420,
        margin=dict(l=160, r=40, t=70, b=80),
        plot_bgcolor="#fafafa",
    )
    return fig


if __name__ == "__main__":
    print("Gerando visualizações com dados simulados...")

    fig1 = make_heatmap()
    fig2 = make_topic_evolution()
    fig3 = make_source_profile()

    fig1.show()
    fig2.show()
    fig3.show()

    print("Três gráficos abertos no browser.")
    print("Estes são os mesmos gráficos que seriam exibidos no dashboard")
    print("com dados reais do banco de dados do Observatório.")
