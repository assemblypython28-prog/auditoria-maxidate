import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time
import io
from PIL import Image
import pytesseract # Motor de OCR mais leve

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
        transition: 0.3s;
    }
    .stButton>button:hover { background-color: #334155; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    
    /* Cards de Dashboard */
    .metric-card {
        background: white; padding: 24px; border-radius: 16px;
        border: 1px solid #E2E8F0; text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }
    
    /* Estilização das Abas */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #F1F5F9; padding: 8px; border-radius: 12px; }
    .stTabs [aria-selected="true"] { background-color: #FFFFFF !important; color: #1E293B !important; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXÃO E LÓGICA DE DADOS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def normalizar_codigo(codigo):
    if pd.isna(codigo) or codigo == "": return ""
    # Remove zeros à esquerda e a parte após o hífen
    return str(codigo).split('-')[0].lstrip('0')

@st.cache_data(ttl=10)
def carregar_da_nuvem():
    try:
        # Lê a planilha configurada nos Secrets
        df = conn.read()
        if df.empty or len(df.columns) < 2: return None
        
        # Garante que as colunas existam
        if 'Status' not in df.columns: df['Status'] = 'Pendente'
        if 'Código do Bem' not in df.columns: return None
        
        # Cria chave de busca simplificada (normalizada)
        df['Chave_Busca'] = df['Código do Bem'].astype(str).apply(normalizar_codigo)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados da nuvem: {e}")
        return None

# Estado da sessão para armazenar o banco de dados
if 'db' not in st.session_state:
    st.session_state.db = carregar_da_nuvem()

# --- 3. INTERFACE PRINCIPAL ---
st.markdown('<h1 style="color: #0F172A; font-weight: 800; letter-spacing: -1px;">🏗️ Auditoria de Ativos Estel</h1>', unsafe_allow_html=True)

# FLUXO DE IMPORTAÇÃO (Só aparece se o banco de dados estiver vazio)
if st.session_state.db is None:
    st.markdown("""
        <div style="background: white; padding: 40px; border-radius: 16px; border: 1px dashed #CBD5E1; text-align: center; margin-top: 20px;">
            <h3 style="color: #1E293B;">Nenhum inventário ativo na nuvem</h3>
            <p style="color: #64748B;">Selecione o arquivo Excel da Estel (CPBE118) para iniciar.</p>
        </div>
    """, unsafe_allow_html=True)
    
    arquivo = st.file_uploader("", type=['xlsx'])
    if arquivo:
        with st.spinner('Sincronizando com a nuvem...'):
            df = pd.read_excel(arquivo)
            df.columns = df.columns.str.strip() # Remove espaços nos cabeçalhos
            
            # Garante coluna Status e cria chave de busca
            if 'Status' not in df.columns: df['Status'] = 'Pendente'
            df['Chave_Busca'] = df['Código do Bem'].astype(str).apply(normalizar_codigo)
            
            # Salva na Planilha Google (dropando a chave temporária)
            conn.update(data=df.drop(columns=['Chave_Busca']))
            st.session_state.db = df
            st.success("Base Estel carregada e sincronizada!")
            time.sleep(1)
            st.rerun()

else:
    # --- APP OPERACIONAL ---
    tab_scan, tab_lista, tab_dash = st.tabs(["🔍 SCANNER IA", "📑 LISTA DE BENS", "📊 DASHBOARD & EXPORT"])

    # --- ABA 1: SCANNER COM CÂMERA ---
    with tab_scan:
        st.markdown("### Tire uma foto da etiqueta de patrimônio")
        foto = st.camera_input("Capturar Etiqueta")
        
        id_detectado = ""
        
        if foto:
            with st.spinner('Analisando imagem...'):
                try:
                    # Converte imagem PIL
                    img = Image.open(foto)
                    # Executa OCR usando Tesseract (motor leve)
                    texto_completo = pytesseract.image_to_string(img)
                    
                    # Filtra apenas números
                    nums = "".join(filter(str.isdigit, texto_completo))
                    
                    if nums:
                        id_detectado = nums
                        st.toast(f"Código detectado pela IA: {id_detectado}")
                    else:
                        st.warning("IA não detectou números. Tente focar melhor ou digite manualmente.")
                except Exception as e:
                    st.error(f"Erro no OCR: {e}")

        st.divider()
        busca = st.text_input("Número do Ativo Detectado (Confirme ou Digite):", value=id_detectado, placeholder="Ex: 01001234")

        if busca:
            # Normaliza o número buscado
            alvo = busca.lstrip('0')
            # Busca na base normalizada
            item_data = st.session_state.db[st.session_state.db['Chave_Busca'] == alvo]

            if not item_data.empty:
                idx = item_data.index[0]
                with st.container(border=True):
                    st.markdown(f"### Ativo Encontrado: {item_data.at[idx, 'Descrição do Bem']}")
                    st.write(f"Código Original: **{item_data.at[idx, 'Código do Bem']}**")
                    st.write(f"Área/Localização: **{item_data.at[idx].get('Área/Localização', 'Não informado')}**")
                    st.write(f"Status Atual: `{item_data.at[idx, 'Status']}`")
                    
                    if st.button("✅ CONFIRMAR PRESENÇA"):
                        # Atualiza Localmente e na Nuvem
                        st.session_state.db.at[idx, 'Status'] = 'Auditado'
                        conn.update(data=st.session_state.db.drop(columns=['Chave_Busca']))
                        st.success("Progresso salvo na nuvem!")
                        time.sleep(0.5)
                        st.rerun()
            else:
                st.warning("⚠️ Ativo não localizado na base original.")
                with st.expander("➕ CADASTRAR COMO SOBRA DE INVENTÁRIO", expanded=True):
                    with st.form("form_sobra"):
                        f_desc = st.text_input("Descrição do Item")
                        if st.form_submit_button("REGISTRAR SOBRA"):
                            nova_sobra = pd.DataFrame([{
                                'Código do Bem': busca, # Usa o que foi digitado/detectado
                                'Descrição do Bem': f"[SOBRA] {f_desc}",
                                'Status': 'Auditado',
                                'Chave_Busca': alvo
                            }])
                            # Adiciona sobra à base e sincroniza
                            st.session_state.db = pd.concat([st.session_state.db, nova_sobra], ignore_index=True)
                            conn.update(data=st.session_state.db.drop(columns=['Chave_Busca']))
                            st.success("Sobra registrada!")
                            time.sleep(1)
                            st.rerun()

    # --- ABA 2: LISTA COMPLETA ---
    with tab_lista:
        st.markdown("### Base de Bens Carregada (Atualizado em tempo real)")
        # Mostra as colunas principais
        st.dataframe(st.session_state.db[['Código do Bem', 'Descrição do Bem', 'Status']], use_container_width=True, hide_index=True)

    # --- ABA 3: DASHBOARD ---
    with tab_dash:
        total = len(st.session_state.db)
        audit = len(st.session_state.db[st.session_state.db['Status'] == 'Auditado'])
        perc = (audit/total*100) if total > 0 else 0
        
        c1, c2 = st.columns(2)
        c1.markdown(f'<div class="metric-card"><h2 style="margin:0;">{audit} / {total}</h2><p style="margin:0; color:#64748B;">ITENS AUDITADOS</p></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><h2 style="margin:0;">{perc:.1f}%</h2><p style="margin:0; color:#64748B;">PROGRESSO TOTAL</p></div>', unsafe_allow_html=True)
        
        st.divider()
        st.subheader("💾 Exportação e Fechamento")
        
        # Preparação do arquivo para download (datado)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.db.drop(columns=['Chave_Busca']).to_excel(writer, index=False)
        data_excel = output.getvalue()
        
        col_d1, col_d2 = st.columns(2)
        
        with col_d1:
            st.download_button(
                label="📥 BAIXAR RELATÓRIO PARCIAL",
                data=data_excel,
                file_name=f"Auditoria_Estel_{time.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Faz o download do progresso atual sem limpar a nuvem."
            )
            
        with col_d2:
            if st.button("🚨 ENCERRAR INVENTÁRIO (LIMPAR NUVEM)", help="Use apenas ao final da obra para liberar o app para um novo Excel."):
                # Processo de limpeza da planilha Google
                df_reset = pd.DataFrame(columns=['Código do Bem', 'Descrição do Bem', 'Status'])
                conn.update(data=df_reset)
                st.session_state.db = None
                st.success("Dados de nuvem limpos com sucesso!")
                time.sleep(2)
                st.rerun()
