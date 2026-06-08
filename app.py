import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import gspread
from google.oauth2.service_account import Credentials
import json
import plotly.express as px
import plotly.graph_objects as go

# Configuração da página para visualização Mobile-First e Temática Elegante
st.set_page_config(
    page_title="Finanças Jonathan", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

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

# FUNÇÃO DE CONVERSÃO BRASILEIRA DE MOEDA (Para relatórios e visualizações)
def formatar_brl(valor):
    try:
        val = float(valor)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

# FUNÇÃO CRÍTICA DE TRATAMENTO NUMÉRICO DE ENTRADA (Impede R$ 8,99 de virar R$ 899,00)
def tratar_entrada_numerica(texto_valor):
    if texto_valor is None or texto_valor == "":
        return 0.0
    
    # Se já for número, retorna direto como float
    if isinstance(texto_valor, (int, float)):
        return float(texto_valor)
        
    try:
        # Remove símbolos de moeda e espaços em branco comuns
        texto_limpo = str(texto_valor).replace("R$", "").replace("r$", "").strip()
        
        # Caso clássico brasileiro: "1.250,50" ou "1,250.50"
        if "," in texto_limpo and "." in texto_limpo:
            idx_comma = texto_limpo.rfind(",")
            idx_dot = texto_limpo.rfind(".")
            if idx_comma > idx_dot:
                # Padrão Brasileiro (ponto milhar, vírgula decimal)
                texto_limpo = texto_limpo.replace(".", "").replace(",", ".")
            else:
                # Padrão Americano (vírgula milhar, ponto decimal)
                texto_limpo = texto_limpo.replace(",", "")
        # Caso: "8,99" -> apenas vírgula separando centavos
        elif "," in texto_limpo:
            texto_limpo = texto_limpo.replace(",", ".")
        
        # Converte para float final do Python
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

# LÓGICA DE FATURA (FECHAMENTO DIA 07) E PARCELAMENTO
def calcular_mes_competencia(data_compra, forma_pagamento):
    if "Cartão" not in forma_pagamento:
        return data_compra.strftime("%Y-%m")
    
    if data_compra.day > 7:
        data_fatura = data_compra + relativedelta(months=1)
    else:
        data_fatura = data_compra
    return data_fatura.strftime("%Y-%m")

# INTERFACE DO USUÁRIO
st.markdown('<div class="main-title">💰 Controle Financeiro Familiar</div>', unsafe_allow_html=True)
st.markdown("### Jonathan Prado")

# Barra de progresso para fechamento da fatura corrente (Dia 07)
hoje = date.today()
vencimento_limite = date(hoje.year, hoje.month, 7)
if hoje.day > 7:
    vencimento_limite = vencimento_limite + relativedelta(months=1)
dias_restantes = (vencimento_limite - hoje).days

st.info(f"⏳ **Fechamento de Faturas:** Faltam **{dias_restantes} dias** para o fechamento dos cartões (Próximo dia 07: {vencimento_limite.strftime('%d/%m/%Y')})")

tabs = st.tabs(["📲 Novo Lançamento", "📊 Dashboard & Resumos", "💳 Controle de Parcelas & Assinaturas", "✏️ Ajustar Lançamentos"])

# TAB 1: FORMULÁRIO DE LANÇAMENTO (OTIMIZADO PARA CELULAR)
with tabs[0]:
    st.subheader("Registrar Gasto ou Entrada")
    if sheet_conn is None:
        st.info("⚠️ **O formulário de envio está temporariamente desativado devido a problemas de conexão.**")
    else:
        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                data = st.date_input("Data do Lançamento", date.today(), format="DD/MM/YYYY")
                descricao = st.text_input("Descrição", placeholder="Ex: Sorveteria Sávio, Roupas na Shein, Mercado Muffato")
                
                # Mudança de Input de Número para TEXTO livre (Garante que a vírgula possa ser digitada no teclado brasileiro do celular)
                valor_texto = st.text_input("Valor (R$)", value="0,00", help="Use vírgula para centavos. Exemplo: 8,99 ou 150,50")
                
                tipo = st.selectbox("Tipo de Lançamento", ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"])
            
            with col2:
                # Lógica dinâmica de categorias
                if tipo == "Gasto Fixo":
                    lista_cats = ["Luz", "Água", "Internet", "Telefone", "Condomínio", "Aluguel", "Plano de Saúde", "Outros Fixos"]
                elif tipo == "Gasto Variável":
                    lista_cats = ["Refeição", "Supermercado", "Abastecimento", "Shopping", "Farmácia", "Lazer", "Viagem", "Presentes", "Outros Variáveis"]
                elif tipo == "Assinatura":
                    lista_cats = ["Streaming (Netflix/Spotify)", "Academia", "Clube de Assinatura", "Software/App", "Outras Assinaturas"]
                else: 
                    lista_cats = ["Salário", "Rendimento", "Pix Recebido", "Outras Entradas"]
                
                categoria = st.selectbox("Categoria", lista_cats)
                
                # Múltipla Escolha para "Para Quem" (Divisão Dinâmica)
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
                    # Converte os responsáveis para formato string separado por vírgula para salvar no Sheets
                    resp_salvar = ", ".join(responsavel)
                    
                    novo_registro = [
                        str(data), 
                        descricao, 
                        float(val_float),  # CORREÇÃO DEFINITIVA: Envia como float puro! Google Sheets decide a formatação local
                        categoria, 
                        tipo, 
                        resp_salvar, 
                        forma_pagto, 
                        parcelado, 
                        int(num_parcelas)
                    ]
                    try:
                        # Envia os dados usando gravação nativa (RAW) para não forçar string parsing local
                        sheet_conn.append_row(novo_registro, value_input_option='RAW')
                        st.success(f"Sucesso! '{descricao}' gravado na planilha com o valor de {formatar_brl(val_float)}.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")
                else:
                    st.error("Por favor, preencha a descrição e um valor decimal válido maior que zero (Exemplo: 8,99).")

# INTERPRETAÇÃO E PROJEÇÃO DOS DADOS
if sheet_conn is not None:
    try:
        # Lê os dados de volta do Sheets
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
                # Lê a data corrigindo strings
                dt_compra = datetime.strptime(str(row['Data']).split()[0], "%Y-%m-%d").date()
            except Exception as parse_error:
                try:
                    dt_compra = datetime.strptime(str(row['Data']).split()[0], "%d/%m/%Y").date()
                except:
                    continue
            
            # TRATAMENTO CRÍTICO DE LEITURA DE VALORES DA PLANILHA (Evita problemas de R$ 899,00)
            valor_raw = row.get('Valor', 0.0)
            valor_total = tratar_entrada_numerica(valor_raw)
                
            tipo_lanc = row.get('Tipo', 'Gasto Variável')
            total_parc = int(row['Parcelas_Totais']) if row.get('Parcelas_Totais') else 1
            
            # Divide o gasto proporcionalmente se houver múltiplos responsáveis (ex: "Jonathan, Bruna")
            resp_raw = str(row.get('Responsavel', 'Jonathan'))
            responsaveis_list = [r.strip() for r in resp_raw.split(",") if r.strip()]
            if not responsaveis_list:
                responsaveis_list = ["Jonathan"]
            
            divisao_pessoas = len(responsaveis_list)
            
            # Se for assinatura, o valor se repete mensalmente. Vamos projetar para os próximos 12 meses
            if tipo_lanc == "Assinatura":
                for m in range(12):
                    dt_recorrente = dt_compra + relativedelta(months=m)
                    mes_competencia = calcular_mes_competencia(dt_recorrente, row.get('Forma_Pagamento', 'Dinheiro'))
                    
                    # Cria um registro dividido proporcionalmente para cada pessoa do multiselect
                    for resp in responsaveis_list:
                        item_proj = row.to_dict()
                        item_proj['Mes_Fatura'] = mes_competencia
                        item_proj['Valor_Parcela'] = valor_total / divisao_pessoas
                        item_proj['Responsavel_Dividido'] = resp
                        item_proj['Parcela_Atual'] = "Recorrente"
                        lista_projetada.append(item_proj)
            else:
                # Compras normais e parceladas
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
            
            # Traduzir a exibição da coluna de datas para formato brasileiro (DD/MM/YYYY)
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
                    mes_atual_padrao = date.today().strftime("%Y-%m")
                    idx_padrao = meses_disponiveis.index(mes_atual_padrao) if mes_atual_padrao in meses_disponiveis else len(meses_disponiveis)-1
                    
                    mes_selecionado = st.selectbox("Selecione o Mês de Análise", meses_disponiveis, index=idx_padrao)
                    
                    df_mes = df_projetado[df_projetado['Mes_Fatura'] == mes_selecionado]
                    
                    # KPIs Principais do Mês Selecionado
                    tot_entradas = df_mes[df_mes['Tipo'] == 'Entrada']['Valor_Parcela'].sum()
                    tot_saidas = df_mes[df_mes['Tipo'] != 'Entrada']['Valor_Parcela'].sum()
                    
                    # Faturas Cartões (Regra Fechamento Dia 07 aplicada)
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
                            <div class="kpi-subtitle">Balanço: {formatar_brl(saldo_final)} sobrou</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with kpi_c3:
                        st.markdown(f"""
                        <div class="kpi-container kpi-nu">
                            <div class="kpi-title">💳 Fatura Nu Bank</div>
                            <div class="kpi-value">{formatar_brl(fatura_nu)}</div>
                            <div class="kpi-subtitle">Fecha no Dia 07</div>
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
                    
                    # SEÇÃO DE GRÁFICOS INTERATIVOS PLOTLY (Paleta Emerald/Indigo)
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
                            # Adiciona o total no centro do donut
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
                                color_continuous_scale=['#a78bfa', '#312e81'] # Tons de Indigo
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
                    
                    # GRÁFICO 3: EVOLUÇÃO MENSAL (LINHAS ENTRADAS VS DESPESAS)
                    st.markdown("**Histórico de Evolução Mensal (Entradas vs Despesas)**")
                    
                    # Puxa dados agrupados por mês de competência de faturas e tipos
                    df_evolucao = df_projetado.groupby(['Mes_Fatura', 'Tipo'])['Valor_Parcela'].sum().unstack(fill_value=0.0).reset_index()
                    
                    if not df_evolucao.empty:
                        # Garante que as colunas existam
                        if 'Entrada' not in df_evolucao.columns: df_evolucao['Entrada'] = 0.0
                        
                        # Soma todas as despesas que não sejam Entradas
                        colunas_despesas = [c for c in df_evolucao.columns if c != 'Mes_Fatura' and c != 'Entrada']
                        df_evolucao['Total_Despesas'] = df_evolucao[colunas_despesas].sum(axis=1)
                        
                        fig_linhas = go.Figure()
                        # Linha de Entradas
                        fig_linhas.add_trace(go.Scatter(
                            x=df_evolucao['Mes_Fatura'], 
                            y=df_evolucao['Entrada'],
                            name='🟢 Entradas (Receitas)',
                            line=dict(color='#10b981', width=3),
                            mode='lines+markers',
                            hovertemplate="Mês: %{x}<br>Receitas: R$ %{y:,.2f}<extra></extra>"
                        ))
                        # Linha de Despesas
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

                    # NOVO GRÁFICO 4: HEATMAP MENSAL DE CATEGORIAS (Filtra apenas Despesas)
                    st.markdown("**Matriz de Calor: Intensidade dos Gastos por Categoria ao longo dos Meses**")
                    df_heatmap_data = df_projetado[df_projetado['Tipo'] != 'Entrada'].groupby(['Mes_Fatura', 'Categoria'])['Valor_Parcela'].sum().reset_index()
                    
                    if not df_heatmap_data.empty:
                        pivot_heatmap = df_heatmap_data.pivot(index='Categoria', columns='Mes_Fatura', values='Valor_Parcela').fillna(0.0)
                        
                        # Paleta de cores gradiente elegante de Emerald para Indigo
                        escala_calor = [
                            [0.0, '#f8fafc'],  # Quase branco (cinza suave) para valores zerados
                            [0.2, '#d1fae5'],  # Verde claro
                            [0.5, '#34d399'],  # Emerald
                            [0.8, '#6366f1'],  # Indigo
                            [1.0, '#1e1b4b']   # Indigo Escuro / Deep Purple
                        ]
                        
                        fig_heatmap = go.Figure(data=go.Heatmap(
                            z=pivot_heatmap.values,
                            x=pivot_heatmap.columns,
                            y=pivot_heatmap.index,
                            colorscale=escala_calor,
                            hovertemplate="Mês: %{x}<br>Categoria: %{y}<br>Valor: R$ %{z:,.2f}<extra></extra>",
                            showscale=True
                        ))
                        
                        fig_heatmap.update_layout(
                            margin=dict(t=10, b=10, l=10, r=10),
                            height=350,
                            xaxis_title="Meses de Competência",
                            yaxis_title="Categorias de Despesa"
                        )
                        st.plotly_chart(fig_heatmap, use_container_width=True)
                    else:
                        st.info("Aguardando lançamentos para renderizar a matriz de calor.")
                    
                    st.write("---")
                    
                    st.markdown("**Extrato Detalhado do Mês de Competência**")
                    # Para a tabela, agrupamos de volta a visualização física das linhas originais (sem duplicar por responsável)
                    # mas exibindo a divisão de forma amigável
                    df_mes_tabela = df_mes.drop_duplicates(subset=['Data', 'Descricao', 'Valor', 'Categoria', 'Forma_Pagamento', 'Parcela_Atual'])
                    
                    df_mes_exibe = df_mes_tabela[['Data_Exibicao', 'Descricao', 'Valor', 'Parcela_Atual', 'Categoria', 'Responsavel', 'Forma_Pagamento', 'Tipo']].copy()
                    df_mes_exibe.rename(columns={'Data_Exibicao': 'Data', 'Valor': 'Valor Total (R$)'}, inplace=True)
                    
                    # Formata coluna valor da tabela para BRL
                    def formatar_valor_tabela(val):
                        # Converte string de vírgula para exibir de forma polida
                        f = tratar_entrada_numerica(val)
                        return formatar_brl(f)
                    df_mes_exibe['Valor Total (R$)'] = df_mes_exibe['Valor Total (R$)'].apply(formatar_valor_tabela)
                    
                    st.dataframe(df_mes_exibe, use_container_width=True)
                else:
                    st.info("Nenhum mês disponível para análise.")

            # TAB 3: CONTROLE DE PARCELAS ACUMULADAS E ASSINATURAS
            with tabs[2]:
                st.subheader("Dívidas Parceladas e Controle de Assinaturas")
                
                hoje_str = date.today().strftime("%Y-%m")
                
                df_futuro = df_projetado[(df_projetado['Mes_Fatura'] > hoje_str) & (df_projetado['Parcelado'] == 'Sim')]
                saldo_devedor_futuro = df_futuro['Valor_Parcela'].sum()
                
                st.warning(f"🏦 **Saldo Devedor Total Acumulado (Faturas Seguintes):** {formatar_brl(saldo_devedor_futuro)}")
                
                col_esquerda, col_direita = st.columns(2)
                
                with col_esquerda:
                    st.markdown("### 💳 Cronograma de Parcelamentos")
                    if not df_futuro.empty:
                        # Agrupa para pivotar sem dar erro de duplicatas
                        cronograma = df_futuro.groupby(['Mes_Fatura', 'Forma_Pagamento'])['Valor_Parcela'].sum().unstack().fillna(0)
                        
                        # Aplica formatação BRL amigável para as colunas do cronograma
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

            # TAB 4: EDITAR E CORRIGIR LANÇAMENTOS (CORREÇÃO DE VALORES VELHOS)
            with tabs[3]:
                st.subheader("Corrigir ou Apagar Lançamentos")
                st.markdown("Selecione um lançamento da lista para editar os valores ou apagá-los definitivamente da planilha.")
                
                # Para editar, mostramos as linhas físicas puras da planilha para não misturar as projeções de parcelas
                df_editor = dados_brutos.copy()
                
                if not df_editor.empty:
                    # Inverte a ordem para que os lançamentos mais recentes fiquem no topo da lista
                    df_editor = df_editor.iloc[::-1].reset_index(drop=True)
                    
                    # Cria um campo textual de identificação amigável para a lista de escolha
                    def gerar_linha_opcao(row):
                        data_formatada = formatar_data_br(row.get('Data', ''))
                        v_float = tratar_entrada_numerica(row.get('Valor', 0.0))
                        v_brl = formatar_brl(v_float)
                        return f"{data_formatada} | {row.get('Descricao', 'Sem Descrição')} | {v_brl} ({row.get('Forma_Pagamento', 'Pix')})"
                    
                    df_editor['Identificacao_Opcao'] = df_editor.apply(gerar_linha_opcao, axis=1)
                    
                    selecao = st.selectbox("Selecione qual item quer alterar ou excluir:", df_editor['Identificacao_Opcao'])
                    
                    if selecao:
                        # Recupera a linha selecionada
                        item_selecionado = df_editor[df_editor['Identificacao_Opcao'] == selecao].iloc[0]
                        
                        # Encontra o índice da linha física real na planilha gspread (considerando cabeçalho na linha 1)
                        # Como invertemos o DataFrame: index_gspread = len(dados_brutos) - index_reverso + 1
                        idx_dataframe = df_editor[df_editor['Identificacao_Opcao'] == selecao].index[0]
                        linha_planilha_real = (len(dados_brutos) - idx_dataframe) + 1  # Soma 1 pelo cabeçalho
                        
                        # Carrega os dados para o formulário de edição
                        try:
                            data_item = datetime.strptime(str(item_selecionado['Data']).split()[0], "%Y-%m-%d").date()
                        except:
                            try:
                                data_item = datetime.strptime(str(item_selecionado['Data']).split()[0], "%d/%m/%Y").date()
                            except:
                                data_item = date.today()
                        
                        # Formata o valor bruto antigo para o padrão textual BR para facilitar a digitação corretiva
                        valor_antigo_float = tratar_entrada_numerica(item_selecionado['Valor'])
                        valor_antigo_br = f"{valor_antigo_float:.2f}".replace(".", ",")
                        
                        # Tratamento de pessoas no multiselect
                        resp_item_raw = str(item_selecionado.get('Responsavel', 'Jonathan'))
                        resp_item_lista = [r.strip() for r in resp_item_raw.split(",") if r.strip()]
                        
                        st.markdown(f"📍 **Editando Linha {linha_planilha_real} da planilha:**")
                        
                        with st.form("form_edicao"):
                            e_col1, e_col2 = st.columns(2)
                            with e_col1:
                                e_data = st.date_input("Nova Data", data_item, format="DD/MM/YYYY")
                                e_desc = st.text_input("Nova Descrição", value=item_selecionado['Descricao'])
                                e_valor_texto = st.text_input("Corrigir Valor (R$)", value=valor_antigo_br, help="Digite o valor correto usando vírgula.")
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
                                    # Cria array atualizado
                                    resp_ed_salvar = ", ".join(e_resp)
                                    
                                    linha_atualizada = [
                                        str(e_data), 
                                        e_desc, 
                                        float(val_novo_float),  # Grava como float numérico para evitar bugs de vírgula/ponto
                                        e_cat, 
                                        e_tipo, 
                                        resp_ed_salvar, 
                                        e_forma, 
                                        e_parcelado, 
                                        int(e_tot_parc)
                                    ]
                                    
                                    try:
                                        # Substitui a linha antiga diretamente na planilha usando gravação em formato nativo RAW
                                        sheet_conn.update(f"A{linha_planilha_real}:I{linha_planilha_real}", [linha_atualizada], value_input_option='RAW')
                                        st.success("Lançamento atualizado com sucesso! Reiniciando visualização...")
                                        st.rerun()
                                    except Exception as err:
                                        st.error(f"Erro ao salvar modificação: {err}")
                        
                        # EXCLUSÃO (Zona de Perigo)
                        st.markdown("---")
                        st.markdown("### ⚠️ Zona de Perigo")
                        confirmar_exclusao = st.checkbox("Eu quero excluir permanentemente este lançamento da minha planilha.")
                        btn_excluir = st.button("❌ APAGAR DEFINITIVAMENTE", disabled=not confirmar_exclusao, type="secondary")
                        
                        if btn_excluir and confirmar_exclusao:
                            try:
                                # Deleta a linha exata da planilha
                                sheet_conn.delete_rows(linha_planilha_real)
                                st.success("Lançamento apagado da planilha!")
                                st.rerun()
                            except Exception as err:
                                st.error(f"Erro ao apagar linha: {err}")
                else:
                    st.info("A planilha está vazia.")
else:
    st.info("Aguardando os primeiros dados da planilha para renderizar os gráficos.")
