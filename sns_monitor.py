#!/usr/bin/env python3
"""
Monitor do Portal da Transparência do SNS
Lê dados da API e compara com séries anuais anteriores.
"""

import warnings
warnings.filterwarnings("ignore")

import requests
import sys
import calendar
from datetime import datetime, date
from typing import Optional
import argparse

BASE_URL = "https://transparencia.sns.gov.pt/api/explore/v2.1/catalog/datasets"

# Datasets a monitorizar com os seus indicadores numéricos principais
DATASETS = {
    "intervencoes-cirurgicas": {
        "nome": "Intervenções Cirúrgicas",
        "campo_tempo": "tempo",
        "indicadores": {
            "no_intervencoes_cirurgicas_programadas": "Cirurgias Programadas",
            "no_intervencoes_cirurgicas_de_ambulatorio": "Cirurgias Ambulatório",
            "no_intervencoes_cirurgicas_urgentes": "Cirurgias Urgentes",
        },
    },
    "atendimentos-por-tipo-de-urgencia-hospitalar-link": {
        "nome": "Urgências Hospitalares",
        "campo_tempo": "tempo",
        "indicadores": {
            "urgencias_geral": "Urgências Gerais",
            "urgencias_pediatricas": "Urgências Pediátricas",
            "total_urgencias": "Total Urgências",
        },
    },
    "atividade-de-internamento-hospitalar": {
        "nome": "Internamento Hospitalar",
        "campo_tempo": "tempo",
        "indicadores": {
            "doentes_saidos": "Doentes Saídos",
            "dias_de_internamento": "Dias de Internamento",
        },
    },
    "demora-media-antes-da-cirurgia": {
        "nome": "Demora Média antes da Cirurgia",
        "campo_tempo": "tempo",
        "indicadores": {
            "demora_media_antes_da_cirurgia": "Demora Média (dias)",
        },
    },
    "ocupacao-do-internamento": {
        "nome": "Taxa de Ocupação Hospitalar",
        "campo_tempo": "tempo",
        "indicadores": {
            "taxa_anual_de_ocupacao_em_internamento": "Taxa Ocupação (%)",
        },
    },
    "partos-e-cesarianas": {
        "nome": "Partos e Cesarianas",
        "campo_tempo": "tempo",
        "indicadores": {
            "no_de_partos": "Total Partos",
            "no_de_cesarianas": "Cesarianas",
        },
    },
}


def fetch_records(dataset_id: str, campo_tempo: str, periodo: str, limit: int = 100) -> list:
    """Busca todos os registos de um dataset para um dado período (YYYY-MM)."""
    url = f"{BASE_URL}/{dataset_id}/records"
    # O campo tempo é do tipo date — filtrar por intervalo mensal
    ano, mes = periodo.split("-")
    ultimo_dia = calendar.monthrange(int(ano), int(mes))[1]
    filtro = f'{campo_tempo} >= "{periodo}-01" AND {campo_tempo} <= "{periodo}-{ultimo_dia:02d}"'
    params = {
        "where": filtro,
        "limit": limit,
        "offset": 0,
    }
    records = []
    while True:
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            print(f"  [ERRO] {dataset_id}: {e}", file=sys.stderr)
            return []

        batch = data.get("results", [])
        records.extend(batch)
        total = data.get("total_count", 0)
        params["offset"] += len(batch)
        if params["offset"] >= total or not batch:
            break
    return records


def aggregate(records: list, indicadores: dict) -> dict:
    """Soma todos os registos para os indicadores relevantes."""
    totais = {campo: 0.0 for campo in indicadores}
    contagens = {campo: 0 for campo in indicadores}
    for rec in records:
        for campo in indicadores:
            val = rec.get(campo)
            if val is not None:
                totais[campo] += float(val)
                contagens[campo] += 1
    # Para métricas que são médias (ex: demora_media, taxa_ocupacao), dividimos
    # pelo nº de registos em vez de somar
    medias = {"demora_media_antes_da_cirurgia", "taxa_anual_de_ocupacao_em_internamento"}
    resultado = {}
    for campo in indicadores:
        if campo in medias and contagens[campo] > 0:
            resultado[campo] = totais[campo] / contagens[campo]
        else:
            resultado[campo] = totais[campo]
    return resultado


def get_periodo_anterior(periodo: str) -> str:
    """Devolve o mesmo mês do ano anterior: '2025-03' -> '2024-03'."""
    ano, mes = periodo.split("-")
    return f"{int(ano) - 1}-{mes}"


def get_ultimos_periodos(periodo_atual: str, n_anos: int = 3) -> list[str]:
    """Devolve o período atual e os N anteriores (mesmo mês)."""
    ano, mes = periodo_atual.split("-")
    return [f"{int(ano) - i}-{mes}" for i in range(n_anos + 1)]


def variacao_pct(atual: float, anterior: float) -> Optional[float]:
    if anterior == 0:
        return None
    return ((atual - anterior) / anterior) * 100


def sinal(pct: Optional[float]) -> str:
    if pct is None:
        return "N/D"
    if pct > 0:
        return f"+{pct:.1f}%"
    return f"{pct:.1f}%"


