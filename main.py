import streamlit as st
import pandas as pd
import easyocr
import numpy as np
import time
import io
from PIL import Image

# --- 1. CONFIGURAÇÃO VISUAL E PWA ---
st.set_page_config(page_title="Estel Asset Manager", page_icon="🏗️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3.5em; background-color: #1b4f72; color: white; font-weight: bold; border: none; }
    .stButton>button:hover { background-color: #2874a6; }
    .stTabs [aria-selected="true"] { background-color: #1b4f72 !important; color: white !important; }
    .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 5px solid #1b4f72; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CARREGAMENTO DA IA ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['en'], gpu=False)

reader = load_ocr()

# --- 3. FUNÇÕES DE SUPORTE ---
def normalizar_codigo(codigo):
    if pd.isna(codigo) or codigo == "": return ""
    return str(codigo).split('-')[0].lstrip('0')

# --- 4. GESTÃO DE ESTADO ---
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
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 80vh; background-image: linear-gradient(rgba(255,255,255,0.8), rgba(255,255,255,0.8)), url('https://images.unsplash.com/photo-1581092162384-8987c1d64718?q=80&w=1000'); background-size: cover;">
                <h1 style="color: #1b4f72; font-family: sans-serif; font-size: 3em;">ESTEL</h1>
                <h2 style="color: #566573;">Asset Management & Auditoria</h2>
                <p>Carregando módulos de visão computacional...</p>
            </div>
            """, unsafe_allow_html=True)
        time.sleep(3)
    st.session_state.splash_done = True
    st.rerun()

# --- 6. INTERFACE PRINCIPAL ---
st.title("🏗️ Asset Management Estel")

if st.session_state.db is None:
    st.subheader("📥 Carga Inicial de Dados")
    st.info("Para começar, faça o upload da planilha de inventário (CPBE118).")
    arquivo = st.file_uploader("Arraste a planilha Adami aqui", type=['xlsx'])
    
    if arquivo:
        df = pd.read_excel(arquivo)
        df.columns = df.columns.str.strip()
        # Garante que as colunas essenciais existem ou cria se necessário
        for col in ['Código do Bem', 'Descrição do Bem', 'Valor Original', 'Valor Total', 'Depreciação Acumulada']:
            if col not in df.columns:
                df[col] = 0 if 'Valor' in col or 'Depr' in col else ""
        
        df = df.dropna(subset=['Código do Bem'])
        df['Chave_Busca'] = df['Código do Bem'].apply(normalizar_codigo)
        st.session_state.db = df
        st.success("Base de dados integrada!")
        st.rerun()
else:
    tab_scan, tab_lista, tab_dash = st.tabs(["📸 SCANNER & BUSCA", "📋 LISTA DE BENS", "📊 RELATÓRIO"])

    # --- ABA 1: SCANNER & CADASTRO ---
    with tab_scan:
        st.subheader("Localizar Ativo")
        foto = st.camera_input("Scanner de Etiqueta")
        
        id_detectado = ""
        if foto:
            with st.spinner('IA Analisando imagem...'):
                img = Image.open(foto)
                results = reader.readtext(np.array(img))
                nums = ["".join(filter(str.isdigit, t)) for (_, t, _) in results if "".join(filter(str.isdigit, t))]
                if nums:
                    id_detectado = nums[0]
                    st.success(f"Deteção Automática: {id_detectado}")

        busca = st.text_input("Digite ou confirme o número do bem:", value=id_detectado)

        if busca:
            alvo = busca.lstrip('0')
            item_data = st.session_state.db[st.session_state.db['Chave_Busca'] == alvo]

            if not item_data.empty:
                idx = item_data.index[0]
                with st.container(border=True):
                    st.markdown(f"### {item_data.at[idx, 'Descrição do Bem']}")
                    st.write(f"**Código Completo:** {item_data.at[idx, 'Código do Bem']}")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("V. Original", f"R$ {item_data.at[idx, 'Valor Original']:,.2f}")
                    c2.metric("V. Total", f"R$ {item_data.at[idx, 'Valor Total']:,.2f}")
                    c3.metric("Depreciação", f"R$ {item_data.at[idx, 'Depreciação Acumulada']:,.2f}")

                    if st.button("✅ CONFIRMAR PRESENÇA"):
                        st.session_state.contabilizados.add(alvo)
                        st.success(f"Item {alvo} marcado como presente!")
                        time.sleep(0.5)
                        st.rerun()
            else:
                # FORMULÁRIO DE CADASTRO COMPLETO (SOBRA DE INVENTÁRIO)
                st.warning("⚠️ Número não encontrado na base de dados.")
                with st.expander("➕ CADASTRAR NOVO ITEM (SOBRA)", expanded=True):
                    with st.form("form_sobra_completo"):
                        st.write("Preencha os campos para incluir este bem no inventário:")
                        f_cod = st.text_input("Código do Bem", value=busca)
                        f_desc = st.text_input("Descrição do Bem")
                        col_a, col_b, col_c = st.columns(3)
                        f_orig = col_a.number_input("Valor Original", min_value=0.0, format="%.2f")
                        f_total = col_b.number_input("Valor Total", min_value=0.0, format="%.2f")
                        f_depr = col_c.number_input("Depreciação Acumulada", min_value=0.0, format="%.2f")
                        
                        if st.form_submit_button("💾 SALVAR E CONFIRMAR"):
                            novo_item = pd.DataFrame([{
                                'Código do Bem': f_cod,
                                'Descrição do Bem': f"[SOBRA] {f_desc}",
                                'Valor Original': f_orig,
                                'Valor Total': f_total,
                                'Depreciação Acumulada': f_depr,
                                'Chave_Busca': f_cod.lstrip('0')
                            }])
                            st.session_state.db = pd.concat([st.session_state.db, novo_item], ignore_index=True)
                            st.session_state.contabilizados.add(f_cod.lstrip('0'))
                            st.success("Novo item cadastrado e auditado!")
                            time.sleep(1)
                            st.rerun()

    # --- ABA 2: LISTA ---
    with tab_lista:
        st.subheader("Status do Inventário")
        df_view = st.session_state.db.copy()
        df_view['Status'] = df_view['Chave_Busca'].apply(lambda x: '✅ OK' if x in st.session_state.contabilizados else '⚠️ PENDENTE')
        
        # Filtros rápidos
        filtro = st.radio("Filtrar por:", ["Todos", "Pendentes", "Auditados"], horizontal=True)
        if filtro == "Pendentes":
            df_view = df_view[df_view['Status'] == '⚠️ PENDENTE']
        elif filtro == "Auditados":
            df_view = df_view[df_view['Status'] == '✅ OK']

        st.dataframe(df_view[['Código do Bem', 'Descrição do Bem', 'Status', 'Valor Total']], use_container_width=True, hide_index=True)

    # --- ABA 3: DASHBOARD ---
    with tab_dash:
        total = len(st.session_state.db)
        encontrados = len(st.session_state.contabilizados)
        perc = (encontrados / total * 100) if total > 0 else 0
        
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            st.markdown(f'<div class="metric-card"><h2>{encontrados} / {total}</h2><p>Auditados</p></div>', unsafe_allow_html=True)
        with c_m2:
            st.markdown(f'<div class="metric-card"><h2>{perc:.1f}%</h2><p>Conclusão</p></div>', unsafe_allow_html=True)
        
        st.progress(perc / 100)
        
        st.divider()
        st.subheader("Extração de Dados")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_view.to_excel(writer, index=False)
        st.download_button("📥 BAIXAR EXCEL ATUALIZADO", output.getvalue(), "relatorio_final_estel.xlsx")
        
        if st.button("🛑 REINICIAR PROCESSO (Limpar tudo)"):
            st.session_state.db = None
            st.session_state.contabilizados = set()
            st.rerun()
