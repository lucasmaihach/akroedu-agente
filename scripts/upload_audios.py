#!/usr/bin/env python3
"""
Script para fazer upload de todos os áudios para a Meta API.

Converte automaticamente qualquer áudio (MP3, WAV, M4A) para OGG/OPUS
antes do upload — necessário para o WhatsApp renderizar como mensagem
de voz (PTT) com ondas de áudio, igual a um áudio gravado pelo celular.

Dependência: ffmpeg instalado no sistema.
  macOS:   brew install ffmpeg
  Ubuntu:  apt install ffmpeg

Uso:
    python scripts/upload_audios.py

Certifique-se de que:
    1. Os áudios estão em audios/<slug_do_curso>/
    2. O .env está preenchido com META_ACCESS_TOKEN e META_PHONE_NUMBER_ID
"""

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

from app.config import settings
from app.services.whatsapp import upload_audio

OUTPUT_FILE = Path("audio_media_ids.json")
CONVERTED_DIR = Path("audios/_converted")

# Formatos aceitos para conversão
SUPPORTED_FORMATS = [".mp3", ".ogg", ".opus", ".m4a", ".wav", ".aac", ".flac"]


# ── Conversão para OGG/OPUS ───────────────────────────────────────────────────

def check_ffmpeg() -> bool:
    """Verifica se o ffmpeg está instalado."""
    return shutil.which("ffmpeg") is not None


def convert_to_ogg_opus(input_path: Path, output_dir: Path) -> Path:
    """
    Converte um arquivo de áudio para OGG/OPUS usando ffmpeg.
    Retorna o caminho do arquivo convertido.

    OGG/OPUS é o único formato que o WhatsApp renderiza como PTT (mensagem de voz).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{input_path.stem}.ogg"

    # Se já for OGG, apenas copia (verifica o codec depois)
    if input_path.suffix.lower() == ".ogg":
        # Mesmo sendo OGG, converte para garantir o codec OPUS correto
        pass

    cmd = [
        "ffmpeg",
        "-y",                    # sobrescreve sem perguntar
        "-i", str(input_path),   # entrada
        "-c:a", "libopus",       # codec OPUS (exigido pelo WhatsApp PTT)
        "-b:a", "32k",           # bitrate ideal para voz
        "-vbr", "on",            # variable bitrate
        "-compression_level", "10",
        "-frame_duration", "60",
        "-application", "voip",  # otimizado para voz
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falhou ao converter '{input_path.name}':\n{result.stderr}"
        )

    return output_path


# ── Upload principal ──────────────────────────────────────────────────────────

async def upload_all_audios():
    """Converte para OGG/OPUS e faz upload de todos os áudios."""

    # Verifica ffmpeg
    if not check_ffmpeg():
        print("❌ ffmpeg não encontrado!")
        print("   macOS:  brew install ffmpeg")
        print("   Ubuntu: sudo apt install ffmpeg")
        sys.exit(1)

    audios_dir = Path("audios")
    media_ids: dict = {}

    if not audios_dir.exists():
        print("❌ Pasta 'audios/' não encontrada!")
        return

    print(f"\n🔄 Modo PTT ativado — todos os áudios serão convertidos para OGG/OPUS\n")

    for course_dir in sorted(audios_dir.iterdir()):
        # Ignora a pasta de convertidos e arquivos soltos
        if not course_dir.is_dir() or course_dir.name.startswith("_"):
            continue

        course_name = course_dir.name
        media_ids[course_name] = {}

        print(f"{'='*70}")
        print(f"📁 Curso: {course_name}")
        print(f"{'='*70}\n")

        # Coleta todos os áudios suportados
        audio_files = []
        for ext in SUPPORTED_FORMATS:
            audio_files.extend(sorted(course_dir.glob(f"*{ext}")))

        if not audio_files:
            print(f"⚠️  Nenhum áudio encontrado em audios/{course_name}/")
            print(f"   Formatos aceitos: {', '.join(SUPPORTED_FORMATS)}\n")
            continue

        converted_course_dir = CONVERTED_DIR / course_name

        for audio_file in audio_files:
            try:
                # 1. Converte para OGG/OPUS
                print(f"🔄 Convertendo: {audio_file.name} → OGG/OPUS...", end=" ", flush=True)
                converted_path = convert_to_ogg_opus(audio_file, converted_course_dir)
                original_size = audio_file.stat().st_size / 1024
                converted_size = converted_path.stat().st_size / 1024
                print(f"✅  ({original_size:.0f}KB → {converted_size:.0f}KB)")

                # 2. Faz upload do arquivo convertido
                print(f"📤 Enviando para Meta API...", end=" ", flush=True)
                media_id = await upload_audio(str(converted_path))
                media_ids[course_name][audio_file.stem] = media_id
                print(f"✅")
                print(f"   🔑 Media ID: {media_id}\n")

            except RuntimeError as e:
                print(f"❌ Erro na conversão")
                print(f"   {e}\n")
            except Exception as e:
                print(f"❌ Erro no upload")
                print(f"   {e}\n")

    # Salva os media_ids em JSON
    with open(OUTPUT_FILE, "w") as f:
        json.dump(media_ids, f, indent=2)

    print(f"\n{'='*70}")
    print(f"✅ Upload concluído!")
    print(f"📝 Media IDs salvos em: {OUTPUT_FILE}")
    print(f"🗑️  Arquivos convertidos em: {CONVERTED_DIR} (pode apagar)")
    print(f"{'='*70}\n")

    # Mostra resumo para copiar
    print("📋 Copie os media_ids para os seus scripts de curso:\n")
    print(json.dumps(media_ids, indent=2))
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🎤 Upload de Áudios PTT para Meta API")
    print(f"   Phone Number ID: {settings.meta_phone_number_id}")
    print(f"   Access Token:    {settings.meta_access_token[:20]}...\n")

    asyncio.run(upload_all_audios())
