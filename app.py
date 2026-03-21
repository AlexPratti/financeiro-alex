import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
from io import BytesIO
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# Configuração da Página
st.set_page_config(page_title="Finanças Alex", page_icon="💰", layout="wide")

# --- VALIDAÇÃO DE USUÁRIO ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Acesso ao Sistema")
    user_input = st.text_input("Informe seu usuário:").strip().lower()
    if st.button("Acessar"):
        if user_input in ["merlim", "pratti"]:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Usuário não autorizado.")
    st.stop()

# --- ATUALIZAÇÃO AUTOMÁTICA (20 segundos) ---
st_autorefresh(interval=20000, key="datarefresh")

# --- CONEXÃO COM SUPABASE ---
conn = st.connection("supabase", type=SupabaseConnection, url=st.secrets["URL_SUPABASE"], key=st.secrets["KEY_SUPABASE"])

st.title("📊 Controle Financeiro Familiar")

# --- FORMULÁRIO DE ENTRADA ---
with st.form("form_despesa", clear_on_submit=True):
    st.subheader("Novo Lançamento")
    desc = st.text_input("Descrição")
    col1, col2 = st.columns(2)
    with col1:
        valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
        cat = st.selectbox("Categoria", ["Água", "Energia", "Internet", "Carro", "Lazer", "Cartão", "Supermercado", "Farmácia", "Outros"])
    with col2:
        metodo = st.selectbox("Método", ["Dinheiro/Pix", "Cartão de Crédito", "Cartão de Débito"])
    
    if st.form_submit_button("🚀 Registrar Despesa"):
        if desc and valor > 0:
            nova_linha = {
                "data_registro": datetime.now().strftime("%d/%m/%Y"),
                "descricao": desc,
                "valor": valor,
                "categoria": cat,
                "metodo": metodo
            }
            try:
                conn.table("controle_financeiro").insert(nova_linha).execute()
                st.success("✅ Registrado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

# --- BUSCA E FILTRAGEM DE DADOS ---
response = conn.table("controle_financeiro").select("*").order("created_at", desc=True).execute()
df_raw = pd.DataFrame(response.data)

if not df_raw.empty:
    # Conversão de datas
    df_raw['data_dt'] = pd.to_datetime(df_raw['data_registro'], format='%d/%m/%Y', errors='coerce')
    df_raw = df_raw.dropna(subset=['data_dt'])
    
    meses_traducao = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
        7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    
    df_raw['Mes_PT'] = df_raw['data_dt'].dt.month.map(meses_traducao)
    df_raw['Ano'] = df_raw['data_dt'].dt.year.astype(str)

    # --- FILTROS NA SIDEBAR (CLIQUE NA SETA NO CANTO SUPERIOR ESQUERDO) ---
    st.sidebar.header("🔍 Filtros de Visualização")
    
    anos_list = sorted(df_raw['Ano'].unique(), reverse=True)
    ano_atual = str(datetime.now().year)
    index_ano = anos_list.index(ano_atual) if ano_atual in anos_list else 0
    ano_sel = st.sidebar.selectbox("Ano", anos_list, index=index_ano)

    meses_ordem = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_atual_nome = meses_traducao[datetime.now().month]
    
    df_ano = df_raw[df_raw['Ano'] == ano_sel]
    meses_disp = [m for m in meses_ordem if m in df_ano['Mes_PT'].unique()]
    
    index_mes = meses_disp.index(mes_atual_nome) if mes_atual_nome in meses_disp else 0
    mes_sel = st.sidebar.selectbox("Mês", meses_disp, index=index_mes)

    # DataFrame Final Filtrado conforme Sidebar
    df = df_ano[df_ano['Mes_PT'] == mes_sel].copy()

    if not df.empty:
        st.divider()
        c1, c2 = st.columns(2)
        total_geral = df["valor"].sum()
        total_cartao = df[df["metodo"] == "Cartão de Crédito"]["valor"].sum()
        c1.metric(f"💰 Total {mes_sel}", f"R$ {total_geral:,.2f}")
        c2.metric("💳 Cartão no Mês", f"R$ {total_cartao:,.2f}")

        # Gráfico por Categoria
        st.subheader(f"Análise por Categoria: {mes_sel}/{ano_sel}")
        resumo_cat = df.groupby("categoria")["valor"].sum()
        st.bar_chart(resumo_cat)

        # --- FUNÇÃO EXCEL FORMATADO ---
        def gerar_excel_formatado(data_frame):
            output = BytesIO()
            df_export = data_frame[['data_registro', 'descricao', 'valor', 'categoria', 'metodo']].copy()
            df_export.columns = ['Data', 'Descrição', 'Valor', 'Categoria', 'Método']
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, sheet_name='Lançamentos', index=False)
                workbook = writer.book
                worksheet = writer.sheets['Lançamentos']
                header_fmt = workbook.add_format({'bold': True, 'align': 'center', 'fg_color': '#1F4E78', 'font_color': 'white', 'border': 1})
                money_fmt = workbook.add_format({'num_format': 'R$ #,##0.00', 'border': 1})
                for col_num, value in enumerate(df_export.columns.values):
                    worksheet.write(0, col_num, value, header_fmt)
                worksheet.set_column('A:B', 20); worksheet.set_column('C:C', 15, money_fmt); worksheet.set_column('D:E', 20)
            return output.getvalue()

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            excel_data = gerar_excel_formatado(df)
            st.download_button(
                label=f"📥 Baixar Relatório {mes_sel} (Excel)",
                data=excel_data,
                file_name=f"Relatorio_{mes_sel}_{ano_sel}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        with col_b2:
            if st.button("🗑️ Limpar Mês Selecionado", type="primary", use_container_width=True):
                try:
                    ids_para_deletar = df['id'].tolist()
                    for id_del in ids_para_deletar:
                        conn.table("controle_financeiro").delete().eq("id", id_del).execute()
                    st.success(f"Dados de {mes_sel} removidos!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

        st.subheader(f"Histórico de {mes_sel}")
        h1, h2, h3, h4, h5 = st.columns([1, 2, 1, 1.5, 0.5])
        h1.write("**Data**"); h2.write("**Descrição**"); h3.write("**Valor**"); h4.write("**Método**"); h5.write("**Ação**")
        
        for _, row in df.iterrows():
            r1, r2, r3, r4, r5 = st.columns([1, 2, 1, 1.5, 0.5])
            r1.write(row['data_registro'])
            r2.write(row['descricao'])
            r3.write(f"R$ {row['valor']:.2f}")
            r4.write(row['metodo'])
            if r5.button("🗑️", key=f"del_{row['id']}"):
                conn.table("controle_financeiro").delete().eq("id", row['id']).execute()
                st.rerun()
    else:
        st.info(f"Nenhum dado encontrado para {mes_sel}/{ano_sel}.")

else:
    st.info("Aguardando lançamentos...")

# Logout na Sidebar
if st.sidebar.button("Sair / Trocar Usuário"):
    st.session_state["autenticado"] = False
    st.rerun()
