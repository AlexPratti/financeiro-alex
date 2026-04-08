import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import pytz
from datetime import datetime, timedelta
import calendar
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Finanças Familiar", page_icon="💰", layout="wide")

# --- AJUSTE DE FUSO HORÁRIO ---
fuso_br = pytz.timezone('America/Sao_Paulo')
agora_br = datetime.now(fuso_br)
hoje_date = agora_br.date()

# --- INICIALIZAÇÃO DE SESSÃO ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "familiar_nome" not in st.session_state:
    st.session_state["familiar_nome"] = ""

usuarios_permitidos = st.secrets["USUARIOS_PERMITIDOS"]
meses_trad = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}

# --- VALIDAÇÃO DE ACESSO ---
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

# --- CONEXÃO E BUSCA (COM CACHE) ---
conn = st.connection("supabase", type=SupabaseConnection, url=st.secrets["URL_SUPABASE"], key=st.secrets["KEY_SUPABASE"])

@st.cache_data(ttl=60)
def carregar_dados():
    d = conn.table("controle_financeiro").select("*").order("created_at", desc=True).execute()
    e = conn.table("entradas_financeiras").select("*").order("created_at", desc=True).execute()
    c = conn.table("gestao_cartoes_vinc").select("*").execute()
    return pd.DataFrame(d.data), pd.DataFrame(e.data), pd.DataFrame(c.data)

df_raw, df_ent_raw, df_cards_config = carregar_dados()

# --- FUNÇÕES DE UTILIDADE ---
def get_vencimento_real(row, df_cards):
    """Calcula a data exata de vencimento considerando se é cartão ou débito."""
    data_reg = pd.to_datetime(row['data_registro'], format='%d/%m/%Y', errors='coerce')
    if row['metodo'] == "Cartão de Crédito" and not df_cards.empty:
        v_info = df_cards[df_cards['id'] == row['id_vinc_cartao']]
        v_dia = int(v_info['dia_vencimento'].iloc[0]) if not v_info.empty else 28
        try:
            return datetime(data_reg.year, data_reg.month, v_dia).date()
        except:
            return datetime(data_reg.year, data_reg.month, 28).date()
    return data_reg.date()

# --- TRATAMENTO INICIAL DOS DADOS ---
if not df_raw.empty:
    df_raw['data_dt'] = pd.to_datetime(df_raw['data_registro'], format='%d/%m/%Y', errors='coerce')
    df_raw['Mes_PT'] = df_raw['data_dt'].dt.month.map(meses_trad)
    df_raw['Ano'] = df_raw['data_dt'].dt.year.astype(str)
    df_raw['vencimento_efetivo'] = df_raw.apply(lambda r: get_vencimento_real(r, df_cards_config), axis=1)

if not df_ent_raw.empty:
    df_ent_raw['data_dt'] = pd.to_datetime(df_ent_raw['data_registro'], format='%d/%m/%Y', errors='coerce')
    df_ent_raw['Mes_PT'] = df_ent_raw['data_dt'].dt.month.map(meses_trad)
    df_ent_raw['Ano'] = df_ent_raw['data_dt'].dt.year.astype(str)

# --- SIDEBAR ---
st.sidebar.write(f"👤 Logado como: **{st.session_state['familiar_nome']}**")
st.sidebar.header("🔍 Filtros de Exibição")
anos_list = sorted(df_raw['Ano'].unique(), reverse=True) if not df_raw.empty else [str(agora_br.year)]
ano_sel = st.sidebar.selectbox("Ano", anos_list)
mes_sel = st.sidebar.selectbox("Mês", list(meses_trad.values()), index=agora_br.month-1)
fams_disp = ["Ocultar", "Todos"] + sorted(usuarios_permitidos)
familiar_filter = st.sidebar.selectbox("Filtrar por Familiar (Visão)", fams_disp, index=1)
mostrar_historico = st.sidebar.checkbox("Exibir Histórico Detalhado", value=True)

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
        
        if st.form_submit_button("Registrar") and desc and valor_total > 0:
            skip_month = 0
            id_card_vinculo = None
            if is_cartao:
                card_info = dict_cartoes.get(metodo_escolhido)
                id_card_vinculo = card_info['id']
                if agora_br.day >= max(1, card_info['venc'] - 7): skip_month = 1
            
            for i in range(num_parcelas):
                mes_t = agora_br.month + i + skip_month
                ano_a = agora_br.year + (mes_t - 1) // 12
                mes_a = (mes_t - 1) % 12 + 1
                _, last_d = calendar.monthrange(ano_a, mes_a)
                dia_v = min(dict_cartoes[metodo_escolhido]['venc'], last_d) if is_cartao else agora_br.day
                data_reg = datetime(ano_a, mes_a, min(dia_v, last_d)).strftime("%d/%m/%Y")
                
                conn.table("controle_financeiro").insert({
                    "data_registro": data_reg, "descricao": f"{desc} ({i+1}/{num_parcelas})" if num_parcelas > 1 else desc,
                    "valor": valor_total/num_parcelas, "categoria": cat, "familiar": st.session_state["familiar_nome"],
                    "metodo": "Cartão de Crédito" if is_cartao else metodo_escolhido, "id_vinc_cartao": id_card_vinculo
                }).execute()
            st.cache_data.clear()
            st.rerun()

