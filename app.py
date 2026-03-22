import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
from io import BytesIO
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# Configuração da Página
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

# Agora a chave 'familiar_nome' é garantida
st.sidebar.write(f"👤 Logado como: **{st.session_state['familiar_nome']}**")
st.title("📊 Controle Financeiro Familiar")

# --- FORMULÁRIO DE ENTRADA ---
with st.form("form_despesa", clear_on_submit=True):
    st.subheader("Novo Lançamento")
    desc = st.text_input("Descrição")
    col1, col2 = st.columns(2)
    with col1:
        valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
        cat = st.selectbox("Categoria", ["Água", "Energia", "Internet", "Lojas Virtuais", "Carro Diversos", "Carro Combustível", "Utilidades Domésticas", "Lazer", "Cartão", "Supermercado", "Farmácia", "Outros"])
    with col2:
        metodo = st.selectbox("Método", ["Dinheiro/Pix", "Cartão de Crédito", "Cartão de Débito"])
    
    if st.form_submit_button("🚀 Registrar Despesa"):
        if desc and valor > 0:
            nova_linha = {
                "data_registro": datetime.now().strftime("%d/%m/%Y"),
                "descricao": desc,
                "valor": valor,
                "categoria": cat,
                "metodo": metodo,
                "familiar": st.session_state["familiar_nome"]
            }
            try:
                conn.table("controle_financeiro").insert(nova_linha).execute()
                st.success(f"✅ Registrado por {st.session_state['familiar_nome']}!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}. Verifique se a coluna 'familiar' existe na tabela.")

# --- BUSCA E FILTRAGEM DE DADOS ---
response = conn.table("controle_financeiro").select("*").order("created_at", desc=True).execute()
df_raw = pd.DataFrame(response.data)

if not df_raw.empty:
    df_raw['data_dt'] = pd.to_datetime(df_raw['data_registro'], format='%d/%m/%Y', errors='coerce')
    df_raw = df_raw.dropna(subset=['data_dt'])
    
    meses_trad = {1:'Janeiro', 2:'Fevereiro', 3:'Março', 4:'Abril', 5:'Maio', 6:'Junho', 
                  7:'Julho', 8:'Agosto', 9:'Setembro', 10:'Outubro', 11:'Novembro', 12:'Dezembro'}
    
    df_raw['Mes_PT'] = df_raw['data_dt'].dt.month.map(meses_trad)
    df_raw['Ano'] = df_raw['data_dt'].dt.year.astype(str)
    
    if 'familiar' not in df_raw.columns:
        df_raw['familiar'] = "Não Inf."
    df_raw['familiar'] = df_raw['familiar'].fillna("Não Inf.")

    st.sidebar.header("🔍 Filtros")
    anos_list = sorted(df_raw['Ano'].unique(), reverse=True)
    ano_sel = st.sidebar.selectbox("Ano", anos_list)

    meses_ordem = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    df_ano = df_raw[df_raw['Ano'] == ano_sel]
    meses_disp = [m for m in meses_ordem if m in df_ano['Mes_PT'].unique()]
    mes_sel = st.sidebar.selectbox("Mês", meses_disp)

    fams_disp = ["Todos"] + sorted(df_raw['familiar'].unique().tolist())
    familiar_filter = st.sidebar.selectbox("Filtrar por Familiar", fams_disp)

    df = df_ano[df_ano['Mes_PT'] == mes_sel].copy()
    if familiar_filter != "Todos":
        df = df[df['familiar'] == familiar_filter]

    if not df.empty:
        st.divider()
        c1, c2 = st.columns(2)
        total_geral = df["valor"].sum()
        total_cartao = df[df["metodo"] == "Cartão de Crédito"]["valor"].sum()
        
        txt_total = f"💰 Total ({familiar_filter})" if familiar_filter != "Todos" else f"💰 Total {mes_sel}"
        c1.metric(txt_total, f"R$ {total_geral:,.2f}")
        c2.metric("💳 Cartão no Período", f"R$ {total_cartao:,.2f}")

        st.subheader(f"Análise: {mes_sel}/{ano_sel} - [{familiar_filter}]")
        resumo_cat = df.groupby("categoria")["valor"].sum()
        st.bar_chart(resumo_cat)

        def gerar_excel_formatado(data_frame):
            output = BytesIO()
            df_export = data_frame[['data_registro', 'descricao', 'valor', 'categoria', 'metodo', 'familiar']].copy()
            df_export.columns = ['Data', 'Descrição', 'Valor', 'Categoria', 'Método', 'Familiar']
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, sheet_name='Lançamentos', index=False)
                workbook = writer.book
                worksheet = writer.sheets['Lançamentos']
                header_fmt = workbook.add_format({'bold': True, 'align': 'center', 'fg_color': '#1F4E78', 'font_color': 'white', 'border': 1})
                money_fmt = workbook.add_format({'num_format': 'R$ #,##0.00', 'border': 1})
                for col_num, value in enumerate(df_export.columns.values):
                    worksheet.write(0, col_num, value, header_fmt)
                worksheet.set_column('A:B', 18); worksheet.set_column('C:C', 15, money_fmt); worksheet.set_column('D:F', 18)
            return output.getvalue()

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.download_button(
                label=f"📥 Relatório {familiar_filter} (Excel)",
                data=gerar_excel_formatado(df),
                file_name=f"Financeiro_{familiar_filter}_{mes_sel}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        with col_b2:
            if st.button("🗑️ Limpar Seleção", type="primary", use_container_width=True):
                for id_del in df['id'].tolist():
                    conn.table("controle_financeiro").delete().eq("id", id_del).execute()
                st.rerun()

        st.subheader(f"Histórico: {familiar_filter}")
        h1, h2, h3, h4, h5, h6 = st.columns([1, 1.5, 1, 1.2, 1, 0.5])
        h1.write("**Data**"); h2.write("**Descrição**"); h3.write("**Valor**"); h4.write("**Método**"); h5.write("**Familiar**"); h6.write("**Ação**")
        
        for _, row in df.iterrows():
            r1, r2, r3, r4, r5, r6 = st.columns([1, 1.5, 1, 1.2, 1, 0.5])
            r1.write(row['data_registro'])
            r2.write(row['descricao'])
            r3.write(f"R$ {row['valor']:.2f}")
            r4.write(row['metodo'])
            r5.write(row['familiar'])
            if r6.button("🗑️", key=f"del_{row['id']}"):
                conn.table("controle_financeiro").delete().eq("id", row['id']).execute()
                st.rerun()
    else:
        st.info(f"Nenhum dado para {familiar_filter} em {mes_sel}/{ano_sel}.")
else:
    st.info("Aguardando lançamentos...")

if st.sidebar.button("Sair / Trocar Usuário"):
    st.session_state["autenticado"] = False
    st.session_state["familiar_nome"] = ""
    st.rerun()
