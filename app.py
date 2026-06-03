import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# Configuração da página para visualização Mobile-First
st.set_page_config(page_title="Finanças Familiares", page_icon="💰", layout="wide")

# CONEXÃO COM O GOOGLE SHEETS
def conectar_planilha():
    scope = ["[https://spreadsheets.google.com/feeds](https://spreadsheets.google.com/feeds)", "[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)"]
    
    # Lendo o JSON que colamos dentro do segredo 'google_credentials'
    try:
        creds_json = json.loads(st.secrets["google_credentials"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
        client = gspread.authorize(creds)
        
        # Conecta diretamente na sua planilha usando o ID
        sheet = client.open_by_key("1JyVUY1pKQs90jtPPBvEHDLnGxBw3wdooEFWSq-1e5D4").worksheet("Lancamentos")
        return sheet
    except Exception as e:
        st.error(f"Erro detalhado de conexão: {e}")
        return None

sheet_conn = conectar_planilha()

# LÓGICA DE FATURA (FECHAMENTO DIA 07) E PARCELAMENTO
def calcular_mes_competencia(data_compra, forma_pagamento):
    if "Cartão" not in forma_pagamento:
        return data_compra.strftime("%Y-%m")
    
    # Se passou do dia 07, a fatura corrente já fechou, vai para o próximo mês
    if data_compra.day > 7:
        data_fatura = data_compra + relativedelta(months=1)
    else:
        data_fatura = data_compra
    return data_fatura.strftime("%Y-%m")

# INTERFACE DO USUÁRIO
st.title("💰 Controle Financeiro Familiar")
st.markdown("### Jonathan & Bruna")

tabs = st.tabs(["📲 Novo Lançamento", "📊 Dashboard & Resumos", "💳 Controle de Parcelas"])

# TAB 1: FORMULÁRIO DE LANÇAMENTO (OTIMIZADO PARA CELULAR)
with tabs[0]:
    st.subheader("Registrar Gasto ou Entrada")
    if sheet_conn is None:
        st.error("O aplicativo não pôde se conectar à planilha. Verifique suas credenciais nos Secrets do Streamlit.")
    else:
        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                data = st.date_input("Data do Lançamento", date.today())
                descricao = st.text_input("Descrição (Ex: Mercado Livre, Ifood)")
                valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
                tipo = st.selectbox("Tipo", ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"])
            
            with col2:
                categoria = st.selectbox("Categoria", ["Supermercado", "Ifood", "Combustível", "Farmácia", "Salário", "Lazer", "Outros"])
                responsavel = st.selectbox("Para Quem?", ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"])
                forma_pagto = st.selectbox("Forma de Pagamento", ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro"])
                
                parcelado = st.radio("Compra Parcelada?", ["Não", "Sim"], horizontal=True)
                if parcelado == "Sim":
                    num_parcelas = st.number_input("Quantidade de Parcelas", min_value=2, max_value=48, value=2, step=1)
                else:
                    num_parcelas = 1
                    
            botao_salvar = st.form_submit_button("🚀 Gravar na Planilha")
            
            if botao_salvar:
                if descricao and valor > 0:
                    novo_registro = [
                        str(data), descricao, valor, categoria, tipo, 
                        responsavel, forma_pagto, parcelado, int(num_parcelas)
                    ]
                    try:
                        sheet_conn.append_row(novo_registro)
                        st.success("Lançamento adicionado com sucesso na base de dados!")
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")
                else:
                    st.error("Por favor, preencha a descrição e o valor.")

# INTERPRETAÇÃO E PROJEÇÃO DOS DADOS
if sheet_conn is not None:
    try:
        dados_brutos = pd.DataFrame(sheet_conn.get_all_records())
    except Exception as e:
        dados_brutos = pd.DataFrame()
        st.warning("Aguardando lançamentos na aba 'Lancamentos' para carregar os gráficos.")

    if not dados_brutos.empty:
        # Processar projeções de parcelas futuras em memória para alimentar o Dashboard
        lista_projetada = []
        for index, row in dados_brutos.iterrows():
            try:
                # Tratar datas vazias ou formatos inválidos
                if not row['Data']:
                    continue
                dt_compra = datetime.strptime(str(row['Data']).split()[0], "%Y-%m-%d").date()
            except Exception as parse_error:
                # Fallback caso a data esteja em outro formato (ex: DD/MM/AAAA)
                try:
                    dt_compra = datetime.strptime(str(row['Data']).split()[0], "%d/%m/%Y").date()
                except:
                    continue
            
            try:
                total_parc = int(row['Parcelas_Totais']) if row['Parcelas_Totais'] else 1
            except:
                total_parc = 1
                
            try:
                valor_total = float(str(row['Valor']).replace(',', '.'))
            except:
                valor_total = 0.0
                
            val_parcela = valor_total / total_parc if row['Parcelado'] == 'Sim' else valor_total
            
            for p in range(total_parc):
                dt_parcela = dt_compra + relativedelta(months=p)
                mes_competencia = calcular_mes_competencia(dt_parcela, row['Forma_Pagamento'])
                
                item_proj = row.to_dict()
                item_proj['Mes_Fatura'] = mes_competencia
                item_proj['Valor_Parcela'] = val_parcela
                item_proj['Parcela_Atual'] = f"{p+1}/{total_parc}"
                lista_projetada.append(item_proj)
                
        if lista_projetada:
            df_projetado = pd.DataFrame(lista_projetada)
            df_projetado['Valor_Parcela'] = df_projetado['Valor_Parcela'].astype(float)
            
            # TAB 2: DASHBOARD
            with tabs[1]:
                st.subheader("Resumo Mensal e Faturas")
                
                meses_disponiveis = sorted(df_projetado['Mes_Fatura'].unique())
                if meses_disponiveis:
                    mes_selecionado = st.selectbox("Selecione o Mês de Análise", meses_disponiveis, index=len(meses_disponiveis)-1)
                    
                    df_mes = df_projetado[df_projetado['Mes_Fatura'] == mes_selecionado]
                    
                    # KPIs Principais
                    tot_entradas = df_mes[df_mes['Tipo'] == 'Entrada']['Valor_Parcela'].sum()
                    tot_saidas = df_mes[df_mes['Tipo'] != 'Entrada']['Valor_Parcela'].sum()
                    fatura_nu = df_mes[df_mes['Forma_Pagamento'] == 'Cartão Nu']['Valor_Parcela'].sum()
                    fatura_bb = df_mes[df_mes['Forma_Pagamento'] == 'Cartão BB']['Valor_Parcela'].sum()
                    
                    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                    kpi1.metric("🟢 Total Entradas", f"R$ {tot_entradas:,.2f}")
                    kpi2.metric("🔴 Total Despesas", f"R$ {tot_saidas:,.2f}")
                    kpi3.metric("💳 Fatura Nu Bank", f"R$ {fatura_nu:,.2f}")
                    kpi4.metric("💳 Fatura Banco do Brasil", f"R$ {fatura_bb:,.2f}")
                    
                    st.markdown("### Distribuição dos Gastos do Mês")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Por Membro da Família / Destino**")
                        df_resp = df_mes[df_mes['Tipo'] != 'Entrada'].groupby('Responsavel')['Valor_Parcela'].sum()
                        st.bar_chart(df_resp)
                    with c2:
                        st.markdown("**Por Tipo de Gasto**")
                        df_tipo = df_mes[df_mes['Tipo'] != 'Entrada'].groupby('Tipo')['Valor_Parcela'].sum()
                        st.bar_chart(df_tipo)
                        
                    st.markdown("**Extrato Detalhado do Mês de Competência**")
                    st.dataframe(df_mes[['Data', 'Descricao', 'Valor_Parcela', 'Parcela_Atual', 'Categoria', 'Responsavel', 'Forma_Pagamento']], use_container_width=True)
                else:
                    st.info("Nenhum mês disponível para análise.")

            # TAB 3: CONTROLE DE PARCELAS ACUMULADAS
            with tabs[2]:
                st.subheader("Dívidas Parceladas e Projeções Futuras")
                
                hoje_str = date.today().strftime("%Y-%m")
                df_futuro = df_projetado[(df_projetado['Mes_Fatura'] > hoje_str) & (df_projetado['Parcelado'] == 'Sim')]
                saldo_devedor_futuro = df_futuro['Valor_Parcela'].sum()
                
                st.warning(f"🏦 **Saldo Devedor Total Acumulado (Faturas Seguintes):** R$ {saldo_devedor_futuro:,.2f}")
                
                st.markdown("### Cronograma de Faturas Futuras")
                if not df_futuro.empty:
                    cronograma = df_futuro.groupby(['Mes_Fatura', 'Forma_Pagamento'])['Valor_Parcela'].sum().unstack().fillna(0)
                    st.dataframe(cronograma, use_container_width=True)
                    
                    st.markdown("### Detalhamento das Parcelas a Vencer")
                    st.dataframe(df_futuro[['Mes_Fatura', 'Descricao', 'Valor_Parcela', 'Parcela_Atual', 'Forma_Pagamento']], use_container_width=True)
                else:
                    st.info("Não há parcelas pendentes para os próximos meses!")
        else:
            st.info("Sem dados projetados disponíveis.")
    else:
        st.info("Sua planilha na aba 'Lancamentos' está vazia. Faça o primeiro lançamento na aba 'Novo Lançamento' acima!")
