import asyncio
import structlog
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

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
from app.script.schedules.curso_1_script import CURSO_1_SCRIPT, CURSO_1_CONFIG
from app.script.schedules.curso_2_script import CURSO_2_SCRIPT, CURSO_2_CONFIG
from app.script.schedules.pos_fisio_neuro_script import POS_FISIO_NEURO_SCRIPT, POS_FISIO_NEURO_CONFIG
from app.followup.service import arm_followup_waiting_reply, mark_price_sent
from app.services.error_alert import notify_conversation_error
from app.utils.business_hours import fit_business_hours, is_within_business_hours, now_utc

logger = structlog.get_logger()


async def _send_text_bubbles(phone: str, text, delay_between: float = 1.2, msg_id: str = "") -> None:
    """
    Envia texto ou lista de textos como bolhas separadas no WhatsApp.
    Mostra indicador de digitação antes de cada bolha e aguarda tempo proporcional.
    """
    items = text if isinstance(text, list) else [text]
    for i, item in enumerate(items):
        delay = whatsapp.estimate_typing_delay(item)
        await whatsapp.send_typing_and_wait(msg_id, delay)
        await whatsapp.send_text(to=phone, text=item)
        if i < len(items) - 1:
            await asyncio.sleep(delay_between)


def _audio_history_label(audio: str) -> str:
    """Gera rótulo amigável do áudio para exibição no painel."""
    if audio.startswith("http"):
        name = Path(urlparse(audio).path).name or "audio_url"
        return f"[áudio enviado] {name}"
    if "." in audio:
        return f"[áudio enviado] {audio}"
    short_media = f"{audio[:12]}..." if len(audio) > 12 else audio
    return f"[áudio enviado] media_id={short_media}"


def _filter_orphan_media_teaser(text_or_list, has_media_assets: bool):
    """Remove frases que prometem mídia quando o passo não possui mídia configurada."""
    if has_media_assets or not text_or_list:
        return text_or_list

    def _is_orphan_teaser(line: str) -> bool:
        lower = line.lower()
        mentions_send = ("vou te mandar" in lower) or ("vou mandar" in lower)
        mentions_media = any(k in lower for k in ["notícia", "noticias", "notícia", "imagem", "foto", "print", "arquivo"])
        return mentions_send and mentions_media

    if isinstance(text_or_list, list):
        filtered = [line for line in text_or_list if not _is_orphan_teaser(str(line))]
        return filtered or None

    if isinstance(text_or_list, str) and _is_orphan_teaser(text_or_list):
        return None

    return text_or_list


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

# Mapa de curso → configurações (price_reveal_step, price_skip_to_step, etc.)
SCRIPT_CONFIGS = {
    CourseSlug.CURSO_1: CURSO_1_CONFIG,
    CourseSlug.CURSO_2: CURSO_2_CONFIG,
    CourseSlug.POS_FISIO_NEURO: POS_FISIO_NEURO_CONFIG,
}


async def _retry_script_step_after_lock(phone: str, attempts: int = 6, interval_seconds: float = 3.0) -> None:
    """
    Quando um inbound chega enquanto outro passo ainda está em execução,
    re-tenta avançar o script por alguns ciclos para não perder o gatilho.
    """
    for attempt in range(1, attempts + 1):
        await asyncio.sleep(interval_seconds)
        sent = await run_script_step(phone, retry_on_lock=False)
        if sent:
            logger.info("🔁 Re-tentativa após lock executou passo com sucesso.", phone=phone, attempt=attempt)
            return

    logger.info("ℹ️ Re-tentativas após lock encerradas sem novo envio.", phone=phone)


async def _run_script_when_business_opens(phone: str, wait_seconds: float) -> None:
    """Reagenda execução de script para o próximo horário comercial."""
    try:
        await asyncio.sleep(wait_seconds)
        # Libera o lock de reagendamento e executa normalmente.
        await release_script_lock(phone)
        await run_script_step(phone, retry_on_lock=False)
    except Exception as e:
        logger.error("❌ Falha no reagendamento de script para horário comercial.", phone=phone, error=str(e))
        await release_script_lock(phone)


