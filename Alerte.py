# app_min.py — Streamlit minimal pour alertes news par pays (Afrique)
# Exécution:  streamlit run app_min.py
# Install:    pip install streamlit feedparser pandas python-dateutil

import base64
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import pandas as pd
import streamlit as st
from dateutil import parser as dparser

st.set_page_config(page_title="Alerte Pays – Afrique (Minimal)", layout="wide")


# ========= Header visuel (logo en base64, safe) =========
def render_header(
    title: str = "Outil de veille risques pays – Afrique",
    logo_filename: str = "logo_bcp.png",
    accent: str = "#F28C00",
    text_color: str = "#4A2E00",
):
    logo_path = Path(__file__).parent / logo_filename
    if logo_path.exists():
        b64 = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        img_html = f'<img src="data:image/png;base64,{b64}" style="height:64px;margin-right:16px;" />'
    else:
        img_html = ""
    html = f"""
    <div style="display:flex;align-items:center;background:#fff;border-bottom:3px solid {accent};
                border-radius:12px;padding:14px 18px;box-shadow:0 2px 6px rgba(0,0,0,0.05);">
        {img_html}
        <div style="color:{text_color};font-size:1.4rem;font-weight:700;">{title}</div>
    </div>
    <div style="height:12px;"></div>
    """
    st.markdown(html, unsafe_allow_html=True)


render_header()

# ===================== Sources =====================
SOURCES = [
    # Afrique généralistes
    "https://www.reuters.com/world/africa/rss",
    "https://feeds.bbci.co.uk/news/world/africa/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/world/africa/rss",
    "https://www.africanews.com/feed/",
    # Economie / marchés (peut aussi parler d'Afrique)
    "https://www.reuters.com/markets/rss",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://www.aljazeera.com/xml/rss/economy.xml",
]

# ===================== Watchlist (pays enrichis) =====================
COUNTRIES = {
    "DZA": ["algeria", "algérie", "alger", "algiers", "dzd", "dinar algerien", "dinar algérien"],
    "AGO": ["angola", "luanda", "aoa", "kwanza"],
    "BEN": ["benin", "bénin", "porto-novo", "cotonou", "xof", "cfa", "franc cfa"],
    "BWA": ["botswana", "gaborone", "bwp", "pula"],
    "BFA": ["burkina faso", "ouagadougou", "xof", "cfa", "franc cfa"],
    "BDI": ["burundi", "bujumbura", "burundian", "bif", "franc burundais"],
    "CMR": ["cameroon", "cameroun", "yaounde", "yaoundé", "douala", "xaf", "cfa", "franc cfa"],
    "CPV": ["cabo verde", "cape verde", "praia", "cve", "escudo"],
    "CAF": ["central african republic", "république centrafricaine", "bangui", "xaf", "cfa"],
    "TCD": ["chad", "tchad", "ndjamena", "n'djamena", "xaf", "cfa"],
    "CIV": ["cote d'ivoire", "côte d'ivoire", "abidjan", "ivoir", "xof", "cfa", "franc cfa"],
    "COD": ["democratic republic of congo", "rdc", "congo-kinshasa", "kinshasa", "congolese", "cdf"],
    "COG": ["republic of congo", "congo-brazzaville", "brazzaville", "xaf", "cfa"],
    "EGY": ["egypt", "egypte", "cairo", "le caire", "egp", "pound", "livre egyptienne"],
    "ETH": ["ethiopia", "éthiopie", "addis ababa", "addis-abeba", "etb", "birr"],
    "GAB": ["gabon", "libreville", "xaf", "cfa"],
    "GMB": ["gambia", "gambie", "banjul", "gmd", "dalasi"],
    "GHA": ["ghana", "accra", "ghs", "cedi"],
    "GIN": ["guinea", "guinée", "conakry", "gnf", "franc guinéen"],
    "KEN": ["kenya", "nairobi", "kes", "shilling kenyan"],
    "MAR": ["morocco", "maroc", "rabat", "casablanca", "tanger", "fes", "fès", "mad", "dirham"],
    "MOZ": ["mozambique", "maputo", "mzn", "metical"],
    "NAM": ["namibia", "namibie", "windhoek", "nad", "dollar namibien"],
    "NER": ["niger", "niamey", "xof", "cfa"],
    "NGA": ["nigeria", "nigéria", "abuja", "lagos", "ngn", "naira"],
    "RWA": ["rwanda", "kigali", "rwf", "franc rwandais"],
    "SEN": ["senegal", "sénégal", "dakar", "xof", "cfa", "franc cfa"],
    "ZAF": ["south africa", "afrique du sud", "pretoria", "johannesburg", "cape town", "durban", "zar", "rand"],
    "TZA": ["tanzania", "tanzanie", "dar es salaam", "dar-es-salaam", "tzs", "shilling tanzanien"],
    "TUN": ["tunisia", "tunisie", "tunis", "tnd", "dinar tunisien"],
    "MLI": ["mali", "bamako", "xof", "cfa", "franc cfa"],
}

