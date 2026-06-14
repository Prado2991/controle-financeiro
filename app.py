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

    /* Título com estilo premium e sólido (evita bugs de destaque/marca-texto) */
    .main-title {
        color: #1e1b4b; /* Azul escuro premium */
        font-size: 32px;
        font-weight: 800;
        margin-bottom: 5px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
</style>
""", unsafe_allow_html=True)

# FUNÇÃO DE CONVERSÃO BRASILEIRA DE MOEDA
def formatar_brl(valor):
    try:
        val = float(valor)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
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
    except Exception as e:
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
        # 🟢 Tipo de Lançamento simplificado mantendo apenas "Gastos Fixos" e "Assinaturas"
        tipo_exibido = st.selectbox(
            "Tipo de Lançamento", 
            [
                "Gasto Variável", 
                "Gasto Fixo", 
                "Assinatura", 
                "Entrada"
            ]
        )
        
        # Define a lista de categorias e o tipo correspondente
        if tipo_exibido == "Gasto Fixo":
            tipo_salvar = "Gasto Fixo"
            lista_cats = ["Luz", "Água", "Plano de Saúde", "Internet (Variável)", "Telefone (Variável)", "Condomínio (Variável)", "Outros Fixos"]
        elif tipo_exibido == "Assinatura":
            tipo_salvar = "Assinatura"
            lista_cats = [
                "Internet", 
                "Telefone/Celular", 
                "Aluguel", 
                "Condomínio", 
                "Academia", 
                "Streaming (Netflix/Spotify/Prime)", 
                "Seguro (Carro/Casa)", 
                "Mensalidade Escolar/Curso", 
                "Outras Assinaturas"
            ]
        elif tipo_exibido == "Gasto Variável":
            tipo_salvar = "Gasto Variável"
            lista_cats = ["Refeição", "Supermercado", "Abastecimento", "Shopping", "Farmácia", "Lazer", "Viagem", "Presentes", "Outros Variáveis"]
        else: 
            tipo_salvar = "Entrada"
            lista_cats = ["Salário", "Rendimento", "Pix Recebido", "Outras Entradas"]
        
        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                # Calendário iniciando na data real do fuso de SP
                data = st.date_input("Data do Lançamento", hoje_brasil, format="DD/MM/YYYY")
                descricao = st.text_input("Descrição", placeholder="Ex: Sorveteria Sávio, Plano Claro, Conta Copel")
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
                
                pode_parcelar = tipo_salvar in ["Gasto Variável", "Gasto Fixo"]
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
                        str(data), descricao, valor_gravar_sheets, categoria, tipo_salvar, 
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
        # Processar projeções de parcelas futuras e assinaturas automáticas em memória
        lista_projetada = []
        for index, row in dados_brutos.iterrows():
            try:
                if not row.get('Data'):
                    continue
                dt_compra = datetime.strptime(str(row['Data']).split()[0], "%Y-%m-%d").date()
            except Exception as parse_error:
                try:
                    dt_compra = datetime.strptime(str(row['Data']).split()[0], "%d/%m/%Y").date()
                except:
                    continue
            
            valor_raw = row.get('Valor', 0.0)
            if isinstance(valor_raw, str):
                valor_total = tratar_entrada_numerica(valor_raw)
            else:
                valor_total = float(valor_raw)
                
            tipo_lanc = row.get('Tipo', 'Gasto Variável')
            total_parc = int(row['Parcelas_Totais']) if row.get('Parcelas_Totais') else 1
            
            # Divisão proporcional de responsáveis
            resp_raw = str(row.get('Responsavel', 'Jonathan'))
            responsaveis_list = [r.strip() for r in resp_raw.split(",") if r.strip()]
            if not responsaveis_list:
                responsaveis_list = ["Jonathan"]
            
            divisao_pessoas = len(responsaveis_list)
            
            # Projeção de Assinaturas e Gastos Fixos Recorrentes para os próximos 12 meses
            if tipo_lanc in ["Assinatura", "Gasto Fixo / Assinatura"]:
                for m in range(12):
                    dt_recorrente = dt_compra + relativedelta(months=m)
                    mes_competencia = calcular_mes_competencia(dt_recorrente, row.get('Forma_Pagamento', 'Dinheiro'))
                    
                    for resp in responsaveis_list:
                        item_proj = row.to_dict()
                        item_proj['Mes_Fatura'] = mes_competencia
                        item_proj['Valor_Parcela'] = valor_total / divisao_pessoas
                        item_proj['Responsavel_Dividido'] = resp
                        item_proj['Parcela_Atual'] = "Recorrente"
                        lista_projetada.append(item_proj)
            else:
                # Compras normais e parceladas (Gasto Variável, Gasto Fixo e Entradas)
                val_parcela = valor_total / total_parc if row.get('Parcelado') == 'Sim' else valor_total
                for p in range(total_parc):
                    dt_parcela = dt_compra + relativedelta(months=p)
                    mes_competencia = calcular_mes_competencia(dt_parcela, row.get('Forma_Pagamento', 'Dinheiro'))
                    
                    for resp in responsaveis_list:
                        item_proj = row.to_dict()
                        item_proj['Mes_Fatura'] = mes_competencia
                        item_proj['Valor_Parcela'] = val_parcela / divisao_pessoas
                        item_proj['Responsavel_Dividido'] = resp
                        item_proj['Parcela_Atual'] = f"{p+1}/{total_parc}" if row.get('Parcelado') == 'Sim' else "1/1"
                        lista_projetada.append(item_proj)
                
        if lista_projetada:
            df_projetado = pd.DataFrame(lista_projetada)
            df_projetado['Valor_Parcela'] = df_projetado['Valor_Parcela'].astype(float)
            
            # Traduzir a exibição da data nas tabelas
            def formatar_data_br(data_str):
                try:
                    dt = datetime.strptime(str(data_str).split()[0], "%Y-%m-%d")
                    return dt.strftime("%d/%m/%Y")
                except:
                    return data_str
            
            df_projetado['Data_Exibicao'] = df_projetado['Data'].apply(formatar_data_br)
            
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
                    
                    st.markdown("### 📊 Análise Setorial das Despesas")
                    
                    g_col1, g_col2 = st.columns(2)
                    
                    # GRÁFICO 1: GASTOS VARIÁVEIS (Foco de Controle Ativo de Despesas)
                    with g_col1:
                        st.markdown("""
                        <div class="dashboard-card">
                            <div class="dashboard-card-title">💸 Gastos Variáveis (Foco de Controle Diário)</div>
                        </div>
                        """, unsafe_allow_html=True)
                        # Filtra apenas os Gastos Variáveis do mês selecionado
                        df_gasto_var = df_mes[df_mes['Tipo'] == 'Gasto Variável'].groupby('Categoria')['Valor_Parcela'].sum().reset_index()
                        
                        if not df_gasto_var.empty:
                            total_g_var = df_gasto_var['Valor_Parcela'].sum()
                            fig_donut_var = px.pie(
                                df_gasto_var, 
                                values='Valor_Parcela', 
                                names='Categoria', 
                                hole=0.5,
                                color_discrete_sequence=['#10b981', '#059669', '#34d399', '#6ee7b7', '#a7f3d0', '#047857', '#065f46', '#064e3b'] # Tons verdes esmeralda
                            )
                            fig_donut_var.update_traces(
                                textinfo='percent+label',
                                hovertemplate="<b>%{label}</b><br>Gasto: R$ %{value:,.2f}<br>Fração: %{percent}<extra></extra>"
                            )
                            fig_donut_var.add_annotation(
                                text=f"Variáveis<br><b>R$ {total_g_var:,.2f}</b>",
                                showarrow=False,
                                font_size=15,
                                font_color="#064e3b"
                            )
                            fig_donut_var.update_layout(
                                margin=dict(t=10, b=10, l=10, r=10),
                                showlegend=False,
                                height=320
                            )
                            st.plotly_chart(fig_donut_var, use_container_width=True)
                        else:
                            st.info("Nenhum Gasto Variável registrado neste mês de análise.")
                            
                    # GRÁFICO 2: GASTOS FIXOS & RECORRENTES (Comprometido estrutural)
                    with g_col2:
                        st.markdown("""
                        <div class="dashboard-card">
                            <div class="dashboard-card-title">🔒 Gastos Fixos & Assinaturas Recorrentes</div>
                        </div>
                        """, unsafe_allow_html=True)
                        # Filtra Gastos Fixos normais, Assinaturas tradicionais e o novo tipo unificado
                        df_gasto_fix = df_mes[df_mes['Tipo'].isin(['Gasto Fixo', 'Assinatura', 'Gasto Fixo / Assus', 'Gasto Fixo / Assinatura'])].groupby('Categoria')['Valor_Parcela'].sum().reset_index()
                        
                        if not df_gasto_fix.empty:
                            total_g_fix = df_gasto_fix['Valor_Parcela'].sum()
                            fig_donut_fix = px.pie(
                                df_gasto_fix, 
                                values='Valor_Parcela', 
                                names='Categoria', 
                                hole=0.5,
                                color_discrete_sequence=['#312e81', '#4338ca', '#4f46e5', '#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe'] # Tons azuis/indigo
                            )
                            fig_donut_fix.update_traces(
                                textinfo='percent+label',
                                hovertemplate="<b>%{label}</b><br>Comprometido: R$ %{value:,.2f}<br>Fração: %{percent}<extra></extra>"
                            )
                            fig_donut_fix.add_annotation(
                                text=f"Comprometido<br><b>R$ {total_g_fix:,.2f}</b>",
                                showarrow=False,
                                font_size=15,
                                font_color="#1e1b4b"
                            )
                            fig_donut_fix.update_layout(
                                margin=dict(t=10, b=10, l=10, r=10),
                                showlegend=False,
                                height=320
                            )
                            st.plotly_chart(fig_donut_fix, use_container_width=True)
                        else:
                            st.info("Nenhum Gasto Fixo ou Assinatura registrado neste mês.")
                    
                    st.write("---")
                    
                    st.markdown("### 📊 Balanço de Participação e Histórico")
                    b_col1, b_col2 = st.columns(2)
                    
                    with b_col1:
                        st.markdown("**Balanço de Gastos Dividido (Proporcional em R$)**")
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
                                height=280
                            )
                            st.plotly_chart(fig_barras, use_container_width=True)
                        else:
                            st.info("Sem dados de despesa para exibir no balanço de divisão.")
                            
                    with b_col2:
                        st.markdown("**Histórico de Evolução Mensal (Receitas vs Despesas)**")
                        df_evolucao = df_projetado.groupby(['Mes_Fatura', 'Tipo'])['Valor_Parcela'].sum().unstack(fill_value=0.0).reset_index()
                        
                        if not df_evolucao.empty:
                            if 'Entrada' not in df_evolucao.columns: df_evolucao['Entrada'] = 0.0
                            
                            colunas_despesas = [c for c in df_evolucao.columns if c != 'Mes_Fatura' and c != 'Entrada']
                            df_evolucao['Total_Despesas'] = df_evolucao[colunas_despesas].sum(axis=1)
                            
                            fig_linhas = go.Figure()
                            fig_linhas.add_trace(go.Scatter(
                                x=df_evolucao['Mes_Fatura'], 
                                y=df_evolucao['Entrada'],
                                name='🟢 Entradas',
                                line=dict(color='#10b981', width=3),
                                mode='lines+markers',
                                hovertemplate="Mês: %{x}<br>Receitas: R$ %{y:,.2f}<extra></extra>"
                            ))
                            fig_linhas.add_trace(go.Scatter(
                                x=df_evolucao['Mes_Fatura'], 
                                y=df_evolucao['Total_Despesas'],
                                name='🔴 Despesas',
                                line=dict(color='#6366f1', width=3),
                                mode='lines+markers',
                                hovertemplate="Mês: %{x}<br>Despesas: R$ %{y:,.2f}<extra></extra>"
                            ))
                            
                            fig_linhas.update_layout(
                                margin=dict(t=20, b=20, l=10, r=10),
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                height=280
                            )
                            st.plotly_chart(fig_linhas, use_container_width=True)
                    
                    st.write("---")
                    
                    st.markdown("**Extrato Detalhado do Mês de Competência**")
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
                    # Filtra tanto o tipo antigo de assinatura quanto o novo modelo recorrente
                    df_assinaturas = df_projetado[df_projetado['Tipo'].isin(['Assinatura', 'Gasto Fixo / Assinatura'])].drop_duplicates(subset=['Descricao'])
                    if not df_assinaturas.empty:
                        tot_mensal_ass = df_assinaturas['Valor_Parcela'].sum()
                        st.success(f"📋 **Custo Mensal de Assinaturas/Contas Fixas:** {formatar_brl(tot_mensal_ass)}")
                        
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
                        except:
                            try:
                                data_item = datetime.strptime(str(item_selecionado['Data']).split()[0], "%d/%m/%Y").date()
                            except:
                                data_item = hoje_brasil
                        
                        valor_antigo_float = tratar_entrada_numerica(item_selecionado['Valor'])
                        valor_antigo_br = f"{valor_antigo_float:.2f}".replace(".", ",")
                        
                        resp_item_raw = str(item_selecionado.get('Responsavel', 'Jonathan'))
                        resp_item_lista = [r.strip() for r in resp_item_raw.split(",") if r.strip()]
                        
                        # Mapeamento limpo e simplificado para as edições
                        tipo_map = {
                            "Gasto Variável": "Gasto Variável",
                            "Gasto Fixo": "Gasto Fixo",
                            "Gasto Fixo (Valor Variável)": "Gasto Fixo",
                            "Assinatura": "Assinatura",
                            "Gasto Fixo / Assinatura": "Assinatura",
                            "Entrada": "Entrada"
                        }
                        stored_tipo = item_selecionado.get('Tipo', 'Gasto Variável')
                        mapped_tipo = tipo_map.get(stored_tipo, "Gasto Variável")
                        
                        st.markdown(f"📍 **Editando Linha {linha_planilha_real} da planilha:**")
                        
                        with st.form("form_edicao"):
                            e_col1, e_col2 = st.columns(2)
                            with e_col1:
                                e_data = st.date_input("Nova Data", data_item, format="DD/MM/YYYY")
                                e_desc = st.text_input("Nova Descrição", value=item_selecionado['Descricao'])
                                e_valor_texto = st.text_input("Corrigir Valor (R$)", value=valor_antigo_br)
                                
                                e_tipo_options = [
                                    "Gasto Variável", 
                                    "Gasto Fixo", 
                                    "Assinatura", 
                                    "Entrada"
                                ]
                                idx_tipo_edicao = e_tipo_options.index(mapped_tipo) if mapped_tipo in e_tipo_options else 0
                                e_tipo = st.selectbox("Novo Tipo", e_tipo_options, index=idx_tipo_edicao)
                                
                            with e_col2:
                                # Reatividade simplificada no formulário de edição
                                if e_tipo == "Gasto Fixo":
                                    tipo_ed_salvar = "Gasto Fixo"
                                    e_lista_cats = ["Luz", "Água", "Plano de Saúde", "Internet (Variável)", "Telefone (Variável)", "Condomínio (Variável)", "Outros Fixos"]
                                elif e_tipo == "Assinatura":
                                    tipo_ed_salvar = "Assinatura"
                                    e_lista_cats = [
                                        "Internet", 
                                        "Telefone/Celular", 
                                        "Aluguel", 
                                        "Condomínio", 
                                        "Academia", 
                                        "Streaming (Netflix/Spotify/Prime)", 
                                        "Seguro (Carro/Casa)", 
                                        "Mensalidade Escolar/Curso", 
                                        "Outras Assinaturas"
                                    ]
                                elif e_tipo == "Gasto Variável":
                                    tipo_ed_salvar = "Gasto Variável"
                                    e_lista_cats = ["Refeição", "Supermercado", "Abastecimento", "Shopping", "Farmácia", "Lazer", "Viagem", "Presentes", "Outros Variáveis"]
                                else: 
                                    tipo_ed_salvar = "Entrada"
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
                                        str(e_data), e_desc, valor_ed_gravar, e_cat, tipo_ed_salvar, 
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
