import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import pytz
from datetime import datetime, timedelta
import calendar
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Finanças Familiar", page_icon="💰", layout="wide")

# --- AJUSTE DE FUSO HORÁRIO (BRASIL) ---
fuso_br = pytz.timezone('America/Sao_Paulo')
agora_br = datetime.now(fuso_br)

# --- INICIALIZAÇÃO SEGURA DO ESTADO DA SESSÃO ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "familiar_nome" not in st.session_state:
    st.session_state["familiar_nome"] = ""

usuarios_permitidos = st.secrets["USUARIOS_PERMITIDOS"]

# --- VALIDAÇÃO DE USUÁRIO ---
if not st.session_state["autenticado"]:
    st.title("🔐 Acesso ao Sistema")
    user_input = st.text_input("Informe seu usuário:").strip().capitalize()
    if st.button("Acessar"):
        if user_input.lower() in [u.lower() for u in usuarios_permitidos]:
            st.session_state["autenticado"] = True
            st.session_state["familiar_nome"] = user_input
            st.rerun()
        else:
            st.error("Usuário não autorizado.")
    st.stop()

st_autorefresh(interval=30000, key="datarefresh")

# --- CONEXÃO COM SUPABASE ---
conn = st.connection("supabase", type=SupabaseConnection, url=st.secrets["URL_SUPABASE"], key=st.secrets["KEY_SUPABASE"])

st.sidebar.write(f"👤 Logado como: **{st.session_state['familiar_nome']}**")
st.title("📊 Controle Financeiro Familiar")

# --- BUSCA DE DADOS ---
resp_desp = conn.table("controle_financeiro").select("*").order("created_at", desc=True).execute()
resp_ent = conn.table("entradas_financeiras").select("*").order("created_at", desc=True).execute()
resp_cards = conn.table("gestao_cartoes_vinc").select("*").execute()

df_raw = pd.DataFrame(resp_desp.data)
df_ent_raw = pd.DataFrame(resp_ent.data)
df_cards_config = pd.DataFrame(resp_cards.data)

meses_trad = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}

# Processamento de Datas
if not df_raw.empty:
    df_raw['data_dt'] = pd.to_datetime(df_raw['data_registro'], format='%d/%m/%Y', errors='coerce')
    df_raw['Mes_PT'] = df_raw['data_dt'].dt.month.map(meses_trad)
    df_raw['Ano'] = df_raw['data_dt'].dt.year.astype(str)

if not df_ent_raw.empty:
    df_ent_raw['data_dt'] = pd.to_datetime(df_ent_raw['data_registro'], format='%d/%m/%Y', errors='coerce')
    df_ent_raw['Mes_PT'] = df_ent_raw['data_dt'].dt.month.map(meses_trad)
    df_ent_raw['Ano'] = df_ent_raw['data_dt'].dt.year.astype(str)

# --- FILTROS SIDEBAR ---
st.sidebar.header("🔍 Filtros de Exibição")
anos_list = sorted(df_raw['Ano'].unique(), reverse=True) if not df_raw.empty else [str(agora_br.year)]
ano_sel = st.sidebar.selectbox("Ano", anos_list)

meses_ordem = list(meses_trad.values())
mes_sel = st.sidebar.selectbox("Mês", meses_ordem, index=agora_br.month-1)

fams_disp = ["Ocultar", "Todos"] + sorted(usuarios_permitidos)
familiar_filter = st.sidebar.selectbox("Filtrar por Familiar (Visão)", fams_disp, index=1)

mostrar_historico = st.sidebar.checkbox("Exibir Histórico Detalhado", value=True)

# --- ABAS ---
tab_gastos, tab_receitas, tab_cartoes, tab_dashboard = st.tabs(["💸 Despesas", "📈 Entradas", "💳 Cartões", "📊 Dashboard"])

