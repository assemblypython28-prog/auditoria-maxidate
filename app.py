import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import easyocr
import numpy as np
import time
import io
from PIL import Image

# --- 1. CONFIGURAÇÃO VISUAL "ESTEL ENTERPRISE" ---
st.set_page_config(page_title="Estel Asset Manager", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #F8FAFC;
    }

    /* Botões Padrão Comercial */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 48px;
        background-color: #1E293B;
        color: white;
        font-weight: 600;
        border: none;
        transition: 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #334155;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* Cards de Dashboard */
    .metric-card {
        background: white;
        padding: 24px;
        border-radius: 16px;
        border: 1px solid #E2E8F0;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }

    /* Estilização das Abas */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #F1F5F9;
        padding: 8px;
        border-radius: 12px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #1E293B !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXÃO E LÓGICA DE PERSISTÊNCIA ---
conn = st.connection("gsheets", type=GSheetsConnection)

def normalizar_codigo(codigo):
    if pd.isna(codigo) or codigo == "": return ""
    return str(codigo).split('-')[0].lstrip('0')

@st.cache_data(ttl=10)
def carregar_da_nuvem():
    try:
        df = conn.read()
        if df.empty or len(df.columns) < 2: 
            return None
        # Garante que a coluna Status exista e cria chave de busca
        if 'Status' not in df.columns: df['Status'] = 'Pendente'
        df['Chave_Busca'] = df['Código do Bem'].astype(str).apply(normalizar_codigo)
        return df
    except:
        return None

# Inicializa o estado do banco de dados
if 'db' not in st.session_state:
    st.session_state.db = carregar_da_nuvem()

# --- 3. MOTOR DE INTELIGÊNCIA ARTIFICIAL ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

# --- 4. INTERFACE PRINCIPAL ---
st.markdown('<h1 style="color: #0F172A; font-weight: 800; letter-spacing: -1px;">🏗️ Auditoria de Ativos Estel</h1>', unsafe_allow_html=True)

# FLUXO A: IMPORTAÇÃO (Se estiver vazio)
if st.session_state.db is None:
    st.markdown("""
        <div style="background: white; padding: 40px; border-radius: 16px; border: 1px dashed #CBD5E1; text-align: center; margin-top: 20px;">
            <h3 style="color: #1E293B;">Nenhum inventário ativo na nuvem</h3>
            <p style="color: #64748B;">Importe o arquivo Excel (CPBE118) para iniciar o monitoramento.</p>
        </div>
    """, unsafe_allow_html=True)
    
    arquivo = st.file_uploader("", type=['xlsx'])
    if arquivo:
        with st.spinner('Sincronizando base com a nuvem...'):
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip()
            if 'Status' not in df.columns: df['Status'] = 'Pendente'
            
            # Normalização e Sincronização Inicial
            df['Chave_Busca'] = df['Código do Bem'].astype(str).apply(normalizar_codigo)
            conn.update(data=df.drop(columns=['Chave_Busca']))
            st.session_state.db = df
            st.success("Base Estel carregada e protegida na nuvem!")
            time.sleep(1.5)
            st.rerun()

# FLUXO B: OPERAÇÃO (Se já houver dados)
else:
    tab_scan, tab_lista, tab_dash = st.tabs(["🔍 SCANNER IA", "📑 LISTA DE CONFERÊNCIA", "📊 DASHBOARD & EXPORT"])

    # --- ABA 1: SCANNER ---
    with tab_scan:
        foto = st.camera_input("Capturar etiqueta de patrimônio")
        id_detectado = ""
        
        if foto:
            with st.spinner('IA analisando...'):
                img = Image.open(foto)
                results = reader.readtext(np.array(img))
                nums = ["".join(filter(str.isdigit, t)) for (_, t, _) in results if "".join(filter(str.isdigit, t))]
                if nums:
                    id_detectado = nums[0]
                    st.toast(f"Código detectado: {id_detectado}")

        busca = st.text_input("Número para busca ou cadastro:", value=id_detectado, placeholder="Digite o ID...")

        if busca:
            alvo = busca.lstrip('0')
            item_data = st.session_state.db[st.session_state.db['Chave_Busca'] == alvo]

            if not item_data.empty:
                idx = item_data.index[0]
                with st.container(border=True):
                    st.markdown(f"### {item_data.at[idx, 'Descrição do Bem']}")
                    st.write(f"Código: **{item_data.at[idx, 'Código do Bem']}**")
                    st.write(f"Status Atual: `{item_data.at[idx, 'Status']}`")
                    
                    if st.button("✅ CONFIRMAR ITEM NO LOCAL"):
                        # Atualiza Local e Nuvem
                        st.session_state.db.at[idx, 'Status'] = 'Auditado'
                        conn.update(data=st.session_state.db.drop(columns=['Chave_Busca']))
                        st.success("Auditado com sucesso na nuvem!")
                        time.sleep(0.5)
                        st.rerun()
            else:
                st.warning("⚠️ Ativo não localizado na base original.")
                with st.expander("➕ CADASTRAR COMO SOBRA DE INVENTÁRIO", expanded=True):
                    with st.form("form_sobra"):
                        f_desc = st.text_input("Descrição da Sobra")
                        f_area = st.text_input("Localização/Área")
                        if st.form_submit_button("SALVAR E AUDITAR"):
                            nova_sobra = pd.DataFrame([{
                                'Código do Bem': busca,
                                'Descrição do Bem': f"[SOBRA] {f_desc}",
                                'Status': 'Auditado',
                                'Chave_Busca': alvo
                            }])
                            st.session_state.db = pd.concat([st.session_state.db, nova_sobra], ignore_index=True)
                            conn.update(data=st.session_state.db.drop(columns=['Chave_Busca']))
                            st.success("Sobra registrada na nuvem!")
                            time.sleep(1)
                            st.rerun()

    # --- ABA 2: LISTA ---
    with tab_lista:
        st.markdown("### Itens Pendentes / Auditados")
        df_view = st.session_state.db.copy()
        filtro = st.radio("Filtro rápido:", ["Todos", "Pendente", "Auditado"], horizontal=True)
        if filtro != "Todos":
            df_view = df_view[df_view['Status'] == filtro]
        
        st.dataframe(df_view[['Código do Bem', 'Descrição do Bem', 'Status']], use_container_width=True, hide_index=True)

    # --- ABA 3: DASHBOARD ---
    with tab_dash:
        total = len(st.session_state.db)
        audit = len(st.session_state.db[st.session_state.db['Status'] == 'Auditado'])
        perc = (audit/total*100) if total > 0 else 0
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="metric-card"><h2 style="margin:0;">{audit} / {total}</h2><p style="margin:0; color:#64748B;">ITENS AUDITADOS</p></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><h2 style="margin:0;">{perc:.1f}%</h2><p style="margin:0; color:#64748B;">PROGRESSO TOTAL</p></div>', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.progress(perc / 100)
        
        st.divider()
        st.subheader("💾 Gerenciamento de Dados")
        
        # Preparação do Excel para Download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.db.drop(columns=['Chave_Busca']).to_excel(writer, index=False)
        
        col_d1, col_d2 = st.columns(2)
        
        with col_d1:
            st.download_button(
                label="📥 BAIXAR RELATÓRIO PARCIAL",
                data=output.getvalue(),
                file_name=f"Auditoria_Estel_{time.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Faz o download dos dados atuais sem limpar a nuvem."
            )
            
        with col_d2:
            if st.button("🚨 ENCERRAR INVENTÁRIO (LIMPAR NUVEM)"):
                # Limpeza da planilha Google para o próximo projeto
                df_reset = pd.DataFrame(columns=['Código do Bem', 'Descrição do Bem', 'Status'])
                conn.update(data=df_reset)
                st.session_state.db = None
                st.success("Dados de nuvem resetados com sucesso!")
                time.sleep(2)
                st.rerun()
