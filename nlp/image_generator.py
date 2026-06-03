import os
import httpx
from datetime import date, datetime, timedelta
from db.connection import get_session
from db.models import DailySummary


def _manaus_yesterday() -> date:
    return (datetime.utcnow() - timedelta(hours=4)).date() - timedelta(days=1)


def _build_prompt(summary_text: str, summary_date: date) -> str:
    date_str = summary_date.strftime("%d/%m/%Y")
    excerpt = summary_text[:400].strip()
    return (
        f"Infográfico editorial digital ilustrado, estilo desenho moderno limpo e informativo, "
        f"formato horizontal 16:9, alta qualidade visual. "
        f"Título 'Manaus em Pauta – {date_str}' em destaque no topo da imagem. "
        f"Cena central: avenida movimentada de Manaus ao final do dia, arquitetura tropical, "
        f"vegetação amazônica exuberante ao fundo, céu com tons quentes. "
        f"Moradores anônimos (sem rostos identificáveis) consultando celulares com notícias. "
        f"Painéis temáticos ao redor da cena central ilustrando visualmente os acontecimentos: {excerpt}. "
        f"Rodapé com texto 'Observatório de Manaus' e 'Informação que conecta. Dados que transformam Manaus.' "
        f"Estilo jornalístico editorial, informativo e leve, sem humor, sem rostos identificáveis, "
        f"sem marcas comerciais, sem representação de políticos reais. "
        f"Paleta de cores: verdes tropicais, azul céu, âmbar e branco. Todo texto em português."
    )


def generate_daily_image() -> bool:
    """Gera a imagem do dia anterior se ainda não existir. Retorna True se gerou."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("  [ImageGen] OPENAI_API_KEY não configurada — imagem não gerada.")
        return False

    yesterday = _manaus_yesterday()
    session = get_session()
    try:
        summary = session.query(DailySummary).filter_by(
            date=yesterday, topic_id=None
        ).first()

        if not summary:
            print(f"  [ImageGen] Sem resumo para {yesterday} — imagem não gerada.")
            return False

        if summary.image_data:
            print(f"  [ImageGen] Imagem de {yesterday} já existe — pulando.")
            return False

        print(f"  [ImageGen] Gerando imagem para {yesterday}...")
        prompt = _build_prompt(summary.summary, yesterday)

        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url

        image_bytes = httpx.get(image_url, timeout=30).content
        summary.image_data = image_bytes
        session.commit()
        print(f"  [ImageGen] Imagem gerada e salva ({len(image_bytes):,} bytes).")
        return True

    except Exception as e:
        print(f"  [ImageGen] Erro: {e}")
        session.rollback()
        return False
    finally:
        session.close()
