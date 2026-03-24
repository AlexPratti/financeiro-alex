import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
from io import BytesIO
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Finanças Alex", page_icon="💰", layout="wide")

# --- INICIALIZAÇÃO SEGURA DO ESTADO DA SESSÃO ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "familiar_nome" not in st.session_state:
    st.session_state["familiar_nome"] = ""

# --- VALIDAÇÃO DE USUÁRIO ---
if not st.session_state["autenticado"]:
    st.title("🔐 Acesso ao Sistema")
    user_input = st.text_input("Informe seu usuário:").strip().capitalize()
    if st.button("Acessar"):
        if user_input.lower() in ["merlim", "pratti"]:
            st.session_state["autenticado"] = True
            st.session_state["familiar_nome"] = user_input
            st.rerun()
        else:
            st.error("Usuário não autorizado.")
    st.stop()

# --- ATUALIZAÇÃO AUTOMÁTICA (20 segundos) ---
st_autorefresh(interval=20000, key="datarefresh")

# --- CONEXÃO COM SUPABASE ---
conn = st.connection("supabase", type=SupabaseConnection, url=st.secrets["URL_SUPABASE"], key=st.secrets["KEY_SUPABASE"])

st.sidebar.write(f"👤 Logado como: **{st.session_state['familiar_nome']}**")
st.title("📊 Controle Financeiro Familiar")

# --- BUSCA E FILTRAGEM DE DADOS (Movido para cima para usar nos formulários) ---
resp_desp = conn.table("controle_financeiro").select("*").order("created_at", desc=True).execute()
resp_ent = conn.table("entradas_financeiras").select("*").order("created_at", desc=True).execute()

df_raw = pd.DataFrame(resp_desp.data)
df_ent_raw = pd.DataFrame(resp_ent.data)

# Processamento inicial de datas para métricas rápidas
meses_trad = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}
total_receitas_mes = 0.0
receita_merlim = 0.0
receita_pratti = 0.0

if not df_ent_raw.empty:
    df_ent_raw['data_dt'] = pd.to_datetime(df_ent_raw['data_registro'], format='%d/%m/%Y', errors='coerce')
    df_ent_raw = df_ent_raw.dropna(subset=['data_dt'])
    df_ent_raw['Mes_PT'] = df_ent_raw['data_dt'].dt.month.map(meses_trad)
    df_ent_raw['Ano'] = df_ent_raw['data_dt'].dt.year.astype(str)
    
    # Cálculo para exibição nos formulários (Mês/Ano atual)
    hoje = datetime.now()
    df_ent_atual = df_ent_raw[(df_ent_raw['Mes_PT'] == meses_trad[hoje.month]) & (df_ent_raw['Ano'] == str(hoje.year))]
    total_receitas_mes = df_ent_atual['valor'].sum()
    receita_merlim = df_ent_atual[df_ent_atual['familiar'] == 'Merlim']['valor'].sum()
    receita_pratti = df_ent_atual[df_ent_atual['familiar'] == 'Pratti']['valor'].sum()

if not df_raw.empty:
    df_raw['data_dt'] = pd.to_datetime(df_raw['data_registro'], format='%d/%m/%Y', errors='coerce')
    df_raw = df_raw.dropna(subset=['data_dt'])
    df_raw['Mes_PT'] = df_raw['data_dt'].dt.month.map(meses_trad)
    df_raw['Ano'] = df_raw['data_dt'].dt.year.astype(str)

# --- FORMULÁRIOS DE ENTRADA ---
st.subheader("📝 Novo Lançamento")
tab_gastos, tab_receitas = st.tabs(["💸 Registrar Despesa", "📈 Registrar Saldo/Entrada"])

