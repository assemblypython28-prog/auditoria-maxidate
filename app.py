import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import pytesseract
import numpy as np
import time
import io
from PIL import Image

# --- 1. CONFIGURAÇÃO VISUAL PROFISSIONAL ---
st.set_page_config(page_title="Estel Asset Manager", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }
    
    /* Botões Padrão Comercial */
    .stButton>button {
        width: 100%; border-radius: 8px; height: 48px;
        background-color: #1E293B; color: white; font-weight: 600; border: none;
    }
    .stButton>button:hover { background-color: #334155; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    
    /* Cards de Dashboard */
    .metric-card {
        background: white; padding: 24px; border-radius: 16px;
        border: 1px solid #E2E8F0; text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    
    /* Abas */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #F1F5F9; padding: 8px; border-radius: 12px; }
    .stTabs [aria-selected="true"] { background-color: #FFFFFF !important; color: #1E293B !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXÃO E LÓGICA DE DADOS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def normalizar_codigo(codigo):
    if pd.isna(codigo) or codigo == "": return ""
    return str(codigo).split('-')[0].lstrip('0')

@st.cache_data(ttl=10)
def carregar_da_nuvem():
    try:
        df = conn.read()
        if df.empty or len(df.columns) < 2: return None
        if 'Status' not in df.columns: df['Status'] = 'Pendente'
        df['Chave_Busca'] = df['Código do Bem'].astype(str).apply(normalizar_codigo)
        return df
    except:
        return None

# Estado da sessão
if 'db' not in st.session_state:
    st.session_state.db = carregar_da_nuvem()

# --- 3. INTERFACE PRINCIPAL ---
st.markdown('<h1 style="color: #0F172A; font-weight: 800;">🏗️ Auditoria de Ativos Estel</h1>', unsafe_allow_html=True)

# Fluxo de Importação
if st.session_state.db is None:
    st.info("Nenhum inventário ativo na nuvem. Importe o Excel para começar.")
    arquivo = st.file_uploader("Arraste o arquivo Excel aqui", type=['xlsx'])
    
    if arquivo:
        with st.spinner('Sincronizando com a nuvem...'):
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip()
            if 'Status' not in df.columns: df['Status'] = 'Pendente'
            df['Chave_Busca'] = df['Código do Bem'].astype(str).apply(normalizar_codigo)
            
            # Salva na Planilha Google (conforme configurado nos Secrets)
            conn.update(data=df.drop(columns=['Chave_Busca']))
            st.session_state.db = df
            st.success("Dados sincronizados!")
            time.sleep(1)
            st.rerun()

else:
    tab_scan, tab_lista, tab_dash = st.tabs(["🔍 SCANNER IA", "📑 LISTA DE BENS", "📊 DASHBOARD & EXPORT"])

    # --- ABA 1: SCANNER ---
    with tab_scan:
        foto = st.camera_input("Scanner de Etiqueta")
        id_detectado = ""
        
        if foto:
            with st.spinner('Lendo etiqueta...'):
                img = Image.open(foto)
                texto = pytesseract.image_to_string(img)
                nums = "".join(filter(str.isdigit, texto))
                if nums:
                    id_detectado = nums
                    st.toast(f"Detectado: {id_detectado}")

        busca = st.text_input("Confirmar Número do Ativo:", value=id_detectado)

        if busca:
            alvo = busca.lstrip('0')
            item_data = st.session_state.db[st.session_state.db['Chave_Busca'] == alvo]

            if not item_data.empty:
                idx = item_data.index[0]
                with st.container(border=True):
                    st.markdown(f"### {item_data.at[idx, 'Descrição do Bem']}")
                    st.write(f"Código: **{item_data.at[idx, 'Código do Bem']}**")
                    st.write(f"Status: `{item_data.at[idx, 'Status']}`")
                    
                    if st.button("✅ CONFIRMAR PRESENÇA"):
                        st.session_state.db.at[idx, 'Status'] = 'Auditado'
                        conn.update(data=st.session_state.db.drop(columns=['Chave_Busca']))
                        st.success("Salvo na nuvem!")
                        time.sleep(0.5)
                        st.rerun()
            else:
                st.warning("⚠️ Ativo não localizado.")
                with st.expander("Cadastrar como Sobra"):
                    with st.form("sobra_form"):
                        f_desc = st.text_input("Descrição do Bem")
                        if st.form_submit_button("Registrar Sobra"):
                            nova = pd.DataFrame([{'Código do Bem': busca, 'Descrição do Bem': f"[SOBRA] {f_desc}", 'Status': 'Auditado', 'Chave_Busca': alvo}])
                            st.session_state.db = pd.concat([st.session_state.db, nova], ignore_index=True)
                            conn.update(data=st.session_state.db.drop(columns=['Chave_Busca']))
                            st.rerun()

    # --- ABA 2: LISTA ---
    with tab_lista:
        st.dataframe(st.session_state.db[['Código do Bem', 'Descrição do Bem', 'Status']], use_container_width=True, hide_index=True)

    # --- ABA 3: DASHBOARD ---
    with tab_dash:
        total = len(st.session_state.db)
        audit = len(st.session_state.db[st.session_state.db['Status'] == 'Auditado'])
        perc = (audit/total*100) if total > 0 else 0
        
        c1, c2 = st.columns(2)
        c1.markdown(f'<div class="metric-card"><h2>{audit} / {total}</h2><p>Auditados</p></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><h2>{perc:.1f}%</h2><p>Conclusão</p></div>', unsafe_allow_html=True)
        
        st.divider()
        
        # Download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.db.drop(columns=['Chave_Busca']).to_excel(writer, index=False)
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button("📥 BAIXAR RELATÓRIO", data=output.getvalue(), file_name="Inventario_Estel.xlsx")
        
        with col_d2:
            if st.button("🚨 ENCERRAR E LIMPAR NUVEM"):
                df_reset = pd.DataFrame(columns=['Código do Bem', 'Status'])
                conn.update(data=df_reset)
                st.session_state.db = None
                st.rerun()
