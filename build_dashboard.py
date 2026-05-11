#!/usr/bin/env python3
"""
Gerador de Dashboard SNS
Busca dados da API do Portal da Transparência e gera um HTML auto-suficiente.
"""

import warnings
warnings.filterwarnings("ignore")

import requests
import json
import sys
import calendar
import argparse
from datetime import datetime, date
from typing import Optional

BASE_URL = "https://transparencia.sns.gov.pt/api/explore/v2.1/catalog/datasets"

# ─── Configuração dos datasets ─────────────────────────────────────────────────

SECOES = {
    "acesso": {
        "titulo": "Acesso & Listas de Espera",
        "icone": "⏳",
        "datasets": {
            "consultas-em-tempo-real": {
                "nome": "1ªs Consultas em Tempo Adequado",
                "campo_tempo": "tempo",
                "indicadores": {
                    "1as_consultas_realizadas_em_tempo_adequado": {"label": "% 1ªs Consultas em TMRG", "tipo": "media", "unidade": "%", "invertido": True},
                    "no_primeiras_ce_realizadas_com_registo_no_cth": {"label": "Total 1ªs Consultas CTH", "tipo": "soma", "unidade": ""},
                },
            },
            "demora-media-antes-da-cirurgia": {
                "nome": "Demora Média antes da Cirurgia",
                "campo_tempo": "tempo",
                "indicadores": {
                    "demora_media_antes_da_cirurgia": {"label": "Demora Média pré-Cirurgia (dias)", "tipo": "media", "unidade": " dias", "invertido": True},
                },
            },
            "atendimentos-em-urgencia-triagem-manchester": {
                "nome": "Triagem de Manchester nas Urgências",
                "campo_tempo": "tempo",
                "indicadores": {
                    "no_de_atendimentos_em_urgencia_su_triagem_manchester_verde": {"label": "Triagem Verde (não urgente)", "tipo": "soma", "unidade": ""},
                    "no_de_atendimentos_em_urgencia_su_triagem_manchester_azul":  {"label": "Triagem Azul (pouco urgente)", "tipo": "soma", "unidade": ""},
                    "no_de_atendimentos_em_urgencia_su_triagem_manchester_amarela": {"label": "Triagem Amarela (urgente)", "tipo": "soma", "unidade": ""},
                    "no_de_atendimentos_em_urgencia_su_triagem_manchester_vermelha": {"label": "Triagem Vermelha (emergência)", "tipo": "soma", "unidade": ""},
                },
            },
            "utentes-inscritos-em-cuidados-de-saude-primarios": {
                "nome": "Cobertura de Médico de Família",
                "campo_tempo": "periodo",
                "indicadores": {
                    "total_utentes_com_mdf_atribuido0": {"label": "% Utentes COM médico de família", "tipo": "media", "unidade": "%", "invertido": False},
                    "total_utentes_sem_mdf_atribuido": {"label": "Utentes SEM médico de família", "tipo": "soma", "unidade": "", "invertido": True},
                },
            },
        },
    },
    "atividade": {
        "titulo": "Atividade Assistencial",
        "icone": "🏥",
        "datasets": {
            "intervencoes-cirurgicas": {
                "nome": "Intervenções Cirúrgicas",
                "campo_tempo": "tempo",
                "indicadores": {
                    "no_intervencoes_cirurgicas_programadas": {"label": "Cirurgias Programadas", "tipo": "soma", "unidade": ""},
                    "no_intervencoes_cirurgicas_de_ambulatorio": {"label": "Cirurgias Ambulatório", "tipo": "soma", "unidade": ""},
                    "no_intervencoes_cirurgicas_urgentes": {"label": "Cirurgias Urgentes", "tipo": "soma", "unidade": ""},
                },
            },
            "atendimentos-por-tipo-de-urgencia-hospitalar-link": {
                "nome": "Urgências Hospitalares",
                "campo_tempo": "tempo",
                "indicadores": {
                    "total_urgencias": {"label": "Total Urgências", "tipo": "soma", "unidade": ""},
                    "urgencias_geral": {"label": "Urgências Gerais", "tipo": "soma", "unidade": ""},
                    "urgencias_pediatricas": {"label": "Urgências Pediátricas", "tipo": "soma", "unidade": ""},
                },
            },
            "01_sica_evolucao-mensal-das-consultas-medicas-hospitalares": {
                "nome": "Consultas Hospitalares",
                "campo_tempo": "tempo",
                "indicadores": {
                    "no_de_consultas_medicas_total": {"label": "Total Consultas", "tipo": "soma", "unidade": ""},
                    "no_de_primeiras_consultas": {"label": "Primeiras Consultas", "tipo": "soma", "unidade": ""},
                    "no_de_consultas_subsequentes": {"label": "Consultas Subsequentes", "tipo": "soma", "unidade": ""},
                },
            },
            "evolucao-das-consultas-medicas-nos-csp": {
                "nome": "Consultas nos Cuidados de Saúde Primários",
                "campo_tempo": "tempo",
                "indicadores": {
                    "no_de_consultas_medicas_presencias_qt": {"label": "Consultas Presenciais CSP", "tipo": "soma", "unidade": ""},
                    "no_de_consultas_medicas_nao_presenciais_ou_inespecificas_qt": {"label": "Consultas Não Presenciais CSP", "tipo": "soma", "unidade": ""},
                },
            },
            "atividade-de-internamento-hospitalar": {
                "nome": "Internamento Hospitalar",
                "campo_tempo": "tempo",
                "indicadores": {
                    "doentes_saidos": {"label": "Doentes Saídos", "tipo": "soma", "unidade": ""},
                    "dias_de_internamento": {"label": "Dias de Internamento", "tipo": "soma", "unidade": ""},
                },
            },
        },
    },
    "financeiro": {
        "titulo": "Financeiro",
        "icone": "💶",
        "datasets": {
            "agregados-economico-financeiros": {
                "nome": "Agregados Económico-Financeiros",
                "campo_tempo": "tempo",
                "indicadores": {
                    "gastos_operacionais": {"label": "Gastos Operacionais", "tipo": "soma", "unidade": "€", "invertido": True},
                    "rendimentos_operacionais": {"label": "Rendimentos Operacionais", "tipo": "soma", "unidade": "€"},
                    "resultado_liquido": {"label": "Resultado Líquido", "tipo": "soma", "unidade": "€", "invertido": True},
                },
            },
            "divida-total-vencida-e-pagamentos": {
                "nome": "Dívida e Pagamentos em Atraso",
                "campo_tempo": "periodo",
                "indicadores": {
                    "divida_total_fornecedores_externos": {"label": "Dívida Total", "tipo": "soma", "unidade": "€", "invertido": True},
                    "divida_vencida_fornecedores_externos": {"label": "Dívida Vencida", "tipo": "soma", "unidade": "€", "invertido": True},
                    "pagamentos_em_atraso": {"label": "Pagamentos em Atraso", "tipo": "soma", "unidade": "€", "invertido": True},
                },
            },
            "despesa-com-medicamentos-nos-hospitais-do-sns": {
                "nome": "Despesa Medicamentos Hospitalar",
                "campo_tempo": "tempo",
                "indicadores": {
                    "encargos_sns_hospitalar": {"label": "Encargos SNS Hospitalar", "tipo": "soma", "unidade": "€", "invertido": True},
                },
            },
            "despesa-com-medicamentos-no-ambulatorio-sns": {
                "nome": "Despesa Medicamentos Ambulatório",
                "campo_tempo": "tempo",
                "indicadores": {
                    "encargos_sns_ambulatorio": {"label": "Encargos SNS Ambulatório", "tipo": "soma", "unidade": "€", "invertido": True},
                    "valor_pvp_ambulatorio": {"label": "Valor PVP Ambulatório", "tipo": "soma", "unidade": "€", "invertido": True},
                },
            },
        },
    },
    "rh": {
        "titulo": "Recursos Humanos",
        "icone": "👩‍⚕️",
        "datasets": {
            "trabalhadores-por-grupo-profissional": {
                "nome": "Trabalhadores por Grupo Profissional",
                "campo_tempo": "periodo",
                "indicadores": {
                    "total_geral": {"label": "Total Trabalhadores", "tipo": "soma", "unidade": ""},
                    "medicos_s_internos": {"label": "Médicos (excl. internos)", "tipo": "soma", "unidade": ""},
                    "medicos_internos": {"label": "Médicos Internos", "tipo": "soma", "unidade": ""},
                    "enfermeiros": {"label": "Enfermeiros", "tipo": "soma", "unidade": ""},
                    "tdt": {"label": "TDT", "tipo": "soma", "unidade": ""},
                },
            },
            "contagem-dos-dias-de-ausencia-ao-trabalho-segundo-o-motivo-de-ausencia": {
                "nome": "Ausências ao Trabalho",
                "campo_tempo": "tempo",
                "indicadores": {
                    "valor": {"label": "Dias de Ausência", "tipo": "soma", "unidade": "", "invertido": True},
                },
            },
            "contagem-das-horas-de-trabalho-nocturno-normal-e-extraordinario": {
                "nome": "Trabalho Suplementar",
                "campo_tempo": "tempo",
                "indicadores": {
                    "trabalho_extraordinario_diurno": {"label": "Trabalho Extraordinário Diurno (h)", "tipo": "soma", "unidade": "", "invertido": True},
                    "trabalho_extraordinario_nocturno": {"label": "Trabalho Extraordinário Nocturno (h)", "tipo": "soma", "unidade": "", "invertido": True},
                },
            },
        },
    },
}


