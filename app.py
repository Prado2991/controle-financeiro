import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import gspread
from google.oauth2.service_account import Credentials
import json
import unicodedata

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

def normalizar_df(df):
    # Dicionário mapeando variações de cabeçalhos comuns para o padrão esperado pelo código
    mapeamento_colunas = {
        'data': 'Data',
        'datadecompra': 'Data',
        'data do lancamento': 'Data',
        'data do lançamento': 'Data',
        'carimbo de data/hora': 'Data',
        'descricao': 'Descricao',
        'descrição': 'Descricao',
        'valor': 'Valor',
        'valor (r$)': 'Valor',
        'categoria': 'Categoria',
        'tipo': 'Tipo',
        'tipo de lancamento': 'Tipo',
        'tipo de lançamento': 'Tipo',
        'responsavel': 'Responsavel',
        'responsável': 'Responsavel',
        'para quem?': 'Responsavel',
        'para quem': 'Responsavel',
        'forma_pagamento': 'Forma_Pagamento',
        'forma de pagamento': 'Forma_Pagamento',
        'forma_pagto': 'Forma_Pagamento',
        'forma de pagto': 'Forma_Pagamento',
        'parcelado': 'Parcelado',
        'compra parcelada?': 'Parcelado',
        'parcelado?': 'Parcelado',
        'parcelas_totais': 'Parcelas_Totais',
        'parcelas totais': 'Parcelas_Totais',
        'quantidade de parcelas': 'Parcelas_Totais'
    }
    
    colunas_novas = {}
    for col in df.columns:
        # Remove acentuação e converte para minúsculo sem espaços nas extremidades
        col_limpa = "".join(c for c in unicodedata.normalize('NFD', str(col)) if unicodedata.category(c) != 'Mn')
        col_normalizada = col_limpa.strip().lower()
        
        if col_normalizada in mapeamento_colunas:
            colunas_novas[col] = mapeamento_colunas[col_normalizada]
        else:
            colunas_novas[col] = str(col).strip()
            
    df = df.rename(columns=colunas_novas)
    
    # Garante a existência das colunas necessárias para evitar KeyError no código
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

tabs = st.tabs(["📲 Novo Lançamento", "📊 Dashboard & Resumos", "💳 Controle de Parcelas & Assinaturas", "✏️ Ajustar Lançamentos"])