# --- ABA 2: ENTRADAS ---
with tab_receitas:
    with st.form("form_entrada", clear_on_submit=True):
        desc_e = st.text_input("Descrição da Receita")
        ce1, ce2 = st.columns(2)
        valor_e = ce1.number_input("Valor (R$)", min_value=0.0)
        tipo_e = ce2.selectbox("Origem", ["Salário", "Adiantamento", "Pix Recebidos", "Valores Recebidos", "Outros"])
        if st.form_submit_button("Registrar Entrada") and desc_e and valor_e > 0:
            conn.table("entradas_financeiras").insert({
                "data_registro": agora_br.strftime("%d/%m/%Y"), "descricao": desc_e, 
                "valor": valor_e, "tipo_entrada": tipo_e, "familiar": st.session_state["familiar_nome"]
            }).execute()
            st.cache_data.clear()
            st.rerun()

# --- ABA 3: GESTÃO DE CARTÕES ---
with tab_cartoes:
    st.subheader("⚙️ Configurar Cartões")
    with st.form("novo_cartao"):
        f1, f2, f3 = st.columns(3)
        banco_n = f1.text_input("Banco")
        cartao_n = f2.text_input("Nome do Cartão (Ex: Black 123)")
        venc_d = f3.number_input("Dia Vencimento", 1, 31, 10)
        
        # O botão DEVE estar dentro do 'with st.form'
        submit_c = st.form_submit_button("Salvar Cartão")
        
        if submit_c:
            if banco_n and cartao_n:
                conn.table("gestao_cartoes_vinc").insert({
                    "banco_nome": banco_n, 
                    "apelido_cartao": cartao_n, 
                    "dia_vencimento": venc_d
                }).execute()
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("Preencha o Banco e o Nome do Cartão.")
    
    if not df_cards_config.empty:
        for _, r in df_cards_config.iterrows():
            with st.expander(f"💳 {r['banco_nome']} - **{r['apelido_cartao']}** (Vence dia {r['dia_vencimento']})"):
                # Botão de excluir fora do form, dentro do expander
                if st.button("Excluir Cartão", key=f"del_c_{r['id']}"):
                    conn.table("gestao_cartoes_vinc").delete().eq("id", r['id']).execute()
                    st.cache_data.clear()
                    st.rerun()
                st.markdown("---")
                df_card_hist = df_raw[df_raw['id_vinc_cartao'] == r['id']] if not df_raw.empty else pd.DataFrame()
                if not df_card_hist.empty:
                    for _, row_c in df_card_hist.sort_values(by="vencimento_efetivo").iterrows():
                        c_col = st.columns([1.5, 3, 1.5])
                        c_col[0].write(f"📅 {row_c['data_registro']}")
                        c_col[1].write(f"{row_c['descricao']}")
                        c_col[2].write(f"**R$ {row_c['valor']:.2f}**")

