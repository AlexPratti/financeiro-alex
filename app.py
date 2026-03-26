import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
from io import BytesIO
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Finanças Familiar", page_icon="💰", layout="wide")

# --- INICIALIZAÇÃO SEGURA DO ESTADO DA SESSÃO ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "familiar_nome" not in st.session_state:
    st.session_state["familiar_nome"] = ""

# Puxa a lista de usuários dos Secrets de forma global
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

# --- ATUALIZAÇÃO AUTOMÁTICA (10 segundos) ---
st_autorefresh(interval=10000, key="datarefresh")

# --- CONEXÃO COM SUPABASE ---
conn = st.connection("supabase", type=SupabaseConnection, url=st.secrets["URL_SUPABASE"], key=st.secrets["KEY_SUPABASE"])

st.sidebar.write(f"👤 Logado como: **{st.session_state['familiar_nome']}**")
st.title("📊 Controle Financeiro Familiar")

# --- BUSCA E FILTRAGEM DE DADOS ---
resp_desp = conn.table("controle_financeiro").select("*").order("created_at", desc=True).execute()
resp_ent = conn.table("entradas_financeiras").select("*").order("created_at", desc=True).execute()
resp_cards = conn.table("gestao_cartoes_vinc").select("*").execute()

df_raw = pd.DataFrame(resp_desp.data)
df_ent_raw = pd.DataFrame(resp_ent.data)
df_cards_config = pd.DataFrame(resp_cards.data)

meses_trad = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}

# Inicializa dicionário de receitas por usuário dinamicamente
receitas_atuais_usuarios = {u: 0.0 for u in usuarios_permitidos}
total_receitas_mes_atual = 0.0

if not df_ent_raw.empty:
    df_ent_raw['data_dt'] = pd.to_datetime(df_ent_raw['data_registro'], format='%d/%m/%Y', errors='coerce')
    df_ent_raw = df_ent_raw.dropna(subset=['data_dt'])
    df_ent_raw['Mes_PT'] = df_ent_raw['data_dt'].dt.month.map(meses_trad)
    df_ent_raw['Ano'] = df_ent_raw['data_dt'].dt.year.astype(str)
    
    hoje = datetime.now()
    df_ent_atual = df_ent_raw[(df_ent_raw['Mes_PT'] == meses_trad[hoje.month]) & (df_ent_raw['Ano'] == str(hoje.year))]
    total_receitas_mes_atual = df_ent_atual['valor'].sum()
    
    for u in usuarios_permitidos:
        receitas_atuais_usuarios[u] = df_ent_atual[df_ent_atual['familiar'] == u]['valor'].sum()

if not df_raw.empty:
    df_raw['data_dt'] = pd.to_datetime(df_raw['data_registro'], format='%d/%m/%Y', errors='coerce')
    df_raw = df_raw.dropna(subset=['data_dt'])
    df_raw['Mes_PT'] = df_raw['data_dt'].dt.month.map(meses_trad)
    df_raw['Ano'] = df_raw['data_dt'].dt.year.astype(str)

# --- FORMULÁRIOS DE ENTRADA ---
st.subheader("📝 Novo Lançamento")
tab_gastos, tab_receitas, tab_gestao_cartoes = st.tabs(["💸 Registrar Despesa", "📈 Registrar Saldo/Entrada", "💳 Gestão de Cartões"])

with tab_gastos:
    st.info(f"💰 **Receitas Totais do Mês Atual:** R$ {total_receitas_mes_atual:,.2f}")
    with st.form("form_despesa", clear_on_submit=True):
        desc = st.text_input("Descrição da Despesa")
        c1, c2 = st.columns(2)
        with c1:
            valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f", key="input_valor_despesa")
            cat = st.selectbox("Categoria", ["Água", "Energia", "Internet", "Lojas Virtuais", "Carro Diversos", "Carro Combustível", "Lazer", "Cartão", "Supermercado", "Farmácia", "Outros"])
        with c2:
            # Lista dinâmica de métodos conforme solicitado
            metodos_fixos = ["Dinheiro/Pix", "Cartão de Débito"]
            dict_cartoes = {row['apelido_cartao']: row['id'] for _, row in df_cards_config.iterrows()} if not df_cards_config.empty else {}
            opcoes_metodo = metodos_fixos + list(dict_cartoes.keys())
            metodo_escolhido = st.selectbox("Método de Pagamento", opcoes_metodo)
        
        if st.form_submit_button("🚀 Registrar Despesa"):
            if desc and valor > 0:
                id_card_vinculo = dict_cartoes.get(metodo_escolhido)
                metodo_final = "Cartão de Crédito" if id_card_vinculo else metodo_escolhido
                
                nova_linha = {
                    "data_registro": datetime.now().strftime("%d/%m/%Y"),
                    "descricao": desc, "valor": valor, "categoria": cat, "metodo": metodo_final,
                    "familiar": st.session_state["familiar_nome"],
                    "id_vinc_cartao": id_card_vinculo
                }
                conn.table("controle_financeiro").insert(nova_linha).execute()
                st.success("✅ Despesa Registrada!")
                st.rerun()