# ─── Fetch & Aggregate ─────────────────────────────────────────────────────────

def fetch_month(dataset_id: str, campo: str, periodo: str) -> list:
    """Busca todos os registos de um dataset para um período YYYY-MM."""
    url = f"{BASE_URL}/{dataset_id}/records"
    ano, mes = periodo.split("-")
    ultimo_dia = calendar.monthrange(int(ano), int(mes))[1]
    filtro = f'{campo} >= "{periodo}-01" AND {campo} <= "{periodo}-{ultimo_dia:02d}"'
    params = {"where": filtro, "limit": 100, "offset": 0}
    records = []
    while True:
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"    [ERRO] {dataset_id} {periodo}: {e}", file=sys.stderr)
            return []
        batch = data.get("results", [])
        records.extend(batch)
        total = data.get("total_count", 0)
        params["offset"] += len(batch)
        if params["offset"] >= total or not batch:
            break
    return records


def aggregate_month(records: list, indicadores: dict) -> dict:
    totais = {k: 0.0 for k in indicadores}
    contagens = {k: 0 for k in indicadores}
    for rec in records:
        for campo, cfg in indicadores.items():
            v = rec.get(campo)
            if v is not None:
                totais[campo] += float(v)
                contagens[campo] += 1
    result = {}
    for campo, cfg in indicadores.items():
        if cfg["tipo"] == "media" and contagens[campo] > 0:
            result[campo] = round(totais[campo] / contagens[campo], 2)
        elif contagens[campo] > 0:
            result[campo] = round(totais[campo], 2)
        else:
            result[campo] = None
    return result


