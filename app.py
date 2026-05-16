import streamlit as st
import pandas as pd
import time
import io
import re
from PIL import Image
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from supabase import create_client, Client

# ============================================================
# INICIALIZACAO DO OCR (uma unica vez)
# ============================================================
@st.cache_resource
def iniciar_ocr():
    return RapidOCR()

ocr_engine = iniciar_ocr()

# ============================================================
# CONFIGURACAO SUPABASE
# ============================================================
@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()

# ============================================================
# FUNCOES DE BANCO DE DADOS (SUPABASE)
# ============================================================
def carregar_do_supabase(obra_id="default"):
    """Carrega inventario do Supabase."""
    try:
        response = supabase.table("inventario").select("*").eq("obra_id", obra_id).execute()
        dados = response.data
        if not dados:
            return pd.DataFrame(columns=["Codigo do Bem", "Descricao do Bem", "Status", "Data Auditoria", "Observacoes"])

        df = pd.DataFrame(dados)
        df = df.rename(columns={
            "codigo": "Codigo do Bem",
            "descricao": "Descricao do Bem",
            "status": "Status",
            "data_auditoria": "Data Auditoria",
            "observacoes": "Observacoes"
        })
        df = df[["Codigo do Bem", "Descricao do Bem", "Status", "Data Auditoria", "Observacoes"]]
        return df
    except Exception as e:
        st.error(f"Erro ao carregar do banco: {e}")
        return pd.DataFrame(columns=["Codigo do Bem", "Descricao do Bem", "Status", "Data Auditoria", "Observacoes"])

def salvar_item_supabase(codigo, descricao, status="Pendente", data_aud="", obs="", obra_id="default"):
    """Salva ou atualiza um item no Supabase."""
    try:
        response = supabase.table("inventario").select("id").eq("codigo", str(codigo)).eq("obra_id", obra_id).execute()

        if response.data:
            supabase.table("inventario").update({
                "status": status,
                "data_auditoria": data_aud,
                "observacoes": obs
            }).eq("codigo", str(codigo)).eq("obra_id", obra_id).execute()
        else:
            supabase.table("inventario").insert({
                "obra_id": obra_id,
                "codigo": str(codigo),
                "descricao": str(descricao),
                "status": status,
                "data_auditoria": data_aud,
                "observacoes": obs
            }).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")
        return False

