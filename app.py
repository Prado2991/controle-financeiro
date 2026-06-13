import io
import json
from datetime import date, datetime
from typing import Optional

import gspread
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pytz
import streamlit as st
from dateutil.relativedelta import relativedelta
from google.oauth2.service_account import Credentials

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Finanças Jonathan",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PLANILHA_ID = "1JyVUY1pKQs90jtPPBvEHDLnGxBw3wdooEFWSq-1e5D4"
ABA_LANCAMENTOS = "Lancamentos"
ABA_ORCAMENTOS = "Orcamentos"

CATEGORIAS_POR_TIPO = {
    "Gasto Fixo": ["Luz", "Água", "Internet", "Telefone", "Condomínio",
                   "Aluguel", "Plano de Saúde", "Outros Fixos"],
    "Gasto Variável": ["Refeição", "Supermercado", "Abastecimento", "Shopping",
                       "Farmácia", "Lazer", "Viagem", "Presentes", "Outros Variáveis"],
    "Assinatura": ["Streaming (Netflix/Spotify)", "Academia", "Clube de Assinatura",
                   "Software/App", "Outras Assinaturas"],
    "Entrada": ["Salário", "Rendimento", "Pix Recebido", "Outras Entradas"],
}
FORMAS_PAGAMENTO = ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"]
RESPONSAVEIS = ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"]

CORES = {
    "entrada": "#10b981", "saida": "#ef4444", "saldo_pos": "#059669",
    "saldo_neg": "#dc2626", "nu": "#8b5cf6", "bb": "#fbbf24",
    "indigo": "#312e81", "emerald": "#047857",
}
PALETA = ["#312e81", "#059669", "#8b5cf6", "#fbbf24", "#0ea5e9", "#ef4444",
          "#10b981", "#6366f1", "#f97316", "#14b8a6", "#a855f7", "#84cc16"]


# ──────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ──────────────────────────────────────────────────────────────────────────────
def hoje_br() -> date:
    return datetime.now(pytz.timezone("America/Sao_Paulo")).date()


def brl(valor) -> str:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "R$ 0,00"
    sinal = "-" if v < 0 else ""
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {s}"


def parse_valor(txt) -> float:
    if txt is None or txt == "":
        return 0.0
    try:
        t = str(txt).replace("R$", "").replace("r$", "").strip()
        if "," in t and "." in t:
            t = t.replace(".", "").replace(",", ".")
        elif "," in t:
            t = t.replace(",", ".")
        return round(float(t), 2)
    except Exception:
        return 0.0


def parse_data(valor) -> Optional[date]:
    if not valor or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = str(valor).split()[0].strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def mes_competencia(d: date, forma: str) -> str:
    """Cartão: <7 → mês anterior; >=7 → mês atual. Outras formas: mês real."""
    if "Cartão" not in str(forma):
        return d.strftime("%Y-%m")
    base = d - relativedelta(months=1) if d.day < 7 else d
    return base.strftime("%Y-%m")


def rotulo_mes(mes_str: str) -> str:
    try:
        dt = datetime.strptime(mes_str, "%Y-%m")
        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                 "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        return f"{meses[dt.month - 1]}/{dt.year}"
    except Exception:
        return mes_str


# ──────────────────────────────────────────────────────────────────────────────
# CONEXÃO GOOGLE SHEETS (cacheada)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="🔌 Conectando à planilha…")
def conectar():
    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]
    if "google_credentials" not in st.secrets:
        return None, "Segredo 'google_credentials' ausente."
    try:
        creds_json = json.loads(st.secrets["google_credentials"])
        if "private_key" in creds_json:
            k = creds_json["private_key"].replace("\\n", "\n")
            if k.startswith('"') and k.endswith('"'):
                k = k[1:-1]
            creds_json["private_key"] = k
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        client = gspread.authorize(creds)
        plan = client.open_by_key(PLANILHA_ID)
        sheet = plan.worksheet(ABA_LANCAMENTOS)
        # garante aba de orçamentos
        try:
            plan.worksheet(ABA_ORCAMENTOS)
        except gspread.WorksheetNotFound:
            nova = plan.add_worksheet(title=ABA_ORCAMENTOS, rows=100, cols=3)
            nova.append_row(["Categoria", "Teto_Mensal", "Atualizado_Em"])
        return (plan, sheet), None
    except Exception as e:
        return None, f"Erro de conexão: {e}"