# --- ABA 1: DESPESAS ---
with tab_gastos:
    st.subheader("📝 Novo Lançamento")
    metodos_fixos = ["Dinheiro/Pix", "Cartão de Débito"]
    dict_cartoes = {row['apelido_cartao']: {'id': row['id'], 'venc': row['dia_vencimento']} for _, row in df_cards_config.iterrows()} if not df_cards_config.empty else {}
    opcoes_metodo = metodos_fixos + list(dict_cartoes.keys())
    
    metodo_escolhido = st.selectbox("Método de Pagamento", opcoes_metodo)
    is_cartao = metodo_escolhido in dict_cartoes.keys()

    with st.form("form_despesa", clear_on_submit=True):
        desc = st.text_input("Descrição")
        c1, c2 = st.columns(2)
        with c1:
            valor_total = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
            cat = st.selectbox("Categoria", ["Água", "Energia", "Internet", "Lojas Virtuais", "Carro", "Lazer", "Supermercado", "Outros"])
        with c2:
            num_parcelas = st.number_input("Parcelas", min_value=1, max_value=24, value=1, disabled=not is_cartao)
        
        if st.form_submit_button("Registrar"):
            if desc and valor_total > 0:
                skip_month = 0
                id_card_vinculo = None
                dia_alvo = agora_br.day
                
                if is_cartao:
                    card_info = dict_cartoes.get(metodo_escolhido)
                    id_card_vinculo = card_info['id']
                    venc = card_info['venc']
                    dia_alvo = venc
                    fechamento = max(1, venc - 7)
                    if agora_br.day >= fechamento: skip_month = 1
                
                for i in range(num_parcelas):
                    mes_t = agora_br.month + i + skip_month
                    ano_a = agora_br.year + (mes_t - 1) // 12
                    mes_a = (mes_t - 1) % 12 + 1
                    _, last_d = calendar.monthrange(ano_a, mes_a)
                    data_reg = datetime(ano_a, mes_a, min(dia_alvo, last_d)).strftime("%d/%m/%Y")
                    
                    conn.table("controle_financeiro").insert({
                        "data_registro": data_reg, "descricao": f"{desc} ({i+1}/{num_parcelas})" if num_parcelas > 1 else desc,
                        "valor": valor_total/num_parcelas, "categoria": cat, "familiar": st.session_state["familiar_nome"],
                        "metodo": "Cartão de Crédito" if is_cartao else metodo_escolhido, "id_vinc_cartao": id_card_vinculo
                    }).execute()
                st.success("Registrado!")
                st.rerun()

# --- ABA 2: ENTRADAS ---
with tab_receitas:
    with st.form("form_entrada", clear_on_submit=True):
        desc_e = st.text_input("Descrição da Receita")
        ce1, ce2 = st.columns(2)
        valor_e = ce1.number_input("Valor (R$)", min_value=0.0)
        tipo_e = ce2.selectbox("Origem", ["Salário", "Serviços", "Outros"])
        if st.form_submit_button("Registrar Entrada"):
            conn.table("entradas_financeiras").insert({
                "data_registro": agora_br.strftime("%d/%m/%Y"), "descricao": desc_e, 
                "valor": valor_e, "tipo_entrada": tipo_e, "familiar": st.session_state["familiar_nome"]
            }).execute()
            st.rerun()

# --- ABA 3: GESTÃO DE CARTÕES ---
with tab_cartoes:
    st.subheader("⚙️ Configurar Cartões")
    with st.form("novo_cartao"):
        f1, f2, f3 = st.columns(3)
        b_nome = f1.text_input("Banco")
        b_apelido = f2.text_input("Nome do Cartão (Ex: Black 123)")
        b_venc = f3.number_input("Dia Vencimento", 1, 31, 10)
        if st.form_submit_button("Salvar"):
            conn.table("gestao_cartoes_vinc").insert({"banco_nome": b_nome, "apelido_cartao": b_apelido, "dia_vencimento": b_venc}).execute()
            st.rerun()
    
    if not df_cards_config.empty:
        for _, r in df_cards_config.iterrows():
            ca, cb = st.columns([4,1])
            ca.write(f"💳 {r['banco_nome']} - **{r['apelido_cartao']}** (Vence dia {r['dia_vencimento']})")
            if cb.button("Excluir", key=f"del_c_{r['id']}"):
                conn.table("gestao_cartoes_vinc").delete().eq("id", r['id']).execute()
                st.rerun()

