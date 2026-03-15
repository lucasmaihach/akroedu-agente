import asyncio
import structlog
from typing import Optional

from app.config import settings
from app.models.lead import Lead, CourseSlug
from app.memory.session import (
    get_lead,
    update_lead_field,
    set_script_lock,
    release_script_lock,
    get_cached_media_id,
    cache_media_id,
)
from app.services import whatsapp
from app.script.schedules.curso_1_script import CURSO_1_SCRIPT
from app.script.schedules.curso_2_script import CURSO_2_SCRIPT
from app.script.schedules.pos_fisio_neuro_script import POS_FISIO_NEURO_SCRIPT

logger = structlog.get_logger()


async def _send_text_bubbles(phone: str, text, delay_between: float = 1.2) -> None:
    """
    Envia texto ou lista de textos como bolhas separadas no WhatsApp.
    Simula o comportamento humano de mandar várias mensagens curtas.
    """
    items = text if isinstance(text, list) else [text]
    for i, item in enumerate(items):
        await whatsapp.send_text(to=phone, text=item)
        if i < len(items) - 1:
            await asyncio.sleep(delay_between)


async def _send_image(phone: str, image: str) -> None:
    """
    Envia uma imagem ao lead.
    - Se começar com 'http': envia por URL pública.
    - Se tiver extensão de imagem: faz upload local para a Meta (com cache no Redis).
    - Caso contrário: trata como media_id já hospedado.
    """
    if image.startswith("http"):
        await whatsapp.send_image_by_url(to=phone, image_url=image)
    elif "." in image:
        media_id = await get_cached_media_id(image)
        if not media_id:
            local_path = f"/app/images/{image}"
            logger.info("📤 Fazendo upload da imagem para a Meta.", file=image)
            media_id = await whatsapp.upload_image(local_path)
            await cache_media_id(image, media_id)
            logger.info("✅ Upload de imagem concluído.", file=image, media_id=media_id)
        await whatsapp.send_image_by_media_id(to=phone, media_id=media_id)
    else:
        await whatsapp.send_image_by_media_id(to=phone, media_id=image)


# Mapa de curso → script de áudios
SCRIPTS = {
    CourseSlug.CURSO_1: CURSO_1_SCRIPT,
    CourseSlug.CURSO_2: CURSO_2_SCRIPT,
    CourseSlug.POS_FISIO_NEURO: POS_FISIO_NEURO_SCRIPT,
}


