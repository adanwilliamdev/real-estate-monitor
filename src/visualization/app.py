"""
src/visualization/app.py
Dashboard do Monitor de Mercado Imobiliário.

Mapa geográfico usa Plotly (scattermapbox com estilo "carto-darkmatter"),
que não exige token de API nem a dependência extra `streamlit-folium`.

v5: identidade "Market Intelligence" — tema escuro (fundo quase-preto
#080B10), azul elétrico como cor de informação/marca, verde para
evolução positiva e vermelho reservado só para anomalias/problemas
(nunca usado em navegação). Cores nativas dos widgets do Streamlit são
aplicadas via .streamlit/config.toml; este arquivo cuida da estrutura,
dos componentes customizados (cartões, painel de anomalias, cabeçalho)
e da paleta dos gráficos Plotly.
"""
import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path ao rodar via `streamlit run`
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.data_ingestion.demo_data import VALID_CITIES
from src.data_processing.analytics import RealEstateAnalytics
from src.data_processing.cleaner import DataCleaner
from src.data_processing.investment import InvestmentAnalyzer
from src.data_processing.ml_models import PricePredictionModel
from src.data_storage.database import DatabaseManager
from src.logging_setup import logger
from src.orchestration.pipeline import run_pipeline

st.set_page_config(
    page_title="Market Intelligence — Real Estate",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------- Tema visual: "Market Intelligence" --------------------
BG = "#080B10"
SIDEBAR_BG = "#0D1117"
CARD = "#111820"
BLUE = "#1683FF"
BLUE_2 = "#0B5CFF"
TEXT = "#F1F5F9"
MUTED = "#8B98A9"
POSITIVE = "#20D68A"
DANGER = "#FF3B4E"
DANGER_NUM = "#FF5263"
DANGER_BG = "#160F13"
DANGER_BORDER = "#3A1B22"
WARNING = "#F5A623"
BORDER = "#202A36"

st.markdown(
    f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, sans-serif;
    }}

    .stApp {{
        background-color: {BG};
        background-image:
            linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
        background-size: 48px 48px;
    }}
    .block-container {{ padding-top: 1.6rem; max-width: 1320px; }}

    /* esconde o chrome padrão do Streamlit (menu, footer, deploy) */
    footer {{ visibility: hidden; height: 0; }}
    [data-testid="stDecoration"] {{ visibility: hidden; }}
    [data-testid="stStatusWidget"] {{ visibility: hidden; }}

    [data-testid="stSidebar"] {{
        background-color: {SIDEBAR_BG};
        border-right: 1px solid {BORDER};
    }}
    [data-testid="stSidebar"] * {{ color: {TEXT}; }}

    /* -------- marca / seções da sidebar -------- */
    .brand-block {{ padding: 4px 0 18px 0; border-bottom: 1px solid {BORDER}; margin-bottom: 18px; }}
    .brand-mark {{ color: {BLUE}; font-size: 1.1rem; font-weight: 800; letter-spacing: -0.01em; }}
    .brand-sub {{
        color: {MUTED}; font-family: 'JetBrains Mono', monospace; font-size: 0.66rem;
        letter-spacing: 0.14em; text-transform: uppercase; margin-top: 2px;
    }}
    .side-section {{
        color: {MUTED}; font-family: 'JetBrains Mono', monospace; font-size: 0.66rem;
        letter-spacing: 0.12em; text-transform: uppercase; margin: 18px 0 4px 0; font-weight: 600;
    }}
    .side-readout {{
        color: {BLUE}; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
        margin: -4px 0 6px 0;
    }}

    /* -------- cabeçalho -------- */
    .eyebrow {{
        color: {BLUE}; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem;
        font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 4px;
    }}
    .main-header {{ font-size: 2rem; font-weight: 800; color: {TEXT}; margin-bottom: 2px; letter-spacing: -0.01em; }}
    .main-subheader {{ color: {MUTED}; font-size: 0.9rem; }}
    .status-pill {{
        display: inline-flex; align-items: center; gap: 6px;
        font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 600;
        color: {POSITIVE}; letter-spacing: 0.06em; text-transform: uppercase;
    }}
    .status-dot {{
        width: 7px; height: 7px; border-radius: 50%; background: {POSITIVE};
        box-shadow: 0 0 8px {POSITIVE}; display: inline-block;
    }}
    .status-time {{ color: {TEXT}; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 600; text-align: right; }}
    .status-caption {{ color: {MUTED}; font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; text-align: right; margin-top: 2px; }}

    /* -------- cartões de indicador -------- */
    .kpi-card {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 16px 18px;
        height: 100%;
    }}
    .kpi-card.danger {{ background: {DANGER_BG}; border-color: {DANGER_BORDER}; }}
    .kpi-label {{
        color: {MUTED}; font-family: 'JetBrains Mono', monospace; font-size: 0.68rem;
        text-transform: uppercase; letter-spacing: 0.09em; margin-bottom: 8px;
    }}
    .kpi-card.danger .kpi-label {{ color: {DANGER}; }}
    .kpi-value {{ color: {TEXT}; font-family: 'JetBrains Mono', monospace; font-size: 1.6rem; font-weight: 700; line-height: 1.1; }}
    .kpi-card.danger .kpi-value {{ color: {DANGER_NUM}; }}
    .kpi-delta-up {{ color: {POSITIVE}; font-size: 0.78rem; font-family: 'JetBrains Mono', monospace; margin-top: 6px; }}
    .kpi-delta-down {{ color: {DANGER}; font-size: 0.78rem; font-family: 'JetBrains Mono', monospace; margin-top: 6px; }}
    .kpi-note {{ color: {MUTED}; font-size: 0.78rem; font-family: 'JetBrains Mono', monospace; margin-top: 6px; }}

    /* -------- selo de veredito -------- */
    .verdict-pill {{
        display: inline-block; padding: 6px 16px; border-radius: 999px;
        background: rgba(22, 131, 255, 0.10); border: 1px solid {BLUE};
        color: {BLUE}; font-family: 'JetBrains Mono', monospace; font-weight: 700;
        font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;
    }}

    /* -------- painel de anomalias -------- */
    .anomaly-panel-header {{
        display: flex; align-items: center; justify-content: space-between;
        background: {DANGER_BG}; border: 1px solid {DANGER_BORDER};
        border-radius: 10px 10px 0 0; padding: 14px 18px;
    }}
    .anomaly-title {{ color: {TEXT}; font-weight: 700; font-size: 0.95rem; }}
    .anomaly-sub {{ color: {MUTED}; font-size: 0.78rem; margin-top: 2px; }}
    .anomaly-count {{ color: {DANGER_NUM}; font-family: 'JetBrains Mono', monospace; font-size: 1.6rem; font-weight: 800; }}
    .anomaly-panel-body {{
        background: {CARD}; border: 1px solid {BORDER}; border-top: none;
        border-radius: 0 0 10px 10px; padding: 14px 18px 18px 18px;
    }}
    .all-clear-panel {{
        background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px;
        padding: 16px 18px; color: {POSITIVE}; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
    }}

    /* -------- notas / alertas -------- */
    .alert-row {{ border-left: 3px solid {BLUE}; background: {CARD}; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px; color: {TEXT}; }}
    .alert-row.critical {{ border-left-color: {DANGER}; }}
    .alert-row.warning {{ border-left-color: {WARNING}; }}
    .alert-row.info {{ border-left-color: {BLUE}; }}
    .alert-tag {{ font-family: 'JetBrains Mono', monospace; font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.1em; color: {MUTED}; }}

    hr {{ border-color: {BORDER}; }}

    /* -------- abas -------- */
    .stTabs [data-baseweb="tab-list"] {{ gap: 22px; border-bottom: 1px solid {BORDER}; }}
    .stTabs [data-baseweb="tab"] {{
        font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; letter-spacing: 0.04em;
        text-transform: uppercase; color: {MUTED}; background: transparent; padding: 0 2px 10px 2px;
    }}
    .stTabs [aria-selected="true"] {{ color: {TEXT} !important; border-bottom-color: {BLUE} !important; font-weight: 700; }}

    /* -------- botões -------- */
    .stButton > button {{
        background: {BLUE}; border: none; border-radius: 6px; color: #05070C;
        font-weight: 700; font-size: 0.82rem; transition: filter 0.15s ease;
    }}
    .stButton > button:hover {{ filter: brightness(1.12); color: #05070C; }}

    [data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace; color: {TEXT}; }}
    [data-testid="stDataFrame"] {{ border: 1px solid {BORDER}; border-radius: 8px; overflow: hidden; }}
</style>
""",
    unsafe_allow_html=True,
)

PLOTLY_TEMPLATE = "plotly_dark"
CHART_COLORWAY = [BLUE, POSITIVE, WARNING, "#5CC9FF", BLUE_2, "#C97CFF"]
BLUE_SCALE = [[0.0, "#0B2B4A"], [0.5, BLUE_2], [1.0, "#5CC9FF"]]


def _themed(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        height=height,
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font_color=MUTED,
        font_family="Inter, sans-serif",
        colorway=CHART_COLORWAY,
        margin=dict(t=50, b=30, l=10, r=10),
        title_font=dict(family="Inter, sans-serif", size=15, color=TEXT),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER)
    return fig


# -------------------- Cache de dados --------------------
@st.cache_data(ttl=3600, show_spinner=False)
def load_data() -> pd.DataFrame:
    """Carrega e limpa os dados do banco, com cache de 1h."""
    try:
        db = DatabaseManager()
        df = db.get_listings()
        if df.empty:
            return df
        cleaner = DataCleaner()
        df = cleaner.clean_listings(df)
        analytics = RealEstateAnalytics()
        df = analytics.detect_anomalies(df)
        return df
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Erro ao carregar dados: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def load_history() -> pd.DataFrame:
    try:
        return DatabaseManager().get_snapshots()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Erro ao carregar histórico: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def load_alerts() -> pd.DataFrame:
    try:
        return DatabaseManager().get_alerts(limit=50)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Erro ao carregar alertas: {exc}")
        return pd.DataFrame()


@st.cache_resource(show_spinner=False)
def load_price_model() -> PricePredictionModel:
    model = PricePredictionModel()
    model.load()
    return model


def fmt_brl(value: float) -> str:
    return f"R$ {value:,.0f}".replace(",", ".")


def fmt_brl_compact(value: float) -> str:
    """Formato compacto tipo 'R$ 282k' / 'R$ 1.75M', usado nos rótulos da sidebar."""
    if value is None:
        return "—"
    if abs(value) >= 1_000_000:
        return f"R$ {value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"R$ {value / 1_000:.0f}k"
    return f"R$ {value:.0f}"


class RealEstateDashboard:
    def __init__(self):
        self.df = load_data()
        self.history = load_history()
        self.alerts_df = load_alerts()
        self.stats = {}
        self.cleaner = DataCleaner()
        self.analytics = RealEstateAnalytics()
        self.investment = InvestmentAnalyzer()
        if not self.df.empty:
            self.stats = self.cleaner.calculate_market_metrics(self.df)
        self.deltas = self._compute_deltas()

    def _compute_deltas(self) -> dict:
        """Variação percentual dos indicadores de mercado vs. a coleta anterior,
        calculada a partir dos snapshots reais gravados a cada execução do pipeline.
        Retorna {} se ainda não houver histórico suficiente (menos de 2 coletas)."""
        if self.history.empty or "captured_at" not in self.history.columns:
            return {}
        hist = self.history.copy()
        hist["captured_at"] = pd.to_datetime(hist["captured_at"])
        agg = hist.groupby("captured_at").agg(
            avg_price=("avg_price", "mean"),
            avg_price_per_m2=("avg_price_per_m2", "mean"),
            avg_area=("avg_area", "mean"),
        ).sort_index()
        if len(agg) < 2:
            return {}
        prev, curr = agg.iloc[-2], agg.iloc[-1]

        def pct(a, b):
            if not a:
                return None
            return (b - a) / a * 100

        return {
            "price": pct(prev["avg_price"], curr["avg_price"]),
            "area": pct(prev["avg_area"], curr["avg_area"]),
            "price_per_m2": pct(prev["avg_price_per_m2"], curr["avg_price_per_m2"]),
        }

    # -------------------- Sidebar --------------------
    def render_sidebar(self) -> pd.DataFrame:
        st.sidebar.markdown(
            '<div class="brand-block"><div class="brand-mark">◆ IMOB</div>'
            '<div class="brand-sub">Market Intelligence</div></div>',
            unsafe_allow_html=True,
        )

        if self.df.empty:
            st.sidebar.markdown('<div class="side-section">Filtros</div>', unsafe_allow_html=True)
            st.sidebar.caption("Sem dados carregados ainda.")
            self._render_collect_data_sidebar()
            return self.df

        st.sidebar.markdown('<div class="side-section">Filtros</div>', unsafe_allow_html=True)

        st.sidebar.markdown('<div class="side-section">Localização</div>', unsafe_allow_html=True)
        cities = ["Todos"] + sorted(self.df["city"].dropna().unique().tolist())
        selected_city = st.sidebar.selectbox("Cidade", cities)

        st.sidebar.markdown('<div class="side-section">Preço</div>', unsafe_allow_html=True)
        min_price = float(self.df["price"].min())
        max_price = float(self.df["price"].max())
        price_range = st.sidebar.slider(
            "Faixa de preço (R$)",
            min_value=min_price,
            max_value=max_price,
            value=(min_price, max_price),
            label_visibility="collapsed",
        )
        st.sidebar.markdown(
            f'<div class="side-readout">{fmt_brl_compact(price_range[0])} — {fmt_brl_compact(price_range[1])}</div>',
            unsafe_allow_html=True,
        )

        st.sidebar.markdown('<div class="side-section">Área</div>', unsafe_allow_html=True)
        min_area = float(self.df["area"].min())
        max_area = float(self.df["area"].max())
        area_range = st.sidebar.slider(
            "Faixa de área (m²)",
            min_value=min_area,
            max_value=max_area,
            value=(min_area, max_area),
            label_visibility="collapsed",
        )
        st.sidebar.markdown(
            f'<div class="side-readout">{area_range[0]:.0f} m² — {area_range[1]:.0f} m²</div>',
            unsafe_allow_html=True,
        )

        st.sidebar.markdown('<div class="side-section">Quartos</div>', unsafe_allow_html=True)
        max_rooms = int(self.df["rooms"].max())
        rooms = st.sidebar.slider("Número de quartos", 0, max_rooms, (0, max_rooms), label_visibility="collapsed")

        filtered_df = self.df[
            (self.df["price"].between(*price_range))
            & (self.df["area"].between(*area_range))
            & (self.df["rooms"].between(*rooms))
        ]
        if selected_city != "Todos":
            filtered_df = filtered_df[filtered_df["city"] == selected_city]

        self._render_collect_data_sidebar()
        self._render_alerts_sidebar()
        return filtered_df

    def _render_collect_data_sidebar(self):
        st.sidebar.markdown("---")
        st.sidebar.markdown('<div class="side-section">Coleta de dados</div>', unsafe_allow_html=True)
        city_input = st.sidebar.selectbox("Cidade a coletar", VALID_CITIES, key="collect_city")
        source = st.sidebar.radio(
            "Fonte",
            options=["demo", "live"],
            help="'demo' gera dados sintéticos realistas (sempre funciona). "
            "'live' tenta raspar o site real e cai para demo se falhar.",
        )
        n_listings = st.sidebar.slider("Qtd. de imóveis (demo)", 50, 1000, 300, step=50)
        train_model = st.sidebar.checkbox("Re-treinar modelo de previsão (ML)", value=True)

        if st.sidebar.button("↻ Atualizar dados", use_container_width=True):
            with st.spinner("Coletando, limpando, treinando modelo e checando alertas..."):
                result = run_pipeline(
                    city=city_input, source=source, n_listings=n_listings,
                    train_model=train_model,
                )
            n_alerts = len(result.get("alerts", []))
            st.sidebar.success(
                f"Coletados {result.get('scraped_count', 0)} imóveis. "
                f"{n_alerts} alerta(s) gerado(s)."
            )
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

    def _render_alerts_sidebar(self):
        if self.alerts_df.empty:
            return
        unread = self.alerts_df[self.alerts_df.get("is_read", False) == False]  # noqa: E712
        if len(unread) > 0:
            st.sidebar.markdown("---")
            st.sidebar.warning(f"{len(unread)} alerta(s) não lido(s) — ver aba Histórico")

    # -------------------- Header / métricas --------------------
    def render_header(self):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown('<div class="eyebrow">Market Intelligence</div>', unsafe_allow_html=True)
            st.markdown('<p class="main-header">Monitor de Mercado Imobiliário</p>', unsafe_allow_html=True)
            st.markdown('<p class="main-subheader">Panorama, previsão e viabilidade de investimento em tempo real</p>', unsafe_allow_html=True)
        with col2:
            st.markdown(
                '<div style="text-align:right;">'
                '<span class="status-pill"><span class="status-dot"></span>Dados ativos</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="status-time">{pd.Timestamp.now().strftime("%d %b %Y").upper()} · '
                f'{pd.Timestamp.now().strftime("%H:%M")}</div>',
                unsafe_allow_html=True,
            )
            if not self.df.empty:
                st.markdown(
                    f'<div class="status-caption">{len(self.df):,}'.replace(",", ".")
                    + f' imóveis · {self.stats.get("unique_cities", 0)} cidades</div>',
                    unsafe_allow_html=True,
                )

    @staticmethod
    def _kpi_card(label: str, value: str, delta: float = None, note: str = None, danger: bool = False):
        delta_html = ""
        if delta is not None:
            cls = "kpi-delta-up" if delta >= 0 else "kpi-delta-down"
            arrow = "↑" if delta >= 0 else "↓"
            delta_html = f'<div class="{cls}">{arrow} {abs(delta):.1f}% vs. coleta anterior</div>'
        elif note:
            delta_html = f'<div class="kpi-note">{note}</div>'
        cls_card = "kpi-card danger" if danger else "kpi-card"
        st.markdown(
            f"""
            <div class="{cls_card}">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                {delta_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    def render_metrics(self, filtered_df: pd.DataFrame):
        if filtered_df.empty:
            st.warning("Nenhum dado encontrado com os filtros selecionados")
            return

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            self._kpi_card("Preço médio", fmt_brl(filtered_df["price"].mean()), delta=self.deltas.get("price"))
        with col2:
            self._kpi_card(
                "Área média (m²)", f"{filtered_df['area'].mean():,.0f}".replace(",", "."),
                delta=self.deltas.get("area"),
            )
        with col3:
            self._kpi_card(
                "Preço por m²", fmt_brl(filtered_df["price_per_m2"].mean()),
                delta=self.deltas.get("price_per_m2"),
            )
        with col4:
            outliers = int(filtered_df["is_anomaly"].sum()) if "is_anomaly" in filtered_df else 0
            pct = (outliers / len(filtered_df) * 100) if len(filtered_df) else 0
            self._kpi_card("Anomalias", str(outliers), note=f"{pct:.1f}% dos imóveis", danger=True)

    # -------------------- Gráficos --------------------
    def render_price_distribution(self, filtered_df: pd.DataFrame):
        if filtered_df.empty:
            return

        col1, col2 = st.columns(2)
        with col1:
            fig = px.histogram(
                filtered_df, x="price", title="Distribuição de preços",
                labels={"price": "Preço (R$)"}, color_discrete_sequence=[BLUE],
            )
            st.plotly_chart(_themed(fig), use_container_width=True)

        with col2:
            fig = px.scatter(
                filtered_df, x="area", y="price", title="Preço × área",
                labels={"area": "Área (m²)", "price": "Preço (R$)"},
                color="rooms", color_continuous_scale=BLUE_SCALE,
                hover_data=["city", "neighborhood"],
            )
            st.plotly_chart(_themed(fig), use_container_width=True)

    def render_geographic_view(self, filtered_df: pd.DataFrame):
        if filtered_df.empty or "latitude" not in filtered_df.columns:
            return

        map_df = filtered_df.dropna(subset=["latitude", "longitude"])
        if map_df.empty:
            return

        st.subheader("Distribuição geográfica")
        fig = px.scatter_mapbox(
            map_df,
            lat="latitude",
            lon="longitude",
            color="price_per_m2",
            size="area",
            hover_name="neighborhood",
            hover_data={"price": True, "area": True, "rooms": True, "city": True,
                        "latitude": False, "longitude": False},
            color_continuous_scale=BLUE_SCALE,
            zoom=10,
            height=500,
            mapbox_style="carto-darkmatter",
        )
        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, paper_bgcolor=CARD)
        st.plotly_chart(fig, use_container_width=True)

    def render_advanced_analytics(self, filtered_df: pd.DataFrame):
        if filtered_df.empty:
            return

        st.subheader("Análises avançadas")
        tab1, tab2, tab3 = st.tabs(["Segmentação", "Tendências", "Por cidade"])

        with tab1:
            if len(filtered_df) >= 10:
                segmented_df = self.analytics.perform_segmentation(filtered_df)
                fig = px.scatter(
                    segmented_df, x="area", y="price_per_m2", color="segment",
                    title="Segmentação de imóveis",
                    labels={"area": "Área (m²)", "price_per_m2": "Preço por m² (R$)"},
                    hover_data=["city", "rooms"],
                )
                st.plotly_chart(_themed(fig), use_container_width=True)
            else:
                st.info("São necessários pelo menos 10 imóveis para segmentação.")

        with tab2:
            cities = filtered_df["city"].value_counts().head(5).index
            if len(cities) > 0:
                city_data = filtered_df[filtered_df["city"].isin(cities)]
                city_avg = city_data.groupby("city")["price_per_m2"].mean().reset_index()
                fig = px.bar(
                    city_avg, x="city", y="price_per_m2",
                    title="Preço por m² por cidade",
                    labels={"city": "Cidade", "price_per_m2": "Preço por m² (R$)"},
                    color="price_per_m2", color_continuous_scale=BLUE_SCALE,
                )
                st.plotly_chart(_themed(fig), use_container_width=True)

        with tab3:
            city_stats = filtered_df.groupby("city").agg(
                preco_medio=("price", "mean"),
                preco_mediano=("price", "median"),
                qtd=("price", "count"),
                area_media=("area", "mean"),
                preco_m2=("price_per_m2", "mean"),
            ).round(2)
            st.dataframe(city_stats, use_container_width=True)

    def render_anomalies(self, filtered_df: pd.DataFrame):
        if filtered_df.empty or "is_anomaly" not in filtered_df.columns:
            return

        anomalies = filtered_df[filtered_df["is_anomaly"]]
        if len(anomalies) == 0:
            st.markdown(
                '<div class="all-clear-panel">✓ Nenhuma anomalia detectada nos dados atuais</div>',
                unsafe_allow_html=True,
            )
            return

        st.markdown(
            f"""
            <div class="anomaly-panel-header">
                <div>
                    <div class="anomaly-title">⚠ Anomalias detectadas</div>
                    <div class="anomaly-sub">Imóveis fora do padrão estatístico esperado</div>
                </div>
                <div class="anomaly-count">{len(anomalies)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="anomaly-panel-body">', unsafe_allow_html=True)
        max_score = float(anomalies["anomaly_score"].max()) or 1.0
        st.dataframe(
            anomalies[["price", "area", "rooms", "city", "price_per_m2", "anomaly_score"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "price": st.column_config.NumberColumn("Preço", format="R$ %.0f"),
                "area": st.column_config.NumberColumn("Área", format="%.1f m²"),
                "rooms": st.column_config.NumberColumn("Quartos", format="%d"),
                "city": st.column_config.TextColumn("Cidade"),
                "price_per_m2": st.column_config.NumberColumn("R$/m²", format="R$ %.0f"),
                "anomaly_score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=max_score, format="%.2f",
                ),
            },
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # -------------------- Previsão de Preço (ML) --------------------
    def render_price_prediction(self):
        st.subheader("Previsão de preço com Machine Learning")
        model = load_price_model()

        if not model.is_ready:
            st.info(
                "Nenhum modelo treinado ainda. Rode uma coleta na barra lateral com "
                "'Re-treinar modelo de previsão' marcado (mínimo de ~30 imóveis)."
            )
            return

        meta = model.metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            self._kpi_card("Precisão do modelo (R²)", f"{meta.get('r2', 0):.2f}")
        with col2:
            self._kpi_card("Erro médio (MAPE)", f"{meta.get('mape', 0):.1%}")
        with col3:
            self._kpi_card("Amostras de treino", str(meta.get("n_samples", 0)))

        st.caption(
            "R² próximo de 1 indica que o modelo explica bem a variação de preços; "
            "MAPE é o erro percentual médio nas previsões do conjunto de teste."
        )

        st.markdown("#### Simular um imóvel")
        cities_available = sorted(self.df["city"].dropna().unique()) if not self.df.empty else []
        with st.form("prediction_form"):
            c1, c2 = st.columns(2)
            with c1:
                area = st.number_input("Área (m²)", min_value=15.0, max_value=1000.0, value=70.0, step=5.0)
                rooms = st.number_input("Quartos", min_value=0, max_value=10, value=2, step=1)
                bathrooms = st.number_input("Banheiros", min_value=0, max_value=10, value=2, step=1)
            with c2:
                city = st.selectbox("Cidade", cities_available or ["São Paulo"])
                hoods = sorted(
                    self.df.loc[self.df["city"] == city, "neighborhood"].dropna().unique()
                ) if not self.df.empty else []
                neighborhood = st.selectbox("Bairro", hoods or ["Centro"])
            submitted = st.form_submit_button("Prever preço", use_container_width=True)

        if submitted:
            try:
                result = model.predict(
                    area=area, rooms=int(rooms), bathrooms=int(bathrooms),
                    city=city, neighborhood=neighborhood,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Não foi possível prever: {exc}")
                return

            c1, c2, c3 = st.columns(3)
            with c1:
                self._kpi_card("Preço estimado", fmt_brl(result["predicted_price"]))
            with c2:
                self._kpi_card(
                    "Intervalo (≈90%)",
                    f"{fmt_brl(result['confidence_interval_low'])} – "
                    f"{fmt_brl(result['confidence_interval_high'])}",
                )
            with c3:
                if result.get("price_per_m2"):
                    self._kpi_card("Preço por m²", fmt_brl(result["price_per_m2"]))

        if meta.get("feature_importance"):
            st.markdown("#### O que mais influencia o preço no modelo atual")
            fi = pd.DataFrame(
                sorted(meta["feature_importance"].items(), key=lambda x: x[1], reverse=True),
                columns=["feature", "importance"],
            )
            fig = px.bar(
                fi, x="importance", y="feature", orientation="h", title="Importância das variáveis",
                color_discrete_sequence=[BLUE],
            )
            st.plotly_chart(_themed(fig, height=300), use_container_width=True)

    # -------------------- Investimento --------------------
    def render_investment(self, filtered_df: pd.DataFrame):
        st.subheader("Análise de investimento")
        st.caption(
            "Estimativas de aluguel usam a razão histórica aluguel/preço típica de "
            "cada cidade. São heurísticas para orientar a análise, não uma avaliação "
            "de aluguel real do imóvel."
        )

        cities_available = sorted(self.df["city"].dropna().unique()) if not self.df.empty else []
        col1, col2 = st.columns([1, 1])
        with col1:
            price = st.number_input("Preço do imóvel (R$)", min_value=10_000.0, value=750_000.0, step=10_000.0)
            area = st.number_input("Área (m²)", min_value=15.0, value=70.0, step=5.0, key="inv_area")
        with col2:
            city = st.selectbox("Cidade", cities_available or ["São Paulo"], key="inv_city")

        if st.button("Calcular viabilidade", use_container_width=True):
            city_df = self.df[self.df["city"] == city] if not self.df.empty else pd.DataFrame()
            market_ppm2 = float(city_df["price_per_m2"].mean()) if not city_df.empty else None
            result = self.investment.analyze(price=price, city=city, area=area, market_price_per_m2=market_ppm2)

            st.markdown(f'<span class="verdict-pill">{result.verdict}</span>', unsafe_allow_html=True)
            st.write("")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                self._kpi_card("Aluguel estimado/mês", fmt_brl(result.estimated_monthly_rent))
            with c2:
                self._kpi_card("Yield bruto (a.a.)", f"{result.gross_yield_annual:.1f}%")
            with c3:
                self._kpi_card("Yield líquido (a.a.)", f"{result.net_yield_annual:.1f}%")
            with c4:
                self._kpi_card("Payback (com custos)", f"{result.payback_years_with_costs:.1f} anos")
            st.info(result.notes)

        st.markdown("#### Melhores oportunidades (yield líquido estimado)")
        if filtered_df.empty:
            st.info("Sem dados suficientes para ranquear oportunidades.")
            return
        ranked = self.investment.rank_best_opportunities(filtered_df, top_n=10)
        if ranked.empty:
            st.info("Sem dados suficientes para ranquear oportunidades.")
        else:
            st.dataframe(ranked, use_container_width=True, hide_index=True)

    # -------------------- Histórico & Alertas --------------------
    def render_history_and_alerts(self):
        st.subheader("Histórico de mercado")
        if self.history.empty or len(self.history) < 2:
            st.info(
                "Ainda não há histórico suficiente. Cada execução do pipeline grava um "
                "snapshot — rode a coleta algumas vezes (em dias diferentes, idealmente) "
                "para ver a série temporal aqui."
            )
        else:
            hist = self.history.copy()
            hist["captured_at"] = pd.to_datetime(hist["captured_at"])
            fig = px.line(
                hist.sort_values("captured_at"), x="captured_at", y="avg_price_per_m2",
                color="city", markers=True,
                title="Evolução do preço médio por m² ao longo do tempo",
                labels={"captured_at": "Data da coleta", "avg_price_per_m2": "Preço médio por m² (R$)",
                        "city": "Cidade"},
            )
            st.plotly_chart(_themed(fig, height=420), use_container_width=True)

        st.markdown("---")
        st.subheader("Alertas de mercado")
        st.caption(
            "Gerados automaticamente a cada coleta: variações relevantes de preço por m² "
            "e picos de anomalias, comparando com a coleta anterior."
        )
        if self.alerts_df.empty:
            st.success("Nenhum alerta registrado ainda.")
            return

        severity_labels = {"critical": "CRÍTICO", "warning": "ALERTA", "info": "INFORMATIVO"}
        for _, row in self.alerts_df.iterrows():
            severity = row.get("severity", "info")
            tag = severity_labels.get(severity, "INFORMATIVO")
            when = pd.to_datetime(row["created_at"]).strftime("%d/%m/%Y %H:%M")
            st.markdown(
                f'<div class="alert-row {severity}">'
                f'<span class="alert-tag">{tag}</span><br>'
                f'<b>{row.get("category", "")}</b> — {row.get("message", "")}'
                f'<br><span style="color:{MUTED};font-size:0.76rem;">{when}</span></div>',
                unsafe_allow_html=True,
            )

    # -------------------- Runner --------------------
    def run(self):
        self.render_header()
        filtered_df = self.render_sidebar()

        if self.df.empty:
            st.info(
                "Nenhum dado disponível ainda.\n\n"
                "Use o painel **Coleta de dados** na barra lateral e clique em "
                "**Atualizar dados** para popular o banco com dados de exemplo "
                "(ou dados reais, se a fonte 'live' estiver disponível)."
            )
            return

        tab_overview, tab_map, tab_analytics, tab_ml, tab_invest, tab_history = st.tabs(
            ["Overview", "Mapa", "Análise", "Previsão", "Investimento", "Histórico"]
        )

        with tab_overview:
            self.render_metrics(filtered_df)
            st.write("")
            self.render_price_distribution(filtered_df)
            st.write("")
            self.render_anomalies(filtered_df)

        with tab_map:
            self.render_geographic_view(filtered_df)

        with tab_analytics:
            self.render_advanced_analytics(filtered_df)

        with tab_ml:
            self.render_price_prediction()

        with tab_invest:
            self.render_investment(filtered_df)

        with tab_history:
            self.render_history_and_alerts()

        st.markdown("---")
        st.caption("Monitor de Mercado Imobiliário · Streamlit + FastAPI + scikit-learn")


def main():
    dashboard = RealEstateDashboard()
    dashboard.run()


# `streamlit run` executa o módulo com __name__ == "__main__"
if __name__ == "__main__":
    main()