# --- ABA 4: DASHBOARD E HISTÓRICO ---
with tab_dashboard:
    if familiar_filter == "Ocultar":
        st.warning("⚠️ Selecione um familiar ou 'Todos' na barra lateral para ver os dados.")
    else:
        # 1. Filtro base por Mês/Ano
        df_view = df_raw[(df_raw['Ano'] == ano_sel) & (df_raw['Mes_PT'] == mes_sel)] if not df_raw.empty else pd.DataFrame()
        df_ent_atual = df_ent_raw[(df_ent_raw['Ano'] == ano_sel) & (df_ent_raw['Mes_PT'] == mes_sel)] if not df_ent_raw.empty else pd.DataFrame()

        if familiar_filter != "Todos":
            df_view = df_view[df_view['familiar'] == familiar_filter] if not df_view.empty else df_view
            df_ent_atual = df_ent_atual[df_ent_atual['familiar'] == familiar_filter] if not df_ent_atual.empty else df_ent_atual

        # 2. CÁLCULO DE SALDO ACUMULADO (PASSADO)
        mes_num_sel = list(meses_trad.keys())[list(meses_trad.values()).index(mes_sel)]
        data_limite_inicio_mes = datetime(int(ano_sel), mes_num_sel, 1).date()
        
        receita_passada = df_ent_raw[df_ent_raw['data_dt'].dt.date < data_limite_inicio_mes]['valor'].sum() if not df_ent_raw.empty else 0.0
        despesa_passada = df_raw[df_raw['data_dt'].dt.date < data_limite_inicio_mes]['valor'].sum() if not df_raw.empty else 0.0
        saldo_inicial_mes = receita_passada - despesa_passada
        
        receita_mes_total = df_ent_atual['valor'].sum() if not df_ent_atual.empty else 0.0
        receita_total_disponivel = saldo_inicial_mes + receita_mes_total

        # 3. LÓGICA DE DÉBITO EFETIVO (O que já saiu do bolso HOJE)
        total_desp_efetiva = 0.0
        if not df_view.empty:
            for _, row in df_view.iterrows():
                data_vencimento_despesa = row['data_dt'].date()
                
                # Se for Cartão de Crédito, a data de vencimento é o dia configurado no cartão
                if row['metodo'] == "Cartão de Crédito":
                    v_info = df_cards_config[df_cards_config['id'] == row['id_vinc_cartao']]
                    v_dia = int(v_info['dia_vencimento'].iloc[0]) if not v_info.empty else 28
                    # Ajusta a data de vencimento para o dia do cartão naquele mês/ano
                    try:
                        data_vencimento_despesa = datetime(row['data_dt'].year, row['data_dt'].month, v_dia).date()
                    except: # Caso o dia não exista no mês (ex: 31 de fevereiro)
                        data_vencimento_despesa = datetime(row['data_dt'].year, row['data_dt'].month, 28).date()

                # SÓ DESCONTA SE A DATA JÁ PASSOU OU É HOJE
                if data_vencimento_despesa <= agora_br.date():
                    total_desp_efetiva += row['valor']

        # 4. EXIBIÇÃO DOS CARDS
        c1, c2, c3 = st.columns(3)
        c1.metric("📈 Receita Total (c/ Saldo)", f"R$ {receita_total_disponivel:,.2f}")
        c2.metric("📉 Despesas Efetivadas", f"R$ {total_desp_efetiva:,.2f}", help="Somente o que já venceu até hoje.")
        c3.metric("⚖️ Saldo Real Agora", f"R$ {(receita_total_disponivel - total_desp_efetiva):,.2f}")

        # 5. GRÁFICO E HISTÓRICO (Mostra tudo do mês para planejamento)
        if not df_view.empty:
            st.subheader(f"Planejamento de Gastos: {mes_sel}")
            st.bar_chart(df_view.groupby("categoria")["valor"].sum())

        if mostrar_historico:
            st.subheader("📋 Histórico Detalhado do Mês")
            if not df_view.empty:
                for _, r in df_view.iterrows():
                    col = st.columns([1, 2, 1, 1, 0.5])
                    col[0].write(r['data_registro'])
                    col[1].write(r['descricao'])
                    col[2].write(f"R$ {r['valor']:.2f}")
                    col[3].write(r['familiar'])
                    if col[4].button("🗑️", key=f"del_d_{r['id']}"):
                        conn.table("controle_financeiro").delete().eq("id", r['id']).execute()
                        st.rerun()

# --- BOTÃO SAIR ---
if st.sidebar.button("Sair / Trocar Usuário"):
    st.session_state["autenticado"] = False
    st.rerun()
