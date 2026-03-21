import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
from io import BytesIO
from datetime import datetime

# Configuração da Página para Mobile e Desktop
st.set_page_config(page_title="Finanças Alex", page_icon="💰", layout="wide")

st.title("📊 Controle Financeiro Familiar")

# 1. Conexão com Supabase (Configurado para suas chaves específicas)
conn = st.connection(
    "supabase", 
    type=SupabaseConnection,
    url=st.secrets["URL_SUPABASE"],
    key=st.secrets["KEY_SUPABASE"]
)

# --- FORMULÁRIO DE ENTRADA ---
with st.form("form_despesa", clear_on_submit=True):
    st.subheader("Novo Lançamento")
    desc = st.text_input("Descrição (ex: Conta de Luz)")
    
    col1, col2 = st.columns(2)
    with col1:
        valor = st.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
        cat = st.selectbox("Categoria", ["Água", "Energia", "Internet", "Carro", "Lazer", "Cartão", "Outros"])
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
                st.success("✅ Registrado com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

# --- BUSCA DE DADOS ---
response = conn.table("controle_financeiro").select("*").order("created_at", desc=True).execute()
df = pd.DataFrame(response.data)

if not df.empty:
    # --- MÉTRICAS DE RESUMO ---
    st.divider()
    c1, c2 = st.columns(2)
    total_geral = df["valor"].sum()
    total_cartao = df[df["metodo"] == "Cartão de Crédito"]["valor"].sum()
    
    c1.metric("💰 Total Geral", f"R$ {total_geral:,.2f}")
    c2.metric("💳 Cartão de Crédito", f"R$ {total_cartao:,.2f}")

    # --- GRÁFICO DE ANÁLISE ---
    st.subheader("Análise por Categoria")
    resumo_cat = df.groupby("categoria")["valor"].sum()
    st.bar_chart(resumo_cat)

    # --- FUNÇÃO PARA EXPORTAÇÃO EXCEL FORMATADO ---
    def gerar_excel_formatado(data_frame):
        output = BytesIO()
        df_export = data_frame[['data_registro', 'descricao', 'valor', 'categoria', 'metodo']].copy()
        df_export.columns = ['Data', 'Descrição', 'Valor', 'Categoria', 'Método']
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_export.to_excel(writer, sheet_name='Lançamentos', index=False)
            workbook = writer.book
            worksheet = writer.sheets['Lançamentos']
            
            header_fmt = workbook.add_format({
                'bold': True, 'align': 'center', 'valign': 'vcenter',
                'fg_color': '#1F4E78', 'font_color': 'white', 'border': 1
            })
            money_fmt = workbook.add_format({'num_format': 'R$ #,##0.00', 'border': 1, 'align': 'center'})
            cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})

            for col_num, value in enumerate(df_export.columns.values):
                worksheet.write(0, col_num, value, header_fmt)
            
            worksheet.set_column('A:A', 15, cell_fmt)
            worksheet.set_column('B:B', 30, cell_fmt)
            worksheet.set_column('C:C', 18, money_fmt)
            worksheet.set_column('D:E', 20, cell_fmt)
            
        return output.getvalue()

    # --- BOTÕES DE AÇÃO ---
    col_btn1, col_btn2 = st.columns([2, 1])
    with col_btn1:
        excel_data = gerar_excel_formatado(df)
        st.download_button(
            label="📥 Baixar Relatório Excel Profissional",
            data=excel_data,
            file_name=f"Financeiro_{datetime.now().strftime('%m_%Y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col_btn2:
        if st.button("🗑️ Limpar Tudo", type="primary", use_container_width=True):
            try:
                # Exclui todos os registros onde o ID não é zero (limpa a tabela)
                conn.table("controle_financeiro").delete().neq("id", 0).execute()
                st.success("Tabela limpa!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao excluir tudo: {e}")

    # --- TABELA DE HISTÓRICO COM COLUNA MÉTODO E EXCLUSÃO ---
    st.subheader("Histórico de Lançamentos")
    
    # Criando colunas para o cabeçalho (Data, Descrição, Valor, Método, Ação)
    h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([1, 2, 1, 1.5, 0.5])
    h_col1.write("**Data**")
    h_col2.write("**Descrição**")
    h_col3.write("**Valor**")
    h_col4.write("**Método**")
    h_col5.write("**Ação**")
    
    for index, row in df.iterrows():
        r_col1, r_col2, r_col3, r_col4, r_col5 = st.columns([1, 2, 1, 1.5, 0.5])
        r_col1.write(row['data_registro'])
        r_col2.write(row['descricao'])
        r_col3.write(f"R$ {row['valor']:.2f}")
        r_col4.write(row['metodo'])
        
        # Botão para excluir linha específica
        if r_col5.button("🗑️", key=f"del_{row['id']}"):
            try:
                conn.table("controle_financeiro").delete().eq("id", row['id']).execute()
                st.success("Excluído!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro: {e}")

else:
    st.info("Aguardando o primeiro lançamento para gerar o resumo...")
