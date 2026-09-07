"""Publicação automática do carrossel diário no Instagram via Graph API.

Fluxo (API de publicação de conteúdo do Instagram, para contas Business):
  1. Renderiza os cards (instagram/generate_cards.py) e salva os bytes de
     cada imagem na tabela `instagram_cards` — o serviço `bot` (que tem
     domínio público) expõe cada uma em /instagram/<data>/<posição>.png,
     porque a API do Instagram só aceita `image_url`, nunca upload direto.
  2. Cria um container de mídia por imagem (is_carousel_item=true).
  3. Cria o container do carrossel (media_type=CAROUSEL) com os filhos e a
     legenda.
  4. Aguarda o container ficar pronto (status_code=FINISHED) e publica.

Publica no máximo uma vez por dia (tabela `instagram_post_logs`, com
UniqueConstraint em `date` filtrado por status="published" — uma falha não
bloqueia a tentativa seguinte, só um sucesso).

Requer as variáveis de ambiente:
  INSTAGRAM_ACCESS_TOKEN      — token de um System User do Meta Business
                                 Suite, com permissão de publicar na conta
  INSTAGRAM_BUSINESS_ACCOUNT_ID — ID da conta Business do Instagram
  INSTAGRAM_IMAGE_BASE_URL    — URL pública do serviço `bot` (ex.:
                                 https://<serviço>.up.railway.app)
"""
import os
import time
from datetime import date, datetime, timedelta

import requests
from sqlalchemy.exc import IntegrityError

from db.connection import get_session
from db.models import InstagramCard, InstagramPostLog
from instagram.generate_cards import fetch_card_data, render_carousel, EXCLUDED_TOPIC_SLUGS

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Tempo máximo esperando o container do carrossel ficar pronto (status_code
# FINISHED) antes de publicar. Containers com poucas imagens costumam ficar
# prontos em poucos segundos, mas a API não garante um teto.
CONTAINER_READY_TIMEOUT_S = 90
CONTAINER_POLL_INTERVAL_S = 5


def _manaus_now() -> datetime:
    return datetime.utcnow() - timedelta(hours=4)


def _manaus_today() -> date:
    return _manaus_now().date()


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value else None


class PublishError(Exception):
    pass


def _graph_call(method: str, path: str, **params) -> dict:
    url = f"{GRAPH_API_BASE}/{path}"
    response = requests.request(method, url, params=params, timeout=30)
    data = response.json()
    if response.status_code >= 400 or "error" in data:
        message = data.get("error", {}).get("message", response.text)
        raise PublishError(f"Graph API ({path}): {message}")
    return data


def _save_cards_to_db(ref_date: date, images: list) -> None:
    session = get_session()
    try:
        for i, img in enumerate(images, start=1):
            from io import BytesIO
            buf = BytesIO()
            img.save(buf, format="PNG")
            image_bytes = buf.getvalue()

            existing = session.query(InstagramCard).filter_by(date=ref_date, position=i).first()
            if existing:
                existing.image_data = image_bytes
            else:
                session.add(InstagramCard(date=ref_date, position=i, image_data=image_bytes))
        session.commit()
    finally:
        session.close()


def _create_carousel_item(ig_user_id: str, image_url: str, access_token: str) -> str:
    data = _graph_call(
        "POST", f"{ig_user_id}/media",
        image_url=image_url, is_carousel_item="true", access_token=access_token,
    )
    return data["id"]


def _create_carousel_container(ig_user_id: str, children_ids: list[str], caption: str, access_token: str) -> str:
    data = _graph_call(
        "POST", f"{ig_user_id}/media",
        media_type="CAROUSEL", children=",".join(children_ids), caption=caption,
        access_token=access_token,
    )
    return data["id"]


def _wait_until_ready(creation_id: str, access_token: str) -> None:
    deadline = time.monotonic() + CONTAINER_READY_TIMEOUT_S
    while time.monotonic() < deadline:
        data = _graph_call("GET", creation_id, fields="status_code", access_token=access_token)
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise PublishError(f"Container {creation_id} falhou no processamento (status ERROR).")
        time.sleep(CONTAINER_POLL_INTERVAL_S)
    raise PublishError(f"Container {creation_id} não ficou pronto em {CONTAINER_READY_TIMEOUT_S}s.")


def _publish_container(ig_user_id: str, creation_id: str, access_token: str) -> str:
    data = _graph_call(
        "POST", f"{ig_user_id}/media_publish",
        creation_id=creation_id, access_token=access_token,
    )
    return data["id"]


def _log_result(session, ref_date: date, status: str, media_id: str | None = None, error: str | None = None):
    try:
        session.add(InstagramPostLog(date=ref_date, status=status, media_id=media_id, error=error))
        session.commit()
    except IntegrityError:
        session.rollback()


def run_instagram_publish(send_after_hour: int = 19, force: bool = False) -> str | None:
    """Gera e publica o carrossel do dia no Instagram. Roda a cada ciclo de
    coleta, mas só publica de fato uma vez por dia, depois de `send_after_hour`
    (horário de Manaus) — publicar cedo demais rende um carrossel com poucos
    temas, porque a coleta do dia ainda está no começo.

    Retorna o media_id publicado, ou None se não publicou (ainda não é hora,
    já publicou hoje, sem temas elegíveis, ou faltou configuração).
    """
    access_token = _env("INSTAGRAM_ACCESS_TOKEN")
    ig_user_id = _env("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    base_url = _env("INSTAGRAM_IMAGE_BASE_URL")
    missing = [name for name, value in [
        ("INSTAGRAM_ACCESS_TOKEN", access_token),
        ("INSTAGRAM_BUSINESS_ACCOUNT_ID", ig_user_id),
        ("INSTAGRAM_IMAGE_BASE_URL", base_url),
    ] if not value]
    if missing:
        print(f"  [Instagram] Variáveis de ambiente ausentes: {', '.join(missing)} — publicação desativada.")
        return None

    manaus_now = _manaus_now()
    if not force and manaus_now.hour < send_after_hour:
        print(f"  [Instagram] Aguardando {send_after_hour}:00 (agora {manaus_now.hour}:00 em Manaus)")
        return None

    today = _manaus_today()
    session = get_session()
    try:
        if not force and session.query(InstagramPostLog).filter_by(date=today, status="published").first():
            print("  [Instagram] Já publicado hoje.")
            return None
    finally:
        session.close()

    data = fetch_card_data(today)
    if not data["topics"]:
        print(f"  [Instagram] Nenhum tema elegível ainda para {today} "
              f"(excluindo {sorted(EXCLUDED_TOPIC_SLUGS)}) — tenta de novo no próximo ciclo.")
        return None

    print(f"  [Instagram] Gerando carrossel de {today} ({len(data['topics'])} temas)...")
    images, caption = render_carousel(today, data)
    _save_cards_to_db(today, images)

    image_urls = [f"{base_url}/instagram/{today.isoformat()}/{i}.png" for i in range(1, len(images) + 1)]

    session = get_session()
    try:
        children_ids = [_create_carousel_item(ig_user_id, url, access_token) for url in image_urls]
        carousel_id = _create_carousel_container(ig_user_id, children_ids, caption, access_token)
        _wait_until_ready(carousel_id, access_token)
        media_id = _publish_container(ig_user_id, carousel_id, access_token)
        print(f"  [Instagram] Publicado — media_id={media_id}")
        _log_result(session, today, "published", media_id=media_id)
        return media_id
    except Exception as e:
        print(f"  [Instagram] Falha ao publicar: {e}")
        _log_result(session, today, "failed", error=str(e))
        return None
    finally:
        session.close()