def build_series(dataset_id: str, cfg: dict, periodos: list, verbose: bool) -> dict:
    """Devolve {campo: {periodo: valor}} para todos os períodos."""
    campo_tempo = cfg["campo_tempo"]
    indicadores = cfg["indicadores"]
    series = {campo: {} for campo in indicadores}

    for p in periodos:
        if verbose:
            print(f"    {p} ...", end=" ", flush=True)
        records = fetch_month(dataset_id, campo_tempo, p)
        agg = aggregate_month(records, indicadores)
        for campo, val in agg.items():
            series[campo][p] = val
        if verbose:
            print("ok" if records else "sem dados")
    return series


def generate_periodos(anos: int) -> list:
    """Devolve períodos mensais desde (hoje - anos) até ao mês anterior."""
    hoje = date.today()
    # mês anterior como ponto final
    if hoje.month == 1:
        fim_ano, fim_mes = hoje.year - 1, 12
    else:
        fim_ano, fim_mes = hoje.year, hoje.month - 1

    periodos = []
    ano, mes = fim_ano - anos + 1, 1
    while (ano, mes) <= (fim_ano, fim_mes):
        periodos.append(f"{ano}-{mes:02d}")
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1
    return periodos


# ─── HTML Template ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard SNS — Portal da Transparência</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --blue: #0066cc;
    --blue-light: #e8f0fb;
    --green: #28a745;
    --red: #dc3545;
    --orange: #fd7e14;
    --gray: #6c757d;
    --bg: #f4f6f9;
    --card: #ffffff;
    --border: #dee2e6;
    --text: #212529;
    --text-muted: #6c757d;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); }
  header { background: #003087; color: white; padding: 16px 24px; display: flex; align-items: center; gap: 16px; box-shadow: 0 2px 4px rgba(0,0,0,.2); }
  header h1 { font-size: 1.3rem; font-weight: 600; }
  header span.sub { font-size: .85rem; opacity: .8; margin-left: 8px; }
  nav { background: white; border-bottom: 1px solid var(--border); display: flex; gap: 0; padding: 0 24px; overflow-x: auto; }
  nav button { padding: 14px 20px; border: none; background: none; cursor: pointer; font-size: .9rem; color: var(--gray); border-bottom: 3px solid transparent; white-space: nowrap; transition: all .2s; }
  nav button:hover { color: var(--blue); }
  nav button.active { color: var(--blue); border-bottom-color: var(--blue); font-weight: 600; }
  .section { display: none; padding: 24px; max-width: 1400px; margin: 0 auto; }
  .section.active { display: block; }
  .kpi-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .kpi { background: var(--card); border-radius: 10px; padding: 18px; box-shadow: 0 1px 3px rgba(0,0,0,.08); border-left: 4px solid var(--blue); }
  .kpi .label { font-size: .78rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: .04em; margin-bottom: 6px; }
  .kpi .value { font-size: 1.6rem; font-weight: 700; color: var(--text); line-height: 1; }
  .kpi .yoy { font-size: .8rem; margin-top: 6px; }
  .kpi .yoy.up { color: var(--green); }
  .kpi .yoy.down { color: var(--red); }
  .kpi .yoy.neutral { color: var(--gray); }
  .kpi.warn { border-left-color: var(--orange); }
  .kpi.good { border-left-color: var(--green); }
  .kpi.bad { border-left-color: var(--red); }
  .charts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(480px, 1fr)); gap: 20px; }
  .chart-card { background: var(--card); border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .chart-card h3 { font-size: .95rem; color: var(--text); margin-bottom: 16px; font-weight: 600; }
  .chart-card canvas { max-height: 280px; }
  .dataset-block { margin-bottom: 32px; }
  .dataset-block h2 { font-size: 1rem; font-weight: 700; color: #003087; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid var(--blue-light); }
  footer { text-align: center; padding: 20px; color: var(--text-muted); font-size: .8rem; margin-top: 32px; }
  @media (max-width: 600px) { .charts-grid { grid-template-columns: 1fr; } .kpi-row { grid-template-columns: 1fr 1fr; } }
</style>
</head>
<body>

<header>
  <div>
    <h1>🏥 Dashboard SNS <span class="sub">Portal da Transparência</span></h1>
  </div>
  <div style="margin-left:auto;font-size:.8rem;opacity:.7">Dados: transparencia.sns.gov.pt &nbsp;|&nbsp; Gerado: __GERADO__</div>
</header>

<nav>
__NAV__
</nav>

__SECTIONS__

<footer>Fonte: Portal da Transparência do SNS (transparencia.sns.gov.pt) &bull; Valores agregados a nível nacional</footer>

<script>
const DATA = __DATA_JSON__;

const PALETTE = [
  '#0066cc','#28a745','#dc3545','#fd7e14','#6f42c1','#20c997','#ffc107','#17a2b8'
];

function fmt(v, unidade) {
  if (v === null || v === undefined) return 'N/D';
  if (unidade === '%') return v.toFixed(1) + '%';
  if (unidade === '€') {
    if (Math.abs(v) >= 1e9) return (v/1e9).toFixed(2) + ' M€M';
    if (Math.abs(v) >= 1e6) return (v/1e6).toFixed(1) + ' M€';
    if (Math.abs(v) >= 1e3) return (v/1e3).toFixed(0) + ' k€';
    return v.toFixed(0) + ' €';
  }
  if (Math.abs(v) >= 1e6) return (v/1e6).toFixed(2) + ' M';
  if (Math.abs(v) >= 1e3) return (v/1e3).toFixed(1) + ' k';
  return v.toFixed(unidade === ' dias' ? 2 : 0);
}

function yoy(curr, prev) {
  if (prev === null || prev === undefined || prev === 0) return null;
  return ((curr - prev) / Math.abs(prev)) * 100;
}

function makeChart(canvasId, labels, datasets, tipo) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  new Chart(ctx, {
    type: tipo || 'line',
    data: {
      labels,
      datasets: datasets.map((d, i) => ({
        label: d.label,
        data: d.data,
        borderColor: PALETTE[i % PALETTE.length],
        backgroundColor: tipo === 'bar' ? PALETTE[i % PALETTE.length] + 'cc' : PALETTE[i % PALETTE.length] + '22',
        fill: tipo !== 'bar',
        tension: 0.3,
        pointRadius: labels.length > 24 ? 0 : 3,
        borderWidth: 2,
      }))
    },
    options: {
      responsive: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const v = ctx.raw;
              if (v === null) return ctx.dataset.label + ': N/D';
              return ctx.dataset.label + ': ' + v.toLocaleString('pt-PT', {maximumFractionDigits: 2});
            }
          }
        }
      },
      scales: {
        x: { ticks: { font: { size: 10 }, maxTicksLimit: 12 } },
        y: { ticks: { font: { size: 10 } } }
      }
    }
  });
}