with tab_receitas:
    cols_rec = st.columns(len(usuarios_permitidos))
    for i, u in enumerate(usuarios_permitidos):
        cols_rec[i].metric(f"Entradas {u} (Mês)", f"R$ {receitas_atuais_usuarios[u]:,.2f}")
    
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

with tab_gestao_cartoes:
    st.subheader("⚙️ Configurar Cartões de Crédito")
    with st.form("form_novo_cartao", clear_on_submit=True):
        f1, f2, f3 = st.columns(3)
        b_nome = f1.text_input("Nome do Banco")
        b_apelido = f2.text_input("Apelido/Identificador (Ex: Final 1234)")
        b_venc = f3.number_input("Dia do Vencimento", 1, 31, 10)
        if st.form_submit_button("Salvar Cartão"):
            if b_nome and b_apelido:
                conn.table("gestao_cartoes_vinc").insert({"banco_nome": b_nome, "apelido_cartao": b_apelido, "dia_vencimento": b_venc}).execute()
                st.success("Cartão cadastrado!")
                st.rerun()
    
    if not df_cards_config.empty:
        st.divider()
        for _, c_row in df_cards_config.iterrows():
            col_a, col_b = st.columns([3, 1])
            col_a.write(f"💳 **{c_row['banco_nome']}** - {c_row['apelido_cartao']} (Vencimento dia {c_row['dia_vencimento']})")
            if col_b.button("🗑️ Excluir", key=f"del_c_{c_row['id']}"):
                conn.table("gestao_cartoes_vinc").delete().eq("id", c_row['id']).execute()
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
    
    fams_disp = ["Todos"] + sorted(list(set(usuarios_permitidos) | set(df_raw['familiar'].unique())))
    familiar_filter = st.sidebar.selectbox("Filtrar por Familiar", fams_disp)

    st.sidebar.divider()
    mostrar_historico = st.sidebar.checkbox("Exibir Histórico Detalhado", value=True)

    df = df_ano[df_ano['Mes_PT'] == mes_sel].copy()
    df_e = df_ent_raw[(df_ent_raw['Ano'] == ano_sel) & (df_ent_raw['Mes_PT'] == mes_sel)].copy() if not df_ent_raw.empty else pd.DataFrame()

    if familiar_filter != "Todos":
        df = df[df['familiar'] == familiar_filter]
        if not df_e.empty:
            df_e = df_e[df_e['familiar'] == familiar_filter]

    # --- MÉTRICAS DINÂMICAS COM LÓGICA DE VENCIMENTO ---
    hoje_dia = datetime.now().day
    total_receitas = df_e["valor"].sum() if not df_e.empty else 0.0
    
    valor_em_aberto_cartao = 0.0
    valor_quitado_cartao = 0.0
    total_despesas_efetivas = 0.0 

    for _, row in df.iterrows():
        if row['metodo'] == "Cartão de Crédito":
            v_info = df_cards_config[df_cards_config['id'] == row['id_vinc_cartao']]
            v_dia = v_info['dia_vencimento'].values[0] if not v_info.empty else 32
            if hoje_dia < v_dia:
                valor_em_aberto_cartao += row['valor']
            else:
                valor_quitado_cartao += row['valor']
                total_despesas_efetivas += row['valor']
        else:
            total_despesas_efetivas += row['valor']

    saldo_total_real = total_receitas - total_despesas_efetivas
    total_cartao_bruto = df[df["metodo"] == "Cartão de Crédito"]["valor"].sum() if not df.empty else 0.0
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric(f"📈 Receitas ({mes_sel})", f"R$ {total_receitas:,.2f}")
    c2.metric(f"📉 Despesas Realizadas", f"R$ {total_despesas_efetivas:,.2f}", help="Soma de Pix/Débito + Cartões já vencidos.")
    c3.metric("⚖️ Saldo Real Atual", f"R$ {saldo_total_real:,.2f}")

    st.info(f"💳 **Info Cartões:** Em Aberto (Futuro): R$ {valor_em_aberto_cartao:,.2f} | Quitado (No mês): R$ {valor_quitado_cartao:,.2f} | Total: R$ {total_cartao_bruto:,.2f}")

    st.write("---")
    cols_individual = st.columns(len(usuarios_permitidos) + 1)
    for i, u in enumerate(usuarios_permitidos):
        rec_u = df_e[df_e['familiar'] == u]['valor'].sum() if not df_e.empty else 0.0
        desp_u_efetiva = 0.0
        df_u = df[df['familiar'] == u]
        for _, r_u in df_u.iterrows():
            if r_u['metodo'] != "Cartão de Crédito":
                desp_u_efetiva += r_u['valor']
            else:
                v_info_u = df_cards_config[df_cards_config['id'] == r_u['id_vinc_cartao']]
                v_dia_u = v_info_u['dia_vencimento'].values[0] if not v_info_u.empty else 32
                if hoje_dia >= v_dia_u:
                    desp_u_efetiva += r_u['valor']
        cols_individual[i].metric(f"⚖️ Saldo ({u})", f"R$ {(rec_u - desp_u_efetiva):,.2f}")
    
    cols_individual[-1].metric("💰 Soma dos Saldos", f"R$ {saldo_total_real:,.2f}")

    if not df.empty:
        st.subheader(f"Análise: {mes_sel}/{ano_sel} - [{familiar_filter}]")
        st.bar_chart(df.groupby("categoria")["valor"].sum())

        def gerar_excel(data_frame):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                data_frame.to_excel(writer, index=False, sheet_name='Lançamentos')
            return output.getvalue()

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.download_button(label="📥 Baixar Dados (Excel)", data=gerar_excel(df), file_name=f"financas_{mes_sel}.xlsx")
        with col_b2:
            if st.button("🗑️ Limpar Despesas do Mês", type="primary", use_container_width=True):
                for id_del in df['id'].tolist():
                    conn.table("controle_financeiro").delete().eq("id", id_del).execute()
                st.rerun()

        if mostrar_historico:
            st.divider()
            st.subheader(f"Histórico de Despesas: {familiar_filter}")
            h = st.columns([1, 1.5, 1, 1.5, 1, 0.5])
            for col, text in zip(h, ["**Data**", "**Descrição**", "**Valor**", "**Método**", "**Familiar**", "**Ação**"]): col.write(text)
            
            for _, row in df.iterrows():
                r = st.columns([1, 1.5, 1, 1.5, 1, 0.5])
                r[0].write(row['data_registro'])
                r[1].write(row['descricao'])
                r[2].write(f"R$ {row['valor']:.2f}")
                
                # Exibe o apelido do cartão no histórico
                metodo_txt = row['metodo']
                if row['metodo'] == "Cartão de Crédito":
                    v_label = df_cards_config[df_cards_config['id'] == row['id_vinc_cartao']]
                    if not v_label.empty: metodo_txt = f"💳 {v_label['apelido_cartao'].values[0]}"
                
                r[3].write(metodo_txt)
                r[4].write(row['familiar'])
                if r[5].button("🗑️", key=f"del_d_{row['id']}"):
                    conn.table("controle_financeiro").delete().eq("id", row['id']).execute()
                    st.rerun()

            if not df_e.empty:
                st.divider()
                st.subheader(f"Histórico de Entradas: {familiar_filter}")
                he = st.columns([1, 2, 1, 1.5, 0.5])
                for col, text in zip(he, ["**Data**", "**Descrição**", "**Valor**", "**Origem**", "**Ação**"]): col.write(text)
                for _, row_e in df_e.iterrows():
                    re = st.columns([1, 2, 1, 1.5, 0.5])
                    re[0].write(row_e['data_registro'])
                    re[1].write(row_e['descricao'])
                    re[2].write(f"R$ {row_e['valor']:.2f}")
                    re[3].write(row_e['tipo_entrada'])
                    if re[4].button("🗑️", key=f"del_e_{row_e['id']}"):
                        conn.table("entradas_financeiras").delete().eq("id", row_e['id']).execute()
                        st.rerun()
else:
    st.info("Nenhum dado encontrado.")

if st.sidebar.button("Sair / Trocar Usuário"):
    st.session_state["autenticado"] = False
    st.session_state["familiar_nome"] = ""
    st.rerun()