def deletar_obra(obra_id):
    """Deleta todos os itens de uma obra."""
    try:
        supabase.table("inventario").delete().eq("obra_id", obra_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao limpar obra: {e}")
        return False

# ============================================================
# FUNCOES DE OCR
# ============================================================
def extrair_codigo_ocr(textos):
    """Extrai o codigo do patrimonio do texto OCR."""
    texto_completo = " ".join(textos).upper().replace(" ", "").replace("-", "")

    padroes = [
        r"CPBE\d{3}(\d{3,6})",
        r"(\d{6,8})",
        r"(\d{3,6})",
    ]

    for padrao in padroes:
        match = re.search(padrao, texto_completo)
        if match:
            return match.group(1).lstrip("0")

    numeros = re.findall(r"\d+", texto_completo)
    if numeros:
        return max(numeros, key=len).lstrip("0")

    return None

def executar_ocr(imagem):
    """Executa OCR em uma imagem PIL."""
    img_array = np.array(imagem)
    result, _ = ocr_engine(img_array)
    if result:
        return [r[1] for r in result]
    return []

# ============================================================
# FUNCOES AUXILIARES
# ============================================================
def normalizar(codigo):
    """Remove zeros a esquerda e sufixos apos hifen."""
    if pd.isna(codigo):
        return ""
    return str(codigo).split("-")[0].lstrip("0")

def limpar_excel(df_raw):
    """Limpa o DataFrame bruto do Excel."""
    if "Codigo do Bem" not in df_raw.columns:
        df_raw.columns = df_raw.iloc[0]
        df_raw = df_raw.iloc[1:].reset_index(drop=True)

    df_raw = df_raw[df_raw["Codigo do Bem"].astype(str).str.match(r"^\d{3,}", na=False)].copy()
    df_raw = df_raw[df_raw["Descricao do Bem"].notna()].copy()
    df_raw = df_raw[df_raw["Descricao do Bem"].astype(str).str.strip() != ""].copy()
    df_raw = df_raw[~df_raw["Descricao do Bem"].astype(str).str.contains("Estel Servicos", na=False)].copy()
    df_raw["Codigo do Bem"] = df_raw["Codigo do Bem"].astype(str).str.strip()

    colunas_manter = ["Codigo do Bem", "Descricao do Bem"]
    df_clean = df_raw[colunas_manter].copy()

    return df_clean

def exportar_excel(df):
    """Exporta DataFrame para Excel em memoria."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Inventario")
    output.seek(0)
    return output

# ============================================================
# CONFIGURACAO VISUAL
# ============================================================
st.set_page_config(page_title="Estel Asset Manager", page_icon="🏗", layout="wide")

st.markdown("""
    <style>
    @import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap");
    html, body, [class*="css"] { font-family: "Inter", sans-serif; background-color: #F8FAFC; }
    .stButton>button { width: 100%; border-radius: 8px; height: 48px; background-color: #1E293B; color: white; font-weight: 600; border: none; }
    .stButton>button:hover { background-color: #334155; }
    .success-box { background: #ECFDF5; border-left: 4px solid #10B981; padding: 16px; border-radius: 8px; margin: 12px 0; }
    .error-box { background: #FEF2F2; border-left: 4px solid #EF4444; padding: 16px; border-radius: 8px; margin: 12px 0; }
    .warning-box { background: #FFFBEB; border-left: 4px solid #F59E0B; padding: 16px; border-radius: 8px; margin: 12px 0; }
    .ocr-box { background: #EFF6FF; border: 2px solid #3B82F6; border-radius: 12px; padding: 16px; margin: 12px 0; }
    </style>
    """, unsafe_allow_html=True)

# ============================================================
# INTERFACE PRINCIPAL
# ============================================================
st.markdown("<h1 style=\"color: #0F172A; margin-bottom: 8px;\">Auditoria de Ativos Estel</h1>", unsafe_allow_html=True)
st.markdown("<p style=\"color: #64748B; margin-bottom: 24px;\">Sistema de auditoria com OCR e persistencia na nuvem</p>", unsafe_allow_html=True)

# Barra lateral
with st.sidebar:
    st.markdown("### Identificacao da Obra")

    try:
        obras_resp = supabase.table("inventario").select("obra_id").execute()
        obras_existentes = list(set([r["obra_id"] for r in obras_resp.data])) if obras_resp.data else []
    except:
        obras_existentes = []

    obra_id = st.text_input(
        "ID da Obra:",
        value=st.session_state.get("obra_id", "obra_001"),
        help="Use um ID unico para cada obra"
    )

    if obras_existentes:
        obra_selecionada = st.selectbox("Ou selecione obra existente:", [""] + obras_existentes)
        if obra_selecionada:
            obra_id = obra_selecionada

    if obra_id != st.session_state.get("obra_id", ""):
        st.session_state.obra_id = obra_id
        st.session_state.db = carregar_do_supabase(obra_id)
        st.rerun()

    st.markdown("---")
    st.markdown("### Importar Excel (CPBE118)")
    arquivo = st.file_uploader("Selecionar ficheiro", type=["xlsx", "xls"])
    if arquivo is not None:
        try:
            df_raw = pd.read_excel(arquivo, header=None)
            df_clean = limpar_excel(df_raw)

            if df_clean.empty:
                st.error("Nenhum item valido encontrado no Excel.")
            else:
                progress_bar = st.progress(0)
                total = len(df_clean)

                for i, (_, row) in enumerate(df_clean.iterrows()):
                    salvar_item_supabase(
                        row["Codigo do Bem"],
                        row["Descricao do Bem"],
                        "Pendente",
                        "",
                        "",
                        obra_id
                    )
                    progress_bar.progress((i + 1) / total)

                st.session_state.db = carregar_do_supabase(obra_id)
                st.success(f"{total} itens importados para obra: {obra_id}")
                time.sleep(1)
                st.rerun()

        except Exception as e:
            st.error(f"Erro ao importar: {e}")

    st.markdown("---")
    st.markdown("### Exportar Excel")
    df_atual = st.session_state.get("db", pd.DataFrame())
    if not df_atual.empty:
        excel_bytes = exportar_excel(df_atual)
        st.download_button(
            label="Baixar Inventario",
            data=excel_bytes,
            file_name=f"inventario_{obra_id}_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Nenhum dado para exportar")

    st.markdown("---")
    st.markdown("### Zona de Perigo")
    if st.button("Limpar Obra (Nova Obra)", type="secondary"):
        deletar_obra(obra_id)
        st.session_state.db = pd.DataFrame(columns=["Codigo do Bem", "Descricao do Bem", "Status", "Data Auditoria", "Observacoes"])
        st.success(f"Obra '{obra_id}' limpa!")
        time.sleep(1)
        st.rerun()

    st.markdown("---")
    st.markdown("**Resumo**")
    df_stats = st.session_state.get("db", pd.DataFrame())
    total = len(df_stats)
    auditados = len(df_stats[df_stats["Status"] == "Auditado"])
    st.metric("Total", total)
    st.metric("Auditados", auditados)
    if total > 0:
        st.progress(auditados / total, text=f"{auditados}/{total}")

# Inicializa session state
if "db" not in st.session_state:
    st.session_state.db = carregar_do_supabase(obra_id)
if "codigo_ocr" not in st.session_state:
    st.session_state.codigo_ocr = ""

# ============================================================
# ABAS PRINCIPAIS
# ============================================================
df_atual = st.session_state.db

if df_atual.empty:
    st.warning("Nenhum inventario carregado. Importe um Excel CPBE118 ou selecione uma obra existente.")
    st.info("""
    Como usar:
    1. Digite um ID de obra (ex: obra_001)
    2. Importe o Excel CPBE118 pela barra lateral
    3. Use a aba "Scanner e OCR" para auditar com foto
    4. Os dados sao salvos automaticamente no Supabase
    """)
else:
    tab1, tab2, tab3 = st.tabs(["Scanner e OCR", "Lista Completa", "Dashboard"])

    # ============================================================
    # ABA 1: SCANNER e OCR
    # ============================================================
    with tab1:
        st.markdown("### Captura da Etiqueta com OCR")
        st.info("Dica: Aponte a camera para a etiqueta do patrimonio e tire a foto. O sistema le o codigo automaticamente.")

        foto = st.camera_input("Aponte a camera para a etiqueta e clique em 'Take Photo'")

        codigo_detectado = None

        if foto is not None:
            col1, col2 = st.columns([1, 1])

            with col1:
                st.image(foto, caption="Foto capturada", use_container_width=True)

            with col2:
                with st.spinner("Analisando imagem com OCR..."):
                    img = Image.open(foto)
                    textos_ocr = executar_ocr(img)

                    if textos_ocr:
                        st.markdown("**Texto detectado:**")
                        for texto in textos_ocr:
                            st.code(texto)

                        codigo_detectado = extrair_codigo_ocr(textos_ocr)

                        if codigo_detectado:
                            st.markdown(
                                '<div class="ocr-box"><h4>Codigo Detectado: <code>' + codigo_detectado + '</code></h4>'
                                '<p>O sistema identificou este codigo na etiqueta!</p></div>',
                                unsafe_allow_html=True
                            )
                            st.session_state.codigo_ocr = codigo_detectado
                        else:
                            st.markdown(
                                '<div class="warning-box"><h4>Codigo nao reconhecido automaticamente</h4>'
                                '<p>Nao foi possivel extrair um codigo valido. Digite manualmente abaixo.</p></div>',
                                unsafe_allow_html=True
                            )
                    else:
                        st.warning("Nenhum texto detectado na imagem. Tente novamente com melhor iluminacao.")

        st.markdown("---")
        st.markdown("### Confirmar ou Digitar Codigo Manualmente")

        busca = st.text_input(
            "Numero do Ativo:",
            value=st.session_state.codigo_ocr,
            placeholder="Ex: 00000333 ou 333"
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Limpar OCR e Tentar Novamente"):
                st.session_state.codigo_ocr = ""
                st.rerun()

        if busca:
            alvo = normalizar(busca)
            item = df_atual[df_atual["Codigo do Bem"].astype(str).apply(normalizar) == alvo]

            if not item.empty:
                idx = item.index[0]
                status_atual = item.at[idx, "Status"]
                descricao = item.at[idx, "Descricao do Bem"]
                codigo_completo = item.at[idx, "Codigo do Bem"]

                cor_status = "#10B981" if status_atual == "Auditado" else "#F59E0B"
                st.markdown(
                    '<div class="success-box"><h4>Item Encontrado</h4>'
                    '<p><strong>Codigo:</strong> ' + codigo_completo + '</p>'
                    '<p><strong>Descricao:</strong> ' + descricao + '</p>'
                    '<p><strong>Status:</strong> <span style="color: ' + cor_status + '; font-weight: bold;">' + status_atual + '</span></p></div>',
                    unsafe_allow_html=True
                )

                if status_atual == "Auditado":
                    st.info("Este item ja foi auditado!")
                    st.write(f"Data: {item.at[idx, 'Data Auditoria']}")
                    if item.at[idx, "Observacoes"]:
                        st.write(f"Obs: {item.at[idx, 'Observacoes']}")
                else:
                    obs = st.text_area("Observacoes (opcional):", placeholder="Ex: Bom estado, localizado no deposito...", height=80)
                    if st.button("CONFIRMAR AUDITORIA", type="primary"):
                        data_agora = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")

                        sucesso = salvar_item_supabase(
                            codigo_completo,
                            descricao,
                            "Auditado",
                            data_agora,
                            obs,
                            obra_id
                        )

                        if sucesso:
                            st.session_state.db.at[idx, "Status"] = "Auditado"
                            st.session_state.db.at[idx, "Data Auditoria"] = data_agora
                            st.session_state.db.at[idx, "Observacoes"] = obs

                            st.balloons()
                            st.success(f'"{descricao}" auditado com sucesso! Salvo na nuvem')
                            st.session_state.codigo_ocr = ""
                            time.sleep(1.5)
                            st.rerun()
            else:
                st.markdown(
                    '<div class="error-box"><h4>Item Nao Encontrado</h4>'
                    '<p>Este codigo nao existe no inventario atual.</p></div>',
                    unsafe_allow_html=True
                )

                with st.expander("Cadastrar como Sobra"):
                    desc_sobra = st.text_input("Descricao da Sobra:", placeholder="Ex: Computador Dell Optiplex")
                    obs_sobra = st.text_area("Observacoes:", placeholder="Ex: Encontrado no escritorio 3...", height=60)
                    if st.button("Salvar como Sobra"):
                        if desc_sobra:
                            data_agora = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")
                            salvar_item_supabase(
                                busca,
                                f"[SOBRA] {desc_sobra}",
                                "Auditado",
                                data_agora,
                                obs_sobra,
                                obra_id
                            )
                            st.session_state.db = carregar_do_supabase(obra_id)
                            st.success("Sobra cadastrada e salva na nuvem!")
                            st.session_state.codigo_ocr = ""
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Digite uma descricao para a sobra.")

    # ============================================================
    # ABA 2: LISTA COMPLETA
    # ============================================================
    with tab2:
        st.markdown("### Inventario Completo")

        df_lista = st.session_state.db

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_status = st.selectbox("Filtrar por Status:", ["Todos", "Pendente", "Auditado", "Sobra"])
        with col_f2:
            busca_texto = st.text_input("Buscar por descricao:", placeholder="Digite para filtrar...")

        df_filtrado = df_lista.copy()
        if filtro_status != "Todos":
            if filtro_status == "Sobra":
                df_filtrado = df_filtrado[df_filtrado["Descricao do Bem"].astype(str).str.contains("SOBRA", na=False)]
            else:
                df_filtrado = df_filtrado[df_filtrado["Status"] == filtro_status]
        if busca_texto:
            df_filtrado = df_filtrado[df_filtrado["Descricao do Bem"].str.contains(busca_texto, case=False, na=False)]

        def colorir_status(val):
            if val == "Auditado":
                return "background-color: #ECFDF5; color: #065F46; font-weight: bold;"
            elif val == "Pendente":
                return "background-color: #FFFBEB; color: #92400E; font-weight: bold;"
            return ""

        st.dataframe(
            df_filtrado.style.applymap(colorir_status, subset=["Status"]),
            use_container_width=True,
            height=500
        )

        st.caption(f"Mostrando {len(df_filtrado)} de {len(df_lista)} itens")

    # ============================================================
    # ABA 3: DASHBOARD
    # ============================================================
    with tab3:
        st.markdown("### Dashboard da Auditoria")

        df_dash = st.session_state.db
        total = len(df_dash)

        if total == 0:
            st.info("Importe dados para ver o dashboard.")
        else:
            col1, col2, col3, col4 = st.columns(4)

            auditados = len(df_dash[df_dash["Status"] == "Auditado"])
            pendentes = len(df_dash[df_dash["Status"] == "Pendente"])
            sobras = len(df_dash[df_dash["Descricao do Bem"].astype(str).str.contains("SOBRA", na=False)])

            with col1:
                st.metric("Total", total)
            with col2:
                st.metric("Auditados", auditados, f"{auditados/total*100:.1f}%")
            with col3:
                st.metric("Pendentes", pendentes, f"-{pendentes/total*100:.1f}%")
            with col4:
                st.metric("Sobras", sobras)

            st.markdown("---")
            st.markdown("#### Progresso da Auditoria")
            progresso = auditados / total
            st.progress(progresso, text=f"{auditados} de {total} itens auditados ({progresso*100:.1f}%)")

            st.markdown("---")
            st.markdown("#### Distribuicao por Status")
            st.bar_chart(df_dash["Status"].value_counts())

            st.markdown("---")
            st.markdown("#### Ultimos Itens Auditados")
            ultimos = df_dash[df_dash["Status"] == "Auditado"].tail(5)
            if not ultimos.empty:
                st.dataframe(ultimos[["Codigo do Bem", "Descricao do Bem", "Data Auditoria", "Observacoes"]], use_container_width=True)
            else:
                st.info("Nenhum item auditado ainda.")

st.markdown("---")
st.caption("Estel Asset Manager v2.0 | Dados salvos no Supabase | OCR com RapidOCR")
