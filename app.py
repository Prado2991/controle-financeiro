import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import gspread
from google.oauth2.service_account import Credentials
import json
import unicodedata

# =============================================================================
# CONFIGURAÇÃO DA PÁGINA — Mobile-First + Tema Premium
# =============================================================================
st.set_page_config(
    page_title="Finanças Jonathan",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Paleta de marca (rebranding)
COR_PRIMARIA = "#6366F1"      # Indigo
COR_SUCESSO  = "#10B981"      # Emerald
COR_PERIGO   = "#EF4444"      # Red
COR_AVISO    = "#F59E0B"      # Amber
COR_NEUTRA   = "#64748B"      # Slate
PALETA_GRAFICO = ["#6366F1", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#EC4899", "#84CC16"]

st.markdown(f"""
<style>
    /* KPIs */
    div[data-testid="stMetricValue"] {{
        font-size: 26px !important;
        font-weight: 700;
        color: {COR_PRIMARIA};
    }}
    div[data-testid="stMetricLabel"] {{
        font-size: 13px !important;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: {COR_NEUTRA};
    }}
    /* Cards de métricas com sombra suave */
    div[data-testid="stMetric"] {{
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.06);
        transition: transform .15s ease, box-shadow .15s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(99, 102, 241, 0.12);
    }}
    /* Botões */
    .stButton>button {{
        border-radius: 10px;
        font-weight: 600;
        transition: all .15s ease;
    }}
    .stButton>button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(99,102,241,0.25);
    }}
    /* Tabs mais elegantes */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px 8px 0 0;
        padding: 8px 14px;
        font-weight: 500;
    }}
    /* Título principal */
    h1 {{
        background: linear-gradient(90deg, {COR_PRIMARIA}, #8B5CF6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# FORMATAÇÃO MONETÁRIA BRASILEIRA (R$ 1.234,56)
# =============================================================================
def format_brl(valor) -> str:
    """Formata float como Real brasileiro: R$ 1.234,56 (ponto como separador
    de milhar e vírgula como decimal). Substitui o f-string americano."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        v = 0.0
    sinal = "-" if v < 0 else ""
    v_abs = abs(v)
    # Truque: format americano e troca de separadores via tokens temporários
    s = f"{v_abs:,.2f}"  # ex: 1,234.56
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return f"{sinal}R$ {s}"

def converter_valor_para_float(texto):
    """Converte qualquer texto monetário ('12,90', '1.250,50', 'R$ 15') em float."""
    if not texto:
        return 0.0
    try:
        texto_limpo = str(texto).replace("R$", "").replace(" ", "").strip()
        if "." in texto_limpo and "," in texto_limpo:
            texto_limpo = texto_limpo.replace(".", "")
        texto_limpo = texto_limpo.replace(",", ".")
        return float(texto_limpo)
    except Exception:
        return 0.0

def limpar_valor_monetario(val):
    try:
        if pd.isna(val) or val == "":
            return 0.0
        val_str = str(val).strip().replace('R$', '').replace(' ', '')
        if '.' in val_str and ',' in val_str:
            val_str = val_str.replace('.', '')
        val_str = val_str.replace(',', '.')
        return float(val_str)
    except Exception:
        return 0.0

# =============================================================================
# CONEXÃO GOOGLE SHEETS
# =============================================================================
@st.cache_resource(show_spinner=False)
def conectar_planilha():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    if "google_credentials" not in st.secrets:
        st.error("❌ **Erro de Configuração:** segredo `google_credentials` não encontrado.")
        return None
    try:
        try:
            creds_json = json.loads(st.secrets["google_credentials"])
        except Exception as json_err:
            st.error(f"❌ **JSON Inválido** em `google_credentials`: {json_err}")
            return None

        if "private_key" in creds_json:
            key_formatada = creds_json["private_key"].replace("\\n", "\n")
            if key_formatada.startswith('"') and key_formatada.endswith('"'):
                key_formatada = key_formatada[1:-1]
            creds_json["private_key"] = key_formatada

        try:
            creds = Credentials.from_service_account_info(creds_json, scopes=scope)
            client = gspread.authorize(creds)
        except Exception as auth_err:
            st.error(f"❌ **Erro de Autenticação Google:** {auth_err}")
            return None

        planilha_id = "1JyVUY1pKQs90jtPPBvEHDLnGxBw3wdooEFWSq-1e5D4"
        try:
            plan_aberta = client.open_by_key(planilha_id)
        except Exception as open_err:
            email_servico = creds_json.get("client_email", "?")
            st.error(f"❌ **Planilha não compartilhada com:** {email_servico}\n\nDetalhe: {open_err}")
            return None

        try:
            return plan_aberta.worksheet("Lancamentos")
        except Exception:
            abas = [w.title for w in plan_aberta.worksheets()]
            st.error(f"❌ Aba 'Lancamentos' não encontrada. Abas existentes: {abas}")
            return None
    except Exception as e:
        st.error(f"❌ Erro inesperado: {e}")
        return None

sheet_conn = conectar_planilha()

# =============================================================================
# NORMALIZAÇÃO E CACHE DE DADOS
# =============================================================================
def normalizar_df(df):
    mapeamento_colunas = {
        'data': 'Data', 'datadecompra': 'Data', 'data do lancamento': 'Data',
        'data do lançamento': 'Data', 'carimbo de data/hora': 'Data',
        'descricao': 'Descricao', 'descrição': 'Descricao',
        'valor': 'Valor', 'valor (r$)': 'Valor',
        'categoria': 'Categoria',
        'tipo': 'Tipo', 'tipo de lancamento': 'Tipo', 'tipo de lançamento': 'Tipo',
        'responsavel': 'Responsavel', 'responsável': 'Responsavel',
        'para quem?': 'Responsavel', 'para quem': 'Responsavel',
        'forma_pagamento': 'Forma_Pagamento', 'forma de pagamento': 'Forma_Pagamento',
        'forma_pagto': 'Forma_Pagamento', 'forma de pagto': 'Forma_Pagamento',
        'parcelado': 'Parcelado', 'compra parcelada?': 'Parcelado', 'parcelado?': 'Parcelado',
        'parcelas_totais': 'Parcelas_Totais', 'parcelas totais': 'Parcelas_Totais',
        'quantidade de parcelas': 'Parcelas_Totais'
    }
    colunas_novas = {}
    for col in df.columns:
        col_limpa = "".join(c for c in unicodedata.normalize('NFD', str(col)) if unicodedata.category(c) != 'Mn')
        col_norm = col_limpa.strip().lower()
        colunas_novas[col] = mapeamento_colunas.get(col_norm, str(col).strip())
    df = df.rename(columns=colunas_novas)

    obrig = ['Data', 'Descricao', 'Valor', 'Categoria', 'Tipo', 'Responsavel', 'Forma_Pagamento', 'Parcelado', 'Parcelas_Totais']
    for col in obrig:
        if col not in df.columns:
            df[col] = 1 if col == 'Parcelas_Totais' else ('Não' if col == 'Parcelado' else (0.0 if col == 'Valor' else ''))
    return df

@st.cache_data(ttl=60, show_spinner="Carregando lançamentos...")
def carregar_dados_brutos():
    """Cacheia a leitura da planilha por 60s — evita chamada à API a cada interação."""
    if sheet_conn is None:
        return pd.DataFrame()
    raw = sheet_conn.get_all_records()
    df = pd.DataFrame(raw)
    return normalizar_df(df)

def calcular_mes_competencia(data_compra, forma_pagamento):
    if "Cartão" not in str(forma_pagamento):
        return data_compra.strftime("%Y-%m")
    if data_compra.day > 7:
        data_fatura = data_compra + relativedelta(months=1)
    else:
        data_fatura = data_compra
    return data_fatura.strftime("%Y-%m")

@st.cache_data(ttl=60, show_spinner=False)
def projetar_lancamentos(dados_brutos: pd.DataFrame) -> pd.DataFrame:
    """Expande parcelamentos, assinaturas (12 meses) e divisão entre responsáveis.
    Cacheado para evitar reprocessar a cada rerun."""
    if dados_brutos.empty:
        return pd.DataFrame()

    lista_projetada = []
    for _, row in dados_brutos.iterrows():
        try:
            if not row.get('Data'):
                continue
            dt_compra = datetime.strptime(str(row['Data']).split()[0], "%Y-%m-%d").date()
        except Exception:
            try:
                dt_compra = datetime.strptime(str(row['Data']).split()[0], "%d/%m/%Y").date()
            except Exception:
                continue

        tipo_lanc = row.get('Tipo', 'Gasto Variável')
        try:
            total_parc = int(row['Parcelas_Totais']) if row.get('Parcelas_Totais') else 1
        except Exception:
            total_parc = 1
        valor_total = limpar_valor_monetario(row.get('Valor', 0.0))

        resp_campo = str(row.get('Responsavel', 'Jonathan'))
        responsaveis = [r.strip() for r in resp_campo.replace('/', ',').split(',') if r.strip()] or ["Jonathan"]
        num_resp = len(responsaveis)

        if tipo_lanc == "Assinatura":
            val_dividido = valor_total / num_resp
            for m in range(12):
                dt_rec = dt_compra + relativedelta(months=m)
                mes_comp = calcular_mes_competencia(dt_rec, row.get('Forma_Pagamento', 'Dinheiro'))
                for r_ind in responsaveis:
                    item = row.to_dict()
                    item.update({'Mes_Fatura': mes_comp, 'Valor_Parcela': val_dividido,
                                 'Responsavel': r_ind, 'Parcela_Atual': "Recorrente"})
                    lista_projetada.append(item)
        else:
            val_parcela = valor_total / total_parc if row.get('Parcelado') == 'Sim' else valor_total
            val_dividido = val_parcela / num_resp
            for p in range(total_parc):
                dt_p = dt_compra + relativedelta(months=p)
                mes_comp = calcular_mes_competencia(dt_p, row.get('Forma_Pagamento', 'Dinheiro'))
                for r_ind in responsaveis:
                    item = row.to_dict()
                    item.update({
                        'Mes_Fatura': mes_comp,
                        'Valor_Parcela': val_dividido,
                        'Responsavel': r_ind,
                        'Parcela_Atual': f"{p+1}/{total_parc}" if row.get('Parcelado') == 'Sim' else "1/1"
                    })
                    lista_projetada.append(item)

    if not lista_projetada:
        return pd.DataFrame()
    df_proj = pd.DataFrame(lista_projetada)
    df_proj['Valor_Parcela'] = df_proj['Valor_Parcela'].astype(float)

    def formatar_data_br(s):
        try:
            return datetime.strptime(str(s).split()[0], "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return s
    df_proj['Data_Exibicao'] = df_proj['Data'].apply(formatar_data_br)
    return df_proj

# =============================================================================
# INTERFACE
# =============================================================================
st.title("💰 Controle Financeiro Familiar")
st.markdown("##### Jonathan Prado")

hoje = date.today()
vencimento_limite = date(hoje.year, hoje.month, 7)
if hoje.day > 7:
    vencimento_limite = vencimento_limite + relativedelta(months=1)
dias_restantes = (vencimento_limite - hoje).days
st.info(f"⏳ **Fechamento de Faturas:** faltam **{dias_restantes} dias** (próximo dia 07: {vencimento_limite.strftime('%d/%m/%Y')})")

tabs = st.tabs(["📲 Novo Lançamento", "📊 Dashboard & Resumos", "💳 Parcelas & Assinaturas", "✏️ Ajustar Lançamentos"])

# ---------------- ABA 0: NOVO LANÇAMENTO ----------------
with tabs[0]:
    st.subheader("Registrar Gasto ou Entrada")
    if sheet_conn is None:
        st.info("⚠️ Formulário desativado por falha de conexão com a planilha.")
    else:
        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                data = st.date_input("Data do Lançamento", date.today(), format="DD/MM/YYYY")
                descricao = st.text_input("Descrição", placeholder="Ex: Sorveteria Sávio, Shein, Muffato")
                valor_texto = st.text_input("Valor (R$)", placeholder="Ex: 12,90 ou 1.500,00")
                tipo = st.selectbox("Tipo de Lançamento",
                                    ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"])
            with col2:
                if tipo == "Gasto Fixo":
                    lista_cats = ["Luz", "Água", "Internet", "Telefone", "Condomínio", "Aluguel", "Plano de Saúde", "Outros Fixos"]
                elif tipo == "Gasto Variável":
                    lista_cats = ["Refeição", "Supermercado", "Abastecimento", "Shopping", "Farmácia", "Lazer", "Viagem", "Presentes", "Outros Variáveis"]
                elif tipo == "Assinatura":
                    lista_cats = ["Streaming (Netflix/Spotify)", "Academia", "Clube de Assinatura", "Software/App", "Outras Assinaturas"]
                else:
                    lista_cats = ["Salário", "Rendimento", "Pix Recebido", "Outras Entradas"]
                categoria = st.selectbox("Categoria", lista_cats)
                responsavel = st.multiselect("Para Quem?",
                                             ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"],
                                             default=["Jonathan"])
                forma_pagto = st.selectbox("Forma de Pagamento",
                                           ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"])
                pode_parcelar = tipo in ["Gasto Variável", "Gasto Fixo"]
                if pode_parcelar:
                    parcelado = st.radio("Compra Parcelada?", ["Não", "Sim"], horizontal=True)
                    num_parcelas = st.number_input("Quantidade de Parcelas", min_value=2, max_value=48, value=2, step=1) if parcelado == "Sim" else 1
                else:
                    parcelado = "Não"
                    num_parcelas = 1

            botao_salvar = st.form_submit_button("🚀 Gravar na Planilha")
            if botao_salvar:
                valor_convertido = converter_valor_para_float(valor_texto)
                if not responsavel:
                    st.error("Selecione pelo menos uma pessoa em 'Para Quem?'.")
                elif descricao and valor_convertido > 0:
                    valor_com_virgula = f"{valor_convertido:.2f}".replace('.', ',')
                    responsavel_str = ", ".join(responsavel)
                    novo_registro = [str(data), descricao, valor_com_virgula, categoria, tipo,
                                     responsavel_str, forma_pagto, parcelado, int(num_parcelas)]
                    try:
                        sheet_conn.append_row(novo_registro, value_input_option='USER_ENTERED')
                        st.success(f"Sucesso! '{descricao}' gravado com valor de {format_brl(valor_convertido)}.")
                        st.balloons()
                        carregar_dados_brutos.clear()
                        projetar_lancamentos.clear()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
                else:
                    st.error("Preencha a descrição e um valor maior que zero (use vírgula para centavos).")

# =============================================================================
# CARGA DE DADOS PARA DASHBOARDS
# =============================================================================
if sheet_conn is not None:
    dados_brutos = carregar_dados_brutos()

    if not dados_brutos.empty:
        df_projetado = projetar_lancamentos(dados_brutos)

        if not df_projetado.empty:
            # ---------------- ABA 1: DASHBOARD ----------------
            with tabs[1]:
                st.subheader("📊 Resumo Mensal e Faturas")

                meses_disponiveis = sorted(df_projetado['Mes_Fatura'].unique())
                if meses_disponiveis:
                    mes_atual_padrao = date.today().strftime("%Y-%m")
                    idx_padrao = meses_disponiveis.index(mes_atual_padrao) if mes_atual_padrao in meses_disponiveis else len(meses_disponiveis) - 1
                    mes_selecionado = st.selectbox("Selecione o Mês de Análise", meses_disponiveis, index=idx_padrao)
                    df_mes = df_projetado[df_projetado['Mes_Fatura'] == mes_selecionado]

                    tot_entradas = df_mes[df_mes['Tipo'] == 'Entrada']['Valor_Parcela'].sum()
                    tot_saidas = df_mes[df_mes['Tipo'] != 'Entrada']['Valor_Parcela'].sum()
                    fatura_nu = df_mes[df_mes['Forma_Pagamento'] == 'Cartão Nu']['Valor_Parcela'].sum()
                    fatura_bb = df_mes[df_mes['Forma_Pagamento'] == 'Cartão BB']['Valor_Parcela'].sum()
                    saldo_final = tot_entradas - tot_saidas
                    cor_saldo = "normal" if saldo_final >= 0 else "inverse"

                    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                    kpi1.metric("🟢 Entradas", format_brl(tot_entradas))
                    kpi2.metric("🔴 Despesas", format_brl(tot_saidas),
                                delta=f"Saldo: {format_brl(saldo_final)}", delta_color=cor_saldo)
                    kpi3.metric("💳 Fatura Nu", format_brl(fatura_nu))
                    kpi4.metric("💳 Fatura BB", format_brl(fatura_bb))

                    st.markdown("### Distribuição dos Gastos do Mês")

                    df_gastos = df_mes[df_mes['Tipo'] != 'Entrada']

                    # ---------- Gráficos interativos com Plotly ----------
                    c1, c2 = st.columns(2)

                    with c1:
                        st.markdown("**Por Destinatário**")
                        df_resp = df_gastos.groupby('Responsavel', as_index=False)['Valor_Parcela'].sum().sort_values('Valor_Parcela', ascending=True)
                        if not df_resp.empty:
                            fig_resp = px.bar(
                                df_resp, x='Valor_Parcela', y='Responsavel', orientation='h',
                                color='Responsavel', color_discrete_sequence=PALETA_GRAFICO,
                                text=df_resp['Valor_Parcela'].apply(format_brl)
                            )
                            fig_resp.update_traces(
                                textposition='outside',
                                hovertemplate='<b>%{y}</b><br>%{text}<extra></extra>',
                                marker_line_width=0
                            )
                            fig_resp.update_layout(
                                showlegend=False, height=320,
                                margin=dict(l=0, r=20, t=10, b=10),
                                xaxis_title=None, yaxis_title=None,
                                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                                xaxis=dict(showgrid=True, gridcolor='#f1f5f9', tickprefix="R$ ", tickformat=",.0f"),
                                transition={'duration': 500, 'easing': 'cubic-in-out'}
                            )
                            st.plotly_chart(fig_resp, use_container_width=True, config={'displayModeBar': False})
                        else:
                            st.info("Sem dados.")

                    with c2:
                        st.markdown("**Por Tipo de Gasto**")
                        df_tipo = df_gastos.groupby('Tipo', as_index=False)['Valor_Parcela'].sum()
                        if not df_tipo.empty:
                            fig_tipo = go.Figure(data=[go.Pie(
                                labels=df_tipo['Tipo'],
                                values=df_tipo['Valor_Parcela'],
                                hole=.6,
                                marker=dict(colors=PALETA_GRAFICO, line=dict(color='#ffffff', width=2)),
                                textinfo='percent',
                                hovertemplate='<b>%{label}</b><br>%{customdata}<br>%{percent}<extra></extra>',
                                customdata=[format_brl(v) for v in df_tipo['Valor_Parcela']],
                                pull=[0.02] * len(df_tipo)
                            )])
                            fig_tipo.update_layout(
                                height=320, showlegend=True,
                                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                                margin=dict(l=0, r=0, t=10, b=10),
                                annotations=[dict(text=f"<b>{format_brl(tot_saidas)}</b><br><span style='font-size:11px;color:#64748b'>Total</span>",
                                                  x=0.5, y=0.5, font_size=14, showarrow=False)],
                                paper_bgcolor='rgba(0,0,0,0)',
                                transition={'duration': 500, 'easing': 'cubic-in-out'}
                            )
                            st.plotly_chart(fig_tipo, use_container_width=True, config={'displayModeBar': False})
                        else:
                            st.info("Sem dados.")

                    # ---------- Categoria + Evolução ----------
                    c3, c4 = st.columns(2)
                    with c3:
                        st.markdown("**Por Categoria**")
                        df_cat = df_gastos.groupby('Categoria', as_index=False)['Valor_Parcela'].sum().sort_values('Valor_Parcela', ascending=True)
                        if not df_cat.empty:
                            fig_cat = px.bar(
                                df_cat, x='Valor_Parcela', y='Categoria', orientation='h',
                                color='Valor_Parcela', color_continuous_scale=['#c7d2fe', COR_PRIMARIA, '#4338ca'],
                                text=df_cat['Valor_Parcela'].apply(format_brl)
                            )
                            fig_cat.update_traces(textposition='outside',
                                                  hovertemplate='<b>%{y}</b><br>%{text}<extra></extra>')
                            fig_cat.update_layout(
                                height=max(280, 30 * len(df_cat)), showlegend=False, coloraxis_showscale=False,
                                margin=dict(l=0, r=20, t=10, b=10),
                                xaxis_title=None, yaxis_title=None,
                                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                                xaxis=dict(showgrid=True, gridcolor='#f1f5f9', tickprefix="R$ ", tickformat=",.0f"),
                                transition={'duration': 500, 'easing': 'cubic-in-out'}
                            )
                            st.plotly_chart(fig_cat, use_container_width=True, config={'displayModeBar': False})

                    with c4:
                        st.markdown("**Evolução Mensal (Entradas vs Despesas)**")
                        df_evol = df_projetado.copy()
                        df_evol['Grupo'] = df_evol['Tipo'].apply(lambda t: 'Entradas' if t == 'Entrada' else 'Despesas')
                        df_evol = df_evol.groupby(['Mes_Fatura', 'Grupo'], as_index=False)['Valor_Parcela'].sum()
                        fig_evol = px.line(
                            df_evol, x='Mes_Fatura', y='Valor_Parcela', color='Grupo',
                            color_discrete_map={'Entradas': COR_SUCESSO, 'Despesas': COR_PERIGO},
                            markers=True
                        )
                        fig_evol.update_traces(line=dict(width=3), marker=dict(size=8),
                                               hovertemplate='<b>%{x}</b><br>%{customdata}<extra></extra>',
                                               customdata=[[format_brl(v)] for v in df_evol['Valor_Parcela']])
                        fig_evol.update_layout(
                            height=320, margin=dict(l=0, r=10, t=10, b=10),
                            xaxis_title=None, yaxis_title=None,
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                            yaxis=dict(showgrid=True, gridcolor='#f1f5f9', tickprefix="R$ ", tickformat=",.0f"),
                            transition={'duration': 500, 'easing': 'cubic-in-out'}
                        )
                        st.plotly_chart(fig_evol, use_container_width=True, config={'displayModeBar': False})

                    # ---------- Extrato Detalhado (sem coluna de Linha) ----------
                    st.markdown("### 📋 Extrato Detalhado do Mês de Competência")
                    df_mes_exibe = df_mes[['Data_Exibicao', 'Descricao', 'Valor_Parcela', 'Parcela_Atual',
                                           'Categoria', 'Responsavel', 'Forma_Pagamento', 'Tipo']].copy()
                    df_mes_exibe.rename(columns={'Data_Exibicao': 'Data',
                                                 'Valor_Parcela': 'Valor da Parcela'}, inplace=True)
                    df_mes_exibe['Valor da Parcela'] = df_mes_exibe['Valor da Parcela'].apply(format_brl)
                    # hide_index=True remove a coluna de índice/linha solicitada
                    st.dataframe(df_mes_exibe, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum mês disponível para análise.")

            # ---------------- ABA 2: PARCELAS ----------------
            with tabs[2]:
                st.subheader("💳 Dívidas Parceladas e Assinaturas")
                hoje_str = date.today().strftime("%Y-%m")
                df_futuro = df_projetado[(df_projetado['Mes_Fatura'] > hoje_str) & (df_projetado['Parcelado'] == 'Sim')]
                saldo_devedor = df_futuro['Valor_Parcela'].sum()
                st.warning(f"🏦 **Saldo Devedor Total (Faturas Seguintes):** {format_brl(saldo_devedor)}")

                col_e, col_d = st.columns(2)
                with col_e:
                    st.markdown("### 📅 Cronograma de Parcelamentos")
                    if not df_futuro.empty:
                        cron = df_futuro.groupby(['Mes_Fatura', 'Forma_Pagamento'])['Valor_Parcela'].sum().unstack().fillna(0)
                        cron_fmt = cron.applymap(format_brl)
                        st.dataframe(cron_fmt, use_container_width=True)

                        st.markdown("**Detalhe das Parcelas Futuras**")
                        df_fut_exibe = df_futuro[['Mes_Fatura', 'Descricao', 'Valor_Parcela',
                                                  'Parcela_Atual', 'Forma_Pagamento']].copy()
                        df_fut_exibe['Valor_Parcela'] = df_fut_exibe['Valor_Parcela'].apply(format_brl)
                        st.dataframe(df_fut_exibe, use_container_width=True, hide_index=True)
                    else:
                        st.info("Sem compras parceladas para os próximos meses.")

                with col_d:
                    st.markdown("### 🔄 Assinaturas Ativas")
                    df_ass = df_projetado[df_projetado['Tipo'] == 'Assinatura'].drop_duplicates(subset=['Descricao'])
                    if not df_ass.empty:
                        tot_ass = df_ass['Valor_Parcela'].sum()
                        st.success(f"📋 **Custo Mensal de Assinaturas:** {format_brl(tot_ass)}")
                        df_ass_exibe = df_ass[['Descricao', 'Valor_Parcela', 'Categoria', 'Forma_Pagamento']].copy()
                        df_ass_exibe['Valor_Parcela'] = df_ass_exibe['Valor_Parcela'].apply(format_brl)
                        st.dataframe(df_ass_exibe, use_container_width=True, hide_index=True)
                    else:
                        st.info("Nenhuma assinatura cadastrada.")

            # ---------------- ABA 3: AJUSTAR ----------------
            with tabs[3]:
                st.subheader("✏️ Alterar ou Excluir Lançamentos")
                lista_ajustavel = []
                for idx, row in dados_brutos.iterrows():
                    num_linha = idx + 2
                    desc = row.get('Descricao', 'Sem Descrição')
                    val = limpar_valor_monetario(row.get('Valor', 0.0))
                    dt = row.get('Data', '')
                    rotulo = f"Linha {num_linha} | {dt} | {desc} — {format_brl(val)}"
                    lista_ajustavel.append({"linha": num_linha, "label": rotulo, "original": row.to_dict()})
                lista_ajustavel.reverse()

                if lista_ajustavel:
                    reg = st.selectbox("Selecione o Lançamento:",
                                       options=lista_ajustavel, format_func=lambda x: x["label"])
                    if reg:
                        orig = reg["original"]
                        linha_planilha = reg["linha"]
                        st.write("---")
                        with st.form("form_edicao_registro"):
                            st.markdown(f"**Editando dados da Linha {linha_planilha}**")
                            col_ed1, col_ed2 = st.columns(2)
                            with col_ed1:
                                try:
                                    dt_orig = datetime.strptime(str(orig.get('Data')).split()[0], "%Y-%m-%d").date()
                                except Exception:
                                    try:
                                        dt_orig = datetime.strptime(str(orig.get('Data')).split()[0], "%d/%m/%Y").date()
                                    except Exception:
                                        dt_orig = date.today()
                                ed_data = st.date_input("Data do Lançamento", dt_orig, format="DD/MM/YYYY")
                                ed_descricao = st.text_input("Descrição", value=orig.get('Descricao', ''))
                                valor_original_texto = f"{limpar_valor_monetario(orig.get('Valor', 0.0)):.2f}".replace('.', ',')
                                ed_valor_texto = st.text_input("Valor (R$)", value=valor_original_texto, placeholder="Ex: 12,90")
                                tipo_orig = orig.get('Tipo', 'Gasto Variável')
                                lista_tipos = ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"]
                                idx_t = lista_tipos.index(tipo_orig) if tipo_orig in lista_tipos else 0
                                ed_tipo = st.selectbox("Tipo de Lançamento", lista_tipos, index=idx_t)
                            with col_ed2:
                                if ed_tipo == "Gasto Fixo":
                                    cats_ed = ["Luz", "Água", "Internet", "Telefone", "Condomínio", "Aluguel", "Plano de Saúde", "Outros Fixos"]
                                elif ed_tipo == "Gasto Variável":
                                    cats_ed = ["Refeição", "Supermercado", "Abastecimento", "Shopping", "Farmácia", "Lazer", "Viagem", "Presentes", "Outros Variáveis"]
                                elif ed_tipo == "Assinatura":
                                    cats_ed = ["Streaming (Netflix/Spotify)", "Academia", "Clube de Assinatura", "Software/App", "Outras Assinaturas"]
                                else:
                                    cats_ed = ["Salário", "Rendimento", "Pix Recebido", "Outras Entradas"]
                                cat_orig = orig.get('Categoria', '')
                                idx_c = cats_ed.index(cat_orig) if cat_orig in cats_ed else 0
                                ed_categoria = st.selectbox("Categoria", cats_ed, index=idx_c)

                                resp_str = str(orig.get('Responsavel', 'Jonathan'))
                                resp_lst = [r.strip() for r in resp_str.replace('/', ',').split(',') if r.strip()] or ["Jonathan"]
                                ed_responsavel = st.multiselect("Para Quem?",
                                                                ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"],
                                                                default=resp_lst)
                                pgto_orig = orig.get('Forma_Pagamento', 'Cartão Nu')
                                lista_pgto = ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"]
                                idx_p = lista_pgto.index(pgto_orig) if pgto_orig in lista_pgto else 0
                                ed_forma_pagto = st.selectbox("Forma de Pagamento", lista_pgto, index=idx_p)

                                if ed_tipo in ["Gasto Variável", "Gasto Fixo"]:
                                    parc_orig = orig.get('Parcelado', 'Não')
                                    idx_pa = 0 if parc_orig == "Não" else 1
                                    ed_parcelado = st.radio("Compra Parcelada?", ["Não", "Sim"], index=idx_pa, horizontal=True)
                                    try:
                                        tot_parc_orig = int(orig.get('Parcelas_Totais', 1))
                                    except Exception:
                                        tot_parc_orig = 1
                                    ed_num_parcelas = st.number_input("Quantidade de Parcelas", min_value=2, max_value=48,
                                                                      value=max(2, tot_parc_orig), step=1) if ed_parcelado == "Sim" else 1
                                else:
                                    ed_parcelado = "Não"
                                    ed_num_parcelas = 1

                            if st.form_submit_button("💾 Salvar Alterações"):
                                ed_valor_float = converter_valor_para_float(ed_valor_texto)
                                if not ed_responsavel:
                                    st.error("Selecione ao menos um responsável.")
                                elif ed_descricao and ed_valor_float > 0:
                                    ed_valor_com_virgula = f"{ed_valor_float:.2f}".replace('.', ',')
                                    ed_resp_str = ", ".join(ed_responsavel)
                                    valores_atualizados = [str(ed_data), ed_descricao, ed_valor_com_virgula,
                                                           ed_categoria, ed_tipo, ed_resp_str, ed_forma_pagto,
                                                           ed_parcelado, int(ed_num_parcelas)]
                                    try:
                                        sheet_conn.update(f"A{linha_planilha}:I{linha_planilha}",
                                                          [valores_atualizados], value_input_option='USER_ENTERED')
                                        st.success(f"Linha {linha_planilha} atualizada com sucesso.")
                                        st.balloons()
                                        carregar_dados_brutos.clear()
                                        projetar_lancamentos.clear()
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Erro ao atualizar: {ex}")
                                else:
                                    st.error("Preencha todos os campos obrigatórios.")

                        st.markdown("---")
                        st.markdown("### ⚠️ Zona de Perigo")
                        confirma = st.checkbox(f"Confirmo que desejo apagar a Linha {linha_planilha} permanentemente.")
                        if st.button("🗑️ Excluir Lançamento", type="primary", disabled=not confirma):
                            try:
                                sheet_conn.delete_rows(linha_planilha)
                                st.success(f"Linha {linha_planilha} excluída.")
                                carregar_dados_brutos.clear()
                                projetar_lancamentos.clear()
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Erro ao excluir: {ex}")
                else:
                    st.info("Nenhum lançamento encontrado.")
        else:
            st.info("Sem dados projetados disponíveis.")
    else:
        st.info("Sua aba 'Lancamentos' está vazia. Faça o primeiro lançamento para começar!")
