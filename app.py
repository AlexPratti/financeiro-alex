import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
from io import BytesIO
from datetime import datetime

# Configuração da Página para Mobile e Desktop
st.set_page_config(page_title="Finanças Alex", page_icon="💰", layout="centered")

st.title("📊 Controle Financeiro Familiar")

# 1. Conexão com Supabase (Configurar nos Secrets do Streamlit Cloud)
conn = st.connection("supabase", type=SupabaseConnection)

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
            # Enviando para a tabela correta no Supabase
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
    c2.metric("💳 No Cartão", f"R$ {total_cartao:,.2f}")

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
            
            # Estilo idêntico à sua referência (Azul Escuro / Branco)
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

    # --- BOTÃO DE DOWNLOAD ---
    excel_data = gerar_excel_formatado(df)
    st.download_button(
        label="📥 Baixar Relatório Excel Profissional",
        data=excel_data,
        file_name=f"Financeiro_{datetime.now().strftime('%m_%Y')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- TABELA DE HISTÓRICO ---
    st.subheader("Histórico de Lançamentos")
    st.dataframe(df[['data_registro', 'descricao', 'valor', 'categoria', 'metodo']], use_container_width=True)
else:
    st.info("Aguardando o primeiro lançamento para gerar o resumo...")

