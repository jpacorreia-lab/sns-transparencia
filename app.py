import streamlit as st
import plotly.graph_objects as go
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard SNS",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS inspirado no CRPM ─────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Sidebar */
  [data-testid="stSidebar"] {
      background: #003087;
  }
  [data-testid="stSidebar"] * {
      color: white !important;
  }
  [data-testid="stSidebar"] .stRadio label {
      color: rgba(255,255,255,0.85) !important;
      font-size: 0.95rem;
  }
  [data-testid="stSidebar"] hr {
      border-color: rgba(255,255,255,0.2);
  }

  /* KPI cards */
  .kpi-card {
      background: white;
      border-radius: 12px;
      padding: 18px 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      border-top: 4px solid #0066cc;
      margin-bottom: 8px;
  }
  .kpi-card.warn  { border-top-color: #fd7e14; }
  .kpi-card.good  { border-top-color: #28a745; }
  .kpi-card.bad   { border-top-color: #dc3545; }
  .kpi-label {
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #6c757d;
      margin-bottom: 4px;
  }
  .kpi-value {
      font-size: 1.7rem;
      font-weight: 700;
      color: #003087;
      line-height: 1.1;
  }
  .kpi-delta {
      font-size: 0.8rem;
      margin-top: 4px;
      font-weight: 600;
  }
  .kpi-delta.up   { color: #28a745; }
  .kpi-delta.down { color: #dc3545; }
  .kpi-delta.flat { color: #6c757d; }
  .kpi-sub {
      font-size: 0.72rem;
      color: #adb5bd;
      margin-top: 2px;
  }

  /* Section header */
  .sec-header {
      font-size: 1.1rem;
      font-weight: 700;
      color: #003087;
      border-bottom: 2px solid #e8f0fb;
      padding-bottom: 6px;
      margin: 20px 0 16px 0;
  }

  /* Main background */
  .stApp { background: #f4f6f9; }
  .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)


# ── Carregar dados ────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data():
    p = Path("dashboard_dados.json")
    if not p.exists():
        st.error("Ficheiro dashboard_dados.json não encontrado. Corre primeiro: python build_dashboard.py")
        st.stop()
    with open(p, encoding="utf-8") as f:
        return json.load(f)

data = load_data()
todos_periodos = data["periodos"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_val(v, unidade):
    if v is None:
        return "N/D"
    if unidade == "%":
        return f"{v:.1f}%"
    if unidade == "€":
        if abs(v) >= 1e9:
            return f"{v/1e9:.2f} MM€"
        if abs(v) >= 1e6:
            return f"{v/1e6:.1f} M€"
        if abs(v) >= 1e3:
            return f"{v/1e3:.0f} k€"
        return f"{v:.0f} €"
    if unidade == " dias":
        return f"{v:.2f} dias"
    if abs(v) >= 1e6:
        return f"{v/1e6:.2f} M"
    if abs(v) >= 1e3:
        return f"{v/1e3:.1f} k"
    return f"{v:.0f}"


def yoy_pct(curr, prev):
    if curr is None or prev is None or prev == 0:
        return None
    return ((curr - prev) / abs(prev)) * 100


def get_prev_periodo(p):
    ano, mes = p.split("-")
    return f"{int(ano)-1}-{mes}"


def ultimo_valor(serie, periodos):
    for p in reversed(periodos):
        v = serie.get(p)
        if v is not None:
            return p, v
    return None, None


def kpi_card(label, value_str, pct, sub="", inverter=False, unidade=""):
    if pct is None:
        delta_html = '<div class="kpi-delta flat">YoY: N/D</div>'
        card_class = "kpi-card"
    else:
        sign = "+" if pct > 0 else ""
        delta_text = f"YoY: {sign}{pct:.1f}%"
        positivo = pct > 0
        if inverter:
            positivo = not positivo
        if positivo:
            css = "up"; card_class = "kpi-card good"
        elif pct < 0:
            css = "down"; card_class = "kpi-card bad"
        else:
            css = "flat"; card_class = "kpi-card"
        delta_html = f'<div class="kpi-delta {css}">{delta_text}</div>'

    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="{card_class}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value_str}</div>
      {delta_html}
      {sub_html}
    </div>"""


def plotly_line(periodos_sel, series_list, title=""):
    """series_list: list of (label, serie_dict, color)"""
    CORES = ["#0066cc","#28a745","#dc3545","#fd7e14","#6f42c1","#20c997"]
    fig = go.Figure()
    for i, (label, serie, _) in enumerate(series_list):
        vals = [serie.get(p) for p in periodos_sel]
        fig.add_trace(go.Scatter(
            x=periodos_sel, y=vals,
            name=label,
            mode="lines+markers",
            line=dict(color=CORES[i % len(CORES)], width=2.5),
            marker=dict(size=5 if len(periodos_sel) <= 24 else 0),
            connectgaps=False,
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#003087")),
        height=300,
        margin=dict(l=10, r=10, t=35, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=11)),
        plot_bgcolor="white",
        paper_bgcolor="white",
        hovermode="x unified",
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(gridcolor="#f0f0f0", tickfont=dict(size=10)),
    )
    return fig


def plotly_bar(periodos_sel, series_list, title="", stack=False):
    CORES = ["#0066cc","#28a745","#dc3545","#fd7e14","#6f42c1","#20c997"]
    fig = go.Figure()
    for i, (label, serie, _) in enumerate(series_list):
        vals = [serie.get(p) for p in periodos_sel]
        fig.add_trace(go.Bar(
            x=periodos_sel, y=vals,
            name=label,
            marker_color=CORES[i % len(CORES)],
        ))
    barmode = "stack" if stack else "group"
    fig.update_layout(
        barmode=barmode,
        title=dict(text=title, font=dict(size=13, color="#003087")),
        height=300,
        margin=dict(l=10, r=10, t=35, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=11)),
        plot_bgcolor="white",
        paper_bgcolor="white",
        hovermode="x unified",
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
        yaxis=dict(gridcolor="#f0f0f0", tickfont=dict(size=10)),
    )
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏥 Dashboard SNS")
    st.markdown("Portal da Transparência")
    st.markdown("---")

    secao = st.radio(
        "Área",
        ["⏳ Acesso & Espera", "🏥 Atividade Assistencial", "💶 Financeiro", "👩‍⚕️ Recursos Humanos"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("**Período**")

    p_ini = st.selectbox("De", todos_periodos, index=0)
    p_fim = st.selectbox("Até", todos_periodos, index=len(todos_periodos)-1)

    # Filtrar lista de períodos
    idx_ini = todos_periodos.index(p_ini)
    idx_fim = todos_periodos.index(p_fim)
    if idx_ini > idx_fim:
        idx_ini, idx_fim = idx_fim, idx_ini
    periodos_sel = todos_periodos[idx_ini:idx_fim+1]

    st.markdown("---")
    ultimo_p = periodos_sel[-1]
    prev_p = get_prev_periodo(ultimo_p)
    st.caption(f"Último período: **{ultimo_p}**")
    st.caption(f"Comparação YoY: **{prev_p}**")

    st.markdown("---")
    st.caption("Fonte: transparencia.sns.gov.pt")
    gerado = data.get("gerado", "")
    if gerado:
        st.caption(f"Dados: {gerado}")


# ── Renderizar secção ─────────────────────────────────────────────────────────

def render_acesso():
    st.markdown('<div class="sec-header">⏳ Acesso & Listas de Espera</div>', unsafe_allow_html=True)

    ds_cth = data["acesso"]["consultas-em-tempo-real"]
    ds_cir = data["acesso"]["demora-media-antes-da-cirurgia"]

    s_tmrg  = ds_cth["series"]["1as_consultas_realizadas_em_tempo_adequado"]
    s_cth   = ds_cth["series"]["no_primeiras_ce_realizadas_com_registo_no_cth"]
    s_dem   = ds_cir["series"]["demora_media_antes_da_cirurgia"]

    # KPIs
    cols = st.columns(3)
    for col, (serie, label, unidade, inverter) in zip(cols, [
        (s_tmrg, "1ªs Consultas em Tempo Adequado", "%", False),
        (s_cth,  "Total 1ªs Consultas CTH",         "",  True),
        (s_dem,  "Demora Média antes da Cirurgia",   " dias", True),
    ]):
        v_atual = serie.get(ultimo_p)
        v_prev  = serie.get(prev_p)
        pct = yoy_pct(v_atual, v_prev)
        col.markdown(kpi_card(label, fmt_val(v_atual, unidade), pct,
                               sub=f"vs {prev_p}: {fmt_val(v_prev, unidade)}",
                               inverter=inverter, unidade=unidade),
                     unsafe_allow_html=True)

    st.plotly_chart(plotly_line(
        periodos_sel,
        [("% 1ªs Consultas em TMRG", s_tmrg, "")],
        title="1ªs Consultas em Tempo Adequado (% dentro do TMRG)"
    ), use_container_width=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(plotly_line(
        periodos_sel,
        [("Total 1ªs Consultas CTH", s_cth, "")],
        title="Total 1ªs Consultas com Registo CTH"
    ), use_container_width=True)
    c2.plotly_chart(plotly_line(
        periodos_sel,
        [("Demora Média (dias)", s_dem, "")],
        title="Demora Média antes da Cirurgia (dias)"
    ), use_container_width=True)


def render_atividade():
    st.markdown('<div class="sec-header">🏥 Atividade Assistencial</div>', unsafe_allow_html=True)

    ds_cir  = data["atividade"]["intervencoes-cirurgicas"]
    ds_urg  = data["atividade"]["atendimentos-por-tipo-de-urgencia-hospitalar-link"]
    ds_con  = data["atividade"]["01_sica_evolucao-mensal-das-consultas-medicas-hospitalares"]
    ds_int  = data["atividade"]["atividade-de-internamento-hospitalar"]

    s_prog  = ds_cir["series"]["no_intervencoes_cirurgicas_programadas"]
    s_amb   = ds_cir["series"]["no_intervencoes_cirurgicas_de_ambulatorio"]
    s_urg_c = ds_cir["series"]["no_intervencoes_cirurgicas_urgentes"]
    s_turg  = ds_urg["series"]["total_urgencias"]
    s_uger  = ds_urg["series"]["urgencias_geral"]
    s_uped  = ds_urg["series"]["urgencias_pediatricas"]
    s_cons  = ds_con["series"]["no_de_consultas_medicas_total"]
    s_pri   = ds_con["series"]["no_de_primeiras_consultas"]
    s_sub   = ds_con["series"]["no_de_consultas_subsequentes"]
    s_dsa   = ds_int["series"]["doentes_saidos"]
    s_dias  = ds_int["series"]["dias_de_internamento"]

    # KPIs principais
    cols = st.columns(4)
    for col, (serie, label, unidade) in zip(cols, [
        (s_prog,  "Cirurgias Programadas",   ""),
        (s_turg,  "Total Urgências",          ""),
        (s_cons,  "Consultas Hospitalares",   ""),
        (s_dsa,   "Doentes Saídos",           ""),
    ]):
        v = serie.get(ultimo_p)
        p = yoy_pct(v, serie.get(prev_p))
        col.markdown(kpi_card(label, fmt_val(v, unidade), p,
                               sub=f"vs {prev_p}: {fmt_val(serie.get(prev_p), unidade)}"),
                     unsafe_allow_html=True)

    # Gráficos
    c1, c2 = st.columns(2)
    c1.plotly_chart(plotly_bar(
        periodos_sel,
        [("Programadas", s_prog, ""), ("Ambulatório", s_amb, ""), ("Urgentes", s_urg_c, "")],
        title="Intervenções Cirúrgicas por Tipo", stack=True
    ), use_container_width=True)
    c2.plotly_chart(plotly_line(
        periodos_sel,
        [("Total", s_turg, ""), ("Gerais", s_uger, ""), ("Pediátricas", s_uped, "")],
        title="Urgências Hospitalares"
    ), use_container_width=True)

    c3, c4 = st.columns(2)
    c3.plotly_chart(plotly_line(
        periodos_sel,
        [("Total", s_cons, ""), ("1ªs Consultas", s_pri, ""), ("Subsequentes", s_sub, "")],
        title="Consultas Médicas Hospitalares"
    ), use_container_width=True)
    c4.plotly_chart(plotly_line(
        periodos_sel,
        [("Doentes Saídos", s_dsa, ""), ("Dias Internamento", s_dias, "")],
        title="Internamento Hospitalar"
    ), use_container_width=True)


def render_financeiro():
    st.markdown('<div class="sec-header">💶 Financeiro</div>', unsafe_allow_html=True)

    ds_agr = data["financeiro"]["agregados-economico-financeiros"]
    ds_div = data["financeiro"]["divida-total-vencida-e-pagamentos"]
    ds_mha = data["financeiro"]["despesa-com-medicamentos-nos-hospitais-do-sns"]
    ds_mam = data["financeiro"]["despesa-com-medicamentos-no-ambulatorio-sns"]

    s_gas  = ds_agr["series"]["gastos_operacionais"]
    s_ren  = ds_agr["series"]["rendimentos_operacionais"]
    s_res  = ds_agr["series"]["resultado_liquido"]
    s_dtot = ds_div["series"]["divida_total_fornecedores_externos"]
    s_dven = ds_div["series"]["divida_vencida_fornecedores_externos"]
    s_pag  = ds_div["series"]["pagamentos_em_atraso"]
    s_mho  = ds_mha["series"]["encargos_sns_hospitalar"]
    s_mam_ = ds_mam["series"]["encargos_sns_ambulatorio"]

    # KPIs
    cols = st.columns(4)
    for col, (serie, label, unidade, inv) in zip(cols, [
        (s_gas,  "Gastos Operacionais",    "€", True),
        (s_ren,  "Rendimentos Operacionais","€", False),
        (s_dtot, "Dívida Total",            "€", True),
        (s_pag,  "Pagamentos em Atraso",   "€", True),
    ]):
        v = serie.get(ultimo_p)
        p = yoy_pct(v, serie.get(prev_p))
        col.markdown(kpi_card(label, fmt_val(v, unidade), p,
                               sub=f"vs {prev_p}: {fmt_val(serie.get(prev_p), unidade)}",
                               inverter=inv),
                     unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(plotly_line(
        periodos_sel,
        [("Gastos Operacionais", s_gas, ""), ("Rendimentos Operacionais", s_ren, "")],
        title="Gastos vs Rendimentos Operacionais (€)"
    ), use_container_width=True)
    c2.plotly_chart(plotly_line(
        periodos_sel,
        [("Resultado Líquido", s_res, "")],
        title="Resultado Líquido (€)"
    ), use_container_width=True)

    c3, c4 = st.columns(2)
    c3.plotly_chart(plotly_line(
        periodos_sel,
        [("Dívida Total", s_dtot, ""), ("Dívida Vencida", s_dven, ""), ("Pagamentos Atraso", s_pag, "")],
        title="Dívida e Pagamentos em Atraso (€)"
    ), use_container_width=True)
    c4.plotly_chart(plotly_line(
        periodos_sel,
        [("Medicamentos Hospitalar", s_mho, ""), ("Medicamentos Ambulatório", s_mam_, "")],
        title="Despesa com Medicamentos SNS (€)"
    ), use_container_width=True)


def render_rh():
    st.markdown('<div class="sec-header">👩‍⚕️ Recursos Humanos</div>', unsafe_allow_html=True)

    ds_trab = data["rh"]["trabalhadores-por-grupo-profissional"]
    ds_aus  = data["rh"]["contagem-dos-dias-de-ausencia-ao-trabalho-segundo-o-motivo-de-ausencia"]

    s_tot  = ds_trab["series"]["total_geral"]
    s_med  = ds_trab["series"]["medicos_s_internos"]
    s_int  = ds_trab["series"]["medicos_internos"]
    s_enf  = ds_trab["series"]["enfermeiros"]
    s_tdt  = ds_trab["series"]["tdt"]
    s_aus  = ds_aus["series"]["valor"]

    # KPIs
    cols = st.columns(4)
    for col, (serie, label) in zip(cols, [
        (s_tot, "Total Trabalhadores"),
        (s_med, "Médicos (excl. internos)"),
        (s_enf, "Enfermeiros"),
        (s_tdt, "TDT"),
    ]):
        v = serie.get(ultimo_p)
        p = yoy_pct(v, serie.get(prev_p))
        col.markdown(kpi_card(label, fmt_val(v, ""), p,
                               sub=f"vs {prev_p}: {fmt_val(serie.get(prev_p), '')}"),
                     unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(plotly_line(
        periodos_sel,
        [
            ("Total", s_tot, ""),
            ("Médicos", s_med, ""),
            ("Internos", s_int, ""),
            ("Enfermeiros", s_enf, ""),
            ("TDT", s_tdt, ""),
        ],
        title="Evolução de Trabalhadores por Grupo Profissional"
    ), use_container_width=True)
    c2.plotly_chart(plotly_line(
        periodos_sel,
        [("Dias de Ausência", s_aus, "")],
        title="Dias de Ausência ao Trabalho"
    ), use_container_width=True)

    # Composição mais recente — gráfico de barras horizontal
    ultimo_p_trab, _ = ultimo_valor(s_tot, periodos_sel)
    if ultimo_p_trab:
        grupos = {
            "Médicos": (s_med.get(ultimo_p_trab) or 0),
            "Médicos Internos": (s_int.get(ultimo_p_trab) or 0),
            "Enfermeiros": (s_enf.get(ultimo_p_trab) or 0),
            "TDT": (s_tdt.get(ultimo_p_trab) or 0),
        }
        outros = (s_tot.get(ultimo_p_trab) or 0) - sum(grupos.values())
        if outros > 0:
            grupos["Outros"] = outros

        fig = go.Figure(go.Bar(
            x=list(grupos.values()),
            y=list(grupos.keys()),
            orientation="h",
            marker_color=["#0066cc","#4d94ff","#28a745","#fd7e14","#6c757d"],
        ))
        fig.update_layout(
            title=dict(text=f"Composição da Força de Trabalho ({ultimo_p_trab})",
                       font=dict(size=13, color="#003087")),
            height=280, margin=dict(l=10, r=10, t=35, b=10),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(gridcolor="#f0f0f0", tickfont=dict(size=10)),
            yaxis=dict(tickfont=dict(size=10)),
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Router ────────────────────────────────────────────────────────────────────
if "Acesso" in secao:
    render_acesso()
elif "Atividade" in secao:
    render_atividade()
elif "Financeiro" in secao:
    render_financeiro()
elif "Recursos" in secao:
    render_rh()