async def run_script_step(phone: str, retry_on_lock: bool = True, acolhimento_override: Optional[str] = None) -> bool:
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

    # Não inicia script antes da resposta ao template inicial.
    if lead.awaiting_template_reply or lead.pending_welcome_template:
        logger.info(
            "⏸️ Script bloqueado aguardando resposta ao template inicial.",
            phone=phone,
            awaiting_template_reply=lead.awaiting_template_reply,
            pending_welcome_template=lead.pending_welcome_template,
        )
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

    # Fora do horário comercial: reagenda para próxima janela útil.
    current_time = now_utc()
    if not is_within_business_hours(current_time):
        next_at = fit_business_hours(current_time)
        wait_seconds = max(1.0, (next_at - current_time).total_seconds())
        lock_ttl = max(180, int(wait_seconds) + 120)
        scheduled = await set_script_lock(phone, ttl_seconds=lock_ttl)

        if scheduled:
            logger.info(
                "🕒 Script fora do horário comercial — reagendado.",
                phone=phone,
                step=step_index,
                next_at=str(next_at),
                wait_seconds=int(wait_seconds),
            )
            asyncio.create_task(_run_script_when_business_opens(phone, wait_seconds))
        else:
            logger.info("🕒 Script já possui reagendamento ativo fora do horário.", phone=phone, step=step_index)

        return False

    # Tenta adquirir o lock para evitar duplo disparo
    locked = await set_script_lock(phone, ttl_seconds=120)
    if not locked:
        logger.info("Script lock ativo, pulando.", phone=phone)
        if retry_on_lock:
            asyncio.create_task(_retry_script_step_after_lock(phone))
        return False

    step = script[step_index]

    # ID da última mensagem recebida — necessário para typing indicator
    msg_id = lead.last_received_msg_id or ""

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
        msg_id = lead.last_received_msg_id or ""

        # Envia acolhimento antes do bloco.
        # Se o dispatcher gerou um acolhimento contextual via LLM (acolhimento_override),
        # ele tem prioridade. Caso contrário, usa as variações pré-definidas no script.
        acolhimento_list = step.get("acolhimento_variations")
        if acolhimento_override:
            # Acolhimento contextual gerado pelo LLM: envia como bolha única.
            delay = whatsapp.estimate_typing_delay(acolhimento_override)
            await whatsapp.send_typing_and_wait(msg_id, delay)
            await whatsapp.send_text(to=phone, text=acolhimento_override)
            await asyncio.sleep(1.5)
        elif acolhimento_list:
            # Fallback: variação pré-definida escolhida deterministicamente pelo telefone.
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
                delay = whatsapp.estimate_typing_delay(part)
                await whatsapp.send_typing_and_wait(msg_id, delay)
                await whatsapp.send_text(to=phone, text=part)
                if i < len(parts) - 1:
                    await asyncio.sleep(1.2)
            await asyncio.sleep(1.5)

        images_before = step.get("images") or []
        images_after = step.get("images_post") or []
        has_media_assets = bool(images_before or images_after or step.get("audio"))

        # Envia mensagem de texto pré-passo (opcional) — suporta str ou list[str]
        pre_text = _filter_orphan_media_teaser(step.get("pre_text"), has_media_assets)
        if pre_text:
            await _send_text_bubbles(phone, pre_text, msg_id=msg_id)
            await asyncio.sleep(1.5)

        # Envia imagens ANTES do áudio (notícias, prints, etc.)
        for img in images_before:
            await _send_image(phone, img)
            await asyncio.sleep(1.5)

        # Envia o áudio
        audio = step.get("audio")
        if audio:
            # Aguarda ANTES do áudio simulando tempo de gravação.
            # O lead vê "digitando..." enquanto Taynara "grava" — muito mais natural
            # do que receber o áudio e depois ficar 60s sem resposta.
            audio_duration = step.get("audio_duration_seconds", 0)
            if audio_duration > 0:
                logger.info(
                    "⏳ Simulando gravação antes de enviar áudio.",
                    phone=phone,
                    step=step_index,
                    duration=audio_duration,
                )
                await whatsapp.send_typing_and_wait(msg_id, audio_duration)
            else:
                await asyncio.sleep(1.5)

            if audio.startswith("http"):
                # URL externa — envia diretamente por link
                await whatsapp.send_audio_by_url(
                    to=phone,
                    audio_url=audio,
                    history_label=_audio_history_label(audio),
                )
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
                await whatsapp.send_audio_by_media_id(
                    to=phone,
                    media_id=media_id,
                    history_label=_audio_history_label(audio),
                )
            else:
                # Já é um media_id hospedado na Meta
                await whatsapp.send_audio_by_media_id(
                    to=phone,
                    media_id=audio,
                    history_label=_audio_history_label(audio),
                )

            await asyncio.sleep(1.5)

        # Envia texto intermediário após áudio (antes das imagens pós-áudio)
        mid_text = step.get("mid_text")
        if mid_text:
            await _send_text_bubbles(phone, mid_text, msg_id=msg_id)
            await asyncio.sleep(1.5)

        # Envia imagens APÓS o áudio (diploma, certificados, etc.)
        for img in images_after:
            await _send_image(phone, img)
            await asyncio.sleep(1.5)

        # Envia mensagem de texto pós-áudio (opcional) — suporta str ou list[str]
        post_text = step.get("post_text")
        if post_text:
            await _send_text_bubbles(phone, post_text, msg_id=msg_id)

        # Marca explicitamente quando o bloco de preço foi enviado.
        course_config = SCRIPT_CONFIGS.get(lead.course_slug, {})
        price_offer_step = course_config.get("price_offer_step")
        if price_offer_step is not None and step_index == price_offer_step:
            await mark_price_sent(phone)

        # Avança o passo do script
        next_step_index = step_index + 1
        await update_lead_field(phone, script_step=next_step_index)

        # Quando acabamos de enviar um passo que aguarda resposta do lead,
        # armamos/reiniciamos a régua de follow-up automática.
        if step.get("trigger") == "response":
            refreshed_lead = await get_lead(phone)
            if refreshed_lead:
                await arm_followup_waiting_reply(refreshed_lead)

        logger.info(
            "🔊 Passo do script executado.",
            phone=phone,
            step=step_index,
            course=lead.course_slug.value,
        )

        # Caso especial POS Fisio Neuro:
        # após o bloco de preço, o follow-up passa a ser controlado pela régua dedicada,
        # não pelos passos automáticos legados do script.
        if lead.course_slug == CourseSlug.POS_FISIO_NEURO and price_offer_step is not None and step_index >= price_offer_step:
            await update_lead_field(phone, script_step=len(script))
            return True

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
        await notify_conversation_error(
            source="script.run_step",
            error=e,
            phone=phone,
            lead_name=lead.name if lead else None,
            stage=lead.stage.value if lead else None,
            user_message="[script execution]",
            extra={"step": step_index, "course": lead.course_slug.value if lead else "unknown"},
        )
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
