"""
Exporta todas as conversas do banco em formato legível para análise.

Uso dentro do container:
    docker exec sales_agent_api python scripts/export_conversations.py

O arquivo gerado fica em /tmp/conversas_relatorio.txt dentro do container.
Para baixar para a máquina local:
    docker cp sales_agent_api:/tmp/conversas_relatorio.txt ~/Desktop/conversas_relatorio.txt
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import asyncpg

_SP_TZ = ZoneInfo("America/Sao_Paulo")

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def pg_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def fmt_dt(dt) -> str:
    if dt is None:
        return "-"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_SP_TZ).strftime("%d/%m/%Y %H:%M")


async def main() -> None:
    dsn = pg_dsn(DATABASE_URL)
    if not dsn:
        print("Erro: DATABASE_URL não definida.", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(dsn)

    leads = await conn.fetch(
        """
        SELECT phone_number, name, stage, course_slug, script_step,
               followup_status, followup_step,
               price_sent_at, created_at, last_inbound_at
        FROM leads
        ORDER BY last_inbound_at DESC NULLS LAST, created_at DESC
        """
    )

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    lines: list[str] = []

    lines.append("╔" + "═" * 78 + "╗")
    lines.append("║" + f"  CONVERSAS COMPLETAS — gerado em {now_str} UTC".ljust(78) + "║")
    lines.append("║" + f"  Total de leads: {len(leads)}".ljust(78) + "║")
    lines.append("╚" + "═" * 78 + "╝")

    for idx, lead in enumerate(leads, start=1):
        phone = lead["phone_number"]
        name  = lead["name"] or "(sem nome)"
        stage = lead["stage"]
        course = lead["course_slug"] or "?"
        step  = lead["script_step"]
        fu_status = lead["followup_status"] or "-"
        price_sent = "sim" if lead["price_sent_at"] else "não"
        created    = fmt_dt(lead["created_at"])
        last_msg   = fmt_dt(lead["last_inbound_at"])

        msgs = await conn.fetch(
            """
            SELECT role, content, created_at
            FROM conversations
            WHERE phone_number = $1
            ORDER BY created_at ASC
            """,
            phone,
        )

        lines.append("")
        lines.append("┌" + "─" * 78 + "┐")
        lines.append("│" + f"  #{idx:03d}  {name}".ljust(78) + "│")
        lines.append("│" + f"  📱 {phone}".ljust(78) + "│")
        lines.append("│" + f"  Curso: {course}  │  Estágio: {stage}  │  Step: {step}  │  Preço enviado: {price_sent}".ljust(78) + "│")
        lines.append("│" + f"  Follow-up: {fu_status}  │  Criado: {created}  │  Última msg: {last_msg}".ljust(78) + "│")
        lines.append("│" + f"  Total de mensagens: {len(msgs)}".ljust(78) + "│")
        lines.append("└" + "─" * 78 + "┘")

        if not msgs:
            lines.append("  (sem mensagens registradas)")
        else:
            for msg in msgs:
                role    = msg["role"]
                ts      = fmt_dt(msg["created_at"])
                content = (msg["content"] or "").strip()

                if role == "user":
                    lines.append("")
                    lines.append(f"  ┌─ 👤 LEAD  [{ts}]")
                    for part in content.splitlines():
                        lines.append(f"  │  {part}")
                    lines.append(f"  └{'─' * 60}")
                else:
                    lines.append("")
                    lines.append(f"  ┌─ 🤖 AGENTE  [{ts}]")
                    for part in content.splitlines():
                        lines.append(f"  │  {part}")
                    lines.append(f"  └{'─' * 60}")

    lines.append("")
    lines.append("╔" + "═" * 78 + "╗")
    lines.append("║" + "  FIM DO RELATÓRIO".ljust(78) + "║")
    lines.append("╚" + "═" * 78 + "╝")

    await conn.close()

    output   = "\n".join(lines)
    out_file = "/tmp/conversas_relatorio.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"✅ Relatório salvo em: {out_file}")
    print(f"   Leads exportados : {len(leads)}")
    print()
    print("Para copiar para o Desktop:")
    print("  docker cp sales_agent_api:/tmp/conversas_relatorio.txt ~/Desktop/conversas_relatorio.txt")


if __name__ == "__main__":
    asyncio.run(main())
