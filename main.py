import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3

# Configuração da página
st.set_page_config(page_title="Maxidate Audit", layout="centered")

# --- BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('auditoria_v4.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS inventario 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    data TEXT, colaborador TEXT, area TEXT, 
                    patrimonio TEXT, descricao TEXT, qtd INTEGER)''')
    conn.close()

init_db()

# --- INTERFACE ---
st.title("🚀 Auditoria Maxidate Pro")
st.subheader("Controle de Patrimônio - Almoxarifado")

# Campos fixos (não resetam ao salvar para agilizar o trabalho)
col1, col2 = st.columns(2)
with col1:
    colaborador = st.text_input("Nome do Colaborador")
with col2:
    area = st.selectbox("Área / Setor", ["Almoxarifado Central", "Manutenção", "Produção", "Escritório"])

st.divider()

# Entrada de Patrimônio: Aceita digitação ou uso da câmera do celular
foto_patrimonio = st.camera_input("Aponte para a etiqueta de Patrimônio")
patrimonio_manual = st.text_input("Ou digite o número do Patrimônio")

# Descrição e Quantidade
descricao = st.text_area("Descrição do Equipamento")
qtd = st.number_input("Quantidade Contada", min_value=1, step=1)

if st.button("📥 Salvar Registro"):
    if (patrimonio_manual or foto_patrimonio) and colaborador:
        data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
        # Se usou a câmera, podemos salvar uma flag ou o ID (Streamlit salva a imagem em memória)
        pat_final = patrimonio_manual if patrimonio_manual else "Captura via Câmera"
        
        conn = sqlite3.connect('auditoria_v4.db')
        conn.execute("INSERT INTO inventario (data, colaborador, area, patrimonio, descricao, qtd) VALUES (?,?,?,?,?,?)",
                     (data_atual, colaborador, area, pat_final, descricao, qtd))
        conn.commit()
        conn.close()
        st.success(f"Item {pat_final} registrado com sucesso!")
    else:
        st.error("Por favor, preencha o Patrimônio e o seu Nome.")

st.divider()

# --- EXPORTAÇÃO ---
st.subheader("📊 Relatório de Auditoria")

if st.button("📂 Gerar Planilha Excel"):
    conn = sqlite3.connect('auditoria_v4.db')
    df = pd.read_sql_query("SELECT id, data, colaborador, area, patrimonio, descricao, qtd FROM inventario", conn)
    conn.close()
    
    if not df.empty:
        # Conversão para Excel em memória
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Auditoria')
        
        st.download_button(
            label="⬇️ Baixar Excel (auditoria_maxidate.xlsx)",
            data=output.getvalue(),
            file_name=f"auditoria_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.dataframe(df) # Mostra uma prévia na tela
    else:
        st.warning("Nenhum dado encontrado para exportar.")