# ===================== Règles de sévérité (enrichies) =====================
SEVERITY_WORDS = {
    "critical": [
        # Coups d'État / conflits majeurs
        "coup d'etat", "coup d’état", "coup", "overthrow", "putsch",
        "martial law", "state of emergency", "état d'urgence", "etat d'urgence",
        "insurrection", "uprising", "civil war", "guerre civile",
        "armed clashes", "affrontements armés", "massacre", "mass killing",
        "genocide", "terror attack", "attentat", "suicide bombing",
        "border clashes", "affrontements frontaliers",
        # Défaut / crise bancaire
        "sovereign default", "default souverain", "défaut souverain",
        "debt standstill", "suspension of payments", "suspension de paiements",
        "bank run", "ruée bancaire", "capital controls", "contrôles de capitaux",
    ],
    "warning": [
        # Sanctions / IFI / notation
        "sanctions", "sanction", "embargo", "asset freeze", "freeze assets",
        "blacklist", "liste noire",
        "imf program", "imf deal", "imf talks", "mission imf", "fmi",
        "world bank loan", "afdb loan", "program review",
        "rating downgrade", "rating cut", "dégradation de la note", "notation abaissée",
        "outlook negative", "perspective négative", "credit watch negative",
        "spread widening", "spreads widened", "cds spike", "cds widened",
        "debt restructuring", "restructuration de la dette", "haircut",
        # FX / inflation / pénuries
        "devaluation", "dévaluation", "currency crash", "currency shortage",
        "fx shortage", "foreign exchange shortage", "parallel market", "black market rate",
        "hyperinflation", "runaway inflation",
        # Protests / grèves
        "violent protest", "protesters clash", "mass protest", "émeutes", "riots",
        "nationwide strike", "general strike", "grève générale", "curfew", "couvre-feu",
        # Energie / logistique
        "fuel shortage", "diesel shortage", "power cuts", "blackout", "load shedding",
        "food shortage", "supply disruption", "port congestion",
    ],
    "watch": [
        # Politique / budget / BC
        "cabinet reshuffle", "remaniement", "government reshuffle",
        "election dispute", "contested election", "vote irregularities", "fraude électorale",
        "parliament dissolved", "dissolution du parlement",
        "budget gap", "financing gap", "arrears", "accumulation of arrears",
        "subsidy reform", "subsidy removal", "fuel price hike", "tax hike",
        "policy rate hike", "emergency rate", "capital adequacy concerns",
        "fx auction", "multiple exchange rates",
        # Sécurité
        "insurgent", "militia", "jihadist", "terror cell", "kidnapping",
        # Catastrophes naturelles
        "flooding", "flash floods", "drought", "landslide", "cyclone", "earthquake",
        # Autres signaux
        "political crisis", "talks stall", "talks collapse",
    ],
}
SEV_RX = {lvl: re.compile("|".join(map(re.escape, words)), re.I) for lvl, words in SEVERITY_WORDS.items()}

# ===================== Filtre thématique politique/économie =====================
TOPIC_INCLUDE_WORDS = [
    # Institutions politiques
    "government", "gouvernement",
    "president", "président",
    "prime minister", "premier ministre",
    "parliament", "parlement",
    "senate", "assembly", "assemblée nationale",
    "cabinet", "ministry", "ministère",
    # Elections / protest
    "election", "vote", "referendum",
    "protest", "demonstration", "manifestation", "riot", "émeute",
    "sanction", "sanctions",
    # Macro / budget / dette
    "imf", "fmi", "world bank", "banque mondiale",
    "afdb", "african development bank",
    "central bank", "banque centrale",
    "policy rate", "interest rate", "taux directeur",
    "inflation", "gdp", "growth", "croissance",
    "budget", "fiscal", "tax", "impôt", "déficit", "deficit",
    "debt", "dette", "sovereign", "eurobond", "bond",
    "cds", "spread", "rating", "notation",
    # Balance des paiements / fx / commerce
    "currency", "fx", "devaluation", "dévaluation", "reserves", "réserves de change",
    "balance of payments", "current account", "trade deficit", "export", "import", "tariff",
    # Conflits / sécurité
    "conflict", "ceasefire", "truce", "insurgent", "militia", "terror", "attaque",
    "border", "frontière",
]
TOPIC_EXCLUDE_WORDS = [
    "match", "football", "soccer", "basketball", "olympic", "coach", "goal", "cup", "tournament",
    "music", "film", "movie", "festival", "celebrity", "art", "culture", "fashion", "concert",
]

INC_RX = re.compile("|".join(map(re.escape, TOPIC_INCLUDE_WORDS)), re.I)
EXC_RX = re.compile("|".join(map(re.escape, TOPIC_EXCLUDE_WORDS)), re.I)


def is_relevant(text: str) -> bool:
    t = text.lower()
    if EXC_RX.search(t):
        return False
    return bool(INC_RX.search(t))