with tabs[0]:
    st.subheader("Registrar Gasto ou Entrada")
    if sheet_conn is None:
        st.info("⚠️ **O formulário de envio está temporariamente desativado devido a problemas de conexão com a planilha.** \n\nPor favor, verifique a mensagem de erro detalhada acima para saber como corrigir.")
    else:
        with st.form("form_lancamento", clear_on_submit=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                # Exibição nativa em formato brasileiro DD/MM/YYYY
                data = st.date_input("Data do Lançamento", date.today(), format="DD/MM/YYYY")
                descricao = st.text_input(
                    "Descrição", 
                    placeholder="Ex: Sorveteria Sávio, Roupas na Shein, Mercado Muffato"
                )
                valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
                
                # Seletor do Tipo de Gasto
                tipo = st.selectbox(
                    "Tipo de Lançamento", 
                    ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"]
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
                
                categoria = st.selectbox("Categoria", lista_cats)
                
                # MULTISELECT para permitir divisão dinâmica de gastos
                responsavel = st.multiselect(
                    "Para Quem?", 
                    ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"],
                    default=["Jonathan"]
                )
                
                forma_pagto = st.selectbox(
                    "Forma de Pagamento", 
                    ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"]
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
                if not responsavel:
                    st.error("Por favor, selecione pelo menos uma pessoa no campo 'Para Quem?'.")
                elif descricao and valor > 0:
                    # Correção Crítica de Decimais: Converte o valor para formato com vírgula do Sheets brasileiro
                    valor_com_virgula = f"{valor:.2f}".replace('.', ',')
                    
                    # Converte lista de responsáveis para String com vírgulas para salvar no Sheets
                    responsavel_str = ", ".join(responsavel)
                    
                    novo_registro = [
                        str(data), descricao, valor_com_virgula, categoria, tipo, 
                        responsavel_str, forma_pagto, parcelado, int(num_parcelas)
                    ]
                    try:
                        # USER_ENTERED força o Sheets a ler "12,90" como o número doze e noventa
                        sheet_conn.append_row(novo_registro, value_input_option='USER_ENTERED')
                        st.success(f"Sucesso! '{descricao}' gravado na planilha.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erro ao salvar na planilha: {e}")
                else:
                    st.error("Por favor, preencha a descrição e defina um valor válido maior que zero.")

if sheet_conn is not None:
    try:
        raw_data = sheet_conn.get_all_records()
        dados_brutos = pd.DataFrame(raw_data)
        dados_brutos = normalizar_df(dados_brutos)
    except Exception as e:
        dados_brutos = pd.DataFrame()
        st.warning("Aguardando lançamentos na aba 'Lancamentos' para carregar os gráficos.")

    if not dados_brutos.empty:
        # Processar projeções de parcelas futuras e divisões dinâmicas em memória
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
            
            # Lógica inteligente de divisão: Detecta se tem mais de um beneficiário na coluna
            responsavel_campo = str(row.get('Responsavel', 'Jonathan'))
            responsaveis_lista = [r.strip() for r in responsavel_campo.replace('/', ',').split(',') if r.strip()]
            if not responsaveis_lista:
                responsaveis_lista = ["Jonathan"]
            
            num_responsaveis = len(responsaveis_lista)
            
            # Projeção automática de assinaturas recorrentes por 12 meses futuros
            if tipo_lanc == "Assinatura":
                # Divide o valor total pelo número de beneficiários selecionados
                val_dividido = valor_total / num_responsaveis
                
                for m in range(12):
                    dt_recorrente = dt_compra + relativedelta(months=m)
                    mes_competencia = calcular_mes_competencia(dt_recorrente, row.get('Forma_Pagamento', 'Dinheiro'))
                    
                    for r_individual in responsaveis_lista:
                        item_proj = row.to_dict()
                        item_proj['Mes_Fatura'] = mes_competencia
                        item_proj['Valor_Parcela'] = val_dividido
                        item_proj['Responsavel'] = r_individual  # Atribui a parcela dividida ao seu respectivo dono no gráfico
                        item_proj['Parcela_Atual'] = "Recorrente"
                        lista_projetada.append(item_proj)
            else:
                # Compras normais e parceladas
                val_parcela = valor_total / total_parc if row.get('Parcelado') == 'Sim' else valor_total
                val_dividido = val_parcela / num_responsaveis
                
                for p in range(total_parc):
                    dt_parcela = dt_compra + relativedelta(months=p)
                    mes_competencia = calcular_mes_competencia(dt_parcela, row.get('Forma_Pagamento', 'Dinheiro'))
                    
                    for r_individual in responsaveis_lista:
                        item_proj = row.to_dict()
                        item_proj['Mes_Fatura'] = mes_competencia
                        item_proj['Valor_Parcela'] = val_dividido
                        item_proj['Responsavel'] = r_individual  # Atribui a fatura dividida ao gráfico do respectivo dono
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

            with tabs[3]:
                st.subheader("✏️ Alterar ou Excluir Lançamentos")
                st.markdown("Se você digitou alguma informação incorreta ou deseja excluir um registro da planilha, ajuste os campos abaixo:")
                
                # Monta lista de registros com o número exato da linha da planilha
                lista_ajustavel = []
                for idx, row in dados_brutos.iterrows():
                    num_linha = idx + 2  # Linha 1 é o cabeçalho, então a primeira linha de dados é a 2
                    desc = row.get('Descricao', 'Sem Descrição')
                    val = limpar_valor_monetario(row.get('Valor', 0.0))
                    dt = row.get('Data', '')
                    
                    rotulo = f"Linha {num_linha} | {dt} | {desc} - R$ {val}"
                    lista_ajustavel.append({"linha": num_linha, "label": rotulo, "original": row.to_dict()})
                
                # Mostra o mais recente primeiro na lista para facilitar no celular
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
                        # Formulário de Edição Pré-preenchido
                        with st.form("form_edicao_registro"):
                            st.markdown(f"**Editando dados da Linha {linha_planilha}**")
                            col_ed1, col_ed2 = st.columns(2)
                            
                            with col_ed1:
                                # Parsing de data segura
                                try:
                                    dt_orig = datetime.strptime(str(orig.get('Data')).split()[0], "%Y-%m-%d").date()
                                except:
                                    try:
                                        dt_orig = datetime.strptime(str(orig.get('Data')).split()[0], "%d/%m/%Y").date()
                                    except:
                                        dt_orig = date.today()
                                
                                ed_data = st.date_input("Data do Lançamento", dt_orig, format="DD/MM/YYYY")
                                ed_descricao = st.text_input("Descrição", value=orig.get('Descricao', ''))
                                ed_valor = st.number_input("Valor (R$)", min_value=0.0, value=limpar_valor_monetario(orig.get('Valor', 0.0)), step=0.01, format="%.2f")
                                
                                tipo_orig = orig.get('Tipo', 'Gasto Variável')
                                lista_tipos_sup = ["Gasto Variável", "Gasto Fixo", "Entrada", "Assinatura"]
                                idx_tipo_orig = lista_tipos_sup.index(tipo_orig) if tipo_orig in lista_tipos_sup else 0
                                ed_tipo = st.selectbox("Tipo de Lançamento", lista_tipos_sup, index=idx_tipo_orig)
                                
                            with col_ed2:
                                # Categorias dinâmicas com base no tipo na edição
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
                                
                                # Leitura e split de múltiplos responsáveis na edição
                                resp_orig_str = str(orig.get('Responsavel', 'Jonathan'))
                                resp_orig_lista = [r.strip() for r in resp_orig_str.replace('/', ',').split(',') if r.strip()]
                                if not resp_orig_lista:
                                    resp_orig_lista = ["Jonathan"]
                                
                                ed_responsavel = st.multiselect(
                                    "Para Quem?", 
                                    ["Jonathan", "Bruna", "Alice", "Casa", "Gatos"],
                                    default=resp_orig_lista
                                )
                                
                                pgto_orig = orig.get('Forma_Pagamento', 'Cartão Nu')
                                lista_pgto_ed = ["Cartão Nu", "Cartão BB", "Pix", "Dinheiro", "Boleto", "Débito em conta"]
                                idx_pgto_ed = lista_pgto_ed.index(pgto_orig) if pgto_orig in lista_pgto_ed else 0
                                ed_forma_pagto = st.selectbox("Forma de Pagamento", lista_pgto_ed, index=idx_pgto_ed)
                                
                                # Lógica de parcelas na edição
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
                                if not ed_responsavel:
                                    st.error("Selecione ao menos um responsável no campo 'Para Quem?'.")
                                elif ed_descricao and ed_valor > 0:
                                    # Formatação de vírgula também no salvamento de edições
                                    ed_valor_com_virgula = f"{ed_valor:.2f}".replace('.', ',')
                                    ed_responsavel_str = ", ".join(ed_responsavel)
                                    
                                    valores_atualizados = [
                                        str(ed_data), ed_descricao, ed_valor_com_virgula, ed_categoria, ed_tipo,
                                        ed_responsavel_str, ed_forma_pagto, ed_parcelado, int(ed_num_parcelas)
                                    ]
                                    try:
                                        # Atualiza a linha exata no Google Sheets (Colunas A-I) com formatação correta
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
                                # Apaga a linha da planilha
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
