import streamlit as st
import pandas as pd
import easyocr
import numpy as np
import time
import io
from PIL import Image

# --- 1. CONFIGURAÇÃO DA PÁGINA (PWA) ---
st.set_page_config(page_title="Inventário Estel", page_icon="🏗️", layout="centered")

# --- 2. SPLASH SCREEN PROFISSIONAL ---
if 'splash_done' not in st.session_state:
    placeholder = st.empty()
    with placeholder.container():
        st.markdown(
            """
            <style>
            .splash-bg {
                background-image: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)), 
                                  url('https://images.unsplash.com/photo-1581092160562-40aa08e78837?q=80&w=2070');
                background-size: cover;
                background-position: center;
                height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                color: white;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                z-index: 9999;
            }
            .loader {
                border: 8px solid #f3f3f3;
                border-top: 8px solid #3498db;
                border-radius: 50%;
                width: 60px;
                height: 60px;
                animation: spin 1s linear infinite;
                margin-bottom: 20px;
            }
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            .fade-in { animation: fadeIn 2s; }
            @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
            </style>
            <div class="splash-bg">
                <div class="loader"></div>
                <h1 class="fade-in">SISTEMA DE INVENTÁRIO</h1>
                <h3 class="fade-in" style="font-weight: 300;">Manutenção e Mecânica Estel</h3>
                <p class="fade-in">Carregando Inteligência Artificial de Visão...</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        time.sleep(4)  # Tempo da animação de abertura
    placeholder.empty()
    st.session_state.splash_done = True

# --- 3. CARREGAMENTO DA IA (EASYOCR) ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

# --- 4. FUNÇÕES DE APOIO ---
def normalizar_codigo(codigo):
    if pd.isna(codigo) or codigo == "": return ""
    return str(codigo).split('-')[0].lstrip('0')

# --- 5. ESTADO DO APP E INTERFACE ---
if 'db' not in st.session_state:
    st.session_state.db = None
if 'contabilizados' not in st.session_state:
    st.session_state.contabilizados = set()

st.title("🏗️ Gestão de Ativos")

# --- SEÇÃO DE IMPORTAÇÃO (VISÍVEL SE NÃO HOUVER DADOS) ---
if st.session_state.db is None:
    st.markdown("### 📥 Iniciar Novo Inventário")
    arquivo = st.file_uploader("Selecione a planilha Excel (CPBE118)", type=['xlsx'])
    
    if arquivo:
        df = pd.read_excel(arquivo)
        df.columns = df.columns.str.strip()
        # Filtra linhas válidas e prepara busca
        df = df.dropna(subset=['Código do Bem'])
        df['Chave_Busca'] = df['Código do Bem'].apply(normalizar_codigo)
        st.session_state.db = df
        st.success("Base Adami carregada com sucesso!")
        st.rerun()

# --- SEÇÃO DE OPERAÇÃO (APÓS IMPORTAR) ---
else:
    # Cabeçalho com métricas
    total = len(st.session_state.db)
    encontrados = len(st.session_state.contabilizados)
    perc = (encontrados / total * 100) if total > 0 else 0
    
    col1, col2, col3 = st.columns([1,1,1])
    col1.metric("Total", total)
    col2.metric("Encontrados", encontrados)
    col3.metric("Progresso", f"{perc:.1f}%")
    st.progress(perc / 100)

    # Scanner IA
    st.subheader("📸 Scanner de Patrimônio")
    foto = st.camera_input("Fotografar etiqueta")
    
    id_detectado = ""
    if foto:
        with st.spinner('IA analisando etiqueta...'):
            img = Image.open(foto)
            results = reader.readtext(np.array(img))
            nums = ["".join(filter(str.isdigit, t)) for (_, t, _) in results if "".join(filter(str.isdigit, t))]
            if nums:
                id_detectado = nums[0]
                st.success(f"🤖 Identificado: {id_detectado}")

    busca = st.text_input("Número do Patrimônio:", value=id_detectado)

    if busca:
        alvo = busca.lstrip('0')
        item = st.session_state.db[st.session_state.db['Chave_Busca'] == alvo]

        if not item.empty:
            idx = item.index[0]
            with st.container(border=True):
                st.write(f"**Descrição:** {item.at[idx, 'Descrição do Bem']}")
                st.write(f"**Código:** {item.at[idx, 'Código do Bem']}")
                
                v_orig = item.at[idx, 'Valor Original']
                v_depr = item.at[idx, 'Depreciação Acumulada']
                st.info(f"💰 Valor Líquido: R$ {v_orig - v_depr:,.2f}")

                if st.button("✅ Confirmar"):
                    st.session_state.contabilizados.add(alvo)
                    st.rerun()
        else:
            st.error("Item não localizado.")

    # Exportação e Reset
    st.divider()
    c_exp, c_res = st.columns(2)
    
    with c_exp:
        df_out = st.session_state.db.copy()
        df_out['Status'] = df_out['Chave_Busca'].apply(lambda x: 'OK' if x in st.session_state.contabilizados else 'PENDENTE')
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_out.to_excel(writer, index=False)
        st.download_button("📥 Baixar Relatório", output.getvalue(), "inventario.xlsx")
        
    with c_res:
        if st.button("⚠️ Reiniciar App"):
            st.session_state.db = None
            st.session_state.contabilizados = set()
            st.session_state.splash_done = None
            st.rerun()