# ===================== Fonctions =====================
@st.cache_data(ttl=180)
def fetch_rss(urls):
    rows = []
    for u in urls:
        try:
            feed = feedparser.parse(u)
        except Exception:
            continue
        for e in feed.entries:
            title = getattr(e, "title", "").strip()
            summary = getattr(e, "summary", getattr(e, "description", "")) or ""
            link = getattr(e, "link", "")
            published = getattr(e, "published", getattr(e, "updated", ""))
            try:
                dt = dparser.parse(published) if published else datetime.now(timezone.utc)
            except Exception:
                dt = datetime.now(timezone.utc)
            rows.append(
                {
                    "title": title,
                    "summary": re.sub(r"<[^>]+>", " ", summary).strip(),
                    "link": link,
                    "published": dt,
                    "source": feed.feed.get("title", u),
                }
            )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("published", ascending=False)
    return df


@st.cache_data
def compile_country_patterns(cdict: dict):
    return {iso: re.compile("|".join(map(re.escape, words)), re.I) for iso, words in cdict.items()}


def detect(text: str, rx_by_country: dict):
    hits = [iso for iso, rx in rx_by_country.items() if rx.search(text)]
    sev = "info"
    low = text.lower()
    if SEV_RX["critical"].search(low):
        sev = "critical"
    elif SEV_RX["warning"].search(low):
        sev = "warning"
    elif SEV_RX["watch"].search(low):
        sev = "watch"
    return hits, sev


# ===================== UI =====================
st.sidebar.header("Filtres")
filter_topics = st.sidebar.checkbox("Politique & économie uniquement", True)
selected = st.sidebar.multiselect("Pays suivis (ISO3)", list(COUNTRIES.keys()), default=list(COUNTRIES.keys()))
refresh_sec = st.sidebar.slider("Auto-refresh (sec)", 30, 600, 120, 30)
sev_filter = st.sidebar.multiselect(
    "Sévérité", ["critical", "warning", "watch", "info"], default=["critical", "warning", "watch"]
)
period = st.sidebar.selectbox("Période", ["24h", "7 jours", "Tout"], index=1)

# ===================== Ingestion & matching =====================
rx_by_country = compile_country_patterns({k: COUNTRIES[k] for k in selected})
raw = fetch_rss(SOURCES)

rows = []
for _, r in raw.iterrows():
    text = f"{r['title']}\n{r['summary']}"
    if filter_topics and not is_relevant(text):
        continue
    countries, sev = detect(text, rx_by_country)
    for c in countries:
        rid = hashlib.sha1((r["link"] + "|" + c).encode()).hexdigest()[:16]
        rows.append(
            {
                "id": rid,
                "country": c,
                "severity": sev,
                "published": r["published"],
                "title": r["title"],
                "source": r["source"],
                "link": r["link"],
            }
        )

alerts = pd.DataFrame(rows)

# Filtre période
now_utc = pd.Timestamp.utcnow()
if not alerts.empty:
    if period == "24h":
        alerts = alerts[alerts["published"] >= (now_utc - pd.Timedelta(days=1))]
    elif period == "7 jours":
        alerts = alerts[alerts["published"] >= (now_utc - pd.Timedelta(days=7))]
    alerts = alerts.sort_values(["severity", "published"], ascending=[True, False])

# ===================== Affichage =====================
st.caption(
    f"Dernière mise à jour: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC · Auto-refresh {refresh_sec}s"
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Alertes totales (filtres)", int(alerts.shape[0]) if not alerts.empty else 0)
with col2:
    if not alerts.empty:
        recent7 = alerts[alerts["published"] >= (now_utc - pd.Timedelta(days=7))]
        st.metric("Alertes 7 jours", int(recent7.shape[0]))
    else:
        st.metric("Alertes 7 jours", 0)
with col3:
    st.metric("Pays suivis", len(selected))

if alerts.empty:
    st.info("Aucune alerte pour les filtres actuels.")
else:
    view = alerts[alerts["severity"].isin(sev_filter)]
    top = view[view["severity"].isin(["critical", "warning"])].head(10)
    if not top.empty:
        st.subheader("Focus immédiat")
        for _, row in top.iterrows():
            color = {
                "critical": "#b30000",
                "warning": "#e68a00",
                "watch": "#2b8cbe",
                "info": "#6c757d",
            }[row["severity"]]
            with st.container(border=True):
                st.markdown(
                    f"**{row['country']}** · <span style='color:{color};font-weight:700'>{row['severity'].upper()}</span>",
                    unsafe_allow_html=True,
                )
                st.write(row["title"])
                st.caption(
                    f"{row['source']} · {pd.to_datetime(row['published']).strftime('%Y-%m-%d %H:%M UTC')}"
                )
                if hasattr(st, "link_button"):
                    st.link_button("Ouvrir", row["link"])
                else:
                    st.markdown(f"[Lien source]({row['link']})")
        st.divider()

    st.subheader("Liste complète")
    tab = view[["published", "country", "severity", "source", "title", "link"]].copy()
    tab["published"] = pd.to_datetime(tab["published"]).dt.strftime("%Y-%m-%d %H:%M UTC")
    st.dataframe(tab, use_container_width=True)

# ===================== Auto-refresh =====================
st.markdown(
    f"""
    <script>
      setTimeout(function() {{ window.location.reload(); }}, {int(refresh_sec)*1000});
    </script>
    """,
    unsafe_allow_html=True,
)
