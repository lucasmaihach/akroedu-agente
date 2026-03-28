"""
Exporta todas as conversas do banco e gera um relatório para análise.
Uso: python scripts/export_conversations.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime

import asyncpg

DATABASE_URL = os.environ.get("DATABASE_URL", "")


def pg_dsn(url: str) -> str:
    """Converte URL asyncpg/sqlalchemy para dsn puro do asyncpg."""
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> None:
    dsn = pg_dsn(DATABASE_URL)
    if not dsn:
        print("Erro: DATABASE_URL não definida.", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(dsn)

    leads = await conn.fetch(
        """
        SELECT phone_number, name, stage, script_step,
               followup_status, followup_step, followup_scenario,
               price_sent_at, created_at, last_inbound_at
        FROM leads
        ORDER BY created_at DESC
        """
    )

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"RELATÓRIO DE CONVERSAS — gerado em {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    lines.append(f"Total de leads: {len(leads)}")
    lines.append("=" * 80)

    for lead in leads:
        phone = lead["phone_number"]
        name = lead["name"] or "(sem nome)"
        stage = lead["stage"]
        step = lead["script_step"]
        fu_status = lead["followup_status"]
        fu_step = lead["followup_step"]
        fu_scenario = lead["followup_scenario"] or "-"
        price_sent = "sim" if lead["price_sent_at"] else "não"
        created = lead["created_at"].strftime("%d/%m/%Y %H:%M") if lead["created_at"] else "-"
        last_inbound = lead["last_inbound_at"].strftime("%d/%m/%Y %H:%M") if lead["last_inbound_at"] else "-"

        msgs = await conn.fetch(
            """
            SELECT role, content, created_at
            FROM conversations
            WHERE phone_number = $1
            ORDER BY created_at
            """,
            phone,
        )

        lines.append("")
        lines.append("-" * 80)
        lines.append(f"LEAD: {name}  |  {phone}")
        lines.append(
            f"Estágio: {stage}  |  Script step: {step}  |  Preço enviado: {price_sent}"
        )
        lines.append(
            f"Follow-up: {fu_status}  |  Step FU: {fu_step}  |  Cenário: {fu_scenario}"
        )
        lines.append(f"Criado: {created}  |  Último inbound: {last_inbound}")
        lines.append(f"Total de mensagens: {len(msgs)}")
        lines.append("")

        if not msgs:
            lines.append("  (sem mensagens registradas)")
        else:
            for msg in msgs:
                role = "LEAD     " if msg["role"] == "user" else "AGENTE   "
                ts = msg["created_at"].strftime("%d/%m %H:%M") if msg["created_at"] else "??/??"
                content = (msg["content"] or "").replace("\n", " ").strip()
                lines.append(f"  [{ts}] {role}: {content}")

    lines.append("")
    lines.append("=" * 80)
    lines.append("FIM DO RELATÓRIO")
    lines.append("=" * 80)

    await conn.close()

    output = "\n".join(lines)
    out_file = "/tmp/conversas_relatorio.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"✅ Relatório salvo em {out_file}")
    print(f"   Total de leads: {len(leads)}")


if __name__ == "__main__":
    asyncio.run(main())