function buildSection(secId) {
  const sec = DATA[secId];
  if (!sec) return;
  const periodos = DATA.periodos;
  const n = periodos.length;

  // Latest period com dados
  Object.entries(sec).forEach(([dsId, dsCfg]) => {
    Object.entries(dsCfg.series).forEach(([campo, serie]) => {
      // KPI card
      const kpiEl = document.getElementById('kpi_' + secId + '_' + campo);
      if (!kpiEl) return;

      // Último valor disponível
      let ultimoP = null, ultimoV = null;
      for (let i = n - 1; i >= 0; i--) {
        const v = serie[periodos[i]];
        if (v !== null && v !== undefined) { ultimoP = periodos[i]; ultimoV = v; break; }
      }
      // Mesmo mês ano anterior
      let prevV = null;
      if (ultimoP) {
        const [a, m] = ultimoP.split('-');
        const prevP = `${+a - 1}-${m}`;
        prevV = serie[prevP] ?? null;
      }

      const pct = yoy(ultimoV, prevV);
      const unidade = dsCfg.indicadores[campo].unidade;
      const fmtVal = ultimoV !== null ? fmt(ultimoV, unidade) : 'N/D';
      kpiEl.querySelector('.value').textContent = fmtVal;
      if (ultimoP) kpiEl.querySelector('.label').textContent += ` (${ultimoP})`;

      const yoyEl = kpiEl.querySelector('.yoy');
      if (pct !== null) {
        const sign = pct >= 0 ? '+' : '';
        yoyEl.textContent = `YoY: ${sign}${pct.toFixed(1)}%`;
        yoyEl.className = 'yoy ' + (pct > 0 ? 'up' : pct < 0 ? 'down' : 'neutral');
      } else {
        yoyEl.textContent = '';
      }
    });

    // Charts
    const labels = periodos;
    const campos = Object.keys(dsCfg.series);
    const chartDatasets = campos.map(campo => ({
      label: dsCfg.indicadores[campo].label,
      data: periodos.map(p => dsCfg.series[campo][p] ?? null),
    }));

    const canvasId = 'chart_' + secId + '_' + dsId.replace(/[^a-z0-9]/g, '_');
    const tipo = dsCfg.chartTipo || 'line';
    makeChart(canvasId, labels, chartDatasets, tipo);
  });
}