async def run_script_step(phone: str) -> bool:
    """
    Executa o próximo passo do script de áudios para o lead.
    Retorna True se enviou alguma coisa, False se o script terminou ou está em lock.
    """
    lead = await get_lead(phone)
    if lead is None:
        logger.warning("Lead não encontrado para execução do script.", phone=phone)
        return False

    # Se já foi escalado, para o script
    if lead.is_escalated:
        return False

    script = SCRIPTS.get(lead.course_slug)
    if script is None:
        logger.warning("Script não encontrado para o curso.", course=lead.course_slug)
        return False

    step_index = lead.script_step

    # Script finalizado
    if step_index >= len(script):
        logger.info("✅ Script finalizado.", phone=phone, course=lead.course_slug)
        return False

    # Tenta adquirir o lock para evitar duplo disparo
    locked = await set_script_lock(phone, ttl_seconds=120)
    if not locked:
        logger.info("Script lock ativo, pulando.", phone=phone)
        return False

    step = script[step_index]

    try:
        # Aguarda o delay definido no passo (em segundos)
        delay = step.get("delay_seconds", 0)
        if delay > 0:
            logger.info(
                "⏳ Aguardando delay do script.",
                phone=phone,
                step=step_index,
                delay=delay,
            )
            await asyncio.sleep(delay)

        # Verifica novamente se o lead ainda está ativo (pode ter escalado durante o delay)
        lead = await get_lead(phone)
        if lead is None or lead.is_escalated:
            return False

        # Envia acolhimento personalizado antes do bloco (se existir variações).
        # A variação é escolhida deterministicamente pelo telefone — mesmo lead,
        # mesmo tom em toda a conversa. Substitui "[nome]" pelo primeiro nome.
        acolhimento_list = step.get("acolhimento_variations")
        if acolhimento_list:
            nome = ""
            if lead and lead.name:
                nome = lead.name.strip().split()[0]
            variation_idx = abs(hash(phone)) % len(acolhimento_list)
            variation = acolhimento_list[variation_idx]
            # Variação pode ser str ou list[str] (múltiplas bolhas)
            parts = variation if isinstance(variation, list) else [variation]
            for i, part in enumerate(parts):
                if nome:
                    part = part.replace("[nome]", nome)
                else:
                    part = part.replace(", [nome]", "").replace("[nome]", "").strip()
                await whatsapp.send_text(to=phone, text=part)
                if i < len(parts) - 1:
                    await asyncio.sleep(1.2)
            await asyncio.sleep(1.5)

        # Envia mensagem de texto pré-passo (opcional) — suporta str ou list[str]
        pre_text = step.get("pre_text")
        if pre_text:
            await _send_text_bubbles(phone, pre_text)
            await asyncio.sleep(1.5)

        # Envia imagens ANTES do áudio (notícias, prints, etc.)
        images_before = step.get("images") or []
        for img in images_before:
            await _send_image(phone, img)
            await asyncio.sleep(1.5)

        # Envia o áudio
        audio = step.get("audio")
        if audio:
            if audio.startswith("http"):
                # URL externa — envia diretamente por link
                await whatsapp.send_audio_by_url(to=phone, audio_url=audio)
            elif "." in audio:
                # Arquivo local — faz upload para a Meta (com cache no Redis)
                # Isso garante que apareça como PTT com ondas de voz no WhatsApp
                media_id = await get_cached_media_id(audio)
                if not media_id:
                    local_path = f"/app/audios/{audio}"
                    logger.info("📤 Fazendo upload do áudio para a Meta.", file=audio)
                    media_id = await whatsapp.upload_audio(local_path)
                    await cache_media_id(audio, media_id)
                    logger.info("✅ Upload concluído e media_id em cache.", file=audio, media_id=media_id)
                await whatsapp.send_audio_by_media_id(to=phone, media_id=media_id)
            else:
                # Já é um media_id hospedado na Meta
                await whatsapp.send_audio_by_media_id(to=phone, media_id=audio)
            await asyncio.sleep(1.5)

        # Envia texto intermediário após áudio (antes das imagens pós-áudio)
        mid_text = step.get("mid_text")
        if mid_text:
            await asyncio.sleep(2)
            await _send_text_bubbles(phone, mid_text)
            await asyncio.sleep(1.5)

        # Envia imagens APÓS o áudio (diploma, certificados, etc.)
        images_after = step.get("images_post") or []
        for img in images_after:
            await _send_image(phone, img)
            await asyncio.sleep(1.5)

        # Envia mensagem de texto pós-áudio (opcional) — suporta str ou list[str]
        post_text = step.get("post_text")
        if post_text:
            await asyncio.sleep(2)
            await _send_text_bubbles(phone, post_text)

        # Avança o passo do script
        next_step_index = step_index + 1
        await update_lead_field(phone, script_step=next_step_index)

        logger.info(
            "🔊 Passo do script executado.",
            phone=phone,
            step=step_index,
            course=lead.course_slug.value,
        )

        # Se o próximo passo tem trigger="auto", agenda execução automática
        # sem precisar esperar uma mensagem do lead
        if next_step_index < len(script):
            next_step = script[next_step_index]
            if next_step.get("trigger") == "auto":
                logger.info(
                    "⏩ Próximo passo é auto — agendando execução automática.",
                    phone=phone,
                    next_step=next_step_index,
                )
                asyncio.create_task(_delayed_step(phone))

        return True

    except Exception as e:
        logger.error("❌ Erro ao executar passo do script.", phone=phone, step=step_index, error=str(e))
        return False

    finally:
        await release_script_lock(phone)


async def schedule_next_step(phone: str) -> None:
    """
    Agenda a execução do próximo passo do script em background.
    Chamado após cada interação do lead para avançar o funil.
    """
    asyncio.create_task(_delayed_step(phone))


async def _delayed_step(phone: str) -> None:
    """Executa o próximo passo do script em background."""
    lead = await get_lead(phone)
    if lead is None:
        return

    script = SCRIPTS.get(lead.course_slug)
    if script is None or lead.script_step >= len(script):
        return

    step = script[lead.script_step]
    trigger = step.get("trigger", "auto")

    # Só executa automaticamente se o trigger for "auto"
    if trigger == "auto":
        await run_script_step(phone)
    # Se trigger == "response", aguarda próxima mensagem do lead (feito no webhook)
