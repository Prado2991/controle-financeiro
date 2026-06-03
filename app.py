import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import gspread
import json

# Configuração da página para visualização Mobile-First e responsiva
st.set_page_config(page_title="Finanças Familiares", page_icon="💰", layout="wide")

# CONEXÃO MODERNA E SEGURA COM O GOOGLE SHEETS
@st.cache_resource
def conectar_planilha():
    try:
        # Carrega o JSON de credenciais guardado com segurança nos Secrets do Streamlit
        creds_json = json.loads(st.secrets["google_credentials"])
        
        # Correção automática de quebras de linha que o Windows ou o Streamlit podem causar na chave
        if "private_key" in creds_json:
            creds_json["private_key"] = creds_json["private_key"].replace("\\n", "\n")
            
        # Conexão oficial e moderna, sem usar a biblioteca legada oauth2client!
        client = gspread.service_account_from_dict(creds_json)
        
        # Abre a planilha pelo ID e mira na aba limpa que você criou
        spreadsheet = client.open_by_key("1JyVUY1pKQs90jtPPBvEHDLnGxBw3wdooEFWSq-1e5D4")
        sheet = spreadsheet.worksheet("Lancamentos")
        return sheet
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha. Verifique suas credenciais. Detalhe: {e}")
        return None

# Tenta estabelecer a conexão principal
sheet_conn = conectar_planilha()

# LÓGICA DE COMPETÊNCIA DA FATURA (FECHAMENTO DIA 07)
def calcular_mes_competencia(data_compra, forma_pagamento):
    # Se não for cartão de crédito, a competência é o próprio mês da compra
    if "Cartão" not in str(forma_pagamento):
        return data_compra.strftime("%Y-%m")
    
    # Se a compra foi feita após o dia 07, entra na fatura do mês seguinte
    if data_compra.day > 7:
        data_fatura = data_compra + relativedelta(months=1)
    else:
        data_fatura = data_compra
    return data_fatura.strftime("%Y-%m")

# TRATAMENTO DE DATAS ROBUSTO
def converter_para_data(valor_data):
    try:
        # Tenta formato padrão (AAAA-MM-DD)
        return datetime.strptime(str(valor_data).split()[0], "%Y-%m-%d").date()
    except ValueError:
        try:
            # Tenta formato brasileiro (DD/MM/AAAA)
            return datetime.strptime(str(valor_data).split()[0], "%d/%m/%Y").date()
        except ValueError:
            return date.today()

# --- INTERFACE DO USUÁRIO ---
st.title("💰 Controle Financeiro")
st.markdown("### Jonathan Prado")

tabs = st.tabs(["📲 Novo Lançamento", "📊 Dashboard & Resumos", "💳 Parcelas & Projeções"])

