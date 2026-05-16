import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import io
from PIL import Image
import easyocr
import numpy as np
import re

# --- INICIALIZAÇÃO DO OCR (uma única vez) ---
@st.cache_resource
def iniciar_ocr():
    return easyocr.Reader(['pt', 'en'], gpu=False)

reader = iniciar_ocr()

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Estel Asset Manager", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #F8FAFC; }
    .stButton>button { width: 100%; border-radius: 8px; height: 48px; background-color: #1E293B; color: white; font-weight: 600; border: none; }
    .metric-card { background: white; padding: 24px; border-radius: 16px; border: 1px solid #E2E8F0; text-align: center; }
    .ocr-result { background: #ECFDF5; border: 2px solid #10B981; border-radius: 12px; padding: 16px; margin: 12px 0; }
    .ocr-error { background: #FEF2F2; border: 2px solid #EF4444; border-radius: 12px; padding: 16px; margin: 12px 0; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXÃO GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def normalizar(c):
    return str(c).split('-')[0].lstrip('0')

def extrair_codigo_ocr(textos):
    """
    Extrai o código do patrimônio do texto OCR.
    Procura por padrões como: CPBE118-00123, 00123, 123, etc.
    """
    texto_completo = ' '.join(textos).upper().replace(' ', '').replace('-', '')
    
    # Padrões comuns em etiquetas de patrimônio
    padroes = [
        r'CPBE\d{3}(\d{3,6})',      # CPBE11800123
        r'CPBE\d{3}-(\d{3,6})',      # CPBE118-00123
        r'(\d{6,8})',                 # 00012345 (código puro)
        r'(\d{3,6})',                 # 12345
    ]
    
    for padrao in padroes:
        match = re.search(padrao, texto_completo)
        if match:
            return match.group(1).lstrip('0')
    
    # Se não encontrou padrão, retorna o maior número encontrado
    numeros = re.findall(r'\d+', texto_completo)
    if numeros:
        return max(numeros, key=len).lstrip('0')
    
    return None

@st.cache_data(ttl=10)
def carregar_dados():
    try:
        df = conn.read()
        if df is None or df.empty: return None
        if 'Status' not in df.columns: df['Status'] = 'Pendente'
        df['Chave'] = df['Código do Bem'].astype(str).apply(normalizar)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")
        return None

if 'db' not in st.session_state:
    st.session_state.db = carregar_dados()

if 'codigo_ocr' not in st.session_state:
    st.session_state.codigo_ocr = ""

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
        st.markdown("### 📸 Tirar Foto da Etiqueta do Património")
        
        # === CÂMERA ===
        foto = st.camera_input("Aponte a câmera para a etiqueta e clique em 'Take Photo'")
        
        codigo_detectado = None
        
        if foto is not None:
            col1, col2 = st.columns(2)
            
            with col1:
                st.image(foto, caption="Foto capturada", use_container_width=True)
            
            with col2:
                with st.spinner("🔍 Analisando imagem com OCR..."):
                    # Converte para formato que o EasyOCR aceita
                    img = Image.open(foto)
                    img_array = np.array(img)
                    
                    # Executa OCR
                    resultados = reader.readtext(img_array, detail=0, paragraph=False)
                    
                    st.markdown("**Texto detectado:**")
                    for i, texto in enumerate(resultados):
                        st.code(texto)
                    
                    # Extrai o código do patrimônio
                    codigo_detectado = extrair_codigo_ocr(resultados)
                    
                    if codigo_detectado:
                        st.markdown(f"""
                        <div class="ocr-result">
                            <h4>✅ Código Detectado: <code>{codigo_detectado}</code></h4>
                            <p>O sistema identificou este código na etiqueta.</p>
                        </div>
                        """, unsafe_allow_html=True)
                        st.session_state.codigo_ocr = codigo_detectado
                    else:
                        st.markdown("""
                        <div class="ocr-error">
                            <h4>⚠️ Código não reconhecido</h4>
                            <p>Não foi possível extrair um código válido da imagem. Digite manualmente abaixo.</p>
                        </div>
                        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### ✏️ Confirmar ou Digitar Código Manualmente")
        
        # Campo preenchido automaticamente pelo OCR (ou vazio)
        busca = st.text_input(
            "Número do Ativo:", 
            value=st.session_state.codigo_ocr,
            placeholder="Ex: 00123 ou CPBE118-00123"
        )
        
        # Botão para limpar o OCR e tentar de novo
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔄 Limpar e Tentar Novamente"):
                st.session_state.codigo_ocr = ""
                st.rerun()
        
        if busca:
            alvo = busca.lstrip('0')
            item = st.session_state.db[st.session_state.db['Chave'] == alvo]
            
            if not item.empty:
                idx = item.index[0]
                with st.container():
                    st.info(f"**Item Localizado:** {item.at[idx, 'Descrição do Bem']}")
                    st.write(f"Status Atual: {item.at[idx, 'Status']}")
                    
                    if st.button("✅ CONFIRMAR AUDITORIA"):
                        st.session_state.db.at[idx, 'Status'] = 'Auditado'
                        conn.create(worksheet="Sheet1", data=st.session_state.db.drop(columns=['Chave']))
                        st.success("Salvo na nuvem com sucesso!")
                        st.session_state.codigo_ocr = ""
                        time.sleep(0.8)
                        st.rerun()
            else:
                st.error("Item não encontrado na base de dados.")
                with st.expander("Cadastrar como Sobra"):
                    desc_sobra = st.text_input("Descrição da Sobra")
                    if st.button("Salvar Sobra"):
                        nova = pd.DataFrame([{
                            'Código do Bem': busca, 
                            'Descrição do Bem': f"[SOBRA] {desc_sobra}", 
                            'Status': 'Auditado', 
                            'Chave': alvo
                        }])
                        st.session_state.db = pd.concat([st.session_state.db, nova], ignore_index=True)
                        conn.create(worksheet="Sheet1", data=st.session_state.db.drop(columns=['Chave']))
                        st.session_state.codigo_ocr = ""
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
