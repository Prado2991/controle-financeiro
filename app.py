import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import gspread
from google.oauth2.service_account import Credentials
import json
import unicodedata
import plotly.express as px
import plotly.graph_objects as go

# Configuração da página para visualização Mobile-First e Temática Elegante
st.set_page_config(
    page_title="Finanças Jonathan", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Transições e Animações com Bezier Cúbico de 500ms */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(15px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .animate-card {
        animation: fadeInUp 500ms cubic-bezier(0.25, 1, 0.5, 1) forwards;
    }

    /* Título principal com gradiente Indigo/Emerald */
    .gradient-title {
        background: linear-gradient(135deg, #6366f1 0%, #10b981 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0.1rem;
        animation: fadeInUp 600ms cubic-bezier(0.25, 1, 0.5, 1) forwards;
    }
    
    .subtitle-text {
        text-align: center;
        color: #6b7280;
        font-size: 1.1rem;
        margin-bottom: 2rem;
        font-weight: 500;
    }

    /* Personalização das Abas (Tabs) do Streamlit */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: transparent;
        border-bottom: 2px solid #e5e7eb;
        padding-bottom: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 10px 22px;
        border-radius: 12px 12px 0px 0px;
        background-color: #f3f4f6;
        color: #4b5563;
        font-weight: 600;
        transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
        border: none;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e5e7eb;
        color: #4f46e5;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2);
    }

    /* Grid e Cartões de KPI Estilizados */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 1.5rem;
        margin-bottom: 2.5rem;
    }
    
    .kpi-card {
        border-radius: 16px;
        padding: 1.6rem;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
        transition: all 400ms cubic-bezier(0.25, 1, 0.5, 1);
        display: flex;
        flex-direction: column;
        justify-content: center;
        border: 1px solid rgba(229, 231, 235, 0.5);
        position: relative;
        overflow: hidden;
    }
    
    .kpi-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 20px 25px -5px rgba(99, 102, 241, 0.15), 0 10px 10px -5px rgba(16, 185, 129, 0.1);
    }
    
    /* Cores dos gradientes dos cards */
    .gradient-entradas {
        background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%);
        color: #ffffff;
    }
    .gradient-despesas {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: #ffffff;
    }
    .gradient-nu {
        background: linear-gradient(135deg, #6d28d9 0%, #7c3aed 100%);
        color: #ffffff;
    }
    .gradient-bb {
        background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
        color: #ffffff;
    }
    
    .kpi-label {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        opacity: 0.9;
        margin-bottom: 0.6rem;
    }
    
    .kpi-value {
        font-size: 1.75rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    
    .kpi-sub {
        font-size: 0.8rem;
        margin-top: 0.6rem;
        opacity: 0.85;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

def formatar_brl(valor):
    """
    Formata um valor float ou string para o padrão de moeda oficial brasileiro (R$ 1.250,50).
    """
    try:
        val_float = float(valor)
        puro = f"{val_float:,.2f}"
        tabela_sub = puro.maketrans(",.", ".,")
        return f"R$ {puro.translate(tabela_sub)}"
    except Exception:
        return "R$ 0,00"

def converter_valor_para_float(texto):
    """
    Converte qualquer formato de texto monetário em float compatível com cálculos.
    """
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

def conectar_planilha():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if "google_credentials" not in st.secrets:
        st.error("""
        ❌ **Erro de Configuração:** O segredo `google_credentials` não foi encontrado no painel de Secrets do Streamlit.
        """)
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
            st.error(f"❌ **A Planilha não foi Compartilhada ou o ID está incorreto!** Compartilhe como Editor com: {email_servico}")
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

def normalizar_df(df):
    mapeamento_colunas = {
        'data': 'Data',
        'datadecompra': 'Data',
        'descricao': 'Descricao',
        'descrição': 'Descricao',
        'valor': 'Valor',
        'categoria': 'Categoria',
        'tipo': 'Tipo',
        'responsavel': 'Responsavel',
        'responsável': 'Responsavel',
        'forma_pagamento': 'Forma_Pagamento',
        'forma de pagamento': 'Forma_Pagamento',
        'parcelado': 'Parcelado',
        'parcelas_totais': 'Parcelas_Totais',
        'parcelas totais': 'Parcelas_Totais'
    }
    
    colunas_novas = {}
    for col in df.columns:
        col_limpa = "".join(c for c in unicodedata.normalize('NFD', str(col)) if unicodedata.category(c) != 'Mn')
        col_normalizada = col_limpa.strip().lower()
        if col_normalizada in mapeamento_colunas:
            colunas_novas[col] = mapeamento_colunas[col_normalizada]
        else:
            colunas_novas[col] = str(col).strip()
            
    df = df.rename(columns=colunas_novas)
    
    colunas_obrigatorias = ['Data', 'Descricao', 'Valor', 'Categoria', 'Tipo', 'Responsavel', 'Forma_Pagamento', 'Parcelado', 'Parcelas_Totais']
    for col in colunas_obrigatorias:
        if col not in df.columns:
            if col == 'Parcelas_Totais':
                df[col] = 1
            elif col == 'Parcelado':
                df[col] = 'Não'
            elif col == 'Valor':
                df[col] = 0.0
            else:
                df[col] = ''
    return df

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

def calcular_mes_competencia(data_compra, forma_pagamento):
    if "Cartão" not in forma_pagamento:
        return data_compra.strftime("%Y-%m")
    if data_compra.day > 7:
        data_fatura = data_compra + relativedelta(months=1)
    else:
        data_fatura = data_compra
    return data_fatura.strftime("%Y-%m")

# Título principal da aplicação com as animações e estilos definidos
st.markdown('<div class="gradient-title">💰 Controle Financeiro Familiar</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">Jonathan Prado</div>', unsafe_allow_html=True)

# Barra informativa do fechamento da fatura
hoje = date.today()
vencimento_limite = date(hoje.year, hoje.month, 7)
if hoje.day > 7:
    vencimento_limite = vencimento_limite + relativedelta(months=1)
dias_restantes = (vencimento_limite - hoje).days
st.info(f"⏳ **Fechamento de Faturas:** Faltam **{dias_restantes} dias** para o fechamento dos cartões (Próximo dia 07: {vencimento_limite.strftime('%d/%m/%Y')})")

tabs = st.tabs(["📲 Novo Lançamento", "📊 Dashboard & Resumos", "💳 Controle de Parcelas & Assinaturas", "✏️ Ajustar Lançamentos"])

with tabs[0]:
    st.subheader("Registrar Gasto ou Entrada")
    if sheet_conn is None:
        st.info("⚠️ **O formulário de envio está temporariamente desativado devido a problemas de conexão com a planilha.**")
    else:
        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                data = st.date_input("Data do Lançamento", date.today(), format="DD/MM/YYYY")
                descricao = st.text_input("Descrição", placeholder="Ex: Sorveteria Sávio, Roupas na Shein, Mercado Muffato")
                valor_texto = st.text_input("Valor (R$)", placeholder="Ex: 12,90 ou 150,00")
                tipo = st.selectbox("Tipo de Lançamento", ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"])
            
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
                responsavel = st.multiselect("Para Quem?", ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"], default=["Jonathan"])
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
                valor_convertido = converter_valor_para_float(valor_texto)
                if not responsavel:
                    st.error("Por favor, selecione pelo menos uma pessoa no campo 'Para Quem?'.")
                elif descricao and valor_convertido > 0:
                    valor_com_virgula = f"{valor_convertido:.2f}".replace('.', ',')
                    responsavel_str = ", ".join(responsavel)
                    
                    novo_registro = [
                        str(data), descricao, valor_com_virgula, categoria, tipo, 
                        responsavel_str, forma_pagto, parcelado, int(num_parcelas)
                    ]
                    try:
                        sheet_conn.append_row(novo_registro, value_input_option='USER_ENTERED')
                        st.success(f"Sucesso! '{descricao}' gravado com valor de {formatar_brl(valor_convertido)}.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")
                else:
                    st.error("Por favor, preencha a descrição e defina um valor válido maior que zero (use a vírgula para centavos).")

if sheet_conn is not None:
    try:
        raw_data = sheet_conn.get_all_records()
        dados_brutos = pd.DataFrame(raw_data)
        dados_brutos = normalizar_df(dados_brutos)
    except Exception as e:
        dados_brutos = pd.DataFrame()
        st.warning("Aguardando lançamentos na aba 'Lancamentos' para carregar os gráficos.")

    if not dados_brutos.empty:
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
            
            tipo_lanc = row.get('Tipo', 'Gasto Variável')
            total_parc = int(row['Parcelas_Totais']) if row.get('Parcelas_Totais') else 1
            valor_total = limpar_valor_monetario(row.get('Valor', 0.0))
            
            responsavel_campo = str(row.get('Responsavel', 'Jonathan'))
            responsaveis_lista = [r.strip() for r in responsavel_campo.replace('/', ',').split(',') if r.strip()]
            if not responsaveis_lista:
                responsaveis_lista = ["Jonathan"]
            
            num_responsaveis = len(responsaveis_lista)
            
            if tipo_lanc == "Assinatura":
                val_dividido = valor_total / num_responsaveis
                for m in range(12):
                    dt_recorrente = dt_compra + relativedelta(months=m)
                    mes_competencia = calcular_mes_competencia(dt_recorrente, row.get('Forma_Pagamento', 'Dinheiro'))
                    
                    for r_individual in responsaveis_lista:
                        item_proj = row.to_dict()
                        item_proj['Mes_Fatura'] = mes_competencia
                        item_proj['Valor_Parcela'] = val_dividido
                        item_proj['Responsavel'] = r_individual
                        item_proj['Parcela_Atual'] = "Recorrente"
                        lista_projetada.append(item_proj)
            else:
                val_parcela = valor_total / total_parc if row.get('Parcelado') == 'Sim' else valor_total
                val_dividido = val_parcela / num_responsaveis
                
                for p in range(total_parc):
                    dt_parcela = dt_compra + relativedelta(months=p)
                    mes_competencia = calcular_mes_competencia(dt_parcela, row.get('Forma_Pagamento', 'Dinheiro'))
                    
                    for r_individual in responsaveis_lista:
                        item_proj = row.to_dict()
                        item_proj['Mes_Fatura'] = mes_competencia
                        item_proj['Valor_Parcela'] = val_dividido
                        item_proj['Responsavel'] = r_individual
                        item_proj['Parcela_Atual'] = f"{p+1}/{total_parc}" if row.get('Parcelado') == 'Sim' else "1/1"
                        lista_projetada.append(item_proj)
                
        if lista_projetada:
            df_projetado = pd.DataFrame(lista_projetada)
            df_projetado['Valor_Parcela'] = df_projetado['Valor_Parcela'].astype(float)
            
            def formatar_data_br(data_str):
                try:
                    dt = datetime.strptime(str(data_str).split()[0], "%Y-%m-%d")
                    return dt.strftime("%d/%m/%Y")
                except:
                    return data_str
            
            df_projetado['Data_Exibicao'] = df_projetado['Data'].apply(formatar_data_br)
            
            with tabs[1]:
                st.subheader("Resumo Mensal e Faturas")
                
                meses_disponiveis = sorted(df_projetado['Mes_Fatura'].unique())
                if meses_disponiveis:
                    mes_atual_padrao = date.today().strftime("%Y-%m")
                    idx_padrao = meses_disponiveis.index(mes_atual_padrao) if mes_atual_padrao in meses_disponiveis else len(meses_disponiveis)-1
                    
                    mes_selecionado = st.selectbox("Selecione o Mês de Análise", meses_disponiveis, index=idx_padrao)
                    df_mes = df_projetado[df_projetado['Mes_Fatura'] == mes_selecionado]
                    
                    # KPIs em memória
                    tot_entradas = df_mes[df_mes['Tipo'] == 'Entrada']['Valor_Parcela'].sum()
                    tot_saidas = df_mes[df_mes['Tipo'] != 'Entrada']['Valor_Parcela'].sum()
                    fatura_nu = df_mes[df_mes['Forma_Pagamento'] == 'Cartão Nu']['Valor_Parcela'].sum()
                    fatura_bb = df_mes[df_mes['Forma_Pagamento'] == 'Cartão BB']['Valor_Parcela'].sum()
                    saldo_final = tot_entradas - tot_saidas
                    
                    # Renderizando os KPI Cards customizados com gradientes e sombras físicas no HTML
                    st.markdown(f"""
                    <div class="kpi-grid">
                        <div class="kpi-card gradient-entradas animate-card">
                            <div class="kpi-label">🟢 Total Entradas</div>
                            <div class="kpi-value">{formatar_brl(tot_entradas)}</div>
                            <div class="kpi-sub">Receitas consolidadas</div>
                        </div>
                        <div class="kpi-card gradient-despesas animate-card" style="animation-delay: 100ms;">
                            <div class="kpi-label">🔴 Total Despesas</div>
                            <div class="kpi-value">{formatar_brl(tot_saidas)}</div>
                            <div class="kpi-sub">Sobrou: {formatar_brl(saldo_final)}</div>
                        </div>
                        <div class="kpi-card gradient-nu animate-card" style="animation-delay: 200ms;">
                            <div class="kpi-label">💳 Fatura Nu Bank</div>
                            <div class="kpi-value">{formatar_brl(fatura_nu)}</div>
                            <div class="kpi-sub">Vencimento estimado</div>
                        </div>
                        <div class="kpi-card gradient-bb animate-card" style="animation-delay: 300ms;">
                            <div class="kpi-label">💳 Fatura BB</div>
                            <div class="kpi-value">{formatar_brl(fatura_bb)}</div>
                            <div class="kpi-sub">Vencimento estimado</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown("### 📊 Gráficos de Análise e Distribuição")
                    
                    # Coluna de gráficos principais
                    col_g1, col_g2 = st.columns(2)
                    
                    # Gráfico Donut de Despesas por Categoria (Com Total no Centro)
                    with col_g1:
                        st.markdown("<h5 style='text-align: center; color: #4b5563; margin-bottom: 1rem;'>Despesas por Categoria</h5>", unsafe_allow_html=True)
                        df_cat = df_mes[df_mes['Tipo'] != 'Entrada'].groupby('Categoria')['Valor_Parcela'].sum().reset_index()
                        
                        if not df_cat.empty:
                            fig_donut = go.Figure(data=[go.Pie(
                                labels=df_cat['Categoria'], 
                                values=df_cat['Valor_Parcela'], 
                                hole=0.6,
                                marker=dict(colors=['#4f46e5', '#10b981', '#6366f1', '#34d399', '#4338ca', '#059669', '#312e81', '#a7f3d0']),
                                hovertemplate="<b>%{label}</b><br>Gasto: R$ %{value:,.2f}<br>Representação: %{percent}<extra></extra>"
                            )])
                            
                            fig_donut.add_annotation(
                                text=f"Total Gastos<br><span style='font-size: 1.1rem; font-weight: 800; color: #1e293b;'>{formatar_brl(tot_saidas)}</span>",
                                showarrow=False,
                                font=dict(size=12, color="#4b5563"),
                                align="center"
                            )
                            
                            fig_donut.update_layout(
                                margin=dict(t=10, b=10, l=10, r=10),
                                height=320,
                                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)'
                            )
                            st.plotly_chart(fig_donut, use_container_width=True)
                        else:
                            st.info("Sem despesas para exibir o donut neste mês.")
                            
                    # Gráfico de Barras Horizontais por Destinatário (BRL nos rótulos)
                    with col_g2:
                        st.markdown("<h5 style='text-align: center; color: #4b5563; margin-bottom: 1rem;'>Distribuição por Destinatário</h5>", unsafe_allow_html=True)
                        df_resp = df_mes[df_mes['Tipo'] != 'Entrada'].groupby('Responsavel')['Valor_Parcela'].sum().reset_index()
                        
                        if not df_resp.empty:
                            df_resp = df_resp.sort_values(by='Valor_Parcela', ascending=True)
                            
                            fig_bar = go.Figure(go.Bar(
                                x=df_resp['Valor_Parcela'],
                                y=df_resp['Responsavel'],
                                orientation='h',
                                marker=dict(
                                    color=df_resp['Valor_Parcela'],
                                    colorscale=[[0, '#6366f1'], [1, '#10b981']],
                                    line=dict(color='rgba(255,255,255,0.5)', width=1)
                                ),
                                text=[formatar_brl(v) for v in df_resp['Valor_Parcela']],
                                textposition='auto',
                                hovertemplate="<b>%{y}</b><br>Valor Total: R$ %{x:,.2f}<extra></extra>"
                            ))
                            
                            fig_bar.update_layout(
                                margin=dict(t=10, b=10, l=10, r=10),
                                height=320,
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                xaxis=dict(showgrid=True, gridcolor='rgba(229,231,235,0.5)', showticklabels=False),
                                yaxis=dict(gridcolor='rgba(0,0,0,0)')
                            )
                            st.plotly_chart(fig_bar, use_container_width=True)
                        else:
                            st.info("Sem dados de destinatários neste mês.")
                    
                    st.write("---")
                    
                    # Gráfico de Evolução Mensal (Linhas: Entradas vs Despesas)
                    st.markdown("<h5 style='color: #4b5563; margin-bottom: 1.5rem;'>📈 Evolução Mensal (Entradas vs Despesas)</h5>", unsafe_allow_html=True)
                    df_evolucao = df_projetado.groupby(['Mes_Fatura', 'Tipo'])['Valor_Parcela'].sum().unstack().fillna(0).reset_index()
                    
                    # Garante a coluna Entrada caso não exista
                    if 'Entrada' not in df_evolucao.columns:
                        df_evolucao['Entrada'] = 0.0
                    
                    # Soma todas as colunas que NÃO são 'Entrada' nem 'Mes_Fatura' para termos as saídas consolidadas
                    cols_despesa = [c for c in df_evolucao.columns if c not in ['Mes_Fatura', 'Entrada']]
                    df_evolucao['Saidas'] = df_evolucao[cols_despesa].sum(axis=1)
                    
                    if not df_evolucao.empty:
                        fig_line = go.Figure()
                        
                        fig_line.add_trace(go.Scatter(
                            x=df_evolucao['Mes_Fatura'],
                            y=df_evolucao['Entrada'],
                            name="Entradas (Receitas)",
                            line=dict(color='#4f46e5', width=3, shape='spline'),
                            mode='lines+markers',
                            marker=dict(size=8, color='#4f46e5'),
                            hovertemplate="Mês: %{x}<br>Entrada: R$ %{y:,.2f}<extra></extra>"
                        ))
                        
                        fig_line.add_trace(go.Scatter(
                            x=df_evolucao['Mes_Fatura'],
                            y=df_evolucao['Saidas'],
                            name="Saídas (Despesas)",
                            line=dict(color='#10b981', width=3, shape='spline'),
                            mode='lines+markers',
                            marker=dict(size=8, color='#10b981'),
                            hovertemplate="Mês: %{x}<br>Despesa: R$ %{y:,.2f}<extra></extra>"
                        ))
                        
                        fig_line.update_layout(
                            margin=dict(t=10, b=10, l=10, r=10),
                            height=300,
                            legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            xaxis=dict(showgrid=True, gridcolor='rgba(229,231,235,0.5)'),
                            yaxis=dict(showgrid=True, gridcolor='rgba(229,231,235,0.5)', tickprefix="R$ ")
                        )
                        st.plotly_chart(fig_line, use_container_width=True)
                    
                    st.write("---")
                    
                    # Heatmap de Categorias vs Meses (Matriz de calor de custos)
                    st.markdown("<h5 style='color: #4b5563; margin-bottom: 1.5rem;'>🔥 Calor de Custos por Categoria</h5>", unsafe_allow_html=True)
                    df_g_varias = df_projetado[df_projetado['Tipo'] != 'Entrada']
                    
                    if not df_g_varias.empty:
                        pivot_heatmap = df_g_varias.pivot_table(
                            index='Categoria', 
                            columns='Mes_Fatura', 
                            values='Valor_Parcela', 
                            aggfunc='sum'
                        ).fillna(0)
                        
                        fig_heat = go.Figure(data=go.Heatmap(
                            z=pivot_heatmap.values,
                            x=pivot_heatmap.columns,
                            y=pivot_heatmap.index,
                            colorscale=[[0, '#f9fafb'], [0.5, '#a5b4fc'], [1, '#059669']],
                            hovertemplate="Mês: %{x}<br>Categoria: %{y}<br>Consumo: R$ %{z:,.2f}<extra></extra>",
                            showscale=True
                        ))
                        
                        fig_heat.update_layout(
                            margin=dict(t=10, b=10, l=10, r=10),
                            height=340,
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(fig_heat, use_container_width=True)
                        
                    st.write("---")
                    
                    st.markdown("**Extrato Detalhado do Mês de Competência**")
                    df_mes_exibe = df_mes[['Data_Exibicao', 'Descricao', 'Valor_Parcela', 'Parcela_Atual', 'Categoria', 'Responsavel', 'Forma_Pagamento', 'Tipo']].copy()
                    df_mes_exibe.rename(columns={'Data_Exibicao': 'Data', 'Valor_Parcela': 'Valor da Parcela (R$)'}, inplace=True)
                    df_mes_exibe['Valor da Parcela (R$)'] = df_mes_exibe['Valor da Parcela (R$)'].apply(formatar_brl)
                    st.dataframe(df_mes_exibe, use_container_width=True)
                else:
                    st.info("Nenhum mês disponível para análise.")

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
                        cronograma = df_futuro.groupby(['Mes_Fatura', 'Forma_Pagamento'])['Valor_Parcela'].sum().unstack().fillna(0)
                        cronograma_brl = cronograma.applymap(formatar_brl)
                        st.dataframe(cronograma_brl, use_container_width=True)
                        
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
                        df_assinaturas_exibe = df_assinaturas[['Descricao', 'Valor_Parcela', 'Categoria', 'Forma_Pagamento']].copy()
                        df_assinaturas_exibe['Valor_Parcela'] = df_assinaturas_exibe['Valor_Parcela'].apply(formatar_brl)
                        st.dataframe(df_assinaturas_exibe, use_container_width=True)
                    else:
                        st.info("Nenhuma assinatura cadastrada.")

            with tabs[3]:
                st.subheader("✏️ Alterar ou Excluir Lançamentos")
                st.markdown("Se digitou alguma informação incorreta ou deseja excluir um registro da planilha, ajuste os campos abaixo:")
                
                lista_ajustavel = []
                for idx, row in dados_brutos.iterrows():
                    num_linha = idx + 2
                    desc = row.get('Descricao', 'Sem Descrição')
                    val = limpar_valor_monetario(row.get('Valor', 0.0))
                    dt = row.get('Data', '')
                    
                    rotulo = f"Linha {num_linha} | {dt} | {desc} - {formatar_brl(val)}"
                    lista_ajustavel.append({"linha": num_linha, "label": rotulo, "original": row.to_dict()})
                
                lista_ajustavel.reverse()
                
                if lista_ajustavel:
                    registro_selecionado = st.selectbox(
                        "Selecione o Lançamento para Corrigir:",
                        options=lista_ajustavel,
                        format_func=lambda x: x["label"]
                    )
                    
                    if registro_selecionado:
                        orig = registro_selecionado["original"]
                        linha_planilha = registro_selecionado["linha"]
                        
                        st.write("---")
                        with st.form("form_edicao_registro"):
                            st.markdown(f"**Editando dados da Linha {linha_planilha}**")
                            col_ed1, col_ed2 = st.columns(2)
                            
                            with col_ed1:
                                try:
                                    dt_orig = datetime.strptime(str(orig.get('Data')).split()[0], "%Y-%m-%d").date()
                                except:
                                    try:
                                        dt_orig = datetime.strptime(str(orig.get('Data')).split()[0], "%d/%m/%Y").date()
                                    except:
                                        dt_orig = date.today()
                                
                                ed_data = st.date_input("Data do Lançamento", dt_orig, format="DD/MM/YYYY")
                                ed_descricao = st.text_input("Descrição", value=orig.get('Descricao', ''))
                                
                                valor_original_texto = f"{limpar_valor_monetario(orig.get('Valor', 0.0)):.2f}".replace('.', ',')
                                ed_valor_texto = st.text_input("Valor (R$)", value=valor_original_texto, placeholder="Ex: 12,90")
                                
                                tipo_orig = orig.get('Tipo', 'Gasto Variável')
                                lista_tipos_sup = ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"]
                                idx_tipo_orig = lista_tipos_sup.index(tipo_orig) if tipo_orig in lista_tipos_sup else 0
                                ed_tipo = st.selectbox("Tipo de Lançamento", lista_tipos_sup, index=idx_tipo_orig)
                                
                            with col_ed2:
                                if ed_tipo == "Gasto Fixo":
                                    lista_cats_ed = ["Luz", "Água", "Internet", "Telefone", "Condomínio", "Aluguel", "Plano de Saúde", "Outros Fixos"]
                                elif ed_tipo == "Gasto Variável":
                                    lista_cats_ed = ["Refeição", "Supermercado", "Abastecimento", "Shopping", "Farmácia", "Lazer", "Viagem", "Presentes", "Outros Variáveis"]
                                elif ed_tipo == "Assinatura":
                                    lista_cats_ed = ["Streaming (Netflix/Spotify)", "Academia", "Clube de Assinatura", "Software/App", "Outras Assinaturas"]
                                else:
                                    lista_cats_ed = ["Salário", "Rendimento", "Pix Recebido", "Outras Entradas"]
                                
                                cat_orig = orig.get('Categoria', '')
                                idx_cat_ed = lista_cats_ed.index(cat_orig) if cat_orig in lista_cats_ed else 0
                                ed_categoria = st.selectbox("Categoria", lista_cats_ed, index=idx_cat_ed)
                                
                                resp_orig_str = str(orig.get('Responsavel', 'Jonathan'))
                                resp_orig_lista = [r.strip() for r in resp_orig_str.replace('/', ',').split(',') if r.strip()]
                                if not resp_orig_lista:
                                    resp_orig_lista = ["Jonathan"]
                                
                                ed_responsavel = st.multiselect("Para Quem?", ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"], default=resp_orig_lista)
                                
                                pgto_orig = orig.get('Forma_Pagamento', 'Cartão Nu')
                                lista_pgto_ed = ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"]
                                idx_pgto_ed = lista_pgto_ed.index(pgto_orig) if pgto_orig in lista_pgto_ed else 0
                                ed_forma_pagto = st.selectbox("Forma de Pagamento", lista_pgto_ed, index=idx_pgto_ed)
                                
                                pode_parcelar_ed = ed_tipo in ["Gasto Variável", "Gasto Fixo"]
                                if pode_parcelar_ed:
                                    parc_orig = orig.get('Parcelado', 'Não')
                                    idx_parc_ed = 0 if parc_orig == "Não" else 1
                                    ed_parcelado = st.radio("Compra Parcelada?", ["Não", "Sim"], index=idx_parc_ed, horizontal=True)
                                    
                                    try:
                                        tot_parc_orig = int(orig.get('Parcelas_Totais', 1))
                                    except:
                                        tot_parc_orig = 1
                                    
                                    if ed_parcelado == "Sim":
                                        ed_num_parcelas = st.number_input("Quantidade de Parcelas", min_value=2, max_value=48, value=max(2, tot_parc_orig), step=1)
                                    else:
                                        ed_num_parcelas = 1
                                else:
                                    ed_parcelado = "Não"
                                    ed_num_parcelas = 1
                                    
                            botao_atualizar = st.form_submit_button("💾 Salvar Alterações")
                            
                            if botao_atualizar:
                                ed_valor_float = converter_valor_para_float(ed_valor_texto)
                                if not ed_responsavel:
                                    st.error("Selecione ao menos um responsável no campo 'Para Quem?'.")
                                elif ed_descricao and ed_valor_float > 0:
                                    ed_valor_com_virgula = f"{ed_valor_float:.2f}".replace('.', ',')
                                    ed_responsavel_str = ", ".join(ed_responsavel)
                                    
                                    valores_atualizados = [
                                        str(ed_data), ed_descricao, ed_valor_com_virgula, ed_categoria, ed_tipo,
                                        ed_responsavel_str, ed_forma_pagto, ed_parcelado, int(ed_num_parcelas)
                                    ]
                                    try:
                                        sheet_conn.update(f"A{linha_planilha}:I{linha_planilha}", [valores_atualizados], value_input_option='USER_ENTERED')
                                        st.success(f"Excelente! Linha {linha_planilha} atualizada com sucesso.")
                                        st.balloons()
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Erro ao atualizar planilha: {ex}")
                                else:
                                    st.error("Preencha todos os campos obrigatórios.")
                        
                        st.markdown("---")
                        st.markdown("### ⚠️ Zona de Perigo (Excluir Permanentemente)")
                        st.write("Marque a caixa de verificação abaixo caso queira remover este registro do seu banco de dados:")
                        confirma_exclusao = st.checkbox(f"Confirmo que desejo apagar para sempre o registro da Linha {linha_planilha}.")
                        
                        if st.button("🗑️ Excluir Lançamento", type="primary", disabled=not confirma_exclusao):
                            try:
                                sheet_conn.delete_rows(linha_planilha)
                                st.success(f"O registro da Linha {linha_planilha} foi excluído da planilha.")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Erro ao excluir o registro: {ex}")
                else:
                    st.info("Nenhum lançamento foi encontrado para editar.")
        else:
            st.info("Sem dados projetados disponíveis.")
    else:
        st.info("Sua planilha na aba 'Lancamentos' está vazia. Faça o primeiro lançamento na aba 'Novo Lançamento' acima para começar!")
