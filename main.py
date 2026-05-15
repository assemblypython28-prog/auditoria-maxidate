import streamlit as st
import pandas as pd
import easyocr
import numpy as np
import time
import io
from PIL import Image

# --- 1. CONFIGURAÇÃO VISUAL E PWA ---
st.set_page_config(page_title="Estel Asset Manager", page_icon="🏗️", layout="wide")

# CSS Avançado para Visual Profissional
st.markdown("""
    <style>
    /* Fundo e Fonte */
    .stApp { background-color: #f4f7f9; }
    
    /* Botões Customizados */
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3.5em;
        background-color: #1b4f72;
        color: white;
        font-weight: bold;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover { background-color: #2874a6; border: none; }
    
    /* Estilização das Abas */
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #e5e8e8;
        border-radius: 5px 5px 0px 0px;
        gap: 1px;
        padding: 10px;
    }
    .stTabs [aria-selected="true"] { background-color: #1b4f72 !important; color: white !important; }

    /* Cards de Informação */
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border-left: 5px solid #1b4f72;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CARREGAMENTO DA INTELIGÊNCIA ARTIFICIAL ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

# --- 3. FUNÇÕES DE SUPORTE ---
def normalizar_codigo(codigo):
    if pd.isna(codigo) or codigo == "": return ""
    return str(codigo).split('-')[0].lstrip('0')

# --- 4. GESTÃO DE ESTADO (MEMÓRIA) ---
if 'db' not in st.session_state:
    st.session_state.db = None
if 'contabilizados' not in st.session_state:
    st.session_state.contabilizados = set()
if 'splash_done' not in st.session_state:
    st.session_state.splash_done = False

# --- 5. SPLASH SCREEN ---
if not st.session_state.splash_done:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown("""
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 80vh;">
                <img src="https://images.unsplash.com/photo-1581092162384-8987c1d64718?q=80&w=300" style="border-radius: 20px; margin-bottom: 20px;">
                <h1 style="color: #1b4f72; font-family: sans-serif;">ESTEL SERVIÇOS INDUSTRIAIS</h1>
                <p style="color: #566573;">Iniciando Módulo de Inventário Adami...</p>
                <div class="loader"></div>
            </div>
            """, unsafe_allow_html=True)
        time.sleep(3)
    st.session_state.splash_done = True
    st.rerun()

# --- 6. INTERFACE PRINCIPAL ---
st.title("🏗️ Asset Management Estel")

if st.session_state.db is None:
    st.subheader("📥 Carga Inicial de Dados")
    arquivo = st.file_uploader("Arraste a planilha Adami (Excel)", type=['xlsx'])
    if arquivo:
        df = pd.read_excel(arquivo)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=['Código do Bem'])
        df['Chave_Busca'] = df['Código do Bem'].apply(normalizar_codigo)
        st.session_state.db = df
        st.success("Base de dados integrada!")
        st.rerun()
else:
    # CRIAÇÃO DAS ABAS
    tab_scan, tab_lista, tab_dash = st.tabs(["📸 SCANNER IA", "📋 ITENS PENDENTES", "📊 DASHBOARD"])

    # --- ABA 1: SCANNER ---
    with tab_scan:
        st.subheader("Leitura de Etiqueta")
        foto = st.camera_input("Focar na etiqueta de património")
        
        id_detectado = ""
        if foto:
            with st.spinner('Analisando...'):
                img = Image.open(foto)
                results = reader.readtext(np.array(img))
                nums = ["".join(filter(str.isdigit, t)) for (_, t, _) in results if "".join(filter(str.isdigit, t))]
                if nums:
                    id_detectado = nums[0]
                    st.success(f"Deteção: {id_detectado}")

        busca = st.text_input("Confirmar Número para Busca:", value=id_detectado)

        if busca:
            alvo = busca.lstrip('0')
            # Busca exata na base
            item_data = st.session_state.db[st.session_state.db['Chave_Busca'] == alvo]

            if not item_data.empty:
                idx = item_data.index[0]
                with st.container(border=True):
                    st.markdown(f"### {item_data.at[idx, 'Descrição do Bem']}")
                    st.write(f"**ID Técnico:** {item_data.at[idx, 'Código do Bem']}")
                    
                    v_orig = item_data.at[idx, 'Valor Original']
                    v_depr = item_data.at[idx, 'Depreciação Acumulada']
                    st.metric("Valor Líquido Contábil", f"R$ {v_orig - v_depr:,.2f}")

                    # CORREÇÃO DO BOTÃO CONFIRMAR
                    if st.button("CONFIRMAR ITEM NO LOCAL"):
                        st.session_state.contabilizados.add(alvo)
                        st.success(f"Item {alvo} registrado com sucesso!")
                        time.sleep(1)
                        st.rerun()
            else:
                st.error("Património não localizado na base Adami.")

    # --- ABA 2: LISTA DE INVENTÁRIO ---
    with tab_lista:
        st.subheader("Itens Pendentes de Conferência")
        df_view = st.session_state.db.copy()
        df_view['Status'] = df_view['Chave_Busca'].apply(lambda x: '✅ OK' if x in st.session_state.contabilizados else '⚠️ PENDENTE')
        
        # Filtro para ver apenas pendentes
        mostrar_apenas = st.checkbox("Mostrar apenas itens pendentes", value=True)
        if mostrar_apenas:
            df_view = df_view[df_view['Status'] == '⚠️ PENDENTE']
        
        st.dataframe(df_view[['Código do Bem', 'Descrição do Bem', 'Status']], use_container_width=True)

    # --- ABA 3: DASHBOARD ---
    with tab_dash:
        st.subheader("Relatório de Progresso")
        total = len(st.session_state.db)
        encontrados = len(st.session_state.contabilizados)
        perc = (encontrados / total * 100) if total > 0 else 0
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown(f'<div class="metric-card"><h2>{encontrados} / {total}</h2><p>Itens Auditados</p></div>', unsafe_allow_html=True)
        with col_m2:
            st.markdown(f'<div class="metric-card"><h2>{perc:.1f}%</h2><p>Progresso Total</p></div>', unsafe_allow_html=True)
        
        st.progress(perc / 100)

        st.divider()
        st.write("### Exportação Final")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_view.to_excel(writer, index=False)
        st.download_button("📥 BAIXAR EXCEL ATUALIZADO", output.getvalue(), "relatorio_estel.xlsx")
        
        if st.button("🛑 REINICIAR SISTEMA"):
            st.session_state.db = None
            st.session_state.contabilizados = set()
            st.rerun()
