import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import date
from io import BytesIO

# =================== CONFIGURAÇÃO BÁSICA ===================
st.set_page_config(page_title="Dashboard de RH", layout="wide")

# =================== ESTILO GLOBAL ===================
st.markdown(
    """
    <style>
    /* ===== Cabeçalho ===== */
    h1 {
        text-align: center;
        font-size: 2.8rem !important;
        font-weight: 800 !important;
        background: linear-gradient(90deg, #ff1493, #ff69b4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0px 0px 15px rgba(255, 20, 147, 0.7);
        margin-bottom: 2rem;
    }

    /* ===== Cards de KPI ===== */
    .kpi-container {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
    }

    .kpi-box {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 0 12px rgba(255, 20, 147, 0.6);
        text-align: center;
        flex-grow: 1;
        min-width: 150px;
        border: 2px solid #ff1493;
        transition: 0.3s;
    }
    .kpi-box:hover {
        transform: scale(1.05);
        box-shadow: 0 0 25px rgba(255, 20, 147, 0.9);
    }

    .kpi-box h4 {
        margin: 0;
        font-size: 1rem;
        color: #444;
    }

    .kpi-box p {
        margin: 0;
        font-size: 2rem;
        font-weight: bold;
        color: #ff1493;
    }

    /* Botões */
    .stButton > button {
        background-color: #ff69b4;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
    }
    .stButton > button:hover {
        background-color: #ff1493;
    }

    .stDownloadButton > button {
        background-color: #ff1493;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
    }
    .stDownloadButton > button:hover {
        background-color: #a9122f;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =================== CABEÇALHO ===================
st.markdown("<h1>📊 Painel de RH</h1>", unsafe_allow_html=True)

# =================== FUNÇÕES ===================
def brl(x: float) -> str:
    try:
        return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

DATE_COLS = ["Data de Nascimento", "Data de Contratacao", "Data de Demissao"]

def prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip()

    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], dayfirst=True, errors="coerce")

    if "Sexo" in df.columns:
        df["Sexo"] = df["Sexo"].str.upper().replace({"MASCULINO": "M", "FEMININO": "F"})

    for col in ["Salario Base", "Impostos", "Beneficios", "VT", "VR"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    today = pd.Timestamp(date.today())

    if "Data de Nascimento" in df.columns:
        df["Idade"] = ((today - df["Data de Nascimento"]).dt.days // 365).clip(lower=0)

    if "Data de Contratacao" in df.columns:
        meses = (today.year - df["Data de Contratacao"].dt.year) * 12 + \
                (today.month - df["Data de Contratacao"].dt.month)
        df["Tempo de Casa (meses)"] = meses.clip(lower=0)

    if "Data de Demissao" in df.columns:
        df["Status"] = np.where(df["Data de Demissao"].notna(), "Desligado", "Ativo")
    else:
        df["Status"] = "Ativo"

    df["Custo Total Mensal"] = df[["Salario Base", "Impostos", "Beneficios", "VT", "VR"]].sum(axis=1)
    return df

@st.cache_data
def load_from_path(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    return prepare_df(df)

@st.cache_data
def load_from_bytes(uploaded_bytes) -> pd.DataFrame:
    df = pd.read_excel(uploaded_bytes, sheet_name=0, engine="openpyxl")
    return prepare_df(df)

# =================== CARREGAMENTO DE DADOS ===================
DEFAULT_EXCEL_PATH = "BaseFuncionarios.xlsx"

with st.sidebar:
    st.header("📂 Fonte de dados")
    up = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    caminho_manual = st.text_input("Ou caminho do Excel", value=DEFAULT_EXCEL_PATH)
    st.divider()

df = None
fonte = None
if up is not None:
    try:
        df = load_from_bytes(up)
        fonte = "Upload"
    except Exception as e:
        st.error(f"Erro ao ler Excel (Upload): {e}")
        st.stop()
else:
    try:
        if not os.path.exists(caminho_manual):
            st.error(f"Arquivo não encontrado em: {caminho_manual}")
            st.stop()
        df = load_from_path(caminho_manual)
        fonte = "Caminho"
    except Exception as e:
        st.error(f"Erro ao ler Excel (Caminho): {e}")
        st.stop()

st.caption(f"Dados carregados via **{fonte}**. Linhas: {len(df)} | Colunas: {len(df.columns)}")

# =================== INDICADORES ===================
def k_headcount_ativo(d): return int((d["Status"] == "Ativo").sum())
def k_desligados(d): return int((d["Status"] == "Desligado").sum())
def k_folha(d): return float(d.loc[d["Status"] == "Ativo", "Salario Base"].sum())
def k_custo_total(d): return float(d.loc[d["Status"] == "Ativo", "Custo Total Mensal"].sum())
def k_idade_media(d): return float(d["Idade"].mean()) if "Idade" in d.columns else 0
def k_avaliacao_media(d):
    return float(d["Avaliação do Funcionário"].mean()) if "Avaliação do Funcionário" in d.columns else 0

st.subheader("📌 Indicadores de RH")
st.markdown('<div class="kpi-container">', unsafe_allow_html=True)
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1: st.markdown(f'<div class="kpi-box"><h4>Headcount Ativo</h4><p>{k_headcount_ativo(df)}</p></div>', unsafe_allow_html=True)
with c2: st.markdown(f'<div class="kpi-box"><h4>Desligados</h4><p>{k_desligados(df)}</p></div>', unsafe_allow_html=True)
with c3: st.markdown(f'<div class="kpi-box"><h4>Folha Salarial</h4><p>{brl(k_folha(df))}</p></div>', unsafe_allow_html=True)
with c4: st.markdown(f'<div class="kpi-box"><h4>Custo Total</h4><p>{brl(k_custo_total(df))}</p></div>', unsafe_allow_html=True)
with c5: st.markdown(f'<div class="kpi-box"><h4>Idade Média</h4><p>{k_idade_media(df):.1f} anos</p></div>', unsafe_allow_html=True)
with c6: st.markdown(f'<div class="kpi-box"><h4>Avaliação Média</h4><p>{k_avaliacao_media(df):.2f}</p></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# =================== GRÁFICOS ===================
st.subheader("📈 Gráficos de RH")
pink_palette = ["#ff1493", "#ff69b4", "#ff85c1", "#ff4da6", "#ff99cc"]

col1, col2 = st.columns(2)
with col1:
    if "Área" in df.columns:
        d = df.groupby("Área").size().reset_index(name="Headcount")
        fig = px.bar(d, x="Área", y="Headcount", title="Headcount por Área", color_discrete_sequence=pink_palette)
        st.plotly_chart(fig, use_container_width=True)

with col2:
    if "Cargo" in df.columns:
        d = df.groupby("Cargo")["Salario Base"].mean().reset_index()
        fig = px.bar(d, x="Cargo", y="Salario Base", title="Salário Médio por Cargo", color_discrete_sequence=pink_palette)
        st.plotly_chart(fig, use_container_width=True)

col3, col4 = st.columns(2)
with col3:
    if "Idade" in df.columns:
        fig = px.histogram(df, x="Idade", nbins=20, title="Distribuição de Idade", color_discrete_sequence=pink_palette)
        st.plotly_chart(fig, use_container_width=True)

with col4:
    if "Sexo" in df.columns:
        d = df["Sexo"].value_counts().reset_index()
        d.columns = ["Sexo", "Contagem"]
        fig = px.pie(d, values="Contagem", names="Sexo", title="Distribuição por Sexo", color_discrete_sequence=pink_palette)
        st.plotly_chart(fig, use_container_width=True)

# =================== TABELA E DOWNLOAD ===================
st.subheader("📑 Tabela de Dados")
st.dataframe(df, use_container_width=True)

csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Baixar CSV", data=csv_bytes, file_name="funcionarios.csv", mime="text/csv")

buff = BytesIO()
with pd.ExcelWriter(buff, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Filtrado")
st.download_button("⬇️ Baixar Excel", data=buff.getvalue(),
                   file_name="funcionarios.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
