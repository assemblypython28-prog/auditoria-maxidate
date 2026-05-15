
import streamlit as st
import pandas as pd
import easyocr
import numpy as np
import cv2
from PIL import Image
import io

# --- CONFIGURAÇÃO DO APP (MODO PWA) ---
st.set_page_config(
    page_title="Inventário Estel AI",
    page_icon="🔍",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Estilo para melhorar a visualização no Tablet/Telemóvel
st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; font-weight: bold; }
    [data-testid="stExpander"] { border: 1px solid #007bff; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- CARREGAMENTO DA INTELIGÊNCIA ARTIFICIAL ---
@st.cache_resource
def load_ocr():
    # Carrega o modelo uma única vez para ganhar velocidade
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

# --- FUNÇÕES DE LÓGICA DE NEGÓCIO ---
def normalizar_codigo(codigo):
    """Limpa '00000333-00' para '333'"""
    if pd.isna(codigo) or codigo == "": return ""
    base = str(codigo).split('-')[0]
    return base.lstrip('0')

def executar_ocr(imagem_bytes):
    """Lógica Opção B: IA lê a foto e extrai números"""
    try:
        img = Image.open(imagem_bytes)
        img_array = np.array(img)
        # O EasyOCR trabalha melhor com RGB ou Escala de Cinza
        results = reader.readtext(img_array)
        
        numeros = []
        for (bbox, texto, prob) in results:
            # Extrai apenas dígitos encontrados no texto
            clean_text = "".join(filter(str.isdigit, texto))
            if clean_text:
                numeros.append(clean_text)
        
        return numeros[0] if numeros else None
    except:
        return None

# --- GESTÃO DE ESTADO (MEMÓRIA DO APP) ---
if 'db' not in st.session_state:
    st.session_state.db = None
if 'contabilizados' not in st.session_state:
    st.session_state.contabilizados = set()

# --- INTERFACE PRINCIPAL ---
st.title("📋 Inventário Patrimonial")

# Sidebar: Importar e Exportar Excel
with st.sidebar:
    st.header("⚙️ Gestão de Dados")
    file = st.file_uploader("Importar Planilha Excel", type=['xlsx'])
    
    if file:
        df_base = pd.read_excel(file)
        # Limpeza de nomes de colunas (remove espaços invisíveis)
        df_base.columns = df_base.columns.str.strip()
        # Cria coluna de busca invisível
        df_base['Busca_IA'] = df_base['Código do Bem'].apply(normalizar_codigo)
        st.session_state.db = df_base
        st.success("Base Estel carregada!")

    if st.session_state.db is not None:
        st.divider()
        if st.button("📤 Gerar Relatório Final"):
            # Adiciona status ao Excel de saída
            df_final = st.session_state.db.copy()
            df_final['Status_Inventario'] = df_final['Busca_IA'].apply(
                lambda x: 'CONTABILIZADO' if x in st.session_state.contabilizados else 'PENDENTE'
            )
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Resultado')
            
            st.download_button(
                label="⬇️ Baixar Excel Atualizado",
                data=output.getvalue(),
                file_name="inventario_finalizado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# --- FLUXO DE TRABALHO NA ÁREA ---
if st.session_state.db is not None:
    # 1. Dashboard de Porcentagem
    total_itens = len(st.session_state.db)
    encontrados = len(st.session_state.contabilizados)
    perc = (encontrados / total_itens * 100) if total_itens > 0 else 0
    
    col1, col2 = st.columns(2)
    col1.metric("Itens Localizados", encontrados)
    col2.metric("Acuracidade", f"{perc:.1f}%")
    st.progress(perc / 100)

    st.divider()

    # 2. Scanner com IA (Opção B)
    st.subheader("📸 Scanner de Etiqueta")
    foto = st.camera_input("Tirar foto do património")
    
    id_detectado = ""
    if foto:
        with st.spinner('IA analisando imagem...'):
            id_detectado = executar_ocr(foto)
            if id_detectado:
                st.success(f"🤖 IA detetou o número: {id_detectado}")
            else:
                st.warning("IA não conseguiu ler. Introduza manualmente abaixo.")

    # 3. Busca e Confirmação
    busca_manual = st.text_input("Confirme ou digite o número:", value=id_detectado)
    
    if busca_manual:
        cod_limpo = busca_manual.lstrip('0')
        df = st.session_state.db
        resultado = df[df['Busca_IA'] == cod_limpo]

        if not resultado.empty:
            idx = resultado.index[0]
            with st.container(border=True):
                st.write(f"**Descrição:** {resultado.at[idx, 'Descrição do Bem']}")
                st.write(f"**Código Real:** {resultado.at[idx, 'Código do Bem']}")
                
                # Cálculos de Valor
                v_orig = resultado.at[idx, 'Valor Original']
                v_depr = resultado.at[idx, 'Depreciação Acumulada']
                v_total = v_orig - v_depr
                
                st.write(f"**Área Registada:** {resultado.at[idx, 'Área'] if 'Área' in resultado.columns else 'N/A'}")
                st.info(f"💰 Valor Líquido: R$ {v_total:,.2f}")

                if st.button("✅ Marcar como Contabilizado"):
                    st.session_state.contabilizados.add(cod_limpo)
                    st.success("Item guardado!")
                    st.rerun()
        else:
            st.error("Património não encontrado na base.")
            with st.expander("➕ Cadastrar como Novo Item"):
                with st.form("form_novo"):
                    c1 = st.text_input("Código", value=busca_manual)
                    c2 = st.text_input("Descrição")
                    c3 = st.text_input("Área")
                    c4 = st.number_input("Valor Original", step=0.01)
                    c5 = st.number_input("Depreciação Acumulada", step=0.01)
                    if st.form_submit_button("Salvar Cadastro"):
                        novo_dado = {
                            'Código do Bem': c1, 'Descrição do Bem': c2, 
                            'Área': c3, 'Valor Original': c4, 
                            'Depreciação Acumulada': c5, 'Busca_IA': c1.lstrip('0')
                        }
                        st.session_state.db = pd.concat([st.session_state.db, pd.DataFrame([novo_dado])], ignore_index=True)
                        st.session_state.contabilizados.add(c1.lstrip('0'))
                        st.rerun()
else:
    st.info("Aguardando importação do Excel para iniciar.")