with tab_gastos:
    st.info(f"💰 **Receitas Totais do Mês Atual:** R$ {total_receitas_mes:,.2f}")
    with st.form("form_despesa", clear_on_submit=True):
        desc = st.text_input("Descrição da Despesa")
        c1, c2 = st.columns(2)
        with c1:
            valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f", key="input_valor_despesa")
            cat = st.selectbox("Categoria", ["Água", "Energia", "Internet", "Lojas Virtuais", "Carro Diversos", "Carro Combustível", "Lazer", "Cartão", "Supermercado", "Farmácia", "Outros"])
        with c2:
            metodo = st.selectbox("Método", ["Dinheiro/Pix", "Cartão de Crédito", "Cartão de Débito"])
        
        if st.form_submit_button("🚀 Registrar Despesa"):
            if desc and valor > 0:
                nova_linha = {
                    "data_registro": datetime.now().strftime("%d/%m/%Y"),
                    "descricao": desc, "valor": valor, "categoria": cat, "metodo": metodo,
                    "familiar": st.session_state["familiar_nome"]
                }
                conn.table("controle_financeiro").insert(nova_linha).execute()
                st.success("✅ Despesa Registrada!")
                st.rerun()

with tab_receitas:
    col_m, col_p = st.columns(2)
    col_m.metric("Entradas Merlim (Mês)", f"R$ {receita_merlim:,.2f}")
    col_p.metric("Entradas Pratti (Mês)", f"R$ {receita_pratti:,.2f}")
    
    with st.form("form_entrada", clear_on_submit=True):
        desc_e = st.text_input("Descrição da Receita (Ex: Salário)")
        ce1, ce2 = st.columns(2)
        with ce1:
            valor_e = st.number_input("Valor Recebido (R$)", min_value=0.0, step=0.01, format="%.2f", key="input_valor_entrada")
        with ce2:
            tipo_e = st.selectbox("Origem", ["Salário", "Adiantamento Salarial", "Serviços Autônomos", "Outros"])
        
        if st.form_submit_button("💰 Registrar Entrada"):
            if desc_e and valor_e > 0:
                nova_entrada = {
                    "data_registro": datetime.now().strftime("%d/%m/%Y"),
                    "descricao": desc_e, "valor": valor_e, "tipo_entrada": tipo_e,
                    "familiar": st.session_state["familiar_nome"]
                }
                conn.table("entradas_financeiras").insert(nova_entrada).execute()
                st.success("✅ Entrada Registrada!")
                st.rerun()