// Tabs
document.querySelectorAll('nav button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('sec_' + btn.dataset.sec).classList.add('active');
  });
});

// Init — activar primeira secção
document.getElementById('sec_acesso').classList.add('active');
['acesso','atividade','financeiro','rh'].forEach(buildSection);
</script>
</body>
</html>
"""


# ─── Geração do HTML ───────────────────────────────────────────────────────────

def render_kpi(sec_id: str, campo: str, label: str) -> str:
    return f"""
      <div class="kpi" id="kpi_{sec_id}_{campo}">
        <div class="label">{label}</div>
        <div class="value">…</div>
        <div class="yoy"></div>
      </div>"""


def render_section(sec_id: str, sec_cfg: dict, datasets_data: dict) -> str:
    blocks = []
    kpis_html = []
    for ds_id, ds_cfg in sec_cfg["datasets"].items():
        ind = ds_cfg["indicadores"]
        for campo, icfg in ind.items():
            kpis_html.append(render_kpi(sec_id, campo, icfg["label"]))

        canvas_id = f"chart_{sec_id}_{ds_id.replace('-','_').replace('.','_')}"
        # sanitize
        canvas_id = "".join(c if c.isalnum() or c == "_" else "_" for c in canvas_id)

        blocks.append(f"""
    <div class="dataset-block">
      <h2>{ds_cfg['nome']}</h2>
      <div class="charts-grid">
        <div class="chart-card" style="grid-column: 1 / -1;">
          <canvas id="{canvas_id}"></canvas>
        </div>
      </div>
    </div>""")

    return f"""
