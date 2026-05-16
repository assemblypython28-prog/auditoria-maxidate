import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import io

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Estel Asset Manager", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }
    .stButton>button { width: 100%; border-radius: 8px; height: 48px; background-color: #1E293B; color: white; font-weight: 600; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXÃO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def normalizar(c):
    return str(c).split('-')[0].lstrip('0')

@st.cache_data(ttl=10)
def carregar_dados():
    try:
        df = conn.read()
        if df is None or df.empty:
            return None
        if 'Status' not in df.columns:
            df['Status'] = 'Pendente'
        df['Chave'] = df['Código do Bem'].astype(str).apply(normalizar)
        return df
    except:
        return None

if 'db' not in st.session_state:
    st.session_state.db = carregar_dados()

# --- 3. INTERFACE ---
st.markdown('<h1 style="color: #0F172A;">🏗️ Auditoria de Ativos Estel</h1>', unsafe_allow_html=True)

if st.session_state.db is None:
    st.warning("Nenhum inventário ativo na nuvem. Importe o Excel para começar.")
    arquivo = st.file_uploader("Selecionar ficheiro CPBE118", type=['xlsx'])
    if arquivo:
        df = pd.read_excel(arquivo)
        df['Status'] = 'Pendente'
        df['Chave'] = df['Código do Bem'].astype(str).apply(normalizar)
        conn.create(worksheet="Sheet1", data=df.drop(columns=['Chave']))
        st.session_state.db = df
        st.rerun()
else:
    t1, t2, t3 = st.tabs(["🔍 SCANNER & FOTO", "📑 LISTA", "📊 DASHBOARD"])

    with t1:
        st.markdown("### Tirar Foto do Património")
        foto = st.camera_input("Capturar Etiqueta")
        
        busca = st.text_input("Confirme o Número do Ativo:")
        
        if busca:
            alvo = busca.lstrip('0')
            item = st.session_state.db[st.session_state.db['Chave'] == alvo]
            
            if not item.empty:
                idx = item.index[0]
                st.info(f"**Item Localizado:** {item.at[idx, 'Descrição do Bem']}")
                st.write(f"Status Atual: {item.at[idx, 'Status']}")
                
                if st.button("✅ CONFIRMAR AUDITORIA"):
                    st.session_state.db.at[idx, 'Status'] = 'Auditado'
                    conn.create(worksheet="Sheet1", data=st.session_state.db.drop(columns=['Chave']))
                    st.success("Salvo na nuvem com sucesso!")
                    time.sleep(0.8)
                    st.rerun()
            else:
                st.error("Item não encontrado na base de dados.")
                with st.expander("Cadastrar como Sobra"):
                    desc_sobra = st.text_input("Descrição da Sobra")
                    if st.button("Salvar Sobra"):
                        nova = pd.DataFrame([{'Código do Bem': busca, 'Descrição do Bem': f"[SOBRA] {desc_sobra}", 'Status': 'Auditado', 'Chave': alvo}])
                        st.session_state.db = pd.concat([st.session_state.db, nova], ignore_index=True)
                        conn.create(worksheet="Sheet1", data=st.session_state.db.drop(columns=['Chave']))
                        st.rerun()

    with t2:
        st.dataframe(st.session_state.db[['Código do Bem', 'Descrição do Bem', 'Status']], use_container_width=True)

    with t3:
        total = len(st.session_state.db)
        audit = len(st.session_state.db[st.session_state.db['Status'] == 'Auditado'])
        st.metric("Total Auditado", f"{audit} de {total}")
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.db.drop(columns=['Chave']).to_excel(writer, index=False)
        st.download_button("📥 BAIXAR EXCEL FINAL", data=output.getvalue(), file_name="inventario_final.xlsx")

        if st.button("🚨 LIMPAR NUVEM (NOVA OBRA)"):
            conn.create(worksheet="Sheet1", data=pd.DataFrame(columns=['Código do Bem', 'Status']))
            st.session_state.db = None
            st.rerun()
