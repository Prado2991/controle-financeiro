import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import gspread
from google.oauth2.service_account import Credentials
import json
import plotly.express as px
import plotly.graph_objects as go
import pytz

# Configuração da página para visualização Mobile-First e Temática Elegante
st.set_page_config(
    page_title="Finanças Jonathan", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Configuração de fuso horário brasileiro para evitar que o calendário mude de dia antes da hora
def obter_hoje_brasil():
    fuso_br = pytz.timezone("America/Sao_Paulo")
    agora_br = datetime.now(fuso_br)
    return agora_br.date()

hoje_brasil = obter_hoje_brasil()

# Estilização CSS personalizada para visual premium, animações fluidas e cores Indigo/Emerald
st.markdown("""
<style>
    /* Transições e animações fluidas (Cúbico de Entrada 500ms) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        transition: all 0.5s cubic-bezier(0.25, 1, 0.5, 1);
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f1f5f9;
        border-radius: 8px 8px 0px 0px;
        gap: 4px;
        padding: 10px 16px;
        font-weight: 600;
        color: #475569;
        transition: all 0.5s cubic-bezier(0.25, 1, 0.5, 1);
    }

    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e2e8f0;
        color: #1e1b4b;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #312e81;
        color: #ffffff !important;
        border-bottom: 3px solid #10b981;
    }

    /* Cards de KPI personalizados com gradientes, sombras físicas e hover */
    .kpi-container {
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        height: 100%;
        color: white;
    }

    .kpi-container:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
    }

    .kpi-entradas {
        background: linear-gradient(135deg, #064e3b 0%, #065f46 100%); /* Emerald escuro */
        border-left: 5px solid #34d399;
    }

    .kpi-saidas {
        background: linear-gradient(135deg, #4c1d95 0%, #5b21b6 100%); /* Purple/Indigo escuro */
        border-left: 5px solid #a78bfa;
    }

    .kpi-nu {
        background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); /* Deep Indigo */
        border-left: 5px solid #818cf8;
    }

    .kpi-bb {
        background: linear-gradient(135deg, #111827 0%, #1f2937 100%); /* Gray/Dark */
        border-left: 5px solid #fbbf24;
    }

    .kpi-title {
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        opacity: 0.9;
        font-weight: 500;
    }

    .kpi-value {
        font-size: 26px;
        font-weight: 700;
        margin-top: 8px;
        margin-bottom: 4px;
    }

    .kpi-subtitle {
        font-size: 12px;
        opacity: 0.8;
    }

    /* Título com gradiente elegante */
    .main-title {
        background: linear-gradient(to right, #312e81, #047857);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 32px;
        font-weight: 800;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# FUNÇÃO DE CONVERSÃO BRASILEIRA DE MOEDA
def formatar_brl(valor):
    try:
        val = float(valor)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

# TRATAMENTO NUMÉRICO DE ENTRADA
def tratar_entrada_numerica(texto_valor):
    if not texto_valor:
        return 0.0
    try:
        texto_limpo = str(texto_valor).replace("R$", "").replace("r$", "").strip()
        if "," in texto_limpo and "." in texto_limpo:
            texto_limpo = texto_limpo.replace(".", "").replace(",", ".")
        elif "," in texto_limpo:
            texto_limpo = texto_limpo.replace(",", ".")
        val_float = float(texto_limpo)
        return round(val_float, 2)
    except Exception:
        return 0.0

# CONEXÃO COM O GOOGLE SHEETS COM DIAGNÓSTICO DETALHADO
def conectar_planilha():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if "google_credentials" not in st.secrets:
        st.error("❌ **Erro de Configuração:** O segredo `google_credentials` não foi encontrado no painel de Secrets do Streamlit.")
        return None
        
    try:
        try:
            creds_json = json.loads(st.secrets["google_credentials"])
        except Exception as json_err:
            st.error(f"❌ **Erro no Formato das Credenciais (JSON Inválido):** {json_err}")
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
            st.error(f"❌ **Erro de Autenticação com o Google:** {auth_err}")
            return None
            
        planilha_id = "1JyVUY1pKQs90jtPPBvEHDLnGxBw3wdooEFWSq-1e5D4"
        try:
            plan_aberta = client.open_by_key(planilha_id)
        except Exception as open_err:
            email_servico = creds_json.get("client_email", "e-mail desconhecido")
            st.error(f"❌ **Planilha não compartilhada com a API:** Compartilhe com `{email_servico}`")
            return None
            
        try:
            sheet = plan_aberta.worksheet("Lancamentos")
            return sheet
        except Exception as sheet_err:
            st.error("❌ **Aba 'Lancamentos' não encontrada na planilha!**")
            return None
            
    except Exception as e:
        st.error(f"❌ **Erro Inesperado na Conexão:** {e}")
        return None

sheet_conn = conectar_planilha()

# LÓGICA DE COBRANÇA DA FATURA (REGRA SOLICITADA POR JONATHAN)
# Compra em Cartão:
# Dia 01 até Dia 06 -> Pertence à fatura do MÊS ANTERIOR.
# Dia 07 em diante -> Pertence à fatura do MÊS ATUAL.
# Outras formas (Pix, Dinheiro, etc): Mês real do calendário.
def calcular_mes_competencia(data_compra, forma_pagamento):
    if "Cartão" not in forma_pagamento:
        return data_compra.strftime("%Y-%m")
    
    dia = data_compra.day
    if dia < 7:
        # Se for entre o dia 1 e dia 6, retrocede 1 mês (Fatura do mês anterior)
        data_fatura = data_compra - relativedelta(months=1)
    else:
        # Se for dia 7 em diante, pertence à fatura do mês atual da compra
        data_fatura = data_compra
        
    return data_fatura.strftime("%Y-%m")

@st.cache_data(ttl=60)
def projetar(df, hoje):
    """
    Função de projeção ultra robusta que previne AttributeError ao converter tuplas
    nomeadas em dicionários flexíveis para busca de atributos.
    """
    if df.empty:
        return pd.DataFrame(), []
        
    lista_projetada = []
    avisos = []
    
    # Normaliza nomes de colunas para evitar espaços indesejados
    df.columns = [col.strip() for col in df.columns]
    
    for r in df.itertuples(index=False):
        # Converte em dict para evitar erros como r._Data ou r._Valor
        r_dict = r._asdict()
        
        # Procura coluna de data com fallbacks
        data_raw = None
        for key in ['Data', '_Data', 'data', '_data']:
            if key in r_dict:
                data_raw = r_dict[key]
                break
        if data_raw is None:
            # Fallback para o primeiro elemento disponível
            data_raw = r_dict[list(r_dict.keys())[0]] if r_dict else None
            
        if not data_raw:
            continue
            
        # Parseia a data com resiliência
        dt_compra = None
        try:
            dt_compra = datetime.strptime(str(data_raw).split()[0], "%Y-%m-%d").date()
        except Exception:
            try:
                dt_compra = datetime.strptime(str(data_raw).split()[0], "%d/%m/%Y").date()
            except Exception:
                continue
                
        # Procura coluna de valor com fallbacks
        valor_raw = 0.0
        for key in ['Valor', '_Valor', 'valor', '_valor']:
            if key in r_dict:
                valor_raw = r_dict[key]
                break
                
        if isinstance(valor_raw, str):
            valor_total = tratar_entrada_numerica(valor_raw)
        else:
            valor_total = float(valor_raw)
            
        # Procura coluna de tipo
        tipo_lanc = 'Gasto Variável'
        for key in ['Tipo', '_Tipo', 'tipo', '_tipo']:
            if key in r_dict:
                tipo_lanc = str(r_dict[key])
                break
                
        # Procura parcelas totais
        total_parc = 1
        for key in ['Parcelas_Totais', '_Parcelas_Totais', 'ParcelasTotais', 'parcelas_totais']:
            if key in r_dict:
                try:
                    total_parc = int(r_dict[key])
                except Exception:
                    total_parc = 1
                break
        if total_parc < 1:
            total_parc = 1
            
        # Procura responsável
        resp_raw = 'Jonathan'
        for key in ['Responsavel', '_Responsavel', 'responsavel', '_responsavel']:
            if key in r_dict:
                resp_raw = str(r_dict[key])
                break
                
        responsaveis_list = [resp.strip() for resp in resp_raw.split(",") if resp.strip()]
        if not responsaveis_list:
            responsaveis_list = ["Jonathan"]
            
        divisao_pessoas = len(responsaveis_list)
        
        # Procura forma de pagamento
        forma_pagto = 'Dinheiro'
        for key in ['Forma_Pagamento', '_Forma_Pagamento', 'forma_pagto', 'forma_pagamento']:
            if key in r_dict:
                forma_pagto = str(r_dict[key])
                break
                
        # Procura se está parcelado
        parcelado_str = 'Não'
        for key in ['Parcelado', '_Parcelado', 'parcelado']:
            if key in r_dict:
                parcelado_str = str(r_dict[key])
                break
                
        # Projeção de assinaturas para os próximos 12 meses
        if tipo_lanc == "Assinatura":
            for m in range(12):
                dt_recorrente = dt_compra + relativedelta(months=m)
                mes_competencia = calcular_mes_competencia(dt_recorrente, forma_pagto)
                
                for resp in responsaveis_list:
                    item_proj = r_dict.copy()
                    item_proj['Mes_Fatura'] = mes_competencia
                    item_proj['Valor_Parcela'] = valor_total / divisao_pessoas
                    item_proj['Responsavel_Dividido'] = resp
                    item_proj['Parcela_Atual'] = "Recorrente"
                    item_proj['Data_Parsed'] = dt_recorrente
                    lista_projetada.append(item_proj)
        else:
            # Compras normais e parceladas
            val_parcela = valor_total / total_parc if parcelado_str == 'Sim' else valor_total
            for p in range(total_parc):
                dt_parcela = dt_compra + relativedelta(months=p)
                mes_competencia = calcular_mes_competencia(dt_parcela, forma_pagto)
                
                for resp in responsaveis_list:
                    item_proj = r_dict.copy()
                    item_proj['Mes_Fatura'] = mes_competencia
                    item_proj['Valor_Parcela'] = val_parcela / divisao_pessoas
                    item_proj['Responsavel_Dividido'] = resp
                    item_proj['Parcela_Atual'] = f"{p+1}/{total_parc}" if parcelado_str == 'Sim' else "1/1"
                    item_proj['Data_Parsed'] = dt_parcela
                    lista_projetada.append(item_proj)
                    
    df_proj = pd.DataFrame(lista_projetada)
    return df_proj, avisos

# INTERFACE DO USUÁRIO
st.markdown('<div class="main-title">💰 Controle Financeiro Familiar</div>', unsafe_allow_html=True)
st.markdown("### Jonathan Prado")

# Lógica de contagem de fechamento baseada na data de SP
vencimento_limite = date(hoje_brasil.year, hoje_brasil.month, 7)
if hoje_brasil.day >= 7:
    vencimento_limite = vencimento_limite + relativedelta(months=1)
dias_restantes = (vencimento_limite - hoje_brasil).days

st.info(f"⏳ **Fechamento de Faturas:** Faltam **{dias_restantes} dias** para o fechamento dos cartões (Fechamento em 06/{vencimento_limite.strftime('%m/%Y')} às 23:59)")

tabs = st.tabs(["📲 Novo Lançamento", "📊 Dashboard & Resumos", "💳 Controle de Parcelas & Assinaturas", "✏️ Ajustar Lançamentos"])

# TAB 1: FORMULÁRIO DE LANÇAMENTO (OTIMIZADO PARA BRASIL)
with tabs[0]:
    st.subheader("Registrar Gasto ou Entrada")
    if sheet_conn is None:
        st.info("⚠️ **O formulário de envio está temporariamente desativado devido a problemas de conexão.**")
    else:
        # Reatividade instantânea na troca de categorias fora do st.form
        tipo = st.selectbox("Tipo de Lançamento", ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"])
        
        # Define a lista de categorias baseado no Tipo selecionado
        if tipo == "Gasto Fixo":
            lista_cats = ["Luz", "Água", "Internet", "Telefone", "Condomínio", "Aluguel", "Plano de Saúde", "Outros Fixos"]
        elif tipo == "Gasto Variável":
            lista_cats = ["Refeição", "Supermercado", "Abastecimento", "Shopping", "Farmácia", "Lazer", "Viagem", "Presentes", "Outros Variáveis"]
        elif tipo == "Assinatura":
            lista_cats = ["Streaming (Netflix/Spotify)", "Academia", "Clube de Assinatura", "Software/App", "Outras Assinaturas"]
        else: 
            lista_cats = ["Salário", "Rendimento", "Pix Recebido", "Outras Entradas"]
        
        # Form de Envio
        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                # Calendário iniciando na data real do fuso de SP
                data = st.date_input("Data do Lançamento", hoje_brasil, format="DD/MM/YYYY")
                descricao = st.text_input("Descrição", placeholder="Ex: Sorveteria Sávio, Roupas na Shein, Mercado Muffato")
                valor_texto = st.text_input("Valor (R$)", value="0,00", help="Use vírgula para centavos. Exemplo: 8,99 ou 150,50")
            
            with col2:
                # Seleção de Categoria dinâmica associada ao Tipo escolhido
                categoria = st.selectbox("Categoria", lista_cats)
                
                responsavel = st.multiselect(
                    "Para Quem?", 
                    ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"],
                    default=["Jonathan"]
                )
                
                forma_pagto = st.selectbox("Forma de Pagamento", ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"])
                
                pode_parcelar = tipo in ["Gasto Variável", "Gasto Fixo"]
                if pode_parcelar:
                    parcelado = st.radio("Compra Parcelada?", ["Não", "Sim"], horizontal=True)
                    if parcelado == "Sim":
                        num_parcelas = st.number_input("Quantidade de Parcelas", min_value=2, max_value=48, value=2, step=1)
                    else:
                        num_parcelas = 1
                else:
                    parcelado = "Não"
                    num_parcelas = 1
                    
            botao_salvar = st.form_submit_button("🚀 Gravar na Planilha")
            
            if botao_salvar:
                val_float = tratar_entrada_numerica(valor_texto)
                
                if not responsavel:
                    st.error("Por favor, selecione pelo menos um responsável pelo gasto.")
                elif descricao and val_float > 0:
                    resp_salvar = ", ".join(responsavel)
                    valor_gravar_sheets = f"{val_float:.2f}".replace(".", ",")
                    
                    novo_registro = [
                        str(data), descricao, valor_gravar_sheets, categoria, tipo, 
                        resp_salvar, forma_pagto, parcelado, int(num_parcelas)
                    ]
                    try:
                        sheet_conn.append_row(novo_registro, value_input_option='USER_ENTERED')
                        st.success(f"Sucesso! '{descricao}' gravado com o valor de {formatar_brl(val_float)}.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")
                else:
                    st.error("Por favor, preencha a descrição e um valor decimal válido maior que zero (Exemplo: 8,99).")

# INTERPRETAÇÃO E PROJEÇÃO DOS DADOS
if sheet_conn is not None:
    try:
        dados_brutos = pd.DataFrame(sheet_conn.get_all_records())
    except Exception as e:
        dados_brutos = pd.DataFrame()
        st.warning("Aguardando lançamentos na aba 'Lancamentos' para carregar os gráficos.")

    if not dados_brutos.empty:
        # Normalização dos cabeçalhos das colunas
        dados_brutos.columns = [col.strip() for col in dados_brutos.columns]
        
        # Execução da nossa projeção blindada e otimizada (Resolvendo erro AttributeError)
        df_projetado, avisos_proj = projetar(dados_brutos, hoje_brasil)
        
        if not df_projetado.empty:
            # Traduzir a exibição da data nas tabelas
            def formatar_data_br(data_str):
                try:
                    dt = datetime.strptime(str(data_str).split()[0], "%Y-%m-%d")
                    return dt.strftime("%d/%m/%Y")
                except Exception:
                    return data_str
            
            df_projetado['Data_Exibicao'] = df_projetado['Data_Parsed'].apply(formatar_data_br)
            
            # TAB 2: DASHBOARD
            with tabs[1]:
                st.subheader("Resumo Mensal e Faturas")
                
                meses_disponiveis = sorted(df_projetado['Mes_Fatura'].unique())
                if meses_disponiveis:
                    # Encontra o mês atual em SP para selecionar dinamicamente como padrão
                    mes_atual_padrao = hoje_brasil.strftime("%Y-%m")
                    idx_padrao = meses_disponiveis.index(mes_atual_padrao) if mes_atual_padrao in meses_disponiveis else len(meses_disponiveis)-1
                    
                    mes_selecionado = st.selectbox("Selecione o Mês de Análise", meses_disponiveis, index=idx_padrao)
                    
                    df_mes = df_projetado[df_projetado['Mes_Fatura'] == mes_selecionado]
                    
                    # KPIs Principais do Mês Selecionado
                    tot_entradas = df_mes[df_mes['Tipo'] == 'Entrada']['Valor_Parcela'].sum()
                    tot_saidas = df_mes[df_mes['Tipo'] != 'Entrada']['Valor_Parcela'].sum()
                    
                    # Faturas Cartões (A nova regra foi aplicada aqui!)
                    fatura_nu = df_mes[df_mes['Forma_Pagamento'] == 'Cartão Nu']['Valor_Parcela'].sum()
                    fatura_bb = df_mes[df_mes['Forma_Pagamento'] == 'Cartão BB']['Valor_Parcela'].sum()
                    
                    saldo_final = tot_entradas - tot_saidas
                    
                    # BLOCOS DE KPI MODERNOS (GRADIENTE, SOMBRA, HOVER)
                    kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
                    
                    with kpi_c1:
                        st.markdown(f"""
                        <div class="kpi-container kpi-entradas">
                            <div class="kpi-title">🟢 Total Entradas</div>
                            <div class="kpi-value">{formatar_brl(tot_entradas)}</div>
                            <div class="kpi-subtitle">Salários & Receitas</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with kpi_c2:
                        st.markdown(f"""
                        <div class="kpi-container kpi-saidas">
                            <div class="kpi-title">🔴 Total Despesas</div>
                            <div class="kpi-value">{formatar_brl(tot_saidas)}</div>
                            <div class="kpi-subtitle">Balanço: {formatar_brl(saldo_final)} de saldo</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with kpi_c3:
                        st.markdown(f"""
                        <div class="kpi-container kpi-nu">
                            <div class="kpi-title">💳 Fatura Nu Bank</div>
                            <div class="kpi-value">{formatar_brl(fatura_nu)}</div>
                            <div class="kpi-subtitle">Competência {mes_selecionado}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with kpi_c4:
                        st.markdown(f"""
                        <div class="kpi-container kpi-bb">
                            <div class="kpi-title">💳 Fatura BB</div>
                            <div class="kpi-value">{formatar_brl(fatura_bb)}</div>
                            <div class="kpi-subtitle">Vence nos próximos dias</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.write("---")
                    
                    # SEÇÃO DE GRÁFICOS INTERATIVOS PLOTLY
                    st.markdown("### Visualização de Distribuição e Análise")
                    
                    g_col1, g_col2 = st.columns(2)
                    
                    with g_col1:
                        st.markdown("**Gastos por Categoria (Donut Chart com Total)**")
                        df_gasto_cat = df_mes[df_mes['Tipo'] != 'Entrada'].groupby('Categoria')['Valor_Parcela'].sum().reset_index()
                        
                        if not df_gasto_cat.empty:
                            total_gastos = df_gasto_cat['Valor_Parcela'].sum()
                            fig_donut = px.pie(
                                df_gasto_cat, 
                                values='Valor_Parcela', 
                                names='Categoria', 
                                hole=0.5,
                                color_discrete_sequence=['#059669', '#312e81', '#10b981', '#4f46e5', '#047857', '#4338ca', '#065f46', '#3730a3', '#064e3b', '#6366f1']
                            )
                            fig_donut.update_traces(
                                textinfo='percent+label',
                                hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>Representa: %{percent}<extra></extra>"
                            )
                            fig_donut.add_annotation(
                                text=f"Total<br><b>R$ {total_gastos:,.2f}</b>",
                                showarrow=False,
                                font_size=16,
                                font_color="#1e1b4b"
                            )
                            fig_donut.update_layout(
                                margin=dict(t=10, b=10, l=10, r=10),
                                showlegend=False,
                                height=350
                            )
                            st.plotly_chart(fig_donut, use_container_width=True)
                        else:
                            st.info("Nenhum gasto registrado para gerar gráfico de rosca.")
                            
                    with g_col2:
                        st.markdown("**Balanço de Gastos Dividido (Barras Horizontais em R$)**")
                        # Gráfico usa a coluna "Responsavel_Dividido" para computar as proporções corretas pós-divisão
                        df_gasto_resp = df_mes[df_mes['Tipo'] != 'Entrada'].groupby('Responsavel_Dividido')['Valor_Parcela'].sum().reset_index()
                        
                        if not df_gasto_resp.empty:
                            fig_barras = px.bar(
                                df_gasto_resp,
                                x='Valor_Parcela',
                                y='Responsavel_Dividido',
                                orientation='h',
                                text='Valor_Parcela',
                                color='Valor_Parcela',
                                color_continuous_scale=['#a78bfa', '#312e81']
                            )
                            fig_barras.update_traces(
                                texttemplate='R$ %{text:,.2f}', 
                                textposition='outside',
                                hovertemplate="<b>%{y}</b><br>Gasto proporcional: R$ %{x:,.2f}<extra></extra>"
                            )
                            fig_barras.update_layout(
                                xaxis_title="Gasto Total Proporcional",
                                yaxis_title="Destinatário",
                                coloraxis_showscale=False,
                                margin=dict(t=10, b=10, l=10, r=10),
                                height=350
                            )
                            st.plotly_chart(fig_barras, use_container_width=True)
                        else:
                            st.info("Sem dados de despesa para exibir no balanço.")
                    
                    st.write("---")
                    
                    # GRÁFICO 3: EVOLUÇÃO MENSAL
                    st.markdown("**Histórico de Evolução Mensal (Entradas vs Despesas)**")
                    
                    df_evolucao = df_projetado.groupby(['Mes_Fatura', 'Tipo'])['Valor_Parcela'].sum().unstack(fill_value=0.0).reset_index()
                    
                    if not df_evolucao.empty:
                        if 'Entrada' not in df_evolucao.columns: df_evolucao['Entrada'] = 0.0
                        
                        colunas_despesas = [c for c in df_evolucao.columns if c != 'Mes_Fatura' and c != 'Entrada']
                        df_evolucao['Total_Despesas'] = df_evolucao[colunas_despesas].sum(axis=1)
                        
                        fig_linhas = go.Figure()
                        fig_linhas.add_trace(go.Scatter(
                            x=df_evolucao['Mes_Fatura'], 
                            y=df_evolucao['Entrada'],
                            name='🟢 Entradas (Receitas)',
                            line=dict(color='#10b981', width=3),
                            mode='lines+markers',
                            hovertemplate="Mês: %{x}<br>Receitas: R$ %{y:,.2f}<extra></extra>"
                        ))
                        fig_linhas.add_trace(go.Scatter(
                            x=df_evolucao['Mes_Fatura'], 
                            y=df_evolucao['Total_Despesas'],
                            name='🔴 Despesas (Gastos)',
                            line=dict(color='#6366f1', width=3),
                            mode='lines+markers',
                            hovertemplate="Mês: %{x}<br>Despesas: R$ %{y:,.2f}<extra></extra>"
                        ))
                        
                        fig_linhas.update_layout(
                            margin=dict(t=20, b=20, l=10, r=10),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            height=300
                        )
                        st.plotly_chart(fig_linhas, use_container_width=True)
                    
                    st.write("---")
                    
                    # MATRIZ DE CALOR (HEATMAP DE CATEGORIAS)
                    st.markdown("**Matriz de Calor de Gastos por Categoria (Últimos 6 meses)**")
                    df_despesas_total = df_projetado[df_projetado['Tipo'] != 'Entrada']
                    if not df_despesas_total.empty:
                        # Pivotando os dados para a estrutura de Heatmap
                        df_heatmap_data = df_despesas_total.groupby(['Categoria', 'Mes_Fatura'])['Valor_Parcela'].sum().unstack(fill_value=0.0)
                        
                        # Limita aos últimos 6 meses de faturamento para melhor layout em tela
                        meses_recentes = sorted(df_despesas_total['Mes_Fatura'].unique())[-6:]
                        df_heatmap_data = df_heatmap_data[meses_recentes]
                        
                        fig_heatmap = go.Figure(data=go.Heatmap(
                            z=df_heatmap_data.values,
                            x=df_heatmap_data.columns,
                            y=df_heatmap_data.index,
                            colorscale='Emrld',
                            hovertemplate="Mês: %{x}<br>Categoria: %{y}<br>Valor: R$ %{z:,.2f}<extra></extra>"
                        ))
                        fig_heatmap.update_layout(
                            xaxis_title="Meses de Fatura",
                            yaxis_title="Categorias",
                            margin=dict(t=20, b=20, l=10, r=10),
                            height=350
                        )
                        st.plotly_chart(fig_heatmap, use_container_width=True)
                    
                    st.write("---")
                    
                    st.markdown("**Extrato Detalhado do Mês de Competência**")
                    # Remove duplicidade de linhas que foram explodidas pelo multiselect para mostrar uma tabela organizada e limpa
                    df_mes_tabela = df_mes.drop_duplicates(subset=['Data', 'Descricao', 'Valor', 'Categoria', 'Forma_Pagamento', 'Parcela_Atual'])
                    
                    df_mes_exibe = df_mes_tabela[['Data_Exibicao', 'Descricao', 'Valor', 'Parcela_Atual', 'Categoria', 'Responsavel', 'Forma_Pagamento', 'Tipo']].copy()
                    df_mes_exibe.rename(columns={'Data_Exibicao': 'Data', 'Valor': 'Valor Total (R$)'}, inplace=True)
                    
                    def formatar_valor_tabela(val):
                        f = tratar_entrada_numerica(val)
                        return formatar_brl(f)
                    df_mes_exibe['Valor Total (R$)'] = df_mes_exibe['Valor Total (R$)'].apply(formatar_valor_tabela)
                    
                    st.dataframe(df_mes_exibe, use_container_width=True)
                else:
                    st.info("Nenhum mês disponível para análise.")

            # TAB 3: CONTROLE DE PARCELAS ACUMULADAS E ASSINATURAS
            with tabs[2]:
                st.subheader("Dívidas Parceladas e Controle de Assinaturas")
                
                hoje_str = hoje_brasil.strftime("%Y-%m")
                
                df_futuro = df_projetado[(df_projetado['Mes_Fatura'] > hoje_str) & (df_projetado['Parcelado'] == 'Sim')]
                saldo_devedor_futuro = df_futuro['Valor_Parcela'].sum()
                
                st.warning(f"🏦 **Saldo Devedor Total Acumulado (Faturas Seguintes):** {formatar_brl(saldo_devedor_futuro)}")
                
                col_esquerda, col_direita = st.columns(2)
                
                with col_esquerda:
                    st.markdown("### 💳 Cronograma de Parcelamentos")
                    if not df_futuro.empty:
                        cronograma = df_futuro.groupby(['Mes_Fatura', 'Forma_Pagamento'])['Valor_Parcela'].sum().unstack().fillna(0)
                        
                        for col in cronograma.columns:
                            cronograma[col] = cronograma[col].apply(formatar_brl)
                        
                        st.dataframe(cronograma, use_container_width=True)
                        
                        st.markdown("**Detalhe das Parcelas Futuras**")
                        df_futuro_exibe = df_futuro[['Mes_Fatura', 'Descricao', 'Valor_Parcela', 'Parcela_Atual', 'Forma_Pagamento']].copy()
                        df_futuro_exibe['Valor_Parcela'] = df_futuro_exibe['Valor_Parcela'].apply(formatar_brl)
                        st.dataframe(df_futuro_exibe, use_container_width=True)
                    else:
                        st.info("Muito bom! Você não tem compras parceladas para os próximos meses.")
                        
                with col_direita:
                    st.markdown("### 🔄 Assinaturas e Recorrências Ativas")
                    df_assinaturas = df_projetado[df_projetado['Tipo'] == 'Assinatura'].drop_duplicates(subset=['Descricao'])
                    if not df_assinaturas.empty:
                        tot_mensal_ass = df_assinaturas['Valor_Parcela'].sum()
                        st.success(f"📋 **Custo Mensal de Assinaturas:** {formatar_brl(tot_mensal_ass)}")
                        
                        df_ass_exibe = df_assinaturas[['Descricao', 'Valor_Parcela', 'Categoria', 'Forma_Pagamento']].copy()
                        df_ass_exibe['Valor_Parcela'] = df_ass_exibe['Valor_Parcela'].apply(formatar_brl)
                        st.dataframe(df_ass_exibe, use_container_width=True)
                    else:
                        st.info("Nenhuma assinatura cadastrada.")

            # TAB 4: EDITAR E CORRIGIR LANÇAMENTOS
            with tabs[3]:
                st.subheader("Corrigir ou Apagar Lançamentos")
                st.markdown("Selecione um lançamento da lista para editar os valores ou apagá-los de forma instantânea.")
                
                df_editor = dados_brutos.copy()
                
                if not df_editor.empty:
                    df_editor = df_editor.iloc[::-1].reset_index(drop=True)
                    
                    def gerar_linha_opcao(row):
                        data_formatada = formatar_data_br(row.get('Data', ''))
                        v_float = tratar_entrada_numerica(row.get('Valor', 0.0))
                        v_brl = formatar_brl(v_float)
                        return f"{data_formatada} | {row.get('Descricao', 'Sem Descrição')} | {v_brl} ({row.get('Forma_Pagamento', 'Pix')})"
                    
                    df_editor['Identificacao_Opcao'] = df_editor.apply(gerar_linha_opcao, axis=1)
                    
                    selecao = st.selectbox("Selecione qual item quer alterar ou excluir:", df_editor['Identificacao_Opcao'])
                    
                    if selecao:
                        item_selecionado = df_editor[df_editor['Identificacao_Opcao'] == selecao].iloc[0]
                        
                        idx_dataframe = df_editor[df_editor['Identificacao_Opcao'] == selecao].index[0]
                        linha_planilha_real = (len(dados_brutos) - idx_dataframe) + 1
                        
                        try:
                            data_item = datetime.strptime(str(item_selecionado['Data']).split()[0], "%Y-%m-%d").date()
                        except Exception:
                            try:
                                data_item = datetime.strptime(str(item_selecionado['Data']).split()[0], "%d/%m/%Y").date()
                            except Exception:
                                data_item = hoje_brasil
                        
                        valor_antigo_float = tratar_entrada_numerica(item_selecionado['Valor'])
                        valor_antigo_br = f"{valor_antigo_float:.2f}".replace(".", ",")
                        
                        resp_item_raw = str(item_selecionado.get('Responsavel', 'Jonathan'))
                        resp_item_lista = [r.strip() for r in resp_item_raw.split(",") if r.strip()]
                        
                        st.markdown(f"📍 **Editando Linha {linha_planilha_real} da planilha:**")
                        
                        with st.form("form_edicao"):
                            e_col1, e_col2 = st.columns(2)
                            with e_col1:
                                e_data = st.date_input("Nova Data", data_item, format="DD/MM/YYYY")
                                e_desc = st.text_input("Nova Descrição", value=item_selecionado['Descricao'])
                                e_valor_texto = st.text_input("Corrigir Valor (R$)", value=valor_antigo_br)
                                e_tipo = st.selectbox(
                                    "Novo Tipo", 
                                    ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"],
                                    index=["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"].index(item_selecionado['Tipo'])
                                )
                            with e_col2:
                                if e_tipo == "Gasto Fixo":
                                    e_lista_cats = ["Luz", "Água", "Internet", "Telefone", "Condomínio", "Aluguel", "Plano de Saúde", "Outros Fixos"]
                                elif e_tipo == "Gasto Variável":
                                    e_lista_cats = ["Refeição", "Supermercado", "Abastecimento", "Shopping", "Farmácia", "Lazer", "Viagem", "Presentes", "Outros Variáveis"]
                                elif e_tipo == "Assinatura":
                                    e_lista_cats = ["Streaming (Netflix/Spotify)", "Academia", "Clube de Assinatura", "Software/App", "Outras Assinaturas"]
                                else: 
                                    e_lista_cats = ["Salário", "Rendimento", "Pix Recebido", "Outras Entradas"]
                                
                                idx_cat_edicao = e_lista_cats.index(item_selecionado['Categoria']) if item_selecionado['Categoria'] in e_lista_cats else 0
                                e_cat = st.selectbox("Nova Categoria", e_lista_cats, index=idx_cat_edicao)
                                
                                e_resp = st.multiselect(
                                    "Novos Responsáveis", 
                                    ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"],
                                    default=resp_item_lista
                                )
                                
                                e_forma = st.selectbox(
                                    "Nova Forma de Pagamento", 
                                    ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"],
                                    index=["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"].index(item_selecionado['Forma_Pagamento'])
                                )
                                
                                e_parcelado = item_selecionado.get('Parcelado', 'Não')
                                e_tot_parc = int(item_selecionado.get('Parcelas_Totais', 1))
                                
                            btn_atualizar = st.form_submit_button("💾 Salvar Alterações")
                            
                            if btn_atualizar:
                                val_novo_float = tratar_entrada_numerica(e_valor_texto)
                                
                                if not e_resp:
                                    st.error("Selecione pelo menos um responsável.")
                                elif e_desc and val_novo_float > 0:
                                    resp_ed_salvar = ", ".join(e_resp)
                                    valor_ed_gravar = f"{val_novo_float:.2f}".replace(".", ",")
                                    
                                    linha_atualizada = [
                                        str(e_data), e_desc, valor_ed_gravar, e_cat, e_tipo, 
                                        resp_ed_salvar, e_forma, e_parcelado, e_tot_parc
                                    ]
                                    
                                    try:
                                        sheet_conn.update(f"A{linha_planilha_real}:I{linha_planilha_real}", [linha_atualizada], value_input_option='USER_ENTERED')
                                        st.success("Lançamento atualizado com sucesso! Reiniciando visualização...")
                                        st.rerun()
                                    except Exception as err:
                                        st.error(f"Erro ao salvar modificação: {err}")
                        
                        # EXCLUSÃO
                        st.markdown("---")
                        st.markdown("### ⚠️ Zona de Perigo")
                        confirmar_exclusao = st.checkbox("Eu quero excluir permanentemente este lançamento da minha planilha.")
                        btn_excluir = st.button("❌ APAGAR DEFINITIVAMENTE", disabled=not confirmar_exclusao, type="secondary")
                        
                        if btn_excluir and confirmar_exclusao:
                            try:
                                sheet_conn.delete_rows(linha_planilha_real)
                                st.success("Lançamento apagado da planilha!")
                                st.rerun()
                            except Exception as err:
                                st.error(f"Erro ao apagar linha: {err}")
                else:
                    st.info("A planilha está vazia.")
else:
    st.info("Aguardando os primeiros dados da planilha para renderizar os gráficos.")
