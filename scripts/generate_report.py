#!/usr/bin/env python3
"""
Script para gerar relatórios de vendas do Sales Agent.

Extrai dados do banco de dados (PostgreSQL) e SprintHub,
e gera um relatório em HTML/JSON.

Uso:
    python scripts/generate_report.py
    python scripts/generate_report.py --format json
    python scripts/generate_report.py --days 7
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.database import AsyncSessionLocal
from app.db.orm_models import LeadORM, ConversationORM
from app.models.lead import LeadStage


async def get_report(days: int = 7) -> dict:
    """Gera relatório dos últimos N dias."""
    async with AsyncSessionLocal() as session:
        # Data de início
        start_date = datetime.now() - timedelta(days=days)

        # Total de leads
        total_leads = await session.execute(
            select(func.count(LeadORM.id))
        )
        total_leads = total_leads.scalar() or 0

        # Leads por estágio
        by_stage = {}
        for stage in LeadStage:
            count = await session.execute(
                select(func.count(LeadORM.id)).where(LeadORM.stage == stage.value)
            )
            by_stage[stage.value] = count.scalar() or 0

        # Leads criados nos últimos N dias
        new_leads = await session.execute(
            select(func.count(LeadORM.id)).where(LeadORM.created_at >= start_date)
        )
        new_leads = new_leads.scalar() or 0

        # Leads convertidos
        converted = await session.execute(
            select(func.count(LeadORM.id)).where(LeadORM.stage == LeadStage.CONVERTED.value)
        )
        converted = converted.scalar() or 0

        # Taxa de conversão
        if new_leads > 0:
            conversion_rate = (converted / new_leads) * 100
        else:
            conversion_rate = 0

        # Leads escalados
        escalated = await session.execute(
            select(func.count(LeadORM.id)).where(LeadORM.is_escalated == True)
        )
        escalated = escalated.scalar() or 0

        # Total de mensagens
        total_messages = await session.execute(
            select(func.count(ConversationORM.id))
        )
        total_messages = total_messages.scalar() or 0

        # Mensagens nos últimos N dias
        recent_messages = await session.execute(
            select(func.count(ConversationORM.id)).where(ConversationORM.created_at >= start_date)
        )
        recent_messages = recent_messages.scalar() or 0

        # Leads por curso
        from app.models.lead import CourseSlug
        by_course = {}
        for course in CourseSlug:
            count = await session.execute(
                select(func.count(LeadORM.id)).where(LeadORM.course_slug == course.value)
            )
            by_course[course.value] = count.scalar() or 0

        # Leads em estágio "HOT" (mais propensos a converter)
        hot_leads = await session.execute(
            select(func.count(LeadORM.id)).where(LeadORM.stage == LeadStage.HOT.value)
        )
        hot_leads = hot_leads.scalar() or 0

    report = {
        "generated_at": datetime.now().isoformat(),
        "period_days": days,
        "summary": {
            "total_leads": total_leads,
            "new_leads_period": new_leads,
            "converted_leads": converted,
            "conversion_rate_percent": round(conversion_rate, 2),
            "escalated_leads": escalated,
            "hot_leads": hot_leads,
            "total_messages": total_messages,
            "messages_period": recent_messages,
        },
        "by_stage": by_stage,
        "by_course": by_course,
    }

    return report


def print_report_text(report: dict):
    """Imprime o relatório em formato texto."""
    print("\n" + "="*70)
    print("📊 RELATÓRIO DE SALES AGENT")
    print("="*70)
    print(f"Gerado em: {report['generated_at']}")
    print(f"Período: Últimos {report['period_days']} dias\n")

    summary = report["summary"]
    print("📈 RESUMO")
    print("-" * 70)
    print(f"Total de leads: {summary['total_leads']}")
    print(f"Novos leads (período): {summary['new_leads_period']}")
    print(f"Leads convertidos: {summary['converted_leads']}")
    print(f"Taxa de conversão: {summary['conversion_rate_percent']}%")
    print(f"Leads escalados: {summary['escalated_leads']}")
    print(f"Leads quentes (HOT): {summary['hot_leads']}")
    print(f"Total de mensagens: {summary['total_messages']}")
    print(f"Mensagens (período): {summary['messages_period']}\n")

    print("🎯 LEADS POR ESTÁGIO")
    print("-" * 70)
    for stage, count in report["by_stage"].items():
        bar = "█" * (count // 2) if count > 0 else ""
        print(f"{stage:15} {count:4} {bar}")

    print("\n📚 LEADS POR CURSO")
    print("-" * 70)
    for course, count in report["by_course"].items():
        bar = "█" * (count // 2) if count > 0 else ""
        print(f"{course:15} {count:4} {bar}")

    print("\n" + "="*70 + "\n")


def generate_html_report(report: dict, output_file: Path):
    """Gera relatório em HTML."""
    summary = report["summary"]

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Relatório Sales Agent</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
            h1 {{ color: #333; text-align: center; }}
            h2 {{ color: #555; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
            .summary {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 20px 0; }}
            .stat {{ background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #007bff; }}
            .stat-label {{ color: #666; margin-top: 5px; }}
            .chart {{ margin: 20px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #007bff; color: white; }}
            tr:hover {{ background-color: #f5f5f5; }}
            .footer {{ text-align: center; color: #999; margin-top: 30px; font-size: 0.9em; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Relatório Sales Agent</h1>
            <p style="text-align: center; color: #666;">
                Gerado em {report['generated_at']}<br>
                Período: Últimos {report['period_days']} dias
            </p>

            <h2>📈 Resumo Executivo</h2>
            <div class="summary">
                <div class="stat">
                    <div class="stat-number">{summary['total_leads']}</div>
                    <div class="stat-label">Total de Leads</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{summary['new_leads_period']}</div>
                    <div class="stat-label">Novos (período)</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{summary['conversion_rate_percent']}%</div>
                    <div class="stat-label">Taxa de Conversão</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{summary['converted_leads']}</div>
                    <div class="stat-label">Convertidos</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{summary['escalated_leads']}</div>
                    <div class="stat-label">Escalados</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{summary['hot_leads']}</div>
                    <div class="stat-label">Leads Quentes</div>
                </div>
            </div>

            <h2>🎯 Leads por Estágio</h2>
            <table>
                <thead>
                    <tr><th>Estágio</th><th>Quantidade</th></tr>
                </thead>
                <tbody>
    """

    for stage, count in report["by_stage"].items():
        html += f"<tr><td>{stage}</td><td>{count}</td></tr>"

    html += """
                </tbody>
            </table>

            <h2>📚 Leads por Curso</h2>
            <table>
                <thead>
                    <tr><th>Curso</th><th>Quantidade</th></tr>
                </thead>
                <tbody>
    """

    for course, count in report["by_course"].items():
        html += f"<tr><td>{course}</td><td>{count}</td></tr>"

    html += """
                </tbody>
            </table>

            <div class="footer">
                <p>Sales Agent © 2024 - Agente de Vendas Inteligente</p>
            </div>
        </div>
    </body>
    </html>
    """

    output_file.write_text(html)
    print(f"✅ Relatório HTML salvo em: {output_file}")


async def main():
    import sys

    days = 7
    format_type = "text"

    # Parse argumentos
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        days = int(sys.argv[idx + 1])

    if "--format" in sys.argv:
        idx = sys.argv.index("--format")
        format_type = sys.argv[idx + 1]

    # Gera relatório
    print("📊 Gerando relatório...")
    report = await get_report(days=days)

    # Exibe/salva conforme o formato
    if format_type == "json":
        print(json.dumps(report, indent=2))
        Path("report.json").write_text(json.dumps(report, indent=2))
        print("✅ Relatório JSON salvo em: report.json")
    elif format_type == "html":
        generate_html_report(report, Path("report.html"))
    else:
        print_report_text(report)


if __name__ == "__main__":
    asyncio.run(main())
