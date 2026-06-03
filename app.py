import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import gspread
from google.oauth2.service_account import Credentials
import json

# Configuração da página para visualização Mobile-First
st.set_page_config(page_title="Finanças Familiares", page_icon="💰", layout="wide")

# CONEXÃO COM O GOOGLE SHEETS COM DIAGNÓSTICO DETALHADO
def conectar_planilha():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. Verificar se o segredo existe no Streamlit
    if "google_credentials" not in st.secrets:
        st.error("""
        ❌ **Erro de Configuração:** O segredo `google_credentials` não foi encontrado no painel de Secrets do Streamlit.
        \n*Como corrigir:* Vá em Settings -> Secrets no painel do Streamlit Cloud e cole as credenciais lá.
        """)
        return None
        
    try:
        # 2. Tentar ler o JSON
        try:
            creds_json = json.loads(st.secrets["google_credentials"])
        except Exception as json_err:
            st.error(f"""
            ❌ **Erro no Formato das Credenciais (JSON Inválido):** O conteúdo dentro de `google_credentials` não é um JSON válido.
            \n*Detalhe técnico:* {json_err}
            \n*Como corrigir:* Verifique se você copiou todo o arquivo `.json` do Google e se ele está envolvido por três aspas simples de cada lado no Secrets:
            \n```toml
            \ngoogle_credentials = '''
            \n{ ... seu json aqui ... }
            \n'''
            \n```
            """)
            return None
        
        # Tratamento da chave privada
        if "private_key" in creds_json:
            key_formatada = creds_json["private_key"].replace("\\n", "\n")
            if key_formatada.startswith('"') and key_formatada.endswith('"'):
                key_formatada = key_formatada[1:-1]
            creds_json["private_key"] = key_formatada
        
        # 3. Autenticar com o Google
        try:
            creds = Credentials.from_service_account_info(creds_json, scopes=scope)
            client = gspread.authorize(creds)
        except Exception as auth_err:
            st.error(f"❌ **Erro de Autenticação com o Google:** As credenciais foram lidas, mas o Google as rejeitou.\n\n*Detalhe:* {auth_err}")
            return None
            
        # 4. Tentar abrir a planilha pelo ID
        planilha_id = "1JyVUY1pKQs90jtPPBvEHDLnGxBw3wdooEFWSq-1e5D4"
        try:
            plan_aberta = client.open_by_key(planilha_id)
        except Exception as open_err:
            email_servico = creds_json.get("client_email", "e-mail desconhecido")
            st.error(f"""
            ❌ **A Planilha não foi Compartilhada ou o ID está incorreto!**
            \nO aplicativo não tem permissão para abrir o seu Google Sheets.
            \n*Como corrigir:* \n1. Abra a sua planilha no seu navegador.
            \n2. Clique no botão azul **Compartilhar** (no canto superior direito).
            \n3. Adicione o e-mail da sua conta de serviço como **Editor**: 
            \n`{email_servico}`
            \n4. Salve o compartilhamento.
            """)
            return None
            
        # 5. Tentar acessar a aba "Lancamentos"
        try:
            sheet = plan_aberta.worksheet("Lancamentos")
            return sheet
        except Exception as sheet_err:
            abas_disponiveis = [w.title for w in plan_aberta.worksheets()]
            st.error(f"""
            ❌ **Aba "Lancamentos" não encontrada na planilha!**
            \nO aplicativo conseguiu conectar, mas não achou a aba com o nome exato de `Lancamentos`.
            \n*Abas que existem na sua planilha atualmente:* {abas_disponiveis}
            \n*Como corrigir:* Crie uma nova aba na sua planilha e nomeie-a exatamente como `Lancamentos` (sem o "ç" e sem o "til").
            """)
            return None
            
    except Exception as e:
        st.error(f"❌ **Erro Inesperado na Conexão:** {e}")
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
st.markdown("### Jonathan Prado")

tabs = st.tabs(["📲 Novo Lançamento", "📊 Dashboard & Resumos", "💳 Controle de Parcelas"])

# TAB 1: FORMULÁRIO DE LANÇAMENTO (OTIMIZADO PARA CELULAR)
with tabs[0]:
    st.subheader("Registrar Gasto ou Entrada")
    if sheet_conn is None:
        st.info("⚠️ **O formulário de envio está temporariamente desativado devido a problemas de conexão com a planilha.** \n\nPor favor, verifique a mensagem de erro detalhada acima para saber como corrigir.")
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
                        st.balloons()
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
                if not row.get('Data'):
                    continue
                dt_compra = datetime.strptime(str(row['Data']).split()[0], "%Y-%m-%d").date()
            except Exception as parse_error:
                try:
                    dt_compra = datetime.strptime(str(row['Data']).split()[0], "%d/%m/%Y").date()
                except:
                    continue
            
            try:
                total_parc = int(row['Parcelas_Totais']) if row.get('Parcelas_Totais') else 1
            except:
                total_parc = 1
                
            try:
                valor_total = float(str(row['Valor']).replace(',', '.'))
            except:
                valor_total = 0.0
                
            val_parcela = valor_total / total_parc if row.get('Parcelado') == 'Sim' else valor_total
            
            for p in range(total_parc):
                dt_parcela = dt_compra + relativedelta(months=p)
                mes_competencia = calcular_mes_competencia(dt_parcela, row.get('Forma_Pagamento', 'Dinheiro'))
                
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
        st.info("Sua planilha na aba 'Lancamentos' está vazia. Faça o primeiro lançamento na aba 'Novo Lançamento' acima para testar!")
