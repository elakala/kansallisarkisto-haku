"""
Kansallisarkiston Sisältöhaku-työkalu
Sukututkimuksen ja historiallisen aineiston hakutyökalu
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import os
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Konfiguraatio ──────────────────────────────────────────────────────────────
ES_URL = "https://es.demo.kansallisarkisto.fi"
PAIVAKIRI_PATH = Path("tutkimuspaivakirja.json")

# Nimivariaatiot (historiallinen sukututkimus)
NIMIVARIAATIOT = {
    "juho": ["juho", "johan", "johannes", "juhana", "juhani"],
    "maria": ["maria", "maaria", "mari", "marja", "margareta", "maaret"],
    "anna": ["anna", "anne", "annikki", "annakaisa"],
    "heikki": ["heikki", "henrik", "henrikki", "henric"],
    "matti": ["matti", "matts", "mattias", "matthias"],
    "kalle": ["kalle", "karl", "carolus", "kaarlo"],
    "liisa": ["liisa", "lisa", "elisabet", "elisabetha", "lisa"],
    "erkki": ["erkki", "eric", "erik", "ericus"],
    "pekka": ["pekka", "petrus", "pietari", "peter", "petr"],
    "tuomas": ["tuomas", "thomas", "tomas"],
}

INDEKSIT = {
    "Tuomiokirjat (1600–1900-luvut)": "tuomiokirjat",
    "Voudintilit (1537–1634)": "voudintilit",
    "Diplomatarium Fennicum (Keskiaika)": "df",
    "Kaikki aineistot": "tuomiokirjat,voudintilit",
}

# ── Apufunktiot ────────────────────────────────────────────────────────────────

def hae_api_avain() -> str | None:
    """Hae API-avain ympäristömuuttujista tai Streamlit secretseistä."""
    # 1. Streamlit secrets
    try:
        return st.secrets["KA_API_KEY"]
    except Exception:
        pass
    # 2. .env / ympäristömuuttuja
    return os.environ.get("KA_API_KEY")


def rakenna_kysely(hakusana: str, vuosi_alku: int, vuosi_loppu: int,
                   indeksi: str, nimivariaatiot: bool) -> dict:
    """Rakenna Elasticsearch-kysely."""
    teksti_kentta = "transcript" if indeksi == "df" else "teksti"
    vuosi_kentta_alku = "dating_start_year" if indeksi == "df" else "alkuvuosi"
    vuosi_kentta_loppu = "dating_end_year" if indeksi == "df" else "loppuvuosi"

    # Nimivariaatiot
    hakusanat = [hakusana]
    if nimivariaatiot:
        alempi = hakusana.lower()
        if alempi in NIMIVARIAATIOT:
            hakusanat = NIMIVARIAATIOT[alempi]
        else:
            # Jokerimerkki: hae myös wildcard-muodossa
            hakusanat = [hakusana, f"{hakusana}*"]

    # Rakenna tekstiosuus
    if len(hakusanat) == 1:
        teksti_osa = {"match": {teksti_kentta: hakusanat[0]}}
    else:
        teksti_osa = {
            "bool": {
                "should": [{"match": {teksti_kentta: s}} for s in hakusanat],
                "minimum_should_match": 1
            }
        }

    # Aikarajaus
    aikasuodatin = {
        "range": {
            vuosi_kentta_alku: {"gte": vuosi_alku, "lte": vuosi_loppu}
        }
    }

    # Highlights
    highlight = {
        "fields": {teksti_kentta: {"fragment_size": 200, "number_of_fragments": 2}},
        "pre_tags": ["**"],
        "post_tags": ["**"]
    }

    # Aggregaatiot
    aggs = {
        "vuosittain": {
            "histogram": {
                "field": vuosi_kentta_alku,
                "interval": 10,
                "min_doc_count": 1
            }
        }
    }

    if indeksi not in ("df",):
        aggs["paikkakunnat"] = {
            "terms": {"field": "aineistokokonaisuus.keyword", "size": 20}
        }

    return {
        "query": {
            "bool": {
                "must": teksti_osa,
                "filter": aikasuodatin
            }
        },
        "highlight": highlight,
        "aggs": aggs,
        "size": 100,
        "from": 0
    }


def tee_haku(api_avain: str, indeksi: str, kysely: dict) -> dict | None:
    """Suorita haku Elasticsearch-rajapintaan."""
    url = f"{ES_URL}/{indeksi}/_search?pretty"
    headers = {
        "Authorization": f"ApiKey {api_avain}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(url, headers=headers, json=kysely, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Yhteys Kansallisarkiston palvelimeen epäonnistui. Tarkista internet-yhteys.")
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 401:
            st.error("🔑 API-avain virheellinen tai puuttuu. Tarkista .env-tiedosto tai Streamlit secrets.")
        else:
            st.error(f"API-virhe {resp.status_code}: {e}")
    except Exception as e:
        st.error(f"Odottamaton virhe: {e}")
    return None


def lataa_paivakirja() -> list:
    if PAIVAKIRI_PATH.exists():
        with open(PAIVAKIRI_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def tallenna_loyto(tulos: dict, muistiinpano: str):
    paivakirja = lataa_paivakirja()
    merkinta = {
        "tallennettu": datetime.now().isoformat(),
        "hakutulos_id": tulos.get("_id"),
        "indeksi": tulos.get("_index"),
        "data": tulos.get("_source", {}),
        "muistiinpano": muistiinpano
    }
    paivakirja.append(merkinta)
    with open(PAIVAKIRI_PATH, "w", encoding="utf-8") as f:
        json.dump(paivakirja, f, ensure_ascii=False, indent=2)
    st.success("✅ Löytö tallennettu tutkimuspäiväkirjaan!")


def nayta_kpi_kortit(osumia: int, data: list, indeksi_avain: str):
    """Näytä KPI-yhteenvetokortit."""
    vuosi_kentta = "dating_start_year" if indeksi_avain == "df" else "alkuvuosi"

    vuodet = []
    for h in data:
        v = h["_source"].get(vuosi_kentta)
        try:
            vuodet.append(int(v))
        except (TypeError, ValueError):
            pass

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔍 Osumia yhteensä", f"{osumia:,}".replace(",", " "))
    col2.metric("📄 Näytetään", len(data))
    col3.metric("📅 Vanhin asiakirja", str(min(vuodet)) if vuodet else "–")
    col4.metric("📅 Uusin asiakirja", str(max(vuodet)) if vuodet else "–")


def nayta_visualisoinnit(resp: dict, indeksi_avain: str):
    """Näytä aikajana- ja paikkakuntakaaviot."""
    # Vuosijakauma aggregaatiosta
    agg_vuodet = resp.get("aggregations", {}).get("vuosittain", {}).get("buckets", [])
    if agg_vuodet:
        df_aika = pd.DataFrame([
            {"Vuosikymmen": b["key"], "Osumia": b["doc_count"]}
            for b in agg_vuodet if b["doc_count"] > 0
        ])
        if not df_aika.empty:
            fig = px.bar(
                df_aika, x="Vuosikymmen", y="Osumia",
                title="📊 Osumien jakautuminen vuosikymmenittäin",
                color="Osumia",
                color_continuous_scale="Teal",
                labels={"Vuosikymmen": "Vuosikymmen (alku)", "Osumia": "Asiakirjoja"}
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                coloraxis_showscale=False
            )
            st.plotly_chart(fig, use_container_width=True)

    # Aineistokokonaisuudet (tuomiokirjat/voudintilit)
    agg_paikat = resp.get("aggregations", {}).get("paikkakunnat", {}).get("buckets", [])
    if agg_paikat:
        df_paikat = pd.DataFrame([
            {"Aineisto": b["key"], "Osumia": b["doc_count"]}
            for b in agg_paikat
        ]).sort_values("Osumia", ascending=True)

        fig2 = px.bar(
            df_paikat, x="Osumia", y="Aineisto",
            orientation="h",
            title="📁 Osumien jakautuminen aineistokokonaisuuksittain",
            color="Osumia",
            color_continuous_scale="Sunset"
        )
        fig2.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            coloraxis_showscale=False,
            height=max(300, len(agg_paikat) * 30)
        )
        st.plotly_chart(fig2, use_container_width=True)


def nayta_tulos(tulos: dict, idx: int, indeksi_avain: str):
    """Näytä yksittäinen hakutulos expander-komponentissa."""
    src = tulos.get("_source", {})
    highlights = tulos.get("highlight", {})

    # Otsikko
    if indeksi_avain == "df":
        otsikko = src.get("df", src.get("indexterm", f"Asiakirja #{idx+1}"))
        vuosi = src.get("dating_start_year", "?")
        paikka = src.get("issuingplace", "")
        teksti_kentta = "transcript"
    else:
        otsikko = src.get("arkistoyksikkö", src.get("aineistokokonaisuus", f"Asiakirja #{idx+1}"))
        vuosi = src.get("alkuvuosi", "?")
        paikka = src.get("aineistokokonaisuus", "")
        teksti_kentta = "teksti"

    otsikko_str = f"📄 {otsikko} ({vuosi})"
    if paikka and paikka != otsikko:
        otsikko_str += f" — {paikka}"

    with st.expander(otsikko_str):
        # Katkelmia
        katkelmat = highlights.get(teksti_kentta, [])
        if katkelmat:
            st.markdown("**Tekstikatkelma:**")
            for k in katkelmat[:2]:
                st.markdown(f"> {k}")
        else:
            teksti = src.get(teksti_kentta, "")
            if teksti:
                st.markdown(f"> {teksti[:400]}{'...' if len(teksti) > 400 else ''}")

        # Metatiedot
        cols = st.columns([2, 2, 1])
        with cols[0]:
            if indeksi_avain != "df":
                st.caption(f"**Aineisto:** {src.get('aineistokokonaisuus', '–')}")
                st.caption(f"**Pääsarja:** {src.get('pääsarja', '–')}")
                st.caption(f"**Arkistoyksikkö:** {src.get('arkistoyksikkö', '–')}")
            else:
                st.caption(f"**Antopaikka:** {src.get('issuingplace', '–')} ({src.get('issuingplacecountry', '')})")
                st.caption(f"**Kieli:** {src.get('language', '–')}")

        with cols[1]:
            st.caption(f"**Aikaväli:** {src.get('alkuvuosi', src.get('dating_start_year', '?'))} – {src.get('loppuvuosi', src.get('dating_end_year', '?'))}")
            url = src.get("url", "")
            if url:
                st.markdown(f"[🔗 Avaa Astiassa]({url})")

        with cols[2]:
            # Tallennusnappi
            if st.button(f"💾 Tallenna löytö", key=f"tallenna_{idx}_{tulos.get('_id')}"):
                st.session_state[f"tallenna_modal_{idx}"] = True

        # Muistiinpano-modal
        if st.session_state.get(f"tallenna_modal_{idx}"):
            muistiinpano = st.text_area(
                "Lisää muistiinpano (valinnainen):",
                key=f"muistiinpano_{idx}",
                placeholder="Esim. Tämä voi olla esi-isä Juho Koivumäki..."
            )
            if st.button("✅ Vahvista tallennus", key=f"vahvista_{idx}"):
                tallenna_loyto(tulos, muistiinpano)
                st.session_state[f"tallenna_modal_{idx}"] = False


# ── Päänäkymä ─────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Kansallisarkisto Sisältöhaku",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # CSS
    st.markdown("""
        <style>
        .main-header { font-size: 2rem; font-weight: 700; color: #1a365d; margin-bottom: 0; }
        .sub-header { color: #4a5568; font-size: 0.95rem; margin-top: 0; }
        .stExpander { border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; }
        </style>
    """, unsafe_allow_html=True)

    # Otsikko
    st.markdown('<p class="main-header">🏛️ Kansallisarkiston Sisältöhaku</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Sukututkimuksen ja historiallisen aineiston tehotyökalu · Elasticsearch-rajapinta</p>', unsafe_allow_html=True)
    st.divider()

    # ── Sivupalkki ─────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("🔍 Hakukriteerit")

        # API-avain
        api_avain = hae_api_avain()
        if not api_avain:
            api_avain = st.text_input(
                "🔑 API-avain",
                type="password",
                help="Hae avain Kansallisarkistolta: sanna.joska@kansallisarkisto.fi\nTai aseta KA_API_KEY ympäristömuuttujaan."
            )
            if api_avain:
                st.success("API-avain asetettu (tässä sessiossa)")
        else:
            st.success("✅ API-avain ladattu ympäristöstä")

        st.divider()

        # Hakusana
        hakusana = st.text_input(
            "📝 Hakusana",
            placeholder="Esim. Koivumäki, Jurva, noita...",
            help="Sukunimi, talonnimi, paikkakunta tai muu hakutermi"
        )

        # Aineistovalinta
        indeksi_nimi = st.selectbox(
            "📚 Aineisto",
            options=list(INDEKSIT.keys()),
            index=0
        )
        indeksi_avain = INDEKSIT[indeksi_nimi]

        # Aikaväli
        st.subheader("📅 Aikaväli")
        vuosi_minimi = 1500 if "voudintilit" in indeksi_avain else (1100 if indeksi_avain == "df" else 1600)
        vuosi_maksimi = 1634 if "voudintilit" in indeksi_avain else (1600 if indeksi_avain == "df" else 1950)

        col1, col2 = st.columns(2)
        with col1:
            vuosi_alku = st.number_input("Alku", min_value=1100, max_value=1980, value=vuosi_minimi, step=10)
        with col2:
            vuosi_loppu = st.number_input("Loppu", min_value=1100, max_value=1980, value=vuosi_maksimi, step=10)

        # Nimivariaatiot
        st.divider()
        nimivariaatiot = st.checkbox(
            "🔤 Nimivariaatiot",
            help="Hakee automaattisesti historiallisia nimivariaatioita (esim. Juho → Johan, Johannes, Juhana)"
        )
        if nimivariaatiot and hakusana:
            alempi = hakusana.lower()
            if alempi in NIMIVARIAATIOT:
                st.info(f"Hakee: {', '.join(NIMIVARIAATIOT[alempi])}")
            else:
                st.info(f"Lisätään jokerimerkki: {hakusana}*")

        # Sivutus
        st.divider()
        tulosten_maara = st.slider("Tulosten määrä", 10, 100, 50, step=10)

        # Hakupainike
        haku_nappi = st.button("🔎 Hae", type="primary", use_container_width=True, disabled=not (hakusana and api_avain))

        if not hakusana:
            st.caption("Syötä hakusana aloittaaksesi.")
        if not api_avain:
            st.caption("API-avain puuttuu.")

    # ── Päänäkymän välilehdet ───────────────────────────────────────────────────
    tab_haku, tab_paivakirja, tab_ohje = st.tabs(["🔍 Hakutulokset", "📓 Tutkimuspäiväkirja", "ℹ️ Ohjeet"])

    with tab_haku:
        if haku_nappi and hakusana and api_avain:
            with st.spinner(f"Haetaan '{hakusana}' aineistosta {indeksi_nimi}..."):
                kysely = rakenna_kysely(hakusana, vuosi_alku, vuosi_loppu, indeksi_avain, nimivariaatiot)
                kysely["size"] = tulosten_maara
                resp = tee_haku(api_avain, indeksi_avain, kysely)

            if resp:
                osumia = resp.get("hits", {}).get("total", {}).get("value", 0)
                tulokset = resp.get("hits", {}).get("hits", [])

                if osumia == 0:
                    st.warning(f"Ei osumia haulle '{hakusana}' valituilla kriteereillä.")
                else:
                    # KPI-kortit
                    nayta_kpi_kortit(osumia, tulokset, indeksi_avain)
                    st.divider()

                    # Visualisoinnit
                    with st.container():
                        nayta_visualisoinnit(resp, indeksi_avain)
                    st.divider()

                    # Tuloslista
                    st.subheader(f"📋 Tulokset (näytetään {len(tulokset)} / {osumia:,} osumaa)")
                    if osumia > tulosten_maara:
                        st.info(f"💡 Rajaa hakua tai suurenna tulosten määrää. Rajapinta palauttaa max 10 000 tulosta.")

                    for idx, tulos in enumerate(tulokset):
                        nayta_tulos(tulos, idx, indeksi_avain)

        elif not haku_nappi:
            st.info("👈 Syötä hakusana sivupalkissa ja paina **Hae**.")

    with tab_paivakirja:
        st.subheader("📓 Tutkimuspäiväkirja")
        paivakirja = lataa_paivakirja()

        if not paivakirja:
            st.info("Päiväkirja on tyhjä. Tallenna löytöjä hakutulosten joukosta.")
        else:
            st.success(f"Tallennettu {len(paivakirja)} löytöä.")

            # Vienti CSV:ksi
            df_pk = pd.json_normalize(paivakirja)
            csv_data = df_pk.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Lataa CSV",
                data=csv_data,
                file_name="tutkimuspaivakirja.csv",
                mime="text/csv"
            )

            for i, merkinta in enumerate(reversed(paivakirja)):
                tallennettu = merkinta.get("tallennettu", "")[:10]
                data = merkinta.get("data", {})
                otsikko = data.get("arkistoyksikkö", data.get("df", f"Löytö #{len(paivakirja)-i}"))
                with st.expander(f"📌 {otsikko} · tallennettu {tallennettu}"):
                    if merkinta.get("muistiinpano"):
                        st.markdown(f"**Muistiinpano:** {merkinta['muistiinpano']}")
                    st.json(data)

            if st.button("🗑️ Tyhjennä päiväkirja", type="secondary"):
                PAIVAKIRI_PATH.unlink(missing_ok=True)
                st.rerun()

    with tab_ohje:
        st.subheader("ℹ️ Käyttöohjeet")
        st.markdown("""
        ### API-avaimen hankkiminen
        Ota yhteyttä Kansallisarkistoon: **sanna.joska@kansallisarkisto.fi**
        
        ### API-avaimen asettaminen
        Luo projektin juureen `.env`-tiedosto:
        ```
        KA_API_KEY=sinun_avaimesi_tähän
        ```
        Tai Streamlit Cloud -julkaisussa lisää avain **Secrets**-asetuksiin:
        ```toml
        KA_API_KEY = "sinun_avaimesi_tähän"
        ```
        
        ### Aineistot
        | Aineisto | Sisältö | Aikaväli |
        |---|---|---|
        | Tuomiokirjat | Yli 7 milj. käräjäkirjasivua | 1600–1900-luvut |
        | Voudintilit | Ruotsin vallan verotusaineisto | 1537–1634 |
        | Diplomatarium Fennicum | Keskiaikaiset asiakirjat | ~1100–1540 |
        
        ### Nimivariaatio-ominaisuus
        Historiallisessa aineistossa sama nimi esiintyy usein eri muodoissa.
        Esimerkiksi *Juho* → Johan, Johannes, Juhana, Juhani.
        
        Mikäli nimeäsi ei löydy variaatiolistasta, työkalu lisää automaattisesti
        jokerimerkin (`*`) haun laajentamiseksi.
        
        ### Tutkimuspäiväkirja
        Tallenna mielenkiintoiset löydöt **Tallenna löytö** -painikkeella.
        Lisää halutessasi muistiinpano. Kaikki löydöt voi viedä CSV-tiedostona
        jatkoanalyysiä varten.
        
        ### Linkit Astiaan
        Tuomiokirja-aineiston tuloksissa on suora linkki Kansallisarkiston
        Astia-palveluun alkuperäisen digitoidun asiakirjan tarkasteluun.
        """)


if __name__ == "__main__":
    main()