# TAB 1: FORMULÁRIO DE LANÇAMENTO
with tabs[0]:
    st.subheader("Registrar Novo Item")
    if sheet_conn is not None:
        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                data = st.date_input("Data da Compra/Gasto", date.today())
                descricao = st.text_input("Descrição", placeholder="Ex: Muffato, Posto, Netflix")
                valor = st.number_input("Valor total da Compra (R$)", min_value=0.0, step=0.01, format="%.2f")
                tipo = st.selectbox("Tipo de Gasto", ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"])
            
            with col2:
                categoria = st.selectbox("Categoria", ["Supermercado", "Ifood/Restaurante", "Combustível", "Farmácia", "Salário/Receita", "Lazer", "Casa", "Gatos", "Outros"])
                responsavel = st.selectbox("Para Quem?", ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"])
                forma_pagto = st.selectbox("Forma de Pagamento", ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Débito"])
                
                parcelado = st.radio("Essa compra é parcelada?", ["Não", "Sim"], horizontal=True)
                if parcelado == "Sim":
                    num_parcelas = st.number_input("Em quantas vezes?", min_value=2, max_value=48, value=2, step=1)
                else:
                    num_parcelas = 1
                    
            botao_salvar = st.form_submit_button("🚀 Gravar Lançamento")
            
            if botao_salvar:
                if descricao and valor > 0:
                    novo_registro = [
                        str(data), descricao, valor, categoria, tipo, 
                        responsavel, forma_pagto, parcelado, int(num_parcelas)
                    ]
                    try:
                        sheet_conn.append_row(novo_registro)
                        st.success("Gravado com sucesso no Google Sheets!")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")
                else:
                    st.error("Preencha a descrição e o valor antes de salvar.")
    else:
        st.warning("O formulário de envio está temporariamente desativado devido a problemas de conexão com a planilha.")

# CARREGAMENTO E PROCESSAMENTO DOS DADOS PARA O DASHBOARD
if sheet_conn is not None:
    try:
        dados_brutos = pd.DataFrame(sheet_conn.get_all_records())
    except Exception as e:
        dados_brutos = pd.DataFrame()
        st.error(f"Erro ao ler registros da planilha: {e}")
    
    if not dados_brutos.empty:
        # GERAÇÃO DA PROJEÇÃO DE PARCELAS EM MEMÓRIA
        lista_projetada = []
        for index, row in dados_brutos.iterrows():
            if not row.get('Data') or not row.get('Valor'):
                continue
                
            dt_compra = converter_para_data(row['Data'])
            
            # Sanitização de valores
            try:
                valor_total = float(str(row['Valor']).replace(',', '.'))
            except ValueError:
                valor_total = 0.0
                
            try:
                total_parc = int(row['Parcelas_Totais']) if row.get('Parcelas_Totais') else 1
            except ValueError:
                total_parc = 1
                
            val_parcela = valor_total / total_parc if str(row.get('Parcelado')).strip().lower() == 'sim' else valor_total
            
            # Loop para gerar lançamentos futuros de parcelas
            for p in range(total_parc):
                dt_parcela = dt_compra + relativedelta(months=p)
                mes_competencia = calcular_mes_competencia(dt_parcela, row.get('Forma_Pagamento', 'Pix'))
                
                item_proj = row.to_dict()
                item_proj['Mes_Fatura'] = mes_competencia
                item_proj['Valor_Parcela'] = val_parcela
                item_proj['Parcela_Atual'] = f"{p+1}/{total_parc}" if total_parc > 1 else "1/1"
                lista_projetada.append(item_proj)
                
        df_projetado = pd.DataFrame(lista_projetada)
        df_projetado['Valor_Parcela'] = pd.to_numeric(df_projetado['Valor_Parcela'], errors='coerce').fillna(0.0)
        
        # TAB 2: DASHBOARD DINÂMICO
        with tabs[1]:
            st.subheader("Resumo de Competência")
            
            meses_disponiveis = sorted(df_projetado['Mes_Fatura'].unique())
            mes_selecionado = st.selectbox(
                "Selecione o mês para analisar:", 
                meses_disponiveis, 
                index=len(meses_disponiveis)-1 if meses_disponiveis else 0
            )
            
            df_mes = df_projetado[df_projetado['Mes_Fatura'] == mes_selecionado]
            
            # KPIs Principais
            tot_entradas = df_mes[df_mes['Tipo'] == 'Entrada']['Valor_Parcela'].sum()
            tot_saidas = df_mes[df_mes['Tipo'] != 'Entrada']['Valor_Parcela'].sum()
            fatura_nu = df_mes[df_mes['Forma_Pagamento'] == 'Cartão Nu']['Valor_Parcela'].sum()
            fatura_bb = df_mes[df_mes['Forma_Pagamento'] == 'Cartão BB']['Valor_Parcela'].sum()
            
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("🟢 Entradas", f"R$ {tot_entradas:,.2f}")
            kpi2.metric("🔴 Despesas Totais", f"R$ {tot_saidas:,.2f}")
            kpi3.metric("💳 Fatura Nu (Vence após dia 07)", f"R$ {fatura_nu:,.2f}")
            kpi4.metric("💳 Fatura BB", f"R$ {fatura_bb:,.2f}")
            
            st.markdown("---")
            
            # Gráficos Leves
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.markdown("**Gastos por Destinatário**")
                df_resp = df_mes[df_mes['Tipo'] != 'Entrada'].groupby('Responsavel')['Valor_Parcela'].sum()
                if not df_resp.empty:
                    st.bar_chart(df_resp)
                else:
                    st.info("Sem dados de despesas neste mês.")
            with col_g2:
                st.markdown("**Gastos por Tipo**")
                df_tipo = df_mes[df_mes['Tipo'] != 'Entrada'].groupby('Tipo')['Valor_Parcela'].sum()
                if not df_tipo.empty:
                    st.bar_chart(df_tipo)
                else:
                    st.info("Sem dados de despesas neste mês.")
            
            st.markdown("#### Lista de Despesas deste Mês")
            st.dataframe(
                df_mes[['Data', 'Descricao', 'Valor_Parcela', 'Parcela_Atual', 'Categoria', 'Responsavel', 'Forma_Pagamento']], 
                use_container_width=True
            )

        # TAB 3: CONTROLE DE PARCELAS ACUMULADAS
        with tabs[2]:
            st.subheader("Análise de Parcelamentos e Saúde Financeira")
            
            hoje_str = date.today().strftime("%Y-%m")
            df_futuro = df_projetado[(df_projetado['Mes_Fatura'] > hoje_str) & (df_projetado['Parcelado'].astype(str).str.lower() == 'sim')]
            saldo_devedor_futuro = df_futuro['Valor_Parcela'].sum()
            
            st.metric("🏦 Saldo Devedor Total Acumulado (Faturas Futuras)", f"R$ {saldo_devedor_futuro:,.2f}")
            st.info("Este valor representa a soma de todas as parcelas que você já se comprometeu a pagar nos meses seguintes.")
            
            if not df_futuro.empty:
                st.markdown("### Cronograma de Vencimentos Futuros")
                cronograma = df_futuro.pivot_table(
                    index='Mes_Fatura', 
                    columns='Forma_Pagamento', 
                    values='Valor_Parcela', 
                    aggfunc='sum'
                ).fillna(0.0)
                st.dataframe(cronograma, use_container_width=True)
                
                st.markdown("### Detalhamento de todas as parcelas em aberto")
                st.dataframe(
                    df_futuro[['Mes_Fatura', 'Descricao', 'Valor_Parcela', 'Parcela_Atual', 'Forma_Pagamento']].sort_values('Mes_Fatura'), 
                    use_container_width=True
                )
            else:
                st.success("Parabéns! Você não possui compras parceladas para os próximos meses.")
    else:
        st.info("Sua planilha está conectada, mas não encontramos lançamentos válidos. Comece a cadastrar na aba 'Novo Lançamento'!")
