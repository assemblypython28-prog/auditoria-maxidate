import streamlit as st
import pandas as pd
import easyocr
import numpy as np
import cv2
from PIL import Image
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Inventário Estel AI", page_icon="🔍", layout="centered")

# Estilo para botões grandes (fácil de clicar no tablet)
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; background-color: #007bff; color: white; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

# --- FUNÇÕES DE APOIO ---
def normalizar_codigo(codigo):
    if pd.isna(codigo) or codigo == "": return ""
    return str(codigo).split('-')[0].lstrip('0')

# --- ESTADO DO APP ---
if 'db' not in st.session_state:
    st.session_state.db = None
if 'contabilizados' not in st.session_state:
    st.session_state.contabilizados = set()

st.title("📋 Inventário Estel")

# --- 1. SEÇÃO DE IMPORTAÇÃO (AGORA NA TELA PRINCIPAL) ---
if st.session_state.db is None:
    st.info("👋 Bem-vindo! Primeiro, importe sua planilha de bens.")
    arquivo_excel = st.file_uploader("Clique aqui para selecionar o Excel (CPBE118)", type=['xlsx', 'csv'])
    
    if arquivo_excel:
        df_base = pd.read_excel(arquivo_excel) if arquivo_excel.name.endswith('xlsx') else pd.read_csv(arquivo_excel)
        df_base.columns = df_base.columns.str.strip()
        
        # Limpeza para focar nos dados reais da Adami
        df_base = df_base.dropna(subset=['Código do Bem'])
        df_base['Chave_Busca'] = df_base['Código do Bem'].apply(normalizar_codigo)
        
        st.session_state.db = df_base
        st.success("Planilha carregada com sucesso! O scanner foi liberado.")
        st.rerun()

# --- 2. FLUXO DE INVENTÁRIO (SÓ APARECE APÓS IMPORTAR) ---
else:
    # Botão para resetar/trocar planilha
    if st.button("🔄 Trocar Planilha / Limpar Dados"):
        st.session_state.db = None
        st.session_state.contabilizados = set()
        st.rerun()

    st.divider()

    # Dashboard de Progresso
    total = len(st.session_state.db)
    encontrados = len(st.session_state.contabilizados)
    perc = (encontrados / total * 100) if total > 0 else 0
    
    c1, c2 = st.columns(2)
    c1.metric("Itens Totais", total)
    c2.metric("Concluído", f"{perc:.1f}%")
    st.progress(perc / 100)

    # Scanner IA
    st.subheader("📸 Scanner de Etiqueta")
    foto = st.camera_input("Tire a foto da etiqueta")
    
    id_detectado = ""
    if foto:
        with st.spinner('IA lendo número...'):
            img = Image.open(foto)
            results = reader.readtext(np.array(img))
            nums = ["".join(filter(str.isdigit, t)) for (_, t, _) in results if "".join(filter(str.isdigit, t))]
            if nums:
                id_detectado = nums[0]
                st.success(f"🤖 IA Identificou: {id_detectado}")

    # Busca e Confirmação
    busca = st.text_input("Confirme o Número (Ex: 333):", value=id_detectado)

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

                if st.button("✅ Confirmar Localização"):
                    st.session_state.contabilizados.add(alvo)
                    st.toast(f"Item {alvo} marcado!")
                    st.rerun()
        else:
            st.error("Número não encontrado no Excel.")
            if st.button("➕ Cadastrar como Novo"):
                with st.form("novo_cad"):
                    st.write("Novo Cadastro")
                    nc1 = st.text_input("Cód", value=busca)
                    nc2 = st.text_input("Descrição")
                    if st.form_submit_button("Salvar"):
                        st.success("Salvo!")

    st.divider()
    
    # Exportação (Sempre visível no final)
    if encontrados > 0:
        st.subheader("📤 Finalizar")
        df_out = st.session_state.db.copy()
        df_out['Status_Inventario'] = df_out['Chave_Busca'].apply(
            lambda x: 'CONTABILIZADO' if x in st.session_state.contabilizados else 'PENDENTE'
        )
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_out.to_excel(writer, index=False)
        st.download_button("📥 Baixar Excel Atualizado", output.getvalue(), "inventario_final.xlsx")