@st.cache_data(ttl=120, show_spinner="📥 Carregando lançamentos…")
def carregar_lancamentos(_sheet) -> pd.DataFrame:
    rows = _sheet.get_all_records()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


@st.cache_data(ttl=120, show_spinner="🎯 Carregando orçamentos…")
def carregar_orcamentos(_plan) -> pd.DataFrame:
    try:
        ws = _plan.worksheet(ABA_ORCAMENTOS)
        df = pd.DataFrame(ws.get_all_records())
        if df.empty:
            return pd.DataFrame(columns=["Categoria", "Teto_Mensal", "Atualizado_Em"])
        df["Teto_Mensal"] = df["Teto_Mensal"].apply(parse_valor)
        return df
    except Exception:
        return pd.DataFrame(columns=["Categoria", "Teto_Mensal", "Atualizado_Em"])


def limpar_cache_dados():
    carregar_lancamentos.clear()
    carregar_orcamentos.clear()


# ──────────────────────────────────────────────────────────────────────────────
# PROJEÇÃO (vetorizada o quanto possível)
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner="📊 Projetando parcelas e assinaturas…")
def projetar(df_bruto: pd.DataFrame, hoje: date) -> tuple[pd.DataFrame, list[str]]:
    """
    Retorna:
      - df_proj: 1 linha por (lançamento, parcela/mês). NÃO explodido por responsável.
                 Coluna Responsaveis = lista; Valor_Parcela = valor já dividido por nº de parcelas.
      - avisos: linhas inválidas para diagnóstico.
    """
    if df_bruto.empty:
        return pd.DataFrame(), []

    df = df_bruto.copy()
    df.columns = [c.strip() for c in df.columns]
    avisos: list[str] = []

    df["_Data"] = df["Data"].apply(parse_data)
    invalidas = df[df["_Data"].isna()]
    if not invalidas.empty:
        avisos.append(f"{len(invalidas)} lançamento(s) com data inválida foram ignorados.")
    df = df[df["_Data"].notna()].copy()

    df["_Valor"] = df["Valor"].apply(parse_valor)
    df["_Tipo"] = df.get("Tipo", "Gasto Variável").fillna("Gasto Variável")
    df["_Forma"] = df.get("Forma_Pagamento", "Dinheiro").fillna("Dinheiro")
    df["_Parc"] = pd.to_numeric(df.get("Parcelas_Totais", 1), errors="coerce").fillna(1).astype(int).clip(lower=1)
    df["_ParceladoFlag"] = df.get("Parcelado", "Não").astype(str).str.lower().eq("sim")
    df["_Parc"] = np.where(df["_ParceladoFlag"], df["_Parc"], 1)

    def split_resp(s):
        lst = [r.strip() for r in str(s or "Jonathan").split(",") if r.strip()]
        return lst or ["Jonathan"]
    df["_Resp"] = df.get("Responsavel", "Jonathan").apply(split_resp)

    limite_futuro = hoje + relativedelta(months=12)
    limite_passado_assin = hoje - relativedelta(months=24)  # cobre histórico recente

    registros = []
    for r in df.itertuples(index=False):
        dt_compra: date = r._Data
        val_total = float(r._Valor)
        n_parc = int(r._Parc)
        val_parc = val_total / n_parc if n_parc > 0 else val_total

        if r._Tipo == "Assinatura":
            # gera meses do max(data compra, hoje-24m) até hoje+12m
            inicio = max(dt_compra, limite_passado_assin.replace(day=dt_compra.day if dt_compra.day <= 28 else 28))
            # iterações mensais
            cur = inicio
            i = 0
            while cur <= limite_futuro and i < 60:
                registros.append({
                    "Data": dt_compra,
                    "Descricao": r.Descricao if hasattr(r, "Descricao") else "",
                    "Categoria": getattr(r, "Categoria", ""),
                    "Tipo": r._Tipo,
                    "Forma_Pagamento": r._Forma,
                    "Responsaveis": r._Resp,
                    "Parcela_Atual": "Recorrente",
                    "Valor_Parcela": val_parc,
                    "Mes_Fatura": mes_competencia(cur, r._Forma),
                    "Eh_Futuro": cur > hoje,
                })
                cur = cur + relativedelta(months=1)
                i += 1
        else:
            for p in range(n_parc):
                dt_parc = dt_compra + relativedelta(months=p)
                registros.append({
                    "Data": dt_compra,
                    "Descricao": getattr(r, "Descricao", ""),
                    "Categoria": getattr(r, "Categoria", ""),
                    "Tipo": r._Tipo,
                    "Forma_Pagamento": r._Forma,
                    "Responsaveis": r._Resp,
                    "Parcela_Atual": f"{p+1}/{n_parc}" if n_parc > 1 else "1/1",
                    "Valor_Parcela": val_parc,
                    "Mes_Fatura": mes_competencia(dt_parc, r._Forma),
                    "Eh_Futuro": dt_parc > hoje,
                })

    df_proj = pd.DataFrame(registros)
    return df_proj, avisos


