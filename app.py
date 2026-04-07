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
    st.title("🔐 Acesso ao Controle Financeiro")
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
st.title("📊 Controle Financeiro Família Pratti")

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
            cat = st.selectbox("Categoria", ["Água", "Energia", "Internet", "Lojas Virtuais", "Carro", "Combustível", "Farmácia", "Lazer", "Dízimo", "Supermercado", "Outros"])
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
        tipo_e = ce2.selectbox("Origem", ["Salário", "Adiantamento", "Pix Recebidos", "Valores Recebidos", "Outros"])
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
            with st.expander(f"💳 {r['banco_nome']} - **{r['apelido_cartao']}** (Vence dia {r['dia_vencimento']})"):
                ca, cb = st.columns([4,1])
                ca.write(f"Configurações do cartão {r['apelido_cartao']}")
                if cb.button("Excluir Cartão", key=f"del_c_{r['id']}"):
                    conn.table("gestao_cartoes_vinc").delete().eq("id", r['id']).execute()
                    st.rerun()
                
                # --- HISTÓRICO ESPECÍFICO DO CARTÃO ---
                st.markdown("---")
                st.write(f"📌 **Lançamentos em aberto neste cartão:**")
                # Filtra despesas vinculadas a este ID de cartão que ainda não venceram ou são do mês selecionado
                df_card_hist = df_raw[df_raw['id_vinc_cartao'] == r['id']] if not df_raw.empty else pd.DataFrame()
                
                if not df_card_hist.empty:
                    # Ordenar por data para facilitar a leitura
                    df_card_hist = df_card_hist.sort_values(by="data_dt", ascending=True)
                    for _, row_c in df_card_hist.iterrows():
                        c_col = st.columns([1.5, 3, 1.5])
                        c_col[0].write(f"📅 {row_c['data_registro']}")
                        c_col[1].write(f"{row_c['descricao']}")
                        c_col[2].write(f"**R$ {row_c['valor']:.2f}**")
                else:
                    st.info("Nenhum lançamento encontrado para este cartão.")

# --- ABA 4: DASHBOARD ---
with tab_dashboard:
    if familiar_filter == "Ocultar":
        st.warning("⚠️ Selecione um familiar ou 'Todos' na barra lateral para ver os dados.")
    else:
        # Identificação dos usuários (Assumindo os dois primeiros da lista de permitidos)
        u1 = sorted(usuarios_permitidos)[0]
        u2 = sorted(usuarios_permitidos)[1] if len(usuarios_permitidos) > 1 else None

        # Função interna para calcular saldo acumulado e efetivo por usuário ou geral
        def calc_status(nome_familiar=None):
            # Receitas Acumuladas (Sempre Total)
            df_e_filt = df_ent_raw if nome_familiar is None else df_ent_raw[df_ent_raw['familiar'] == nome_familiar]
            total_rec = df_e_filt['valor'].sum() if not df_e_filt.empty else 0.0

            # Despesas Efetivadas (Tudo que já venceu até hoje)
            df_d_filt = df_raw if nome_familiar is None else df_raw[df_raw['familiar'] == nome_familiar]
            total_desp_e = 0.0
            if not df_d_filt.empty:
                for _, row in df_d_filt.iterrows():
                    data_v = row['data_dt'].date()
                    if row['metodo'] == "Cartão de Crédito":
                        v_info = df_cards_config[df_cards_config['id'] == row['id_vinc_cartao']]
                        v_dia = int(v_info['dia_vencimento'].iloc[0]) if not v_info.empty else 28
                        try: data_v = datetime(row['data_dt'].year, row['data_dt'].month, v_dia).date()
                        except: data_v = datetime(row['data_dt'].year, row['data_dt'].month, 28).date()
                    if data_v <= agora_br.date():
                        total_desp_e += row['valor']
            
            return total_rec, total_desp_e, (total_rec - total_desp_e)

        # Cálculo das 3 Linhas
        t_rec, t_desp, t_saldo = calc_status(None)
        u1_rec, u1_desp, u1_saldo = calc_status(u1)
        if u2: u2_rec, u2_desp, u2_saldo = calc_status(u2)

        # Exibição das Métricas Fixas (Independente de Filtro)
        st.subheader("📌 Status Financeiro Atual (Acumulado)")
        
        # Linha 1: TOTAL
        c1, c2, c3 = st.columns(3)
        c1.metric("📈 Receita Total (Geral)", f"R$ {t_rec:,.2f}")
        c2.metric("📉 Despesas Efetivadas (Geral)", f"R$ {t_desp:,.2f}")
        c3.metric("⚖️ Saldo Real Total", f"R$ {t_saldo:,.2f}")
        st.divider()

        # Linha 2: USUÁRIO 1
        c4, c5, c6 = st.columns(3)
        c4.metric(f"💰 Receita ({u1})", f"R$ {u1_rec:,.2f}")
        c5.metric(f"💸 Despesas ({u1})", f"R$ {u1_desp:,.2f}")
        c6.metric(f"🧤 Saldo Real ({u1})", f"R$ {u1_saldo:,.2f}")

        # Linha 3: USUÁRIO 2
        if u2:
            c7, c8, c9 = st.columns(3)
            c7.metric(f"💰 Receita ({u2})", f"R$ {u2_rec:,.2f}")
            c8.metric(f"💸 Despesas ({u2})", f"R$ {u2_desp:,.2f}")
            c9.metric(f"🧤 Saldo Real ({u2})", f"R$ {u2_saldo:,.2f}")
        
        st.write("")
        st.markdown("---")

        # Sub-Abas para os dados filtrados
        st.subheader(f"🔍 Análise de {mes_sel}/{ano_sel}")
        sub_receitas, sub_despesas, sub_graficos = st.tabs(["📈 Detalhe Receitas", "💸 Detalhe Despesas", "📊 Gráficos & Histórico"])

        # Filtragem para as Sub-Abas (Respeita a Sidebar)
        df_view_d = df_raw[(df_raw['Ano'] == ano_sel) & (df_raw['Mes_PT'] == mes_sel)] if not df_raw.empty else pd.DataFrame()
        df_view_e = df_ent_raw[(df_ent_raw['Ano'] == ano_sel) & (df_ent_raw['Mes_PT'] == mes_sel)] if not df_ent_raw.empty else pd.DataFrame()
        if familiar_filter != "Todos":
            df_view_d = df_view_d[df_view_d['familiar'] == familiar_filter] if not df_view_d.empty else df_view_d
            df_view_e = df_view_e[df_view_e['familiar'] == familiar_filter] if not df_view_e.empty else df_view_e

        with sub_receitas:
            if not df_view_e.empty:
                st.dataframe(df_view_e[['data_registro', 'descricao', 'valor', 'tipo_entrada', 'familiar']], use_container_width=True, hide_index=True)
            else: st.info("Sem receitas para este período.")

        with sub_despesas:
            if not df_view_d.empty:
                st.dataframe(df_view_d[['data_registro', 'descricao', 'valor', 'categoria', 'metodo', 'familiar']], use_container_width=True, hide_index=True)
            else: st.info("Sem despesas para este período.")

        with sub_graficos:
            if not df_view_d.empty:
                st.subheader(f"Gastos por Categoria: {mes_sel}")
                st.bar_chart(df_view_d.groupby("categoria")["valor"].sum())
            
            if mostrar_historico and not df_view_d.empty:
                st.subheader("📋 Histórico Detalhado (Ações)")
                for _, r in df_view_d.iterrows():
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