# --- FILTRAGEM DE DADOS NA SIDEBAR ---
if not df_raw.empty:
    st.sidebar.header("🔍 Filtros")
    anos_list = sorted(df_raw['Ano'].unique(), reverse=True)
    ano_sel = st.sidebar.selectbox("Ano", anos_list)
    
    meses_ordem = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    df_ano = df_raw[df_raw['Ano'] == ano_sel]
    meses_disp = [m for m in meses_ordem if m in df_ano['Mes_PT'].unique()]
    mes_sel = st.sidebar.selectbox("Mês", meses_disp)
    
    fams_disp = ["Todos"] + sorted(df_raw['familiar'].unique().tolist())
    familiar_filter = st.sidebar.selectbox("Filtrar por Familiar", fams_disp)

    # --- NOVO: CONTROLE DE VISIBILIDADE ---
    st.sidebar.divider()
    mostrar_historico = st.sidebar.checkbox("Exibir Histórico Detalhado", value=True)

    # Filtragem Final dos DataFrames
    df = df_ano[df_ano['Mes_PT'] == mes_sel].copy()
    df_e = pd.DataFrame()
    if not df_ent_raw.empty:
        df_e = df_ent_raw[(df_ent_raw['Ano'] == ano_sel) & (df_ent_raw['Mes_PT'] == mes_sel)].copy()

    if familiar_filter != "Todos":
        df = df[df['familiar'] == familiar_filter]
        if not df_e.empty:
            df_e = df_e[df_e['familiar'] == familiar_filter]

    # --- MÉTRICAS ---
    st.divider()
    c1, c2, c3 = st.columns(3)
    
    total_despesas = df["valor"].sum() if not df.empty else 0.0
    total_receitas = df_e["valor"].sum() if not df_e.empty else 0.0
    saldo_final = total_receitas - total_despesas
    total_cartao = df[df["metodo"] == "Cartão de Crédito"]["valor"].sum() if not df.empty else 0.0
    
    c1.metric(f"📈 Receitas ({mes_sel})", f"R$ {total_receitas:,.2f}")
    c2.metric(f"📉 Despesas ({mes_sel})", f"R$ {total_despesas:,.2f}")
    c3.metric("⚖️ Saldo do Período", f"R$ {saldo_final:,.2f}", delta=f"Cartão: R$ {total_cartao:,.2f}", delta_color="inverse")

    if not df.empty:
        st.subheader(f"Análise: {mes_sel}/{ano_sel} - [{familiar_filter}]")
        resumo_cat = df.groupby("categoria")["valor"].sum()
        st.bar_chart(resumo_cat)

        def gerar_excel(data_frame):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                data_frame.to_excel(writer, index=False, sheet_name='Lançamentos')
            return output.getvalue()

        excel_data = gerar_excel(df)
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.download_button(label="📥 Baixar Dados (Excel)", data=excel_data, file_name=f"financas_{mes_sel}.xlsx")
        
        with col_b2:
            if st.button("🗑️ Limpar Despesas do Mês", type="primary", use_container_width=True):
                for id_del in df['id'].tolist():
                    conn.table("controle_financeiro").delete().eq("id", id_del).execute()
                st.rerun()

        # --- EXIBIÇÃO CONDICIONAL DO HISTÓRICO ---
        if mostrar_historico:
            st.divider()
            # Histórico de Despesas
            st.subheader(f"Histórico de Despesas: {familiar_filter}")
            h1, h2, h3, h4, h5, h6 = st.columns([1, 1.5, 1, 1.2, 1, 0.5])
            h1.write("**Data**"); h2.write("**Descrição**"); h3.write("**Valor**"); h4.write("**Método**"); h5.write("**Familiar**"); h6.write("**Ação**")
            
            for _, row in df.iterrows():
                r1, r2, r3, r4, r5, r6 = st.columns([1, 1.5, 1, 1.2, 1, 0.5])
                r1.write(row['data_registro'])
                r2.write(row['descricao'])
                r3.write(f"R$ {row['valor']:.2f}")
                r4.write(row['metodo'])
                r5.write(row['familiar'])
                if r6.button("🗑️", key=f"del_d_{row['id']}"):
                    conn.table("controle_financeiro").delete().eq("id", row['id']).execute()
                    st.rerun()

            # Histórico de Entradas
            if not df_e.empty:
                st.divider()
                st.subheader(f"Histórico de Entradas: {familiar_filter}")
                he1, he2, he3, he4, he5 = st.columns([1, 2, 1, 1.5, 0.5])
                he1.write("**Data**"); he2.write("**Descrição**"); he3.write("**Valor**"); he4.write("**Origem**"); he5.write("**Ação**")
                for _, row_e in df_e.iterrows():
                    re1, re2, re3, re4, re5 = st.columns([1, 2, 1, 1.5, 0.5])
                    re1.write(row_e['data_registro'])
                    re2.write(row_e['descricao'])
                    re3.write(f"R$ {row_e['valor']:.2f}")
                    re4.write(row_e['tipo_entrada'])
                    if re5.button("🗑️", key=f"del_e_{row_e['id']}"):
                        conn.table("entradas_financeiras").delete().eq("id", row_e['id']).execute()
                        st.rerun()
        else:
            st.info("💡 O histórico detalhado está oculto. Use a barra lateral para exibir.")
else:
    st.info("Nenhum dado encontrado para os filtros selecionados.")

# --- BOTÃO SAIR ---
if st.sidebar.button("Sair / Trocar Usuário"):
    st.session_state["autenticado"] = False
    st.session_state["familiar_nome"] = ""
    st.rerun()
