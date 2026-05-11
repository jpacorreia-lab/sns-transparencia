import streamlit as st
import plotly.graph_objects as go
import json
import numpy as np
from pathlib import Path

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
         box-shadow:0 2px 6px rgba(0,0,0,.07); border-top:4px solid #0066cc; margin-bottom:6px; }
  .kpi.bad  { border-top-color:#dc3545; }
  .kpi.good { border-top-color:#28a745; }
  .kpi-label { font-size:.7rem; text-transform:uppercase; letter-spacing:.06em; color:#6c757d; margin-bottom:3px; }
  .kpi-value { font-size:1.6rem; font-weight:700; color:#003087; line-height:1.1; }
  .kpi-delta { font-size:.78rem; font-weight:600; margin-top:3px; }
  .kpi-delta.up   { color:#28a745; }
  .kpi-delta.down { color:#dc3545; }
  .kpi-delta.flat { color:#6c757d; }
  .kpi-sub { font-size:.68rem; color:#adb5bd; margin-top:1px; }
  .sec-title { font-size:1.05rem; font-weight:700; color:#003087;
               border-bottom:2px solid #dce4f0; padding-bottom:5px; margin:18px 0 14px; }
  .insight { background:#fff3cd; border-left:4px solid #ffc107;
             padding:10px 14px; border-radius:6px; font-size:.85rem; margin-bottom:14px; color:#664d03; }
  .insight.red { background:#f8d7da; border-left-color:#dc3545; color:#58151c; }
</style>
""", unsafe_allow_html=True)


# ── Dados ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load():
    p = Path("dashboard_dados.json")
    if not p.exists():
        st.error("dashboard_dados.json não encontrado. Corre: python build_dashboard.py")
        st.stop()
    with open(p, encoding="utf-8") as f:
        return json.load(f)

data = load()
periodos_todos = data["periodos"]
CORES = ["#0066cc","#dc3545","#28a745","#fd7e14","#6f42c1","#20c997","#17a2b8"]


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt(v, u=""):
    if v is None: return "N/D"
    if u == "%": return f"{v:.1f}%"
    if u == "€":
        if abs(v) >= 1e9: return f"{v/1e9:.2f} MM€"
        if abs(v) >= 1e6: return f"{v/1e6:.1f} M€"
        return f"{v/1e3:.0f} k€"
    if u == "dias": return f"{v:.2f} dias"
    if abs(v) >= 1e6: return f"{v/1e6:.2f} M"
    if abs(v) >= 1e3: return f"{v/1e3:.1f} k"
    return f"{int(v):,}".replace(",", " ")

def yoy(curr, prev):
    if None in (curr, prev) or prev == 0: return None
    return (curr - prev) / abs(prev) * 100

def ultimo_com_dados(serie, periodos):
    """Último (periodo, valor) com dados reais."""
    for p in reversed(periodos):
        v = serie.get(p)
        if v is not None:
            return p, v
    return None, None

def show_kpi(col, serie, label, invertido=False, unidade=""):
    """Renderiza um KPI card usando o último período com dados."""
    up, v = ultimo_com_dados(serie, periodos)
    if up is None:
        col.markdown(f'<div class="kpi"><div class="kpi-label">{label}</div>'
                     f'<div class="kpi-value">N/D</div></div>', unsafe_allow_html=True)
        return
    prev_p = f"{int(up[:4])-1}{up[4:]}"
    v_prev = serie.get(prev_p)
    p = yoy(v, v_prev)

    fv = fmt(v, unidade)
    sub = f"{up}"
    if v_prev is not None:
        sub += f" | vs {prev_p[:4]}: {fmt(v_prev, unidade)}"

    if p is None:
        cls, dcls, dtxt = "kpi", "flat", "YoY: N/D"
    else:
        s = "+" if p > 0 else ""
        dtxt = f"YoY {s}{p:.1f}%"
        bom = (p > 0) if not invertido else (p < 0)
        if bom:        cls, dcls = "kpi good", "up"
        elif p == 0:   cls, dcls = "kpi", "flat"
        else:          cls, dcls = "kpi bad",  "down"

    col.markdown(f"""<div class="{cls}">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{fv}</div>
  <div class="kpi-delta {dcls}">{dtxt}</div>
  <div class="kpi-sub">{sub}</div>
</div>""", unsafe_allow_html=True)

def get(sec, ds_id, campo):
    return data.get(sec, {}).get(ds_id, {}).get("series", {}).get(campo, {})


# ── Agregação & Gráficos ──────────────────────────────────────────────────────
def agregar_anual(serie, periodos, tipo):
    por_ano = {}
    for p in periodos:
        v = serie.get(p)
        if v is None: continue
        por_ano.setdefault(p[:4], []).append(v)
    return {a: round((sum(vs)/len(vs)) if tipo=="media" else sum(vs), 2)
            for a, vs in por_ano.items()}

def media_movel(serie, periodos, janela=6):
    vals = [serie.get(p) for p in periodos]
    result = {}
    for i, p in enumerate(periodos):
        w = [v for v in vals[max(0,i-janela+1):i+1] if v is not None]
        result[p] = round(sum(w)/len(w), 2) if w else None
    return result

def trend_line(labels, ys):
    pts = [(i, y) for i, y in enumerate(ys) if y is not None]
    if len(pts) < 3: return [], []
    xs, yvs = zip(*pts)
    m, b = np.polyfit(xs, yvs, 1)
    return labels, [m*i+b for i in range(len(labels))]

def chart(series_list, titulo="", modo="Anual", tipo_chart="line", stack=False):
    """
    series_list: [(label, serie_dict, tipo_agg)]
    tipo_agg: "soma" | "media"
    """
    fig = go.Figure()

    if modo == "Anual":
        anos = sorted(set(p[:4] for p in periodos))
        for i, (label, serie, tipo_agg) in enumerate(series_list):
            agg = agregar_anual(serie, periodos, tipo_agg)
            ys  = [agg.get(a) for a in anos]
            cor = CORES[i % len(CORES)]
            fig.add_trace(go.Bar(x=anos, y=ys, name=label, marker_color=cor+"cc"))
            tx, ty = trend_line(anos, ys)
            if tx:
                fig.add_trace(go.Scatter(x=tx, y=ty, name=f"↗ {label}",
                    mode="lines", line=dict(color=cor, width=2, dash="dot"),
                    showlegend=(len(series_list)==1)))
        fig.update_layout(barmode="stack" if stack else "group")

    elif modo == "Média Móvel 6m":
        for i, (label, serie, _) in enumerate(series_list):
            ys_raw = [serie.get(p) for p in periodos]
            ys_mm  = [media_movel(serie, periodos).get(p) for p in periodos]
            cor = CORES[i % len(CORES)]
            fig.add_trace(go.Scatter(x=periodos, y=ys_raw, name=label,
                mode="lines", line=dict(color=cor+"44", width=1), showlegend=True))
            fig.add_trace(go.Scatter(x=periodos, y=ys_mm, name=f"MM6 {label}",
                mode="lines", line=dict(color=cor, width=2.5)))

    else:  # Mensal
        for i, (label, serie, _) in enumerate(series_list):
            ys  = [serie.get(p) for p in periodos]
            cor = CORES[i % len(CORES)]
            if tipo_chart == "bar":
                fig.add_trace(go.Bar(x=periodos, y=ys, name=label, marker_color=cor+"cc"))
            else:
                fig.add_trace(go.Scatter(x=periodos, y=ys, name=label,
                    mode="lines+markers", line=dict(color=cor, width=2.5),
                    marker=dict(size=3 if len(periodos)>30 else 5), connectgaps=False))
        if stack: fig.update_layout(barmode="stack")

    fig.update_layout(
        title=dict(text=titulo, font=dict(size=12, color="#003087")),
        height=290, margin=dict(l=8,r=8,t=36,b=8),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
        plot_bgcolor="white", paper_bgcolor="white", hovermode="x unified",
        xaxis=dict(showgrid=False, tickfont=dict(size=9),
                   tickangle=-30 if modo=="Mensal" and len(periodos)>24 else 0),
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
    modo = st.radio("Modo", ["Anual", "Média Móvel 6m", "Mensal"], label_visibility="collapsed")
    st.markdown("---")
    st.markdown("**Período**")
    anos_disp = sorted(set(p[:4] for p in periodos_todos))
    ano_ini = st.selectbox("De", anos_disp, index=0)
    ano_fim = st.selectbox("Até", anos_disp, index=len(anos_disp)-1)
    periodos = [p for p in periodos_todos if ano_ini <= p[:4] <= ano_fim]
    st.markdown("---")
    st.caption("Fonte: transparencia.sns.gov.pt")


# ── Secções ───────────────────────────────────────────────────────────────────
def secao_visao_geral():
    st.markdown('<div class="sec-title">📊 Visão Geral — Indicadores Críticos do SNS</div>', unsafe_allow_html=True)
    st.markdown('<div class="insight red">⚠️ Os indicadores abaixo mostram a evolução dos principais problemas estruturais do SNS. Vermelho = deterioração face ao ano anterior.</div>', unsafe_allow_html=True)

    st.markdown("**Acesso & Listas de Espera**")
    c = st.columns(4)
    show_kpi(c[0], get("acesso","consultas-em-tempo-real","1as_consultas_realizadas_em_tempo_adequado"), "% 1ªs Consultas em TMRG", invertido=True, unidade="%")
    show_kpi(c[1], get("acesso","demora-media-antes-da-cirurgia","demora_media_antes_da_cirurgia"), "Demora Média pré-Cirurgia", invertido=True, unidade="dias")
    show_kpi(c[2], get("acesso","utentes-inscritos-em-cuidados-de-saude-primarios","total_utentes_sem_mdf_atribuido"), "Utentes sem Médico de Família", invertido=True)
    show_kpi(c[3], get("acesso","atendimentos-em-urgencia-triagem-manchester","no_de_atendimentos_em_urgencia_su_triagem_manchester_verde"), "Triagem Verde (evitáveis)", invertido=True)

    st.markdown("**Sustentabilidade Financeira**")
    c = st.columns(4)
    show_kpi(c[0], get("financeiro","agregados-economico-financeiros","resultado_liquido"), "Resultado Líquido SNS", invertido=True, unidade="€")
    show_kpi(c[1], get("financeiro","divida-total-vencida-e-pagamentos","divida_vencida_fornecedores_externos"), "Dívida Vencida", invertido=True, unidade="€")
    show_kpi(c[2], get("financeiro","divida-total-vencida-e-pagamentos","pagamentos_em_atraso"), "Pagamentos em Atraso", invertido=True, unidade="€")
    show_kpi(c[3], get("financeiro","despesa-com-medicamentos-no-ambulatorio-sns","encargos_sns_ambulatorio"), "Medicamentos Ambulatório", invertido=True, unidade="€")

    st.markdown("**Recursos Humanos**")
    c = st.columns(4)
    show_kpi(c[0], get("rh","trabalhadores-por-grupo-profissional","enfermeiros"), "Enfermeiros")
    show_kpi(c[1], get("rh","trabalhadores-por-grupo-profissional","medicos_s_internos"), "Médicos (excl. internos)")
    show_kpi(c[2], get("rh","contagem-dos-dias-de-ausencia-ao-trabalho-segundo-o-motivo-de-ausencia","valor"), "Dias de Ausência", invertido=True)
    show_kpi(c[3], get("rh","contagem-das-horas-de-trabalho-nocturno-normal-e-extraordinario","trabalho_extraordinario_diurno"), "Horas Extra Diurnas", invertido=True)

    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.plotly_chart(chart([("Resultado Líquido", get("financeiro","agregados-economico-financeiros","resultado_liquido"), "soma")],
        "Resultado Líquido do SNS (€)", modo), use_container_width=True)
    c2.plotly_chart(chart([("Utentes sem Médico de Família", get("acesso","utentes-inscritos-em-cuidados-de-saude-primarios","total_utentes_sem_mdf_atribuido"), "soma")],
        "Utentes sem Médico de Família", modo), use_container_width=True)
    c3, c4 = st.columns(2)
    c3.plotly_chart(chart([
        ("Triagem Verde", get("acesso","atendimentos-em-urgencia-triagem-manchester","no_de_atendimentos_em_urgencia_su_triagem_manchester_verde"), "soma"),
        ("Triagem Azul",  get("acesso","atendimentos-em-urgencia-triagem-manchester","no_de_atendimentos_em_urgencia_su_triagem_manchester_azul"),  "soma"),
    ], "Urgências Evitáveis (Verde + Azul)", modo), use_container_width=True)
    c4.plotly_chart(chart([("Dias de Ausência", get("rh","contagem-dos-dias-de-ausencia-ao-trabalho-segundo-o-motivo-de-ausencia","valor"), "soma")],
        "Absentismo — Dias de Ausência", modo), use_container_width=True)


def secao_acesso():
    st.markdown('<div class="sec-title">⏳ Acesso & Listas de Espera</div>', unsafe_allow_html=True)
    st.markdown('<div class="insight red">A percentagem de 1ªs consultas em TMRG mantém-se abaixo de 60%. A triagem verde nas urgências revela que os CSP não absorvem a procura.</div>', unsafe_allow_html=True)

    c = st.columns(4)
    show_kpi(c[0], get("acesso","consultas-em-tempo-real","1as_consultas_realizadas_em_tempo_adequado"), "% 1ªs Consultas em TMRG", invertido=True, unidade="%")
    show_kpi(c[1], get("acesso","demora-media-antes-da-cirurgia","demora_media_antes_da_cirurgia"), "Demora Média pré-Cirurgia", invertido=True, unidade="dias")
    show_kpi(c[2], get("acesso","utentes-inscritos-em-cuidados-de-saude-primarios","total_utentes_sem_mdf_atribuido"), "Utentes sem Médico de Família", invertido=True)
    show_kpi(c[3], get("acesso","utentes-inscritos-em-cuidados-de-saude-primarios","total_utentes_com_mdf_atribuido0"), "% com Médico de Família", unidade="%")

    c1, c2 = st.columns(2)
    c1.plotly_chart(chart([("% em TMRG", get("acesso","consultas-em-tempo-real","1as_consultas_realizadas_em_tempo_adequado"), "media")],
        "1ªs Consultas em Tempo Adequado (%)", modo), use_container_width=True)
    c2.plotly_chart(chart([("Demora Média (dias)", get("acesso","demora-media-antes-da-cirurgia","demora_media_antes_da_cirurgia"), "media")],
        "Demora Média antes da Cirurgia (dias)", modo), use_container_width=True)

    c3, c4 = st.columns(2)
    c3.plotly_chart(chart([
        ("Verde — não urgente",  get("acesso","atendimentos-em-urgencia-triagem-manchester","no_de_atendimentos_em_urgencia_su_triagem_manchester_verde"),  "soma"),
        ("Azul — pouco urgente", get("acesso","atendimentos-em-urgencia-triagem-manchester","no_de_atendimentos_em_urgencia_su_triagem_manchester_azul"),   "soma"),
        ("Amarela — urgente",    get("acesso","atendimentos-em-urgencia-triagem-manchester","no_de_atendimentos_em_urgencia_su_triagem_manchester_amarela"), "soma"),
        ("Vermelha — emergência",get("acesso","atendimentos-em-urgencia-triagem-manchester","no_de_atendimentos_em_urgencia_su_triagem_manchester_vermelha"),"soma"),
    ], "Triagem de Manchester nas Urgências", modo, stack=True), use_container_width=True)
    c4.plotly_chart(chart([("Utentes sem Médico de Família", get("acesso","utentes-inscritos-em-cuidados-de-saude-primarios","total_utentes_sem_mdf_atribuido"), "soma")],
        "Utentes sem Médico de Família atribuído", modo), use_container_width=True)


def secao_atividade():
    st.markdown('<div class="sec-title">🏥 Atividade Assistencial</div>', unsafe_allow_html=True)

    c = st.columns(4)
    show_kpi(c[0], get("atividade","intervencoes-cirurgicas","no_intervencoes_cirurgicas_programadas"), "Cirurgias Programadas")
    show_kpi(c[1], get("atividade","atendimentos-por-tipo-de-urgencia-hospitalar-link","total_urgencias"), "Total Urgências")
    show_kpi(c[2], get("atividade","01_sica_evolucao-mensal-das-consultas-medicas-hospitalares","no_de_consultas_medicas_total"), "Consultas Hospitalares")
    show_kpi(c[3], get("atividade","atividade-de-internamento-hospitalar","doentes_saidos"), "Doentes Saídos")

    c1, c2 = st.columns(2)
    c1.plotly_chart(chart([
        ("Programadas", get("atividade","intervencoes-cirurgicas","no_intervencoes_cirurgicas_programadas"), "soma"),
        ("Ambulatório",  get("atividade","intervencoes-cirurgicas","no_intervencoes_cirurgicas_de_ambulatorio"), "soma"),
        ("Urgentes",     get("atividade","intervencoes-cirurgicas","no_intervencoes_cirurgicas_urgentes"), "soma"),
    ], "Intervenções Cirúrgicas por Tipo", modo, stack=True), use_container_width=True)
    c2.plotly_chart(chart([
        ("Total",        get("atividade","atendimentos-por-tipo-de-urgencia-hospitalar-link","total_urgencias"), "soma"),
        ("Gerais",       get("atividade","atendimentos-por-tipo-de-urgencia-hospitalar-link","urgencias_geral"), "soma"),
        ("Pediátricas",  get("atividade","atendimentos-por-tipo-de-urgencia-hospitalar-link","urgencias_pediatricas"), "soma"),
    ], "Urgências Hospitalares", modo), use_container_width=True)

    c3, c4 = st.columns(2)
    c3.plotly_chart(chart([
        ("Total Consultas Hosp.", get("atividade","01_sica_evolucao-mensal-das-consultas-medicas-hospitalares","no_de_consultas_medicas_total"), "soma"),
        ("1ªs Consultas",        get("atividade","01_sica_evolucao-mensal-das-consultas-medicas-hospitalares","no_de_primeiras_consultas"), "soma"),
    ], "Consultas Médicas Hospitalares", modo), use_container_width=True)
    c4.plotly_chart(chart([
        ("Presenciais CSP",     get("atividade","evolucao-das-consultas-medicas-nos-csp","no_de_consultas_medicas_presencias_qt"), "soma"),
        ("Não Presenciais CSP", get("atividade","evolucao-das-consultas-medicas-nos-csp","no_de_consultas_medicas_nao_presenciais_ou_inespecificas_qt"), "soma"),
    ], "Consultas nos Cuidados de Saúde Primários", modo), use_container_width=True)


def secao_financeiro():
    st.markdown('<div class="sec-title">💶 Financeiro</div>', unsafe_allow_html=True)
    st.markdown('<div class="insight red">O SNS tem défice operacional estrutural. Os gastos crescem acima das receitas e a dívida a fornecedores acumula, tornando o sistema financeiramente insustentável.</div>', unsafe_allow_html=True)

    c = st.columns(4)
    show_kpi(c[0], get("financeiro","agregados-economico-financeiros","gastos_operacionais"), "Gastos Operacionais", invertido=True, unidade="€")
    show_kpi(c[1], get("financeiro","agregados-economico-financeiros","resultado_liquido"), "Resultado Líquido", invertido=True, unidade="€")
    show_kpi(c[2], get("financeiro","divida-total-vencida-e-pagamentos","divida_vencida_fornecedores_externos"), "Dívida Vencida", invertido=True, unidade="€")
    show_kpi(c[3], get("financeiro","divida-total-vencida-e-pagamentos","pagamentos_em_atraso"), "Pagamentos em Atraso", invertido=True, unidade="€")

    c1, c2 = st.columns(2)
    c1.plotly_chart(chart([
        ("Gastos Operacionais",     get("financeiro","agregados-economico-financeiros","gastos_operacionais"), "soma"),
        ("Rendimentos Operacionais",get("financeiro","agregados-economico-financeiros","rendimentos_operacionais"), "soma"),
    ], "Gastos vs Rendimentos Operacionais (€)", modo), use_container_width=True)
    c2.plotly_chart(chart([("Resultado Líquido", get("financeiro","agregados-economico-financeiros","resultado_liquido"), "soma")],
        "Resultado Líquido do SNS (€)", modo), use_container_width=True)

    c3, c4 = st.columns(2)
    c3.plotly_chart(chart([
        ("Dívida Total",      get("financeiro","divida-total-vencida-e-pagamentos","divida_total_fornecedores_externos"), "soma"),
        ("Dívida Vencida",    get("financeiro","divida-total-vencida-e-pagamentos","divida_vencida_fornecedores_externos"), "soma"),
        ("Pagamentos Atraso", get("financeiro","divida-total-vencida-e-pagamentos","pagamentos_em_atraso"), "soma"),
    ], "Dívida a Fornecedores (€)", modo), use_container_width=True)
    c4.plotly_chart(chart([
        ("Medicamentos Hospitalar",  get("financeiro","despesa-com-medicamentos-nos-hospitais-do-sns","encargos_sns_hospitalar"), "soma"),
        ("Medicamentos Ambulatório", get("financeiro","despesa-com-medicamentos-no-ambulatorio-sns","encargos_sns_ambulatorio"), "soma"),
    ], "Despesa com Medicamentos SNS (€)", modo), use_container_width=True)


def secao_rh():
    st.markdown('<div class="sec-title">👩‍⚕️ Recursos Humanos</div>', unsafe_allow_html=True)
    st.markdown('<div class="insight">⚠️ Absentismo e horas extraordinárias crescentes são sinal de sobrecarga. Constituem um risco sério para a retenção de profissionais no SNS.</div>', unsafe_allow_html=True)

    c = st.columns(4)
    show_kpi(c[0], get("rh","trabalhadores-por-grupo-profissional","total_geral"), "Total Trabalhadores")
    show_kpi(c[1], get("rh","trabalhadores-por-grupo-profissional","enfermeiros"), "Enfermeiros")
    show_kpi(c[2], get("rh","contagem-dos-dias-de-ausencia-ao-trabalho-segundo-o-motivo-de-ausencia","valor"), "Dias de Ausência", invertido=True)
    show_kpi(c[3], get("rh","contagem-das-horas-de-trabalho-nocturno-normal-e-extraordinario","trabalho_extraordinario_diurno"), "Horas Extra Diurnas", invertido=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(chart([
        ("Total",    get("rh","trabalhadores-por-grupo-profissional","total_geral"), "soma"),
        ("Médicos",  get("rh","trabalhadores-por-grupo-profissional","medicos_s_internos"), "soma"),
        ("Internos", get("rh","trabalhadores-por-grupo-profissional","medicos_internos"), "soma"),
        ("Enfermeiros",get("rh","trabalhadores-por-grupo-profissional","enfermeiros"), "soma"),
        ("TDT",      get("rh","trabalhadores-por-grupo-profissional","tdt"), "soma"),
    ], "Trabalhadores por Grupo Profissional", modo), use_container_width=True)
    c2.plotly_chart(chart([("Dias de Ausência", get("rh","contagem-dos-dias-de-ausencia-ao-trabalho-segundo-o-motivo-de-ausencia","valor"), "soma")],
        "Absentismo — Dias de Ausência ao Trabalho", modo), use_container_width=True)

    c3, c4 = st.columns(2)
    c3.plotly_chart(chart([
        ("Extraordinário Diurno",  get("rh","contagem-das-horas-de-trabalho-nocturno-normal-e-extraordinario","trabalho_extraordinario_diurno"), "soma"),
        ("Extraordinário Nocturno",get("rh","contagem-das-horas-de-trabalho-nocturno-normal-e-extraordinario","trabalho_extraordinario_nocturno"), "soma"),
    ], "Horas de Trabalho Extraordinário", modo), use_container_width=True)

    # Composição actual
    s_tot = get("rh","trabalhadores-por-grupo-profissional","total_geral")
    p_ref, _ = ultimo_com_dados(s_tot, periodos)
    if p_ref:
        grupos = {
            "Médicos": get("rh","trabalhadores-por-grupo-profissional","medicos_s_internos").get(p_ref) or 0,
            "Internos": get("rh","trabalhadores-por-grupo-profissional","medicos_internos").get(p_ref) or 0,
            "Enfermeiros": get("rh","trabalhadores-por-grupo-profissional","enfermeiros").get(p_ref) or 0,
            "TDT": get("rh","trabalhadores-por-grupo-profissional","tdt").get(p_ref) or 0,
        }
        outros = (s_tot.get(p_ref) or 0) - sum(grupos.values())
        if outros > 0: grupos["Outros"] = outros
        fig = go.Figure(go.Bar(
            x=list(grupos.values()), y=list(grupos.keys()), orientation="h",
            marker_color=["#0066cc","#4d94ff","#28a745","#fd7e14","#6c757d"],
        ))
        fig.update_layout(title=dict(text=f"Composição ({p_ref})", font=dict(size=12,color="#003087")),
            height=260, margin=dict(l=8,r=8,t=36,b=8),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(gridcolor="#f0f0f0",tickfont=dict(size=9)),
            yaxis=dict(tickfont=dict(size=9)))
        c4.plotly_chart(fig, use_container_width=True)


# ── Router ────────────────────────────────────────────────────────────────────
if   "Visão"     in secao: secao_visao_geral()
elif "Acesso"    in secao: secao_acesso()
elif "Atividade" in secao: secao_atividade()
elif "Financeiro"in secao: secao_financeiro()
elif "Recursos"  in secao: secao_rh()
