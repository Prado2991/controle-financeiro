import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import gspread
from google.oauth2.service_account import Credentials
import json

# Configuração da página para visualização Mobile-First e Temática Elegante
st.set_page_config(
    page_title="Finanças Jonathan", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Estilização CSS personalizada para deixar o App Premium e Amigável no Celular
st.markdown("""
<style>
    /* Estilização dos blocos de métricas (KPIs) */
    div[data-testid="stMetricValue"] {
        font-size: 24px !important;
        font-weight: bold;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 14px !important;
    }
    /* Estilização de botões */
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

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
        
        Como corrigir: Vá em Settings -> Secrets no painel do Streamlit Cloud e cole as credenciais lá.
        """)
        return None
        
    try:
        # 2. Tentar ler o JSON
        try:
            creds_json = json.loads(st.secrets["google_credentials"])
        except Exception as json_err:
            st.error(f"""
            ❌ **Erro no Formato das Credenciais (JSON Inválido):** O conteúdo dentro de `google_credentials` não é um JSON válido.
            
            Detalhe técnico: {json_err}
            
            Como corrigir: Verifique se você copiou todo o arquivo .json do Google e se ele está envolvido por três aspas simples de cada lado no Secrets:
            
            google_credentials = '''
            {{ ... seu json aqui ... }}
            '''
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
            
            O aplicativo não tem permissão para abrir o seu Google Sheets.
            
            Como corrigir:
            1. Abra a sua planilha no seu navegador.
            2. Clique no botão azul "Compartilhar" (no canto superior direito).
            3. Adicione o e-mail da sua conta de serviço como Editor:
            
            {email_servico}
            
            4. Salve o compartilhamento.
            """)
            return None
            
        # 5. Tentar acessar a aba "Lancamentos"
        try:
            sheet = plan_aberta.worksheet("Lancamentos")
            return sheet
        except Exception as sheet_err:
            abas_disponiveis = [w.title for w in plan_aberta.worksheets()]
            st.error(f"""
            ❌ **Aba 'Lancamentos' não encontrada na planilha!**
            
            O aplicativo conseguiu conectar, mas não achou a aba com o nome exato de 'Lancamentos'.
            
            Abas que existem na sua planilha atualmente: {abas_disponiveis}
            
            Como corrigir: Crie uma nova aba na sua planilha e nomeie-a exatamente como 'Lancamentos' (sem o 'ç' e sem o 'til').
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

# Barra de progresso para fechamento da fatura corrente (Dia 07)
hoje = date.today()
vencimento_limite = date(hoje.year, hoje.month, 7)
if hoje.day > 7:
    vencimento_limite = vencimento_limite + relativedelta(months=1)
dias_restantes = (vencimento_limite - hoje).days

st.info(f"⏳ **Fechamento de Faturas:** Faltam **{dias_restantes} dias** para o fechamento dos cartões (Próximo dia 07: {vencimento_limite.strftime('%d/%m/%Y')})")

tabs = st.tabs(["📲 Novo Lançamento", "📊 Dashboard & Resumos", "💳 Controle de Parcelas & Assinaturas"])

# TAB 1: FORMULÁRIO DE LANÇAMENTO (OTIMIZADO PARA CELULAR)
with tabs[0]:
    st.subheader("Registrar Gasto ou Entrada")
    if sheet_conn is None:
        st.info("⚠️ **O formulário de envio está temporariamente desativado devido a problemas de conexão com a planilha.** \n\nPor favor, verifique a mensagem de erro detalhada acima para saber como corrigir.")
    else:
        # ATALHOS RÁPIDOS DE LANÇAMENTO (Melhoria de usabilidade para o dia a dia na rua)
        st.markdown("⚡ **Lançamentos Rápidos (Clique para preencher os campos comuns):**")
        c_at1, c_at2, c_at3, c_at4 = st.columns(4)
        
        # Variáveis de sessão para preencher os valores padrão do form
        if "fast_desc" not in st.session_state: st.session_state.fast_desc = ""
        if "fast_val" not in st.session_state: st.session_state.fast_val = 0.0
        if "fast_tipo" not in st.session_state: st.session_state.fast_tipo = "Gasto Variável"
        if "fast_cat" not in st.session_state: st.session_state.fast_cat = "Refeição"
        if "fast_pgto" not in st.session_state: st.session_state.fast_pgto = "Cartão Nu"
        if "fast_resp" not in st.session_state: st.session_state.fast_resp = "Jonathan"

        if c_at1.button("☕ Cafezinho / Lanche (R$ 15,00)"):
            st.session_state.fast_desc = "Café / Lanche rápido"
            st.session_state.fast_val = 15.00
            st.session_state.fast_tipo = "Gasto Variável"
            st.session_state.fast_cat = "Refeição"
            st.session_state.fast_pgto = "Cartão Nu"
            st.toast("Preenchido: Cafezinho!")

        if c_at2.button("⛽ Abastecimento (R$ 100,00)"):
            st.session_state.fast_desc = "Posto de Combustível"
            st.session_state.fast_val = 100.00
            st.session_state.fast_tipo = "Gasto Variável"
            st.session_state.fast_cat = "Abastecimento"
            st.session_state.fast_pgto = "Cartão BB"
            st.toast("Preenchido: Abastecimento!")

        if c_at3.button("🍔 iFood / Jantar (R$ 60,00)"):
            st.session_state.fast_desc = "Jantar Delivery"
            st.session_state.fast_val = 60.00
            st.session_state.fast_tipo = "Gasto Variável"
            st.session_state.fast_cat = "Refeição"
            st.session_state.fast_pgto = "Cartão Nu"
            st.toast("Preenchido: iFood/Jantar!")

        if c_at4.button("🛒 Supermercado (R$ 250,00)"):
            st.session_state.fast_desc = "Supermercado Muffato"
            st.session_state.fast_val = 250.00
            st.session_state.fast_tipo = "Gasto Variável"
            st.session_state.fast_cat = "Supermercado"
            st.session_state.fast_pgto = "Cartão Nu"
            st.toast("Preenchido: Supermercado!")

        st.write("---")

        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                # Exibição nativa em formato brasileiro DD/MM/YYYY
                data = st.date_input("Data do Lançamento", date.today(), format="DD/MM/YYYY")
                descricao = st.text_input(
                    "Descrição", 
                    value=st.session_state.fast_desc, 
                    placeholder="Ex: Sorveteria Sávio, Roupas na Shein, Mercado Muffato"
                )
                valor = st.number_input("Valor (R$)", min_value=0.0, value=st.session_state.fast_val, step=0.01, format="%.2f")
                
                # Seletor do Tipo de Gasto
                tipo = st.selectbox(
                    "Tipo de Lançamento", 
                    ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"],
                    index=["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"].index(st.session_state.fast_tipo)
                )
            
            with col2:
                # LÓGICA DE CATEGORIAS DINÂMICAS: Muda com base no tipo selecionado
                if tipo == "Gasto Fixo":
                    lista_cats = ["Luz", "Água", "Internet", "Telefone", "Condomínio", "Aluguel", "Plano de Saúde", "Outros Fixos"]
                elif tipo == "Gasto Variável":
                    lista_cats = ["Refeição", "Supermercado", "Abastecimento", "Shopping", "Farmácia", "Lazer", "Viagem", "Presentes", "Outros Variáveis"]
                elif tipo == "Assinatura":
                    lista_cats = ["Streaming (Netflix/Spotify)", "Academia", "Clube de Assinatura", "Software/App", "Outras Assinaturas"]
                else:  # Entrada
                    lista_cats = ["Salário", "Rendimento", "Pix Recebido", "Outras Entradas"]
                
                # Definir índice correto se vier de atalho rápido
                idx_cat = 0
                if st.session_state.fast_cat in lista_cats:
                    idx_cat = lista_cats.index(st.session_state.fast_cat)

                categoria = st.selectbox("Categoria", lista_cats, index=idx_cat)
                
                responsavel = st.selectbox(
                    "Para Quem?", 
                    ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"],
                    index=["Jonathan", "Bruna", "Alice", "Casa", "Gatos"].index(st.session_state.fast_resp)
                )
                
                forma_pagto = st.selectbox(
                    "Forma de Pagamento", 
                    ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"],
                    index=["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"].index(st.session_state.fast_pgto)
                )
                
                # Bloqueador de Parcelamento para tipos inadequados
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
                if descricao and valor > 0:
                    # Salva a data no padrão ISO YYYY-MM-DD para evitar erros no Excel/Sheets
                    novo_registro = [
                        str(data), descricao, valor, categoria, tipo, 
                        responsavel, forma_pagto, parcelado, int(num_parcelas)
                    ]
                    try:
                        sheet_conn.append_row(novo_registro)
                        st.success(f"Sucesso! '{descricao}' gravado na planilha.")
                        st.balloons()
                        
                        # Limpa estados rápidos após envio bem-sucedido
                        st.session_state.fast_desc = ""
                        st.session_state.fast_val = 0.0
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")
                else:
                    st.error("Por favor, preencha a descrição e defina um valor válido maior que zero.")

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
            
            tipo_lanc = row.get('Tipo', 'Gasto Variável')
            total_parc = int(row['Parcelas_Totais']) if row.get('Parcelas_Totais') else 1
            valor_total = float(str(row['Valor']).replace(',', '.')) if row.get('Valor') else 0.0
            
            # Se for assinatura, o valor se repete mensalmente. Vamos projetar para os próximos 12 meses
            if tipo_lanc == "Assinatura":
                for m in range(12):
                    dt_recorrente = dt_compra + relativedelta(months=m)
                    mes_competencia = calcular_mes_competencia(dt_recorrente, row.get('Forma_Pagamento', 'Dinheiro'))
                    
                    item_proj = row.to_dict()
                    item_proj['Mes_Fatura'] = mes_competencia
                    item_proj['Valor_Parcela'] = valor_total
                    item_proj['Parcela_Atual'] = "Recorrente"
                    lista_projetada.append(item_proj)
            else:
                # Compras normais e parceladas
                val_parcela = valor_total / total_parc if row.get('Parcelado') == 'Sim' else valor_total
                for p in range(total_parc):
                    dt_parcela = dt_compra + relativedelta(months=p)
                    mes_competencia = calcular_mes_competencia(dt_parcela, row.get('Forma_Pagamento', 'Dinheiro'))
                    
                    item_proj = row.to_dict()
                    item_proj['Mes_Fatura'] = mes_competencia
                    item_proj['Valor_Parcela'] = val_parcela
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
                    # Encontra o mês atual no formato YYYY-MM para sugerir como padrão
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
                    cor_saldo = "normal" if saldo_final >= 0 else "inverse"
                    
                    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                    kpi1.metric("🟢 Total Entradas", f"R$ {tot_entradas:,.2f}")
                    kpi2.metric("🔴 Total Despesas", f"R$ {tot_saidas:,.2f}", delta=f"Sobrou: R$ {saldo_final:,.2f}", delta_color=cor_saldo)
                    kpi3.metric("💳 Fatura Nu Bank", f"R$ {fatura_nu:,.2f}")
                    kpi4.metric("💳 Fatura Banco do Brasil", f"R$ {fatura_bb:,.2f}")
                    
                    st.markdown("### Distribuição dos Gastos do Mês")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Por Destinatário (Balanço de Membro/Destino)**")
                        df_resp = df_mes[df_mes['Tipo'] != 'Entrada'].groupby('Responsavel')['Valor_Parcela'].sum()
                        st.bar_chart(df_resp)
                    with c2:
                        st.markdown("**Por Tipo de Gasto (Fixo, Variável, Assinatura)**")
                        df_tipo = df_mes[df_mes['Tipo'] != 'Entrada'].groupby('Tipo')['Valor_Parcela'].sum()
                        st.bar_chart(df_tipo)
                        
                    st.markdown("**Extrato Detalhado do Mês de Competência**")
                    # Ajustado para exibir no formato de data brasileiro
                    df_mes_exibe = df_mes[['Data_Exibicao', 'Descricao', 'Valor_Parcela', 'Parcela_Atual', 'Categoria', 'Responsavel', 'Forma_Pagamento', 'Tipo']].copy()
                    df_mes_exibe.rename(columns={'Data_Exibicao': 'Data', 'Valor_Parcela': 'Valor da Parcela (R$)'}, inplace=True)
                    st.dataframe(df_mes_exibe, use_container_width=True)
                else:
                    st.info("Nenhum mês disponível para análise.")

            # TAB 3: CONTROLE DE PARCELAS ACUMULADAS E ASSINATURAS
            with tabs[2]:
                st.subheader("Dívidas Parceladas e Controle de Assinaturas")
                
                hoje_str = date.today().strftime("%Y-%m")
                
                # Focar apenas em parcelamentos ativos no futuro
                df_futuro = df_projetado[(df_projetado['Mes_Fatura'] > hoje_str) & (df_projetado['Parcelado'] == 'Sim')]
                saldo_devedor_futuro = df_futuro['Valor_Parcela'].sum()
                
                st.warning(f"🏦 **Saldo Devedor Total Acumulado (Faturas Seguintes):** R$ {saldo_devedor_futuro:,.2f}")
                
                col_esquerda, col_direita = st.columns(2)
                
                with col_esquerda:
                    st.markdown("### 💳 Cronograma de Parcelamentos")
                    if not df_futuro.empty:
                        cronograma = df_futuro.groupby(['Mes_Fatura', 'Forma_Pagamento'])['Valor_Parcela'].sum().unstack().fillna(0)
                        st.dataframe(cronograma, use_container_width=True)
                        
                        st.markdown("**Detalhe das Parcelas Futuras**")
                        st.dataframe(df_futuro[['Mes_Fatura', 'Descricao', 'Valor_Parcela', 'Parcela_Atual', 'Forma_Pagamento']], use_container_width=True)
                    else:
                        st.info("Muito bom! Você não tem compras parceladas para os próximos meses.")
                        
                with col_direita:
                    st.markdown("### 🔄 Assinaturas e Recorrências Ativas")
                    # Filtrar itens de assinatura
                    df_assinaturas = df_projetado[df_projetado['Tipo'] == 'Assinatura'].drop_duplicates(subset=['Descricao'])
                    if not df_assinaturas.empty:
                        tot_mensal_ass = df_assinaturas['Valor_Parcela'].sum()
                        st.success(f"📋 **Custo Mensal de Assinaturas:** R$ {tot_mensal_ass:,.2f}")
                        st.dataframe(df_assinaturas[['Descricao', 'Valor_Parcela', 'Categoria', 'Forma_Pagamento']], use_container_width=True)
                    else:
                        st.info("Nenhuma assinatura cadastrada. Registre uma com o tipo 'Assinatura' para acompanhar o impacto automático.")
        else:
            st.info("Sem dados projetados disponíveis.")
    else:
        st.info("Sua planilha na aba 'Lancamentos' está vazia. Faça o primeiro lançamento na aba 'Novo Lançamento' acima para começar!")