<section class="section" id="sec_{sec_id}">
  <div class="kpi-row">{''.join(kpis_html)}
  </div>
  {''.join(blocks)}
</section>"""


def build_nav(secoes: dict) -> str:
    first = True
    parts = []
    for sec_id, sec_cfg in secoes.items():
        active = "active" if first else ""
        parts.append(
            f'  <button data-sec="{sec_id}" class="{active}">'
            f'{sec_cfg["icone"]} {sec_cfg["titulo"]}</button>'
        )
        first = False
    return "\n".join(parts)


def fetch_all(periodos: list, verbose: bool) -> dict:
    """Busca todos os dados e devolve estrutura para JSON."""
    result = {}
    for sec_id, sec_cfg in SECOES.items():
        result[sec_id] = {}
        for ds_id, ds_cfg in sec_cfg["datasets"].items():
            print(f"\n  [{sec_cfg['titulo']}] {ds_cfg['nome']}")
            series = build_series(ds_id, ds_cfg, periodos, verbose)
            result[sec_id][ds_id] = {
                "nome": ds_cfg["nome"],
                "indicadores": {
                    campo: {"label": icfg["label"], "unidade": icfg["unidade"]}
                    for campo, icfg in ds_cfg["indicadores"].items()
                },
                "series": series,
                "chartTipo": ds_cfg.get("chart_tipo", "line"),
            }
    return result


def main():
    parser = argparse.ArgumentParser(description="Gerador de Dashboard SNS")
    parser.add_argument("--anos", type=int, default=3, help="Anos de histórico (default: 3)")
    parser.add_argument("--output", default="dashboard.html", help="Ficheiro HTML de saída")
    parser.add_argument("--verbose", action="store_true", help="Mostra progresso detalhado")
    parser.add_argument("--dados", default=None, help="Usa ficheiro JSON de dados em cache (não faz fetch)")
    args = parser.parse_args()

    periodos = generate_periodos(args.anos)
    print(f"Períodos: {periodos[0]} → {periodos[-1]} ({len(periodos)} meses)")

    if args.dados:
        print(f"A carregar dados de {args.dados}...")
        with open(args.dados, encoding="utf-8") as f:
            dados = json.load(f)
        periodos = dados.get("periodos", periodos)
        data_payload = dados
    else:
        print("A buscar dados da API SNS...")
        dados = fetch_all(periodos, args.verbose)
        data_payload = {"periodos": periodos, **dados}

        # Cache
        cache_file = args.output.replace(".html", "_dados.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data_payload, f, ensure_ascii=False)
        print(f"\nDados em cache: {cache_file}")

    # Build HTML
    nav = build_nav(SECOES)
    sections = []
    for sec_id, sec_cfg in SECOES.items():
        sections.append(render_section(sec_id, sec_cfg, dados.get(sec_id, {})))

    # Activate first section
    html = HTML_TEMPLATE
    html = html.replace("__GERADO__", datetime.now().strftime("%Y-%m-%d %H:%M"))
    html = html.replace("__NAV__", nav)
    html = html.replace("__SECTIONS__", "\n".join(sections))
    html = html.replace("__DATA_JSON__", json.dumps(data_payload, ensure_ascii=False))

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard gerado: {args.output}")


if __name__ == "__main__":
    main()