def cor(pct: Optional[float], inverter: bool = False) -> str:
    """Retorna código ANSI: verde se melhora, vermelho se piora."""
    if pct is None:
        return ""
    positivo = pct > 0
    if inverter:
        positivo = not positivo
    if positivo:
        return "\033[92m"  # verde
    elif pct < 0:
        return "\033[91m"  # vermelho
    return ""


RESET = "\033[0m"

# Indicadores onde subir é mau (ex: demora, ocupação acima de 100%)
INDICADORES_INVERTER = {"demora_media_antes_da_cirurgia"}


def formatar_valor(campo: str, valor: float) -> str:
    if campo in {"taxa_anual_de_ocupacao_em_internamento"}:
        return f"{valor:.1f}%"
    if campo in {"demora_media_antes_da_cirurgia"}:
        return f"{valor:.2f} dias"
    return f"{int(valor):,}".replace(",", " ")


def run_report(periodo: str, n_anos: int, sem_cor: bool, filtro_dataset: Optional[str] = None, output: Optional[str] = None):
    periodos = get_ultimos_periodos(periodo, n_anos)
    periodo_anterior = periodos[1] if len(periodos) > 1 else None

    linhas = []

    def out(s=""):
        linhas.append(s)
        print(s)

    out(f"\n{'='*72}")
    out(f"  RELATÓRIO SNS — Período: {periodo}  |  Comparação com {n_anos} ano(s)")
    out(f"  Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    out(f"{'='*72}\n")

    datasets_a_usar = {
        k: v for k, v in DATASETS.items()
        if filtro_dataset is None or filtro_dataset in k
    }

    for dataset_id, config in datasets_a_usar.items():
        nome = config["nome"]
        campo_tempo = config["campo_tempo"]
        indicadores = config["indicadores"]

        out(f"{'─'*72}")
        out(f"  {nome}")
        out(f"{'─'*72}")

        # Busca dados para todos os períodos
        dados_por_periodo = {}
        for p in periodos:
            registos = fetch_records(dataset_id, campo_tempo, p)
            if registos:
                dados_por_periodo[p] = aggregate(registos, indicadores)
            else:
                dados_por_periodo[p] = None

        atual = dados_por_periodo.get(periodo)
        if atual is None:
            out(f"  Sem dados disponíveis para {periodo}\n")
            continue

        for campo, label in indicadores.items():
            val_atual = atual.get(campo, 0)
            val_ant = dados_por_periodo.get(periodo_anterior, {}) or {}
            val_ant = val_ant.get(campo)

            pct = variacao_pct(val_atual, val_ant) if val_ant is not None else None
            inverter = campo in INDICADORES_INVERTER
            c = "" if sem_cor else cor(pct, inverter)
            r = "" if sem_cor else RESET

            out(f"  {label:<40} {formatar_valor(campo, val_atual):>15}")
            out(f"  {'':40} YoY: {c}{sinal(pct)}{r}")

            if pct is not None:
                out(f"  {'':40} ({periodo_anterior}: {formatar_valor(campo, val_ant)})")

            # Série histórica
            serie_vals = []
            for p in reversed(periodos):
                d = dados_por_periodo.get(p)
                if d:
                    serie_vals.append(f"{p}: {formatar_valor(campo, d.get(campo, 0))}")
            out(f"  {'':40} Série: {' | '.join(serie_vals)}")
            out()

    out(f"{'='*72}\n")

    if output:
        # Guarda versão sem códigos ANSI no ficheiro
        import re
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        with open(output, "w", encoding="utf-8") as f:
            for linha in linhas:
                f.write(ansi_escape.sub("", linha) + "\n")
        print(f"  Relatório guardado em: {output}")


def list_datasets():
    print("\nDatasets disponíveis no monitor:\n")
    for ds_id, cfg in DATASETS.items():
        print(f"  {ds_id}")
        print(f"    Nome: {cfg['nome']}")
        for campo, label in cfg['indicadores'].items():
            print(f"    - {label} ({campo})")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Monitor do Portal da Transparência do SNS"
    )
    parser.add_argument(
        "--periodo",
        default=None,
        help="Período a analisar no formato YYYY-MM (default: mês anterior)",
    )
    parser.add_argument(
        "--anos",
        type=int,
        default=3,
        help="Número de anos anteriores para a série (default: 3)",
    )
    parser.add_argument(
        "--sem-cor",
        action="store_true",
        help="Desativa cores ANSI no output",
    )
    parser.add_argument(
        "--listar",
        action="store_true",
        help="Lista os datasets configurados e sai",
    )
    parser.add_argument(
        "--dataset",
        default=None,
        help="Filtra por ID de dataset (parcial, ex: cirurg)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Guarda o relatório num ficheiro de texto (sem cores ANSI)",
    )
    args = parser.parse_args()

    if args.listar:
        list_datasets()
        return

    if args.periodo:
        periodo = args.periodo
    else:
        hoje = date.today()
        # Usa o mês anterior (mais provável de ter dados completos)
        if hoje.month == 1:
            periodo = f"{hoje.year - 1}-12"
        else:
            periodo = f"{hoje.year}-{hoje.month - 1:02d}"

    run_report(periodo, args.anos, args.sem_cor, args.dataset, args.output)


if __name__ == "__main__":
    main()
