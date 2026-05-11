import streamlit as st
import plotly.graph_objects as go
import json
import numpy as np
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="Dashboard SNS — Transparência",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #003087; }
  [data-testid="stSidebar"] * { color: white !important; }
  [data-testid="stSidebar"] .stRadio label { color: rgba(255,255,255,0.85) !important; }
  [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2); }
  .stApp { background: #f0f2f6; }
  .block-container { padding-top: 1.2rem; }
  .kpi { background:white; border-radius:10px; padding:16px 18px;
         box-shadow:0 2px 6px rgba(0,0,0,.07); border-top:4px solid #0066cc;
         margin-bottom:6px; }
  .kpi.bad  { border-top-color:#dc3545; }
  .kpi.warn { border-top-color:#fd7e14; }
  .kpi.good { border-top-color:#28a745; }
  .kpi-label { font-size:.7rem; text-transform:uppercase; letter-spacing:.06em;
               color:#6c757d; margin-bottom:3px; }
  .kpi-value { font-size:1.6rem; font-weight:700; color:#003087; line-height:1.1; }
  .kpi-delta { font-size:.78rem; font-weight:600; margin-top:3px; }
  .kpi-delta.up   { color:#28a745; }
  .kpi-delta.down { color:#dc3545; }
  .kpi-delta.flat { color:#6c757d; }
  .kpi-sub { font-size:.68rem; color:#adb5bd; margin-top:1px; }
  .sec-title { font-size:1.05rem; font-weight:700; color:#003087;
               border-bottom:2px solid #dce4f0; padding-bottom:5px;
               margin:18px 0 14px; }
  .insight { background:#fff3cd; border-left:4px solid #ffc107;
             padding:10px 14px; border-radius:6px; font-size:.85rem;
             margin-bottom:14px; color:#664d03; }
  .insight.red { background:#f8d7da; border-left-color:#dc3545; color:#58151c; }
</style>
""", unsafe_allow_html=True)


# ── Dados ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load():
    p = Path("dashboard_dados.json")
    if not p.exists():
        st.error("Ficheiro dashboard_dados.json não encontrado.")
        st.stop()
    with open(p, encoding="utf-8") as f:
        return json.load(f)

data = load()
periodos_todos = data["periodos"]


# ── Helpers ───────────────────────────────────────────────────────────────────
CORES = ["#0066cc","#dc3545","#28a745","#fd7e14","#6f42c1","#20c997","#17a2b8"]

def fmt(v, u):
    if v is None: return "N/D"
    if u == "%": return f"{v:.1f}%"
    if u == "€":
        if abs(v) >= 1e9: return f"{v/1e9:.2f} MM€"
        if abs(v) >= 1e6: return f"{v/1e6:.1f} M€"
        return f"{v/1e3:.0f} k€"
    if u == " dias": return f"{v:.2f} dias"
    if abs(v) >= 1e6: return f"{v/1e6:.2f} M"
    if abs(v) >= 1e3: return f"{v/1e3:.1f} k"
    return f"{int(v):,}".replace(",", " ")

def yoy(curr, prev):
    if None in (curr, prev) or prev == 0: return None
    return (curr - prev) / abs(prev) * 100

def kpi_card(label, val, pct, sub="", invertido=False):
    fv = fmt(val, "")
    if pct is None:
        cls, dcls, dtxt = "kpi", "flat", "YoY: N/D"
    else:
        s = "+" if pct > 0 else ""
        dtxt = f"YoY {s}{pct:.1f}%"
        bom = pct > 0 if not invertido else pct < 0
        if bom:   cls, dcls = "kpi good", "up"
        elif pct == 0: cls, dcls = "kpi", "flat"
        else:     cls, dcls = "kpi bad",  "down"
    sub_h = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""<div class="{cls}">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{fv}</div>
  <div class="kpi-delta {dcls}">{dtxt}</div>
  {sub_h}
</div>"""

def agregar_anual(serie, periodos, tipo):
    """Agrega série mensal por ano."""
    por_ano = {}
    for p in periodos:
        v = serie.get(p)
        if v is None: continue
        ano = p[:4]
        por_ano.setdefault(ano, []).append(v)
    result = {}
    for ano, vals in por_ano.items():
        if tipo == "media":
            result[ano] = round(sum(vals) / len(vals), 2)
        else:
            result[ano] = round(sum(vals), 2)
    return result

def media_movel(serie, periodos, janela=6):
    """Média móvel simples."""
    vals = [serie.get(p) for p in periodos]
    result = {}
    for i, p in enumerate(periodos):
        janela_vals = [v for v in vals[max(0, i-janela+1):i+1] if v is not None]
        result[p] = round(sum(janela_vals)/len(janela_vals), 2) if janela_vals else None
    return result

def linha_tendencia(x_num, y_vals):
    """Linha de tendência linear (regressão simples)."""
    pts = [(xi, yi) for xi, yi in zip(x_num, y_vals) if yi is not None]
    if len(pts) < 3: return [], []
    xs, ys = zip(*pts)
    xs, ys = np.array(xs), np.array(ys)
    m, b = np.polyfit(xs, ys, 1)
    return list(x_num), [m*xi + b for xi in x_num]

def chart(labels, series_list, titulo="", modo="Mensal", tipo_chart="line",
          unidade="", stack=False):
    """
    series_list: [(label, {periodo: val}, tipo_agg, invertido)]
    modo: Mensal | Anual | Média Móvel 6m
    """
    fig = go.Figure()

    if modo == "Anual":
        anos = sorted(set(p[:4] for p in labels))
        for i, (label, serie, tipo_agg, _inv) in enumerate(series_list):
            agg = agregar_anual(serie, labels, tipo_agg)
            ys = [agg.get(a) for a in anos]
            cor = CORES[i % len(CORES)]
            if tipo_chart == "bar" or len(series_list) > 1:
                fig.add_trace(go.Bar(x=anos, y=ys, name=label,
                                     marker_color=cor + "cc"))
            else:
                fig.add_trace(go.Bar(x=anos, y=ys, name=label,
                                     marker_color=cor + "cc"))
            # Linha de tendência
            tx, ty = linha_tendencia(list(range(len(anos))), ys)
            if tx:
                fig.add_trace(go.Scatter(
                    x=anos, y=ty, name=f"Tendência ({label})",
                    mode="lines", line=dict(color=cor, width=2, dash="dot"),
                    showlegend=len(series_list) == 1,
                ))
        barmode = "stack" if stack else "group"
        fig.update_layout(barmode=barmode)

    elif modo == "Média Móvel 6m":
        for i, (label, serie, _ta, _inv) in enumerate(series_list):
            mm = media_movel(serie, labels, 6)
            ys_raw = [serie.get(p) for p in labels]
            ys_mm  = [mm.get(p) for p in labels]
            cor = CORES[i % len(CORES)]
            fig.add_trace(go.Scatter(
                x=labels, y=ys_raw, name=label,
                mode="lines", line=dict(color=cor+"55", width=1),
                showlegend=True,
            ))
            fig.add_trace(go.Scatter(
                x=labels, y=ys_mm, name=f"MM6 {label}",
                mode="lines", line=dict(color=cor, width=2.5),
            ))
    else:  # Mensal
        for i, (label, serie, _ta, _inv) in enumerate(series_list):
            ys = [serie.get(p) for p in labels]
            cor = CORES[i % len(CORES)]
            if tipo_chart == "bar":
                fig.add_trace(go.Bar(x=labels, y=ys, name=label,
                                     marker_color=cor + "cc"))
            else:
                fig.add_trace(go.Scatter(
                    x=labels, y=ys, name=label, mode="lines+markers",
                    line=dict(color=cor, width=2.5),
                    marker=dict(size=4 if len(labels) <= 30 else 0),
                    connectgaps=False,
                ))
        if stack:
            fig.update_layout(barmode="stack")

    fig.update_layout(
        title=dict(text=titulo, font=dict(size=12, color="#003087")),
        height=290,
        margin=dict(l=8, r=8, t=36, b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    font=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="white",
        hovermode="x unified",
        xaxis=dict(showgrid=False, tickfont=dict(size=9),
                   tickangle=-30 if modo == "Mensal" and len(labels) > 24 else 0),
        yaxis=dict(gridcolor="#f0f0f0", tickfont=dict(size=9)),
    )
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏥 SNS em Números")
    st.markdown("*Monitorização do Sistema de Saúde*")
    st.markdown("---")

    secao = st.radio("Área", [
        "📊 Visão Geral",
        "⏳ Acesso & Listas de Espera",
        "🏥 Atividade Assistencial",
        "💶 Financeiro",
        "👩‍⚕️ Recursos Humanos",
    ], label_visibility="collapsed")

    st.markdown("---")
    st.markdown("**Visualização**")
    modo = st.radio("Modo", ["Anual", "Média Móvel 6m", "Mensal"],
                    label_visibility="collapsed")

    st.markdown("---")
    st.markdown("**Período**")
    anos_disp = sorted(set(p[:4] for p in periodos_todos))
    ano_ini = st.selectbox("De", anos_disp, index=0)
    ano_fim = st.selectbox("Até", anos_disp, index=len(anos_disp)-1)
    periodos = [p for p in periodos_todos if ano_ini <= p[:4] <= ano_fim]

    st.markdown("---")
    ultimo_p = periodos[-1] if periodos else periodos_todos[-1]
    prev_p   = f"{int(ultimo_p[:4])-1}{ultimo_p[4:]}"
    st.caption(f"Último período: **{ultimo_p}**")
    st.caption("Fonte: transparencia.sns.gov.pt")


# ── Secções ───────────────────────────────────────────────────────────────────

def kpis_row(campos, sec_key, unidade_map=None):
    """Renderiza uma linha de KPI cards."""
    cols = st.columns(len(campos))
    for col, (ds_id, campo, label, invertido) in zip(cols, campos):
        ds = data[sec_key].get(ds_id, {})
        serie = ds.get("series", {}).get(campo, {})
        v = serie.get(ultimo_p)
        v_prev = serie.get(prev_p)
        p = yoy(v, v_prev)
        col.markdown(
            kpi_card(label, v, p, sub=f"vs {prev_p[:4]}: {fmt(v_prev, '')}", invertido=invertido),
            unsafe_allow_html=True
        )

def secao_visao_geral():
    st.markdown('<div class="sec-title">📊 Visão Geral — Indicadores Críticos do SNS</div>',
                unsafe_allow_html=True)

    st.markdown("""<div class="insight red">
    ⚠️ Os indicadores abaixo mostram a evolução dos principais problemas estruturais do SNS.
    Valores a <strong>vermelho</strong> indicam deterioração face ao ano anterior.
    </div>""", unsafe_allow_html=True)

    # Linha 1 — Acesso
    st.markdown("**Acesso & Listas de Espera**")
    kpis_row([
        ("consultas-em-tempo-real",                "1as_consultas_realizadas_em_tempo_adequado", "% 1ªs Consultas em TMRG", True),
        ("demora-media-antes-da-cirurgia",          "demora_media_antes_da_cirurgia",             "Demora Média pré-Cirurgia", True),
        ("utentes-inscritos-em-cuidados-de-saude-primarios", "total_utentes_sem_mdf_atribuido",  "Utentes sem Médico de Família", True),
        ("atendimentos-em-urgencia-triagem-manchester","no_de_atendimentos_em_urgencia_su_triagem_manchester_verde","Triagem Verde (evitáveis)", True),
    ], "acesso")

    # Linha 2 — Financeiro
    st.markdown("**Sustentabilidade Financeira**")
    kpis_row([
        ("agregados-economico-financeiros",         "resultado_liquido",                          "Resultado Líquido SNS",   True),
        ("divida-total-vencida-e-pagamentos",       "divida_vencida_fornecedores_externos",       "Dívida Vencida",          True),
        ("divida-total-vencida-e-pagamentos",       "pagamentos_em_atraso",                       "Pagamentos em Atraso",    True),
        ("despesa-com-medicamentos-nos-hospitais-do-sns","encargos_sns_hospitalar",               "Encargos Medicamentos Hosp.", True),
    ], "financeiro")

    # Linha 3 — RH
    st.markdown("**Recursos Humanos**")
    kpis_row([
        ("trabalhadores-por-grupo-profissional",    "enfermeiros",                               "Enfermeiros",             False),
        ("trabalhadores-por-grupo-profissional",    "medicos_s_internos",                        "Médicos (excl. internos)",False),
        ("contagem-dos-dias-de-ausencia-ao-trabalho-segundo-o-motivo-de-ausencia","valor",        "Dias de Ausência",        True),
        ("contagem-das-horas-de-trabalho-nocturno-normal-e-extraordinario","trabalho_extraordinario_diurno","Horas Extra Diurnas",True),
    ], "rh")

    # Gráficos resumo
    st.markdown("---")
    c1, c2 = st.columns(2)

    # Resultado líquido
    s_res = data["financeiro"]["agregados-economico-financeiros"]["series"]["resultado_liquido"]
    c1.plotly_chart(chart(periodos, [("Resultado Líquido (€)", s_res, "soma", True)],
                          "Resultado Líquido do SNS (€)", modo), use_container_width=True)

    # Triagem verde
    s_verde = data["acesso"]["atendimentos-em-urgencia-triagem-manchester"]["series"].get(
        "no_de_atendimentos_em_urgencia_su_triagem_manchester_verde", {})
    c2.plotly_chart(chart(periodos, [("Triagem Verde (não urgente)", s_verde, "soma", True)],
                          "Urgências Evitáveis — Triagem Verde", modo), use_container_width=True)

    c3, c4 = st.columns(2)
    s_sem_mdf = data["acesso"]["utentes-inscritos-em-cuidados-de-saude-primarios"]["series"].get(
        "total_utentes_sem_mdf_atribuido", {})
    c3.plotly_chart(chart(periodos, [("Utentes sem Médico de Família", s_sem_mdf, "soma", True)],
                          "Utentes sem Médico de Família atribuído", modo), use_container_width=True)

    s_aus = data["rh"]["contagem-dos-dias-de-ausencia-ao-trabalho-segundo-o-motivo-de-ausencia"]["series"]["valor"]
    c4.plotly_chart(chart(periodos, [("Dias de Ausência", s_aus, "soma", True)],
                          "Absentismo — Dias de Ausência ao Trabalho", modo), use_container_width=True)


def secao_acesso():
    st.markdown('<div class="sec-title">⏳ Acesso & Listas de Espera</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="insight red">
    A percentagem de primeiras consultas realizadas dentro do tempo máximo de resposta garantido (TMRG)
    mantém-se abaixo de 60%, e a presença crescente de triagem verde nas urgências indica que
    os cuidados de saúde primários não conseguem absorver a procura.
    </div>""", unsafe_allow_html=True)

    ds_cth   = data["acesso"]["consultas-em-tempo-real"]
    ds_cir   = data["acesso"]["demora-media-antes-da-cirurgia"]
    ds_man   = data["acesso"]["atendimentos-em-urgencia-triagem-manchester"]
    ds_mdf   = data["acesso"]["utentes-inscritos-em-cuidados-de-saude-primarios"]

    s_tmrg  = ds_cth["series"]["1as_consultas_realizadas_em_tempo_adequado"]
    s_cth   = ds_cth["series"]["no_primeiras_ce_realizadas_com_registo_no_cth"]
    s_dem   = ds_cir["series"]["demora_media_antes_da_cirurgia"]
    s_verde = ds_man["series"].get("no_de_atendimentos_em_urgencia_su_triagem_manchester_verde", {})
    s_azul  = ds_man["series"].get("no_de_atendimentos_em_urgencia_su_triagem_manchester_azul", {})
    s_verm  = ds_man["series"].get("no_de_atendimentos_em_urgencia_su_triagem_manchester_vermelha", {})
    s_sem   = ds_mdf["series"].get("total_utentes_sem_mdf_atribuido", {})
    s_pct   = ds_mdf["series"].get("total_utentes_com_mdf_atribuido0", {})

    cols = st.columns(4)
    for col, (serie, label, inv) in zip(cols, [
        (s_tmrg, "% 1ªs Consultas em TMRG", True),
        (s_dem,  "Demora Média pré-Cirurgia", True),
        (s_sem,  "Utentes sem Médico de Família", True),
        (s_verde,"Triagem Verde (não urgente)", True),
    ]):
        v = serie.get(ultimo_p); vp = serie.get(prev_p)
        col.markdown(kpi_card(label, v, yoy(v, vp),
                               sub=f"vs {prev_p[:4]}: {fmt(vp,'')}", invertido=inv),
                     unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(chart(periodos,
        [("% em TMRG", s_tmrg, "media", True)],
        "1ªs Consultas Realizadas em Tempo Adequado (%)", modo),
        use_container_width=True)
    c2.plotly_chart(chart(periodos,
        [("Demora Média (dias)", s_dem, "media", True)],
        "Demora Média antes da Cirurgia (dias)", modo),
        use_container_width=True)

    c3, c4 = st.columns(2)
    c3.plotly_chart(chart(periodos, [
        ("Verde — não urgente", s_verde, "soma", True),
        ("Azul — pouco urgente", s_azul,  "soma", True),
        ("Vermelha — emergência", s_verm, "soma", False),
    ], "Triagem de Manchester nas Urgências", modo, stack=True),
        use_container_width=True)
    c4.plotly_chart(chart(periodos,
        [("Utentes sem Médico de Família", s_sem, "soma", True)],
        "Utentes sem Médico de Família atribuído", modo),
        use_container_width=True)


def secao_atividade():
    st.markdown('<div class="sec-title">🏥 Atividade Assistencial</div>',
                unsafe_allow_html=True)

    ds_cir  = data["atividade"]["intervencoes-cirurgicas"]
    ds_urg  = data["atividade"]["atendimentos-por-tipo-de-urgencia-hospitalar-link"]
    ds_con  = data["atividade"]["01_sica_evolucao-mensal-das-consultas-medicas-hospitalares"]
    ds_csp  = data["atividade"]["evolucao-das-consultas-medicas-nos-csp"]
    ds_int  = data["atividade"]["atividade-de-internamento-hospitalar"]

    s_prog = ds_cir["series"]["no_intervencoes_cirurgicas_programadas"]
    s_amb  = ds_cir["series"]["no_intervencoes_cirurgicas_de_ambulatorio"]
    s_urgc = ds_cir["series"]["no_intervencoes_cirurgicas_urgentes"]
    s_turg = ds_urg["series"]["total_urgencias"]
    s_uger = ds_urg["series"]["urgencias_geral"]
    s_uped = ds_urg["series"]["urgencias_pediatricas"]
    s_cons = ds_con["series"]["no_de_consultas_medicas_total"]
    s_pri  = ds_con["series"]["no_de_primeiras_consultas"]
    s_pres = ds_csp["series"]["no_de_consultas_medicas_presencias_qt"]
    s_npre = ds_csp["series"]["no_de_consultas_medicas_nao_presenciais_ou_inespecificas_qt"]
    s_dsa  = ds_int["series"]["doentes_saidos"]

    cols = st.columns(4)
    for col, (serie, label) in zip(cols, [
        (s_prog, "Cirurgias Programadas"),
        (s_turg, "Total Urgências"),
        (s_cons, "Consultas Hospitalares"),
        (s_dsa,  "Doentes Saídos"),
    ]):
        v = serie.get(ultimo_p); vp = serie.get(prev_p)
        col.markdown(kpi_card(label, v, yoy(v,vp), sub=f"vs {prev_p[:4]}: {fmt(vp,'')}"),
                     unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(chart(periodos, [
        ("Programadas", s_prog, "soma", False),
        ("Ambulatório",  s_amb,  "soma", False),
        ("Urgentes",     s_urgc, "soma", False),
    ], "Intervenções Cirúrgicas por Tipo", modo, stack=True),
        use_container_width=True)
    c2.plotly_chart(chart(periodos, [
        ("Total", s_turg, "soma", False),
        ("Gerais", s_uger, "soma", False),
        ("Pediátricas", s_uped, "soma", False),
    ], "Urgências Hospitalares", modo), use_container_width=True)

    c3, c4 = st.columns(2)
    c3.plotly_chart(chart(periodos, [
        ("Total Consultas Hosp.", s_cons, "soma", False),
        ("1ªs Consultas", s_pri, "soma", False),
    ], "Consultas Médicas Hospitalares", modo), use_container_width=True)
    c4.plotly_chart(chart(periodos, [
        ("Presenciais CSP", s_pres, "soma", False),
        ("Não Presenciais CSP", s_npre, "soma", False),
    ], "Consultas nos Cuidados de Saúde Primários", modo), use_container_width=True)


def secao_financeiro():
    st.markdown('<div class="sec-title">💶 Financeiro</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="insight red">
    O SNS apresenta défice operacional estrutural e dívida crescente a fornecedores.
    Os gastos crescem sistematicamente acima das receitas, tornando o sistema financeiramente insustentável.
    </div>""", unsafe_allow_html=True)

    ds_agr = data["financeiro"]["agregados-economico-financeiros"]
    ds_div = data["financeiro"]["divida-total-vencida-e-pagamentos"]
    ds_mho = data["financeiro"]["despesa-com-medicamentos-nos-hospitais-do-sns"]
    ds_mam = data["financeiro"]["despesa-com-medicamentos-no-ambulatorio-sns"]

    s_gas  = ds_agr["series"]["gastos_operacionais"]
    s_ren  = ds_agr["series"]["rendimentos_operacionais"]
    s_res  = ds_agr["series"]["resultado_liquido"]
    s_dtot = ds_div["series"]["divida_total_fornecedores_externos"]
    s_dven = ds_div["series"]["divida_vencida_fornecedores_externos"]
    s_pag  = ds_div["series"]["pagamentos_em_atraso"]
    s_mho_ = ds_mho["series"]["encargos_sns_hospitalar"]
    s_mam_ = ds_mam["series"]["encargos_sns_ambulatorio"]

    cols = st.columns(4)
    for col, (serie, label, inv) in zip(cols, [
        (s_gas,  "Gastos Operacionais",  True),
        (s_res,  "Resultado Líquido",    True),
        (s_dtot, "Dívida Total",         True),
        (s_pag,  "Pagamentos em Atraso", True),
    ]):
        v = serie.get(ultimo_p); vp = serie.get(prev_p)
        col.markdown(kpi_card(label, v, yoy(v,vp),
                               sub=f"vs {prev_p[:4]}: {fmt(vp,'€')}", invertido=inv),
                     unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(chart(periodos, [
        ("Gastos Operacionais", s_gas, "soma", True),
        ("Rendimentos Operacionais", s_ren, "soma", False),
    ], "Gastos vs Rendimentos Operacionais (€)", modo), use_container_width=True)
    c2.plotly_chart(chart(periodos, [
        ("Resultado Líquido", s_res, "soma", True),
    ], "Resultado Líquido do SNS (€)", modo), use_container_width=True)

    c3, c4 = st.columns(2)
    c3.plotly_chart(chart(periodos, [
        ("Dívida Total", s_dtot, "soma", True),
        ("Dívida Vencida", s_dven, "soma", True),
        ("Pagamentos Atraso", s_pag, "soma", True),
    ], "Dívida a Fornecedores (€)", modo), use_container_width=True)
    c4.plotly_chart(chart(periodos, [
        ("Medicamentos Hospitalar", s_mho_, "soma", True),
        ("Medicamentos Ambulatório", s_mam_, "soma", True),
    ], "Despesa com Medicamentos SNS (€)", modo), use_container_width=True)


def secao_rh():
    st.markdown('<div class="sec-title">👩‍⚕️ Recursos Humanos</div>',
                unsafe_allow_html=True)
    st.markdown("""<div class="insight">
    ⚠️ O absentismo e as horas extraordinárias crescentes são sinal de sobrecarga dos profissionais de saúde
    e constituem um risco para a retenção de talento no SNS.
    </div>""", unsafe_allow_html=True)

    ds_tr  = data["rh"]["trabalhadores-por-grupo-profissional"]
    ds_aus = data["rh"]["contagem-dos-dias-de-ausencia-ao-trabalho-segundo-o-motivo-de-ausencia"]
    ds_ext = data["rh"]["contagem-das-horas-de-trabalho-nocturno-normal-e-extraordinario"]

    s_tot  = ds_tr["series"]["total_geral"]
    s_med  = ds_tr["series"]["medicos_s_internos"]
    s_int  = ds_tr["series"]["medicos_internos"]
    s_enf  = ds_tr["series"]["enfermeiros"]
    s_tdt  = ds_tr["series"]["tdt"]
    s_aus  = ds_aus["series"]["valor"]
    s_extd = ds_ext["series"]["trabalho_extraordinario_diurno"]
    s_extn = ds_ext["series"]["trabalho_extraordinario_nocturno"]

    cols = st.columns(4)
    for col, (serie, label, inv) in zip(cols, [
        (s_tot,  "Total Trabalhadores",  False),
        (s_enf,  "Enfermeiros",          False),
        (s_aus,  "Dias de Ausência",     True),
        (s_extd, "Horas Extra Diurnas",  True),
    ]):
        v = serie.get(ultimo_p); vp = serie.get(prev_p)
        col.markdown(kpi_card(label, v, yoy(v,vp),
                               sub=f"vs {prev_p[:4]}: {fmt(vp,'')}", invertido=inv),
                     unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(chart(periodos, [
        ("Total", s_tot, "soma", False),
        ("Médicos", s_med, "soma", False),
        ("Internos", s_int, "soma", False),
        ("Enfermeiros", s_enf, "soma", False),
        ("TDT", s_tdt, "soma", False),
    ], "Trabalhadores por Grupo Profissional", modo), use_container_width=True)
    c2.plotly_chart(chart(periodos, [
        ("Dias de Ausência", s_aus, "soma", True),
    ], "Absentismo — Dias de Ausência ao Trabalho", modo), use_container_width=True)

    c3, c4 = st.columns(2)
    c3.plotly_chart(chart(periodos, [
        ("Extraordinário Diurno", s_extd, "soma", True),
        ("Extraordinário Nocturno", s_extn, "soma", True),
    ], "Horas de Trabalho Extraordinário", modo), use_container_width=True)

    # Composição actual
    p_trab = next((p for p in reversed(periodos) if s_tot.get(p) is not None), None)
    if p_trab:
        grupos = {
            "Médicos": s_med.get(p_trab) or 0,
            "Médicos Internos": s_int.get(p_trab) or 0,
            "Enfermeiros": s_enf.get(p_trab) or 0,
            "TDT": s_tdt.get(p_trab) or 0,
        }
        outros = (s_tot.get(p_trab) or 0) - sum(grupos.values())
        if outros > 0: grupos["Outros"] = outros
        fig = go.Figure(go.Bar(
            x=list(grupos.values()), y=list(grupos.keys()),
            orientation="h",
            marker_color=["#0066cc","#4d94ff","#28a745","#fd7e14","#6c757d"],
        ))
        fig.update_layout(
            title=dict(text=f"Composição ({p_trab})",
                       font=dict(size=12, color="#003087")),
            height=260, margin=dict(l=8, r=8, t=36, b=8),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(gridcolor="#f0f0f0", tickfont=dict(size=9)),
            yaxis=dict(tickfont=dict(size=9)),
        )
        c4.plotly_chart(fig, use_container_width=True)


# ── Router ────────────────────────────────────────────────────────────────────
if   "Visão"      in secao: secao_visao_geral()
elif "Acesso"     in secao: secao_acesso()
elif "Atividade"  in secao: secao_atividade()
elif "Financeiro" in secao: secao_financeiro()
elif "Recursos"   in secao: secao_rh()
