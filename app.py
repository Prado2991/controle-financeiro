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

# Configuração da página do Streamlit
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

    /* Título Sólido Premium para Celulares */
    .main-title {
        color: #1e1b4b; /* Azul Escuro Premium Sólido */
        font-size: 32px;
        font-weight: 800;
        margin-bottom: 5px;
    }

    /* Estilo para os Cards de Gráficos no Dashboard */
    .dashboard-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
        border: 1px solid #f1f5f9;
        margin-bottom: 20px;
    }

    .dashboard-card-title {
        color: #0f172a;
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Traduzir e formatar a exibição da data para o formato brasileiro de forma segura e global
def formatar_data_br(data_str):
    if not data_str:
        return ""
    try:
        # Tenta formato ISO (AAAA-MM-DD)
        dt = datetime.strptime(str(data_str).split()[0], "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except:
        try:
            # Tenta formato brasileiro já gravado (DD/MM/YYYY)
            dt = datetime.strptime(str(data_str).split()[0], "%d/%m/%Y")
            return dt.strftime("%d/%m/%Y")
        except:
            return str(data_str)

# FUNÇÃO DE CONVERSÃO BRASILEIRA DE MOEDA
def formatar_brl(valor):
    try:
        val = float(valor)
        return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"

# TRATEMENTO NUMÉRICO DE ENTRADA RESILIENTE
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

# Categorias base do sistema (estabilizadas por tipo)
base_cats = {
    "Gasto Fixo": ["Luz", "Água", "Gás", "Diarista", "Psicóloga", "Pagamento do cartão", "Internet", "Telefone", "Condomínio", "Aluguel", "Plano de Saúde", "Outros Fixos"],
    "Gasto Variável": ["Refeição", "Supermercado", "Abastecimento", "Shopping", "Farmácia", "Lazer", "Viagem", "Presentes", "Barbearia", "Lotérica", "Outros Variáveis"],
    "Assinatura": ["Streaming (Netflix/Spotify)", "Academia", "Clube de Assinatura", "Software/App", "Outras Assinaturas"],
    "Entrada": ["Salário", "Rendimento", "Pix Recebido", "Diárias", "Outras Entradas"]
}

# Função de carregamento dinâmico de categorias com detecção automática de novos itens da planilha
def obter_categorias_por_tipo(tipo, df_bruto=None):
    cats = base_cats.get(tipo, []).copy()
    if df_bruto is not None and not df_bruto.empty:
        col_categoria = None
        col_tipo = None
        # Identificação resiliente de cabeçalho (independente de acentos e caixa)
        for col in df_bruto.columns:
            col_limpa = str(col).lower().replace("_", "").replace(" ", "").strip()
            if col_limpa == 'categoria':
                col_categoria = col
            elif col_limpa == 'tipo':
                col_tipo = col
                
        if col_categoria and col_tipo:
            unique_cats = df_bruto[df_bruto[col_tipo] == tipo][col_categoria].dropna().unique()
            for c in unique_cats:
                c_str = str(c).strip()
                if c_str and c_str not in cats and c_str != "Outra (Criar Nova...)":
                    cats.append(c_str)
                    
    # Garante que a opção de criar nova categoria personalizada sempre esteja em último no seletor
    if "Outra (Criar Nova...)" in cats:
        cats.remove("Outra (Criar Nova...)")
    cats.append("Outra (Criar Nova...)")
    return cats

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

# LÓGICA DE COBRANÇA DA FATURA (ALINHADO COM FLUXO REAL DE FECHAMENTO JONATHAN)
# Ciclo de faturamento: O cartão fecha no dia 06.
# Portanto, todos os gastos de 07/06 até 06/07 pertencem ao Mês de Consumo 06 (Junho).
# Entradas (Salários, Diárias, Pix): Sempre no mês calendário real do recebimento, sem recuar.
def calcular_mes_competencia(data_compra, forma_pagamento, tipo_lancamento):
    if tipo_lancamento == "Entrada" or "Cartão" not in str(forma_pagamento):
        return data_compra.strftime("%Y-%m")
    
    dia = data_compra.day
    if dia < 7:
        # Se for entre o dia 1 e dia 6, pertence ao faturamento do mês anterior
        data_fatura = data_compra - relativedelta(months=1)
    else:
        # Se for dia 7 em diante, pertence ao faturamento do mês atual
        data_fatura = data_compra
        
    return data_fatura.strftime("%Y-%m")

# EXTRATOR ROBUSTO DE COLUNAS DA PLANILHA (PREVINE INCONSISTÊNCIAS NO GOOGLE SHEETS)
def obter_coluna_safe(row, *nomes_coluna, fallback=""):
    row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
    for nome in nomes_coluna:
        if nome in row_dict:
            return row_dict[nome]
        nome_limpo = nome.lower().replace("_", "").replace(" ", "").strip()
        for k, v in row_dict.items():
            k_limpo = str(k).lower().replace("_", "").replace(" ", "").strip()
            if k_limpo == nome_limpo:
                return v
    return fallback

# Carregamento prévio de dados brutos para alimentar listagens dinâmicas
if sheet_conn is not None:
    try:
        dados_brutos = pd.DataFrame(sheet_conn.get_all_records())
    except Exception as e:
        dados_brutos = pd.DataFrame()
else:
    dados_brutos = pd.DataFrame()

st.markdown('<div class="main-title">💰 Controle Financeiro Familiar</div>', unsafe_allow_html=True)
st.markdown("### Jonathan Prado")

# Lógica de contagem de fechamento baseada na data de SP
vencimento_limite = date(hoje_brasil.year, hoje_brasil.month, 7)
if hoje_brasil.day >= 7:
    vencimento_limite = vencimento_limite + relativedelta(months=1)
dias_restantes = (vencimento_limite - hoje_brasil).days

st.info(f"⏳ **Fechamento de Faturas:** Faltam **{dias_restantes} dias** para o fechamento dos cartões (Fechamento em 06/{vencimento_limite.strftime('%m/%Y')} às 23:59)")

tabs = st.tabs(["📲 Novo Lançamento", "📊 Dashboard & Resumos", "💳 Controle de Parcelas & Assinaturas", "✏️ Ajustar Lançamentos"])

with tabs[0]:
    st.subheader("Registrar Gasto ou Entrada")
    if sheet_conn is None:
        st.info("⚠️ **O formulário de envio está temporariamente desativado devido a problemas de conexão.**")
    else:
        # Escolha do Tipo de Lançamento fora do formulário para reatividade instantânea das categorias
        tipo = st.selectbox("Tipo de Lançamento", ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"])
        
        # Pega a lista dinâmica de categorias para o tipo selecionado (mesclando com itens do banco de dados)
        lista_cats = obter_categorias_por_tipo(tipo, dados_brutos)
        
        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                data = st.date_input("Data do Lançamento", hoje_brasil, format="DD/MM/YYYY")
                descricao = st.text_input("Descrição", placeholder="Ex: Mercado Muffato, Barbearia, Diária Consultório")
                valor_texto = st.text_input("Valor (R$)", value="0,00", help="Use vírgula para centavos. Exemplo: 8,99 ou 150,50")
            
            with col2:
                categoria_sel = st.selectbox("Categoria", lista_cats)
                
                # Exibe input de categoria customizada se a opção for criar nova
                nova_categoria = ""
                if categoria_sel == "Outra (Criar Nova...)":
                    nova_categoria = st.text_input("Nome da nova Categoria:", placeholder="Digite o nome aqui (Ex: IPVA, Dentista)")
                
                responsavel = st.multiselect(
                    "Para Quem?", 
                    ["Jonathan", "Casa", "Gatos"],
                    default=["Jonathan"]
                )
                
                # UX Guardrail: Entradas de dinheiro não devem oferecer cartões como forma de recebimento!
                if tipo == "Entrada":
                    forma_pagto = st.selectbox("Forma de Recebimento", ["Pix", "Dinheiro", "Boleto", "Débito em conta"])
                else:
                    forma_pagto = st.selectbox("Forma de Pagamento", ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"])
                
                # Seletor de parcelamento direto e robusto
                pode_parcelar = tipo in ["Gasto Variável", "Gasto Fixo"]
                if pode_parcelar:
                    num_parcelas = st.number_input(
                        "Quantidade de Parcelas (Mantenha 1 se for à vista)", 
                        min_value=1, 
                        max_value=48, 
                        value=1, 
                        step=1,
                        help="Se for parcelado informe a quantidade de meses. Para compras normais à vista, deixe em 1."
                    )
                    parcelado = "Sim" if num_parcelas > 1 else "Não"
                else:
                    parcelado = "Não"
                    num_parcelas = 1
                    
            botao_salvar = st.form_submit_button("🚀 Gravar na Planilha")
            
            if botao_salvar:
                val_float = tratar_entrada_numerica(valor_texto)
                
                # Resolve categoria personalizada caso selecionado
                categoria_gravar = categoria_sel
                if categoria_sel == "Outra (Criar Nova...)":
                    if not nova_categoria.strip():
                        st.error("❌ **Erro:** Digite um nome para a nova categoria personalizada!")
                        st.stop()
                    else:
                        categoria_gravar = nova_categoria.strip().title()
                
                if not responsavel:
                    st.error("Por favor, selecione pelo menos um responsável pelo lançamento.")
                elif descricao and val_float > 0:
                    resp_salvar = ", ".join(responsavel)
                    valor_gravar_sheets = f"{val_float:.2f}".replace(".", ",")
                    
                    novo_registro = [
                        str(data), descricao, valor_gravar_sheets, categoria_gravar, tipo, 
                        resp_salvar, forma_pagto, parcelado, int(num_parcelas)
                    ]
                    try:
                        sheet_conn.append_row(novo_registro, value_input_option='USER_ENTERED')
                        st.success(f"Sucesso! '{descricao}' gravado com o valor de {formatar_brl(val_float)}.")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")
                else:
                    st.error("Por favor, preencha a descrição e um valor decimal válido maior que zero (Exemplo: 8,99).")

if sheet_conn is not None:
    if not dados_brutos.empty:
        lista_projetada = []
        for index, row in dados_brutos.iterrows():
            data_raw = obter_coluna_safe(row, 'Data', 'data', fallback='')
            if not data_raw:
                continue
                
            try:
                dt_compra = datetime.strptime(str(data_raw).split()[0], "%Y-%m-%d").date()
            except:
                try:
                    dt_compra = datetime.strptime(str(data_raw).split()[0], "%d/%m/%Y").date()
                except:
                    continue
            
            valor_raw = obter_coluna_safe(row, 'Valor', 'valor', fallback=0.0)
            valor_total = tratar_entrada_numerica(valor_raw) if isinstance(valor_raw, str) else float(valor_raw)
            
            tipo_lanc = obter_coluna_safe(row, 'Tipo', 'tipo_lancamento', fallback='Gasto Variável')
            forma_pagto = obter_coluna_safe(row, 'Forma_Pagamento', 'forma_pagto', 'Forma de Pagamento', fallback='Dinheiro')
            parcelado_status = obter_coluna_safe(row, 'Parcelado', 'parcelado', fallback='Não')
            
            total_parc_raw = obter_coluna_safe(row, 'Parcelas_Totais', 'parcelas_totais', 'Parcelas', fallback=1)
            total_parc = int(total_parc_raw) if total_parc_raw and pd.notna(total_parc_raw) else 1
            
            # Divisão de responsáveis
            resp_raw = str(obter_coluna_safe(row, 'Responsavel', 'responsável', fallback='Jonathan'))
            responsaveis_list = [r.strip() for r in resp_raw.split(",") if r.strip()]
            if not responsaveis_list:
                responsaveis_list = ["Jonathan"]
            
            divisao_pessoas = len(responsaveis_list)
            
            # Projeção de assinaturas para os próximos 12 meses
            if tipo_lanc == "Assinatura":
                for m in range(12):
                    dt_recorrente = dt_compra + relativedelta(months=m)
                    mes_competencia = calcular_mes_competencia(dt_recorrente, forma_pagto, tipo_lanc)
                    
                    for resp in responsaveis_list:
                        item_proj = row.to_dict()
                        item_proj['Mes_Fatura'] = mes_competencia
                        item_proj['Valor_Parcela'] = valor_total / divisao_pessoas
                        item_proj['Responsavel_Dividido'] = resp
                        item_proj['Parcela_Atual'] = "Recorrente"
                        item_proj['Data_Exibicao'] = formatar_data_br(dt_compra)
                        lista_projetada.append(item_proj)
            else:
                # Compras normais, à vista ou parceladas
                is_parcelado = str(parcelado_status).strip() == 'Sim' or total_parc > 1
                val_parcela = valor_total / total_parc if is_parcelado and total_parc > 0 else valor_total
                for p in range(total_parc):
                    dt_parcela = dt_compra + relativedelta(months=p)
                    mes_competencia = calcular_mes_competencia(dt_parcela, forma_pagto, tipo_lanc)
                    
                    for resp in responsaveis_list:
                        item_proj = row.to_dict()
                        item_proj['Mes_Fatura'] = mes_competencia
                        item_proj['Valor_Parcela'] = val_parcela / divisao_pessoas
                        item_proj['Responsavel_Dividido'] = resp
                        item_proj['Parcela_Atual'] = f"{p+1}/{total_parc}" if is_parcelado else "1/1"
                        item_proj['Data_Exibicao'] = formatar_data_br(dt_compra)
                        lista_projetada.append(item_proj)
                
        if lista_projetada:
            df_projetado = pd.DataFrame(lista_projetada)
            df_projetado['Valor_Parcela'] = df_projetado['Valor_Parcela'].astype(float)
            df_projetado['Data_Exibicao'] = df_projetado['Data'].apply(formatar_data_br)
            
            with tabs[1]:
                st.subheader("Resumo Mensal e Faturas")
                
                meses_disponiveis = sorted(df_projetado['Mes_Fatura'].unique())
                if meses_disponiveis:
                    mes_atual_padrao = hoje_brasil.strftime("%Y-%m")
                    idx_padrao = meses_disponiveis.index(mes_atual_padrao) if mes_atual_padrao in meses_disponiveis else len(meses_disponiveis)-1
                    
                    mes_selecionado = st.selectbox("Selecione o Mês de Análise", meses_disponiveis, index=idx_padrao)
                    
                    df_mes = df_projetado[df_projetado['Mes_Fatura'] == mes_selecionado]
                    
                    # KPIs principais do mês selecionado
                    tot_entradas = df_mes[df_mes['Tipo'] == 'Entrada']['Valor_Parcela'].sum()
                    tot_saidas = df_mes[df_mes['Tipo'] != 'Entrada']['Valor_Parcela'].sum()
                    
                    fatura_nu = df_mes[df_mes['Forma_Pagamento'] == 'Cartão Nu']['Valor_Parcela'].sum()
                    fatura_bb = df_mes[df_mes['Forma_Pagamento'] == 'Cartão BB']['Valor_Parcela'].sum()
                    
                    saldo_final = tot_entradas - tot_saidas
                    
                    # Painel de KPIs modernos em colunas
                    kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
                    
                    with kpi_c1:
                        st.markdown(f"""
                        <div class="kpi-container kpi-entradas">
                            <div class="kpi-title">🟢 Total Entradas</div>
                            <div class="kpi-value">{formatar_brl(tot_entradas)}</div>
                            <div class="kpi-subtitle">Salário e Diárias</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with kpi_c2:
                        st.markdown(f"""
                        <div class="kpi-container kpi-saidas">
                            <div class="kpi-title">🔴 Total Despesas</div>
                            <div class="kpi-value">{formatar_brl(tot_saidas)}</div>
                            <div class="kpi-subtitle">Balanço: {formatar_brl(saldo_final)}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with kpi_c3:
                        st.markdown(f"""
                        <div class="kpi-container kpi-nu">
                            <div class="kpi-title">💳 Fatura Nu Bank</div>
                            <div class="kpi-value">{formatar_brl(fatura_nu)}</div>
                            <div class="kpi-subtitle">Fechamento do mês {mes_selecionado}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    with kpi_c4:
                        st.markdown(f"""
                        <div class="kpi-container kpi-bb">
                            <div class="kpi-title">💳 Fatura BB</div>
                            <div class="kpi-value">{formatar_brl(fatura_bb)}</div>
                            <div class="kpi-subtitle">Fechamento do mês {mes_selecionado}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.write("---")
                    
                    st.markdown("### 📊 Análise Setorial do Orçamento")
                    g_col1, g_col2 = st.columns(2)
                    
                    with g_col1:
                        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
                        st.markdown('<div class="dashboard-card-title">💸 Gastos Variáveis (Controle Ativo e Flexível)</div>', unsafe_allow_html=True)
                        df_gasto_var = df_mes[df_mes['Tipo'] == 'Gasto Variável'].groupby('Categoria')['Valor_Parcela'].sum().reset_index()
                        
                        if not df_gasto_var.empty:
                            total_g_var = df_gasto_var['Valor_Parcela'].sum()
                            fig_donut_var = px.pie(
                                df_gasto_var, 
                                values='Valor_Parcela', 
                                names='Categoria', 
                                hole=0.5,
                                color_discrete_sequence=['#10b981', '#059669', '#34d399', '#6ee7b7', '#a7f3d0', '#047857', '#065f46', '#064e3b']
                            )
                            fig_donut_var.update_traces(
                                textinfo='percent+label',
                                hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>Representa: %{percent}<extra></extra>"
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
                            st.info("Nenhum Gasto Variável registrado neste período.")
                        st.markdown('</div>', unsafe_allow_html=True)
                            
                    with g_col2:
                        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
                        st.markdown('<div class="dashboard-card-title">🔒 Gastos Fixos & Assinaturas (Custo Estrutural)</div>', unsafe_allow_html=True)
                        df_gasto_fix = df_mes[df_mes['Tipo'].isin(['Gasto Fixo', 'Assinatura'])].groupby('Categoria')['Valor_Parcela'].sum().reset_index()
                        
                        if not df_gasto_fix.empty:
                            total_g_fix = df_gasto_fix['Valor_Parcela'].sum()
                            fig_donut_fix = px.pie(
                                df_gasto_fix, 
                                values='Valor_Parcela', 
                                names='Categoria', 
                                hole=0.5,
                                color_discrete_sequence=['#312e81', '#4338ca', '#4f46e5', '#6366f1', '#818cf8', '#a5b4fc', '#c7d2fe']
                            )
                            fig_donut_fix.update_traces(
                                textinfo='percent+label',
                                hovertemplate="<b>%{label}</b><br>Valor: R$ %{value:,.2f}<br>Representa: %{percent}<extra></extra>"
                            )
                            fig_donut_fix.add_annotation(
                                text=f"Estrutural<br><b>R$ {total_g_fix:,.2f}</b>",
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
                            st.info("Nenhum custo fixo ou assinatura registrado neste mês.")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.write("---")
                    
                    st.markdown("### 👥 Balanço de Participação e Histórico")
                    b_col1, b_col2 = st.columns(2)
                    
                    with b_col1:
                        st.markdown("**Balanço de Gastos Dividido (Proporcional em R$)**")
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
                            st.info("Sem dados de despesa para exibir no balanço.")
                            
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
                    
                    st.markdown("### 📝 Extrato Detalhado do Mês de Competência")
                    
                    df_mes_tabela = df_mes.drop_duplicates(subset=['Data', 'Descricao', 'Valor', 'Categoria', 'Forma_Pagamento', 'Parcela_Atual'])
                    df_mes_exibe = df_mes_tabela[['Data_Exibicao', 'Descricao', 'Valor', 'Parcela_Atual', 'Categoria', 'Responsavel', 'Forma_Pagamento', 'Tipo']].copy()
                    df_mes_exibe.rename(columns={'Data_Exibicao': 'Data', 'Valor': 'Valor Total (R$)'}, inplace=True)
                    
                    # Seção de Filtros dinâmicos e inteligentes para o extrato
                    st.markdown("##### 🔍 Filtros Rápidos do Extrato")
                    f_col1, f_col2, f_col3 = st.columns(3)
                    with f_col1:
                        filtro_cat = st.multiselect(
                            "Filtrar por Categoria:",
                            options=sorted(list(df_mes_exibe['Categoria'].dropna().unique())),
                            placeholder="Todas as categorias"
                        )
                    with f_col2:
                        filtro_resp = st.multiselect(
                            "Filtrar por Quem:",
                            options=sorted(list(df_mes_exibe['Responsavel'].dropna().unique())),
                            placeholder="Todos"
                        )
                    with f_col3:
                        filtro_pagto = st.multiselect(
                            "Filtrar por Forma de Pagamento:",
                            options=sorted(list(df_mes_exibe['Forma_Pagamento'].dropna().unique())),
                            placeholder="Todas as formas"
                        )
                    
                    # Aplicação combinada de filtros no DataFrame
                    df_filtrado = df_mes_exibe.copy()
                    if filtro_cat:
                        df_filtrado = df_filtrado[df_filtrado['Categoria'].isin(filtro_cat)]
                    if filtro_resp:
                        df_filtrado = df_filtrado[df_filtrado['Responsavel'].isin(filtro_resp)]
                    if filtro_pagto:
                        df_filtrado = df_filtrado[df_filtrado['Forma_Pagamento'].isin(filtro_pagto)]
                    
                    # Formatação de valores apenas no momento de exibição final
                    def formatar_valor_tabela(val):
                        f = tratar_entrada_numerica(val)
                        return formatar_brl(f)
                        
                    df_filtrado_exibe = df_filtrado.copy()
                    df_filtrado_exibe['Valor Total (R$)'] = df_filtrado_exibe['Valor Total (R$)'].apply(formatar_valor_tabela)
                    
                    st.dataframe(df_filtrado_exibe, use_container_width=True)
                    
                    st.write("---")
                    st.markdown("### 📈 Histórico de Contas de Consumo (Luz / Água / Gás)")
                    st.markdown("Acompanhe o consumo das principais utilidades domésticas ao longo dos meses para monitorar o orçamento.")
                    
                    categorias_disponiveis = sorted(list(dados_brutos['Categoria'].unique())) if 'Categoria' in dados_brutos.columns else []
                    default_contas = [cat for cat in categorias_disponiveis if any(p in cat.lower() for p in ["luz", "água", "agua", "gás", "gas"])]
                    
                    contas_selecionadas = st.multiselect(
                        "Selecione as contas para análise no histórico:",
                        options=categorias_disponiveis,
                        default=default_contas if default_contas else (categorias_disponiveis[:2] if len(categorias_disponiveis) >= 2 else categorias_disponiveis)
                    )
                    
                    if contas_selecionadas:
                        df_historico = dados_brutos[dados_brutos['Categoria'].isin(contas_selecionadas)].copy()
                        
                        def parse_data_historico(data_val):
                            try:
                                return datetime.strptime(str(data_val).split()[0], "%Y-%m-%d").date()
                            except:
                                try:
                                    return datetime.strptime(str(data_val).split()[0], "%d/%m/%Y").date()
                                except:
                                    return None
                        
                        df_historico['Data_Parsed'] = df_historico['Data'].apply(parse_data_historico)
                        df_historico = df_historico.dropna(subset=['Data_Parsed'])
                        df_historico['Valor_Float'] = df_historico['Valor'].apply(tratar_entrada_numerica)
                        df_historico['Mes_Ano'] = df_historico['Data_Parsed'].apply(lambda x: x.strftime("%Y-%m"))
                        
                        if not df_historico.empty:
                            df_hist_grouped = df_historico.groupby(['Mes_Ano', 'Categoria'])['Valor_Float'].sum().reset_index()
                            df_hist_grouped = df_hist_grouped.sort_values('Mes_Ano')
                            
                            fig_historico = px.line(
                                df_hist_grouped,
                                x='Mes_Ano',
                                y='Valor_Float',
                                color='Categoria',
                                markers=True,
                                title="Evolução Mensal de Contas Domésticas (R$)",
                                labels={'Mes_Ano': 'Período', 'Valor_Float': 'Valor Pago (R$)', 'Categoria': 'Conta'},
                                color_discrete_sequence=['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6']
                            )
                            fig_historico.update_layout(xaxis_type='category', hovermode='x unified', height=350)
                            fig_historico.update_traces(hovertemplate="R$ %{y:,.2f}")
                            st.plotly_chart(fig_historico, use_container_width=True)
                            
                            st.markdown("**Valores Detalhados por Período:**")
                            df_pivot = df_hist_grouped.pivot(index='Mes_Ano', columns='Categoria', values='Valor_Float').fillna(0.0)
                            df_pivot_exibe = df_pivot.copy()
                            for col in df_pivot_exibe.columns:
                                df_pivot_exibe[col] = df_pivot_exibe[col].apply(formatar_brl)
                            
                            df_pivot_exibe = df_pivot_exibe.reset_index()
                            df_pivot_exibe.rename(columns={'Mes_Ano': 'Mês / Ano'}, inplace=True)
                            st.dataframe(df_pivot_exibe, use_container_width=True)
                        else:
                            st.info("Nenhum lançamento com valores válidos encontrado para as categorias selecionadas.")
                else:
                    st.info("Nenhum mês disponível para análise.")

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
                        st.info("Muito bem! Você não tem compras parceladas para os próximos meses.")
                        
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
                        
                        st.markdown(f"📍 **Editando Linha {linha_planilha_real} da planilha:**")
                        
                        # FORMULÁRIO DE EDIÇÃO CORRIGIDO COM CAMPOS SEGUROS E PERSONALIZADOS
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
                                # Carrega as categorias de edição dinamicamente com suporte à criação
                                e_lista_cats = obter_categorias_por_tipo(e_tipo, dados_brutos)
                                
                                # Fallback seguro caso o item possua categoria customizada não listada inicialmente
                                cat_original = item_selecionado['Categoria']
                                if cat_original not in e_lista_cats:
                                    e_lista_cats.insert(0, cat_original)
                                    
                                if "Outra (Criar Nova...)" in e_lista_cats:
                                    e_lista_cats.remove("Outra (Criar Nova...)")
                                e_lista_cats.append("Outra (Criar Nova...)")
                                
                                idx_cat_edicao = e_lista_cats.index(cat_original) if cat_original in e_lista_cats else 0
                                e_cat_sel = st.selectbox("Nova Categoria", e_lista_cats, index=idx_cat_edicao)
                                
                                e_nova_categoria = ""
                                if e_cat_sel == "Outra (Criar Nova...)":
                                    e_nova_categoria = st.text_input("Nome da nova Categoria (Edição):", placeholder="Digite a nova categoria")
                                
                                e_resp = st.multiselect(
                                    "Novos Responsáveis", 
                                    ["Jonathan", "Casa", "Gatos"],
                                    default=[r for r in resp_item_lista if r in ["Jonathan", "Casa", "Gatos"]]
                                )
                                
                                e_forma = st.selectbox(
                                    "Nova Forma de Pagamento", 
                                    ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"],
                                    index=["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"].index(item_selecionado['Forma_Pagamento'])
                                )
                                
                                # Habilitando correção de parcelas na edição histórica
                                e_pode_parcelar = e_tipo in ["Gasto Variável", "Gasto Fixo"]
                                if e_pode_parcelar:
                                    e_tot_parc = st.number_input(
                                        "Quantidade de Parcelas (Corrigir)", 
                                        min_value=1, 
                                        max_value=48, 
                                        value=int(item_selecionado.get('Parcelas_Totais', 1)) if pd.notna(item_selecionado.get('Parcelas_Totais')) else 1, 
                                        step=1
                                    )
                                    e_parcelado = "Sim" if e_tot_parc > 1 else "Não"
                                else:
                                    e_parcelado = "Não"
                                    e_tot_parc = 1
                                
                            btn_atualizar = st.form_submit_button("💾 Salvar Alterações")
                            
                            if btn_atualizar:
                                val_novo_float = tratar_entrada_numerica(e_valor_texto)
                                
                                e_cat_final = e_cat_sel
                                if e_cat_sel == "Outra (Criar Nova...)":
                                    if not e_nova_categoria.strip():
                                        st.error("❌ **Erro:** Digite um nome para a nova categoria personalizada na edição!")
                                        st.stop()
                                    else:
                                        e_cat_final = e_nova_categoria.strip().title()
                                
                                if not e_resp:
                                    st.error("Selecione pelo menos um responsável.")
                                elif e_desc and val_novo_float > 0:
                                    resp_ed_salvar = ", ".join(e_resp)
                                    valor_ed_gravar = f"{val_novo_float:.2f}".replace(".", ",")
                                    
                                    linha_atualizada = [
                                        str(e_data), e_desc, valor_ed_gravar, e_cat_final, e_tipo, 
                                        resp_ed_salvar, e_forma, e_parcelado, int(e_tot_parc)
                                    ]
                                    try:
                                        sheet_conn.update(f"A{linha_planilha_real}:I{linha_planilha_real}", [linha_atualizada], value_input_option='USER_ENTERED')
                                        st.success("Lançamento atualizado com sucesso! Reiniciando...")
                                        st.rerun()
                                    except Exception as err:
                                        st.error(f"Erro ao salvar modificação: {err}")
                        
                        # EXCLUSÃO DEFINITIVA
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