def explodir_responsaveis(df_proj: pd.DataFrame) -> pd.DataFrame:
    """Para visões 'por pessoa': divide o valor pelo nº de responsáveis."""
    if df_proj.empty:
        return df_proj
    df = df_proj.copy()
    df["_n"] = df["Responsaveis"].apply(len)
    df["Valor_Pessoa"] = df["Valor_Parcela"] / df["_n"]
    df = df.explode("Responsaveis").rename(columns={"Responsaveis": "Responsavel"})
    return df


# ──────────────────────────────────────────────────────────────────────────────
# CSS LEVE
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.main-title{background:linear-gradient(90deg,#312e81,#047857);-webkit-background-clip:text;
-webkit-text-fill-color:transparent;font-size:30px;font-weight:800;margin-bottom:0;}
.subtitle{color:#64748b;margin-top:0;margin-bottom:18px;}
.insight-box{background:linear-gradient(135deg,#f0fdf4 0%,#eef2ff 100%);
border-left:4px solid #10b981;padding:14px 18px;border-radius:8px;margin:8px 0;
font-size:14px;color:#1e293b;}
.alert-box{background:#fef2f2;border-left:4px solid #ef4444;padding:14px 18px;
border-radius:8px;margin:8px 0;font-size:14px;color:#7f1d1d;}
div[data-testid="stMetric"]{background:#ffffff;padding:14px;border-radius:10px;
box-shadow:0 1px 3px rgba(0,0,0,0.08);border:1px solid #e2e8f0;}
div[data-testid="stMetricLabel"]{font-weight:600;color:#475569;}
.stTabs [data-baseweb="tab-list"]{gap:4px;}
.stTabs [data-baseweb="tab"]{background:#f1f5f9;border-radius:8px 8px 0 0;
padding:8px 14px;font-weight:600;color:#475569;}
.stTabs [aria-selected="true"]{background:#312e81!important;color:#fff!important;}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────────────────────
HOJE = hoje_br()
st.markdown('<div class="main-title">💰 Controle Financeiro Familiar</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Jonathan Prado · visão completa de receitas, despesas e saldo</div>',
            unsafe_allow_html=True)

# Fechamento de faturas
venc = date(HOJE.year, HOJE.month, 7)
if HOJE.day >= 7:
    venc = venc + relativedelta(months=1)
dias_restantes = (venc - HOJE).days
st.info(f"⏳ **Fechamento das faturas:** faltam **{dias_restantes} dias** "
        f"(corte em 06/{venc.strftime('%m/%Y')} às 23:59)")

# Conexão
conn, erro = conectar()
if erro:
    st.error(f"❌ {erro}")
    st.stop()
plan, sheet = conn


# ──────────────────────────────────────────────────────────────────────────────
# TABS
# ──────────────────────────────────────────────────────────────────────────────
tab_novo, tab_dash, tab_parc, tab_cat, tab_orc, tab_aj = st.tabs([
    "📲 Novo Lançamento",
    "📊 Dashboard & Resumo",
    "💳 Parcelas & Assinaturas",
    "📂 Categorias & Métodos",
    "🎯 Orçamento",
    "✏️ Ajustar",
])

# ============================================================================
# TAB 1 — NOVO LANÇAMENTO
# ============================================================================
with tab_novo:
    st.subheader("Registrar gasto ou entrada")
    tipo = st.selectbox("Tipo de Lançamento", list(CATEGORIAS_POR_TIPO.keys()))
    lista_cats = CATEGORIAS_POR_TIPO[tipo]

    with st.form("form_lanc", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            data_l = st.date_input("Data", HOJE, format="DD/MM/YYYY")
            descricao = st.text_input("Descrição",
                                      placeholder="Ex: Sorveteria Sávio, Mercado Muffato")
            valor_txt = st.text_input("Valor (R$)", value="0,00",
                                      help="Use vírgula para centavos. Ex: 8,99")
        with c2:
            categoria = st.selectbox("Categoria", lista_cats)
            responsavel = st.multiselect("Para Quem?", RESPONSAVEIS, default=["Jonathan"])
            forma = st.selectbox("Forma de Pagamento", FORMAS_PAGAMENTO)
            pode_parcelar = tipo in ["Gasto Variável", "Gasto Fixo"]
            if pode_parcelar:
                parcelado = st.radio("Parcelada?", ["Não", "Sim"], horizontal=True)
                n_parc = st.number_input("Nº de Parcelas", 2, 48, 2, 1) if parcelado == "Sim" else 1
            else:
                parcelado, n_parc = "Não", 1

        salvar = st.form_submit_button("🚀 Gravar na Planilha", use_container_width=True)

        if salvar:
            val = parse_valor(valor_txt)
            if not responsavel:
                st.error("Selecione ao menos um responsável.")
            elif not descricao or val <= 0:
                st.error("Preencha descrição e valor maior que zero (ex: 8,99).")
            else:
                registro = [
                    str(data_l), descricao,
                    f"{val:.2f}".replace(".", ","),
                    categoria, tipo, ", ".join(responsavel),
                    forma, parcelado, int(n_parc),
                ]
                try:
                    sheet.append_row(registro, value_input_option="USER_ENTERED")
                    limpar_cache_dados()
                    st.success(f"✅ '{descricao}' gravado: {brl(val)}")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erro ao gravar: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# CARREGAMENTO DE DADOS (apenas se houver lançamentos)
# ──────────────────────────────────────────────────────────────────────────────
df_bruto = carregar_lancamentos(sheet)
df_orc = carregar_orcamentos(plan)

if df_bruto.empty:
    with tab_dash:
        st.info("Nenhum lançamento ainda. Use a aba **Novo Lançamento** para começar.")
    st.stop()

df_proj, avisos = projetar(df_bruto, HOJE)
if avisos:
    with st.expander("⚠️ Diagnóstico"):
        for a in avisos:
            st.warning(a)

if df_proj.empty:
    with tab_dash:
        st.info("Sem dados projetados para exibir.")
    st.stop()

df_pessoa = explodir_responsaveis(df_proj)


# ============================================================================
# TAB 2 — DASHBOARD & RESUMO
# ============================================================================
with tab_dash:
    meses = sorted(df_proj["Mes_Fatura"].unique())
    mes_atual = HOJE.strftime("%Y-%m")
    idx_def = meses.index(mes_atual) if mes_atual in meses else len(meses) - 1
    mes_sel = st.selectbox("📅 Mês de competência",
                           meses, index=idx_def,
                           format_func=rotulo_mes)

    df_mes = df_proj[df_proj["Mes_Fatura"] == mes_sel]
    df_mes_pessoa = df_pessoa[df_pessoa["Mes_Fatura"] == mes_sel]

    # KPIs
    entradas = df_mes.loc[df_mes["Tipo"] == "Entrada", "Valor_Parcela"].sum()
    despesas = df_mes.loc[df_mes["Tipo"] != "Entrada", "Valor_Parcela"].sum()
    saldo = entradas - despesas
    fat_nu = df_mes.loc[(df_mes["Forma_Pagamento"] == "Cartão Nu") &
                        (df_mes["Tipo"] != "Entrada"), "Valor_Parcela"].sum()
    fat_bb = df_mes.loc[(df_mes["Forma_Pagamento"] == "Cartão BB") &
                        (df_mes["Tipo"] != "Entrada"), "Valor_Parcela"].sum()

    # Variação vs mês anterior
    idx_sel = meses.index(mes_sel)
    delta_str = None
    if idx_sel > 0:
        mes_ant = meses[idx_sel - 1]
        desp_ant = df_proj.loc[(df_proj["Mes_Fatura"] == mes_ant) &
                               (df_proj["Tipo"] != "Entrada"), "Valor_Parcela"].sum()
        if desp_ant > 0:
            var = (despesas - desp_ant) / desp_ant * 100
            delta_str = f"{var:+.1f}% vs {rotulo_mes(mes_ant)}"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🟢 Entradas", brl(entradas))
    k2.metric("🔴 Despesas", brl(despesas), delta=delta_str, delta_color="inverse")
    k3.metric("💰 Saldo", brl(saldo),
              delta="positivo" if saldo >= 0 else "negativo",
              delta_color="normal" if saldo >= 0 else "inverse")
    k4.metric("💳 Faturas (Nu + BB)", brl(fat_nu + fat_bb),
              delta=f"Nu {brl(fat_nu)} · BB {brl(fat_bb)}")

    # ── Resumo inteligente
    insights = []
    df_desp = df_mes[df_mes["Tipo"] != "Entrada"]
    if not df_desp.empty:
        top_cat = df_desp.groupby("Categoria")["Valor_Parcela"].sum().sort_values(ascending=False)
        pct = top_cat.iloc[0] / despesas * 100 if despesas > 0 else 0
        insights.append(f"📌 Maior categoria: **{top_cat.index[0]}** com "
                        f"**{brl(top_cat.iloc[0])}** ({pct:.0f}% das despesas).")
    if delta_str:
        seta = "📈" if despesas > desp_ant else "📉"
        insights.append(f"{seta} Despesas **{delta_str}**.")
    insights.append(f"⏳ Faltam **{dias_restantes} dias** para o fechamento das faturas.")

    # Saldo projetado considerando meses futuros
    futuro = df_proj[(df_proj["Mes_Fatura"] > mes_sel) & (df_proj["Tipo"] != "Entrada")]
    if not futuro.empty:
        comp_futuro = futuro["Valor_Parcela"].sum()
        insights.append(f"🔮 Compromissos futuros já lançados: **{brl(comp_futuro)}** "
                        f"em {futuro['Mes_Fatura'].nunique()} mês(es).")

    # Alertas de orçamento do mês
    alertas_orc = []
    if not df_orc.empty and not df_desp.empty:
        gasto_cat = df_desp.groupby("Categoria")["Valor_Parcela"].sum()
        for _, row in df_orc.iterrows():
            cat, teto = row["Categoria"], row["Teto_Mensal"]
            if teto <= 0:
                continue
            gasto = gasto_cat.get(cat, 0)
            pct = gasto / teto * 100
            if pct >= 90:
                alertas_orc.append(f"⛔ **{cat}**: {brl(gasto)} / {brl(teto)} ({pct:.0f}%)")
            elif pct >= 70:
                alertas_orc.append(f"🟡 **{cat}**: {brl(gasto)} / {brl(teto)} ({pct:.0f}%)")

    for txt in insights:
        st.markdown(f'<div class="insight-box">{txt}</div>', unsafe_allow_html=True)
    for txt in alertas_orc:
        st.markdown(f'<div class="alert-box">{txt}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📈 Visualizações")

    g1, g2 = st.columns(2)

    # Donut categorias
    with g1:
        st.markdown("**Gastos por Categoria**")
        if not df_desp.empty:
            dfc = df_desp.groupby("Categoria")["Valor_Parcela"].sum().reset_index()
            fig = px.pie(dfc, values="Valor_Parcela", names="Categoria",
                         hole=0.55, color_discrete_sequence=PALETA)
            fig.update_traces(
                textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>",
            )
            fig.add_annotation(text=f"<b>{brl(despesas)}</b><br><span style='font-size:11px;color:#64748b'>Total</span>",
                               showarrow=False, font_size=15)
            fig.update_layout(showlegend=False, height=340,
                              margin=dict(t=10, b=10, l=10, r=10),
                              transition_duration=400)
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.info("Sem gastos no mês.")

    # Barras formas de pagamento
    with g2:
        st.markdown("**Formas de Pagamento**")
        if not df_desp.empty:
            dff = (df_desp.groupby("Forma_Pagamento")["Valor_Parcela"].sum()
                   .sort_values(ascending=True).reset_index())
            fig = px.bar(dff, x="Valor_Parcela", y="Forma_Pagamento",
                         orientation="h", text="Valor_Parcela",
                         color="Valor_Parcela",
                         color_continuous_scale=["#a5b4fc", "#312e81"])
            fig.update_traces(
                texttemplate="R$ %{text:,.2f}", textposition="outside",
                hovertemplate="<b>%{y}</b><br>%{x:,.2f}<extra></extra>",
            )
            fig.update_layout(xaxis_title="", yaxis_title="",
                              coloraxis_showscale=False, height=340,
                              margin=dict(t=10, b=10, l=10, r=40),
                              transition_duration=400)
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar": False})
        else:
            st.info("Sem dados.")

    # Linha temporal
    st.markdown("**Evolução Mensal (Entradas × Despesas × Saldo)**")
    df_ev = df_proj.copy()
    df_ev["GrupoTipo"] = np.where(df_ev["Tipo"] == "Entrada", "Entrada", "Despesa")
    pv = (df_ev.groupby(["Mes_Fatura", "GrupoTipo"])["Valor_Parcela"].sum()
          .unstack(fill_value=0.0).reset_index())
    if "Entrada" not in pv.columns: pv["Entrada"] = 0.0
    if "Despesa" not in pv.columns: pv["Despesa"] = 0.0
    pv["Saldo"] = pv["Entrada"] - pv["Despesa"]
    pv["Label"] = pv["Mes_Fatura"].apply(rotulo_mes)
    pv["Futuro"] = pv["Mes_Fatura"] > mes_atual

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pv["Label"], y=pv["Entrada"], name="🟢 Entradas",
                             line=dict(color=CORES["entrada"], width=3),
                             mode="lines+markers",
                             hovertemplate="%{x}<br>Entradas: R$ %{y:,.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=pv["Label"], y=pv["Despesa"], name="🔴 Despesas",
                             line=dict(color=CORES["saida"], width=3),
                             mode="lines+markers",
                             hovertemplate="%{x}<br>Despesas: R$ %{y:,.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=pv["Label"], y=pv["Saldo"], name="💰 Saldo",
                             line=dict(color=CORES["indigo"], width=3, dash="dot"),
                             mode="lines+markers", fill="tozeroy",
                             fillcolor="rgba(49,46,129,0.08)",
                             hovertemplate="%{x}<br>Saldo: R$ %{y:,.2f}<extra></extra>"))
    # zona futura
    futuros = pv[pv["Futuro"]]
    if not futuros.empty:
        fig.add_vrect(x0=futuros["Label"].iloc[0], x1=futuros["Label"].iloc[-1],
                      fillcolor="rgba(148,163,184,0.10)", line_width=0,
                      annotation_text="Projeção", annotation_position="top left")
    fig.update_layout(height=340, margin=dict(t=30, b=10, l=10, r=10),
                      legend=dict(orientation="h", y=1.1, x=1, xanchor="right"),
                      hovermode="x unified", transition_duration=400)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Por responsável + Treemap
    g3, g4 = st.columns(2)
    with g3:
        st.markdown("**Gastos por Pessoa (proporcional)**")
        df_p = df_mes_pessoa[df_mes_pessoa["Tipo"] != "Entrada"]
        if not df_p.empty:
            dfr = df_p.groupby("Responsavel")["Valor_Pessoa"].sum().reset_index()
            fig = px.bar(dfr.sort_values("Valor_Pessoa"),
                         x="Valor_Pessoa", y="Responsavel", orientation="h",
                         text="Valor_Pessoa", color="Responsavel",
                         color_discrete_sequence=PALETA)
            fig.update_traces(texttemplate="R$ %{text:,.2f}", textposition="outside",
                              hovertemplate="<b>%{y}</b><br>%{x:,.2f}<extra></extra>")
            fig.update_layout(xaxis_title="", yaxis_title="", showlegend=False,
                              height=320, margin=dict(t=10, b=10, l=10, r=40))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("Sem dados.")
    with g4:
        st.markdown("**Mapa: Tipo → Categoria**")
        if not df_desp.empty:
            fig = px.treemap(df_desp, path=["Tipo", "Categoria"], values="Valor_Parcela",
                             color="Valor_Parcela", color_continuous_scale="Tealgrn")
            fig.update_traces(hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<extra></extra>")
            fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10),
                              coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Extrato
    st.markdown("---")
    st.markdown("### 📋 Extrato Detalhado")
    f1, f2, f3 = st.columns(3)
    with f1:
        cat_f = st.multiselect("Categoria", sorted(df_mes["Categoria"].unique()))
    with f2:
        forma_f = st.multiselect("Forma de Pagamento", sorted(df_mes["Forma_Pagamento"].unique()))
    with f3:
        tipo_f = st.multiselect("Tipo", sorted(df_mes["Tipo"].unique()))

    df_ext = df_mes.copy()
    if cat_f:   df_ext = df_ext[df_ext["Categoria"].isin(cat_f)]
    if forma_f: df_ext = df_ext[df_ext["Forma_Pagamento"].isin(forma_f)]
    if tipo_f:  df_ext = df_ext[df_ext["Tipo"].isin(tipo_f)]

    df_ext_show = df_ext.assign(
        Data=df_ext["Data"].apply(lambda d: d.strftime("%d/%m/%Y") if isinstance(d, date) else d),
        Responsaveis=df_ext["Responsaveis"].apply(lambda x: ", ".join(x)),
    )[["Data", "Descricao", "Categoria", "Tipo", "Forma_Pagamento",
       "Responsaveis", "Parcela_Atual", "Valor_Parcela"]]

    st.dataframe(
        df_ext_show, use_container_width=True, hide_index=True,
        column_config={
            "Valor_Parcela": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            "Descricao": "Descrição",
            "Forma_Pagamento": "Forma",
            "Parcela_Atual": "Parcela",
        },
    )

    # Exportar
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df_ext_show.to_excel(w, index=False, sheet_name=mes_sel)
    st.download_button(
        "⬇️ Exportar Excel deste mês", buf.getvalue(),
        file_name=f"extrato_{mes_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ============================================================================
# TAB 3 — PARCELAS & ASSINATURAS
# ============================================================================
with tab_parc:
    st.subheader("💳 Parcelas em aberto e assinaturas recorrentes")
    parc_abertas = df_proj[(df_proj["Parcela_Atual"].str.contains("/")) &
                           (df_proj["Eh_Futuro"])]
    if parc_abertas.empty:
        st.info("Nenhuma parcela futura em aberto.")
    else:
        df_show = parc_abertas.assign(
            Responsaveis=parc_abertas["Responsaveis"].apply(lambda x: ", ".join(x))
        )[["Mes_Fatura", "Descricao", "Categoria", "Forma_Pagamento",
           "Parcela_Atual", "Valor_Parcela", "Responsaveis"]]
        st.dataframe(df_show, use_container_width=True, hide_index=True,
                     column_config={
                         "Valor_Parcela": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                         "Mes_Fatura": "Mês",
                     })

    st.markdown("### 🔁 Assinaturas ativas")
    assin = df_bruto[df_bruto.get("Tipo", "") == "Assinatura"]
    if assin.empty:
        st.info("Nenhuma assinatura cadastrada.")
    else:
        assin_show = assin.assign(Valor_BRL=assin["Valor"].apply(parse_valor))
        st.dataframe(
            assin_show[["Descricao", "Categoria", "Valor_BRL", "Forma_Pagamento"]],
            use_container_width=True, hide_index=True,
            column_config={"Valor_BRL": st.column_config.NumberColumn("Valor mensal", format="R$ %.2f")},
        )
        total_assin = assin_show["Valor_BRL"].sum()
        st.success(f"💸 Total mensal em assinaturas: **{brl(total_assin)}** · "
                   f"Anualizado: **{brl(total_assin * 12)}**")


# ============================================================================
# TAB 4 — CATEGORIAS & MÉTODOS
# ============================================================================
with tab_cat:
    st.subheader("📂 Análise por Categoria")
    df_d = df_proj[df_proj["Tipo"] != "Entrada"]
    if df_d.empty:
        st.info("Sem despesas registradas.")
    else:
        resumo_cat = df_d.groupby("Categoria").agg(
            Total=("Valor_Parcela", "sum"),
            Lancamentos=("Valor_Parcela", "count"),
            Ticket_Medio=("Valor_Parcela", "mean"),
            Ultima_Data=("Data", "max"),
        ).reset_index().sort_values("Total", ascending=False)
        resumo_cat["Ultima_Data"] = resumo_cat["Ultima_Data"].apply(
            lambda d: d.strftime("%d/%m/%Y") if isinstance(d, date) else "—")
        st.dataframe(resumo_cat, use_container_width=True, hide_index=True,
                     column_config={
                         "Total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                         "Ticket_Medio": st.column_config.NumberColumn("Ticket Médio", format="R$ %.2f"),
                         "Ultima_Data": "Última ocorrência",
                     })

    st.markdown("### 💳 Análise por Método de Pagamento")
    if df_d.empty:
        st.info("Sem dados.")
    else:
        total = df_d["Valor_Parcela"].sum()
        resumo_m = df_d.groupby("Forma_Pagamento").agg(
            Total=("Valor_Parcela", "sum"),
            Lancamentos=("Valor_Parcela", "count"),
        ).reset_index().sort_values("Total", ascending=False)
        resumo_m["% do Total"] = (resumo_m["Total"] / total * 100).round(1)
        st.dataframe(resumo_m, use_container_width=True, hide_index=True,
                     column_config={
                         "Total": st.column_config.NumberColumn("Total", format="R$ %.2f"),
                         "% do Total": st.column_config.NumberColumn("%", format="%.1f%%"),
                     })


# ============================================================================
# TAB 5 — ORÇAMENTO
# ============================================================================
with tab_orc:
    st.subheader("🎯 Orçamento mensal por categoria")
    st.caption("Defina um teto para cada categoria. O Dashboard alertará quando passar de 70% e 90%.")

    todas_cats = sorted({c for cats in CATEGORIAS_POR_TIPO.values() for c in cats
                         if not c.startswith("Salário") and not c.startswith("Pix Recebido")
                         and not c.startswith("Rendimento") and not c.startswith("Outras Entradas")})

    orc_dict = dict(zip(df_orc.get("Categoria", []), df_orc.get("Teto_Mensal", [])))

    with st.form("form_orc"):
        novos = {}
        col_a, col_b = st.columns(2)
        for i, cat in enumerate(todas_cats):
            target = col_a if i % 2 == 0 else col_b
            atual = float(orc_dict.get(cat, 0) or 0)
            with target:
                novos[cat] = st.text_input(
                    f"{cat}", value=f"{atual:.2f}".replace(".", ",") if atual > 0 else "",
                    placeholder="0,00", key=f"orc_{cat}",
                )
        salvar_orc = st.form_submit_button("💾 Salvar orçamentos", use_container_width=True)

        if salvar_orc:
            try:
                ws = plan.worksheet(ABA_ORCAMENTOS)
                ws.clear()
                ws.append_row(["Categoria", "Teto_Mensal", "Atualizado_Em"])
                rows = []
                agora = datetime.now(pytz.timezone("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M")
                for cat, txt in novos.items():
                    val = parse_valor(txt)
                    if val > 0:
                        rows.append([cat, f"{val:.2f}".replace(".", ","), agora])
                if rows:
                    ws.append_rows(rows, value_input_option="USER_ENTERED")
                limpar_cache_dados()
                st.success("✅ Orçamentos atualizados.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

    # Visualização atual do mês
    st.markdown("### Status do mês atual")
    mes_a = HOJE.strftime("%Y-%m")
    df_mes_a = df_proj[(df_proj["Mes_Fatura"] == mes_a) & (df_proj["Tipo"] != "Entrada")]
    gasto_por_cat = df_mes_a.groupby("Categoria")["Valor_Parcela"].sum() if not df_mes_a.empty else pd.Series()

    if df_orc.empty:
        st.info("Nenhum orçamento definido ainda.")
    else:
        for _, row in df_orc.iterrows():
            cat, teto = row["Categoria"], row["Teto_Mensal"]
            if teto <= 0:
                continue
            gasto = float(gasto_por_cat.get(cat, 0))
            pct = min(gasto / teto, 1.0)
            if gasto >= teto:        emoji = "⛔"
            elif pct >= 0.9:         emoji = "🔴"
            elif pct >= 0.7:         emoji = "🟡"
            else:                    emoji = "🟢"
            st.write(f"{emoji} **{cat}** — {brl(gasto)} de {brl(teto)} ({pct*100:.0f}%)")
            st.progress(pct)


# ============================================================================
# TAB 6 — AJUSTAR
# ============================================================================
with tab_aj:
    st.subheader("✏️ Ajustar lançamentos da planilha")
    st.caption("Edite valores diretamente. Use o botão para salvar; o cache é renovado automaticamente.")

    df_edit = df_bruto.copy()
    df_edit.insert(0, "Linha_Planilha", range(2, len(df_edit) + 2))

    edited = st.data_editor(
        df_edit, use_container_width=True, hide_index=True,
        num_rows="fixed", key="editor_lanc",
        disabled=["Linha_Planilha"],
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Salvar alterações", use_container_width=True):
            try:
                colunas = [c for c in edited.columns if c != "Linha_Planilha"]
                valores = edited[colunas].astype(str).values.tolist()
                # Reescreve a partir da linha 2
                inicio = "A2"
                sheet.update(inicio, valores, value_input_option="USER_ENTERED")
                limpar_cache_dados()
                st.success("✅ Planilha atualizada.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
    with c2:
        linha_del = st.number_input("Excluir linha nº (2 = primeira)",
                                    min_value=2, max_value=len(df_edit) + 1, value=2)
        if st.button("🗑️ Excluir linha", use_container_width=True):
            try:
                sheet.delete_rows(int(linha_del))
                limpar_cache_dados()
                st.success(f"Linha {linha_del} excluída.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")