# --- ABA 4: DASHBOARD ---
with tab_dashboard:
    if familiar_filter == "Ocultar":
        st.warning("⚠️ Selecione um familiar.")
    else:
        u1, u2 = sorted(usuarios_permitidos)[0], sorted(usuarios_permitidos)[1] if len(usuarios_permitidos)>1 else None

        def calc_status(nome=None):
            df_e = df_ent_raw if nome is None else df_ent_raw[df_ent_raw['familiar'] == nome]
            df_d = df_raw if nome is None else df_raw[df_raw['familiar'] == nome]
            rec = df_e['valor'].sum() if not df_e.empty else 0.0
            desp = df_d[df_d['vencimento_efetivo'] <= hoje_date]['valor'].sum() if not df_d.empty else 0.0
            return rec, desp, rec - desp

        st.subheader("📌 Status Financeiro Atual (Acumulado)")
        for label, nome in [("Geral", None), (u1, u1), (u2, u2)]:
            if nome or label == "Geral":
                r, d, s = calc_status(nome)
                col1, col2, col3 = st.columns(3)
                col1.metric(f"📈 Receita ({label})", f"R$ {r:,.2f}")
                col2.metric(f"📉 Despesas ({label})", f"R$ {d:,.2f}")
                col3.metric(f"⚖️ Saldo ({label})", f"R$ {s:,.2f}")
                if label != u2: st.divider()

        st.markdown("---")
        st.subheader(f"🔍 Análise de {mes_sel}/{ano_sel}")
        sub_rec, sub_desp, sub_graf = st.tabs(["📈 Receitas", "💸 Despesas", "📊 Gráficos"])
        
        df_v_d = df_raw[(df_raw['Ano'] == ano_sel) & (df_raw['Mes_PT'] == mes_sel)] if not df_raw.empty else pd.DataFrame()
        df_v_e = df_ent_raw[(df_ent_raw['Ano'] == ano_sel) & (df_ent_raw['Mes_PT'] == mes_sel)] if not df_ent_raw.empty else pd.DataFrame()
        if familiar_filter != "Todos":
            df_v_d = df_v_d[df_v_d['familiar'] == familiar_filter] if not df_v_d.empty else df_v_d
            df_v_e = df_v_e[df_v_e['familiar'] == familiar_filter] if not df_v_e.empty else df_v_e

        with sub_rec: 
            if not df_view_e.empty:
                # Seleção de colunas relevantes
                cols_rec = ['data_registro', 'descricao', 'valor', 'tipo_entrada', 'familiar']
                df_exibir_e = df_view_e[cols_rec].copy()
                
                # Exibição com filtros interativos nas colunas
                st.dataframe(
                    df_exibir_e, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "descricao": st.column_config.TextColumn("Descrição", help="Filtre por nome"),
                        "tipo_entrada": st.column_config.SelectColumn("Origem", help="Filtre por tipo")
                    }
                )
                # Totalizador no final
                total_mes_rec = df_exibir_e['valor'].sum()
                st.markdown(f"**Total de Receitas no Período: R$ {total_mes_rec:,.2f}**")
            else: 
                st.info("Nenhuma receita encontrada para este período.")

        with sub_desp: 
            if not df_view_d.empty:
                # Seleção de colunas relevantes
                cols_desp = ['data_registro', 'descricao', 'valor', 'categoria', 'metodo', 'familiar']
                df_exibir_d = df_view_d[cols_desp].copy()
                
                # Exibição com filtros interativos nas colunas
                st.dataframe(
                    df_exibir_d, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "descricao": st.column_config.TextColumn("Descrição"),
                        "categoria": st.column_config.SelectColumn("Categoria"),
                        "metodo": st.column_config.SelectColumn("Método")
                    }
                )
                # Totalizador no final
                total_mes_desp = df_exibir_d['valor'].sum()
                st.markdown(f"**Total de Despesas no Período: R$ {total_mes_desp:,.2f}**")
            else: 
                st.info("Nenhuma despesa encontrada para este período.")


        
        with sub_graf:
            if not df_v_d.empty:
                st.bar_chart(df_v_d.groupby("categoria")["valor"].sum())
                if mostrar_historico:
                    for _, r in df_v_d.iterrows():
                        c = st.columns([1, 2, 1, 1, 0.5])
                        c[0].write(r['data_registro']); c[1].write(r['descricao']); c[2].write(f"R$ {r['valor']:.2f}"); c[3].write(r['familiar'])
                        if c[4].button("🗑️", key=f"del_v_{r['id']}"):
                            conn.table("controle_financeiro").delete().eq("id", r['id']).execute()
                            st.cache_data.clear()
                            st.rerun()

if st.sidebar.button("Sair"):
    st.session_state["autenticado"] = False
    st.rerun()
