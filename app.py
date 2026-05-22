"""
Kansallisarkiston Sisältöhaku-työkalu
Sukututkimuksen ja historiallisen aineiston hakutyökalu
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# ── Konfiguraatio ──────────────────────────────────────────────────────────────
ES_URL = "https://es.demo.kansallisarkisto.fi"

NIMIVARIAATIOT = {
    "juho": ["juho", "johan", "johannes", "juhana", "juhani"],
    "maria": ["maria", "maaria", "mari", "marja", "margareta", "maaret"],
    "anna": ["anna", "anne", "annikki", "annakaisa"],
    "heikki": ["heikki", "henrik", "henrikki", "henric"],
    "matti": ["matti", "matts", "mattias", "matthias"],
    "kalle": ["kalle", "karl", "carolus", "kaarlo"],
    "liisa": ["liisa", "lisa", "elisabet", "elisabetha"],
    "erkki": ["erkki", "eric", "erik", "ericus"],
    "pekka": ["pekka", "petrus", "pietari", "peter"],
    "tuomas": ["tuomas", "thomas", "tomas"],
    "jaakko": ["jaakko", "jacob", "jakob", "jaakob"],
    "mikko": ["mikko", "michel", "michael", "mikael"],
    "riitta": ["riitta", "britta", "brita", "margareta"],
    "kaisa": ["kaisa", "kajsa", "katarina", "katharina"],
}

INDEKSIT = {
    "Tuomiokirjat (1600–1900-luvut)": "tuomiokirjat",
    "Voudintilit (1537–1634)": "voudintilit",
    "Diplomatarium Fennicum (Keskiaika)": "df",
    "Kaikki aineistot": "tuomiokirjat,voudintilit",
}

# ── Apufunktiot ────────────────────────────────────────────────────────────────

def hae_api_avain():
    try:
        return st.secrets["KA_API_KEY"]
    except Exception:
        pass
    return os.environ.get("KA_API_KEY")


def rakenna_kysely(hakusana, vuosi_alku, vuosi_loppu, indeksi, nimivariaatiot):
    teksti_kentta = "transcript" if indeksi == "df" else "teksti"
    vuosi_kentta_alku = "dating_start_year" if indeksi == "df" else "alkuvuosi"

    hakusanat = [hakusana]
    if nimivariaatiot:
        alempi = hakusana.lower()
        if alempi in NIMIVARIAATIOT:
            hakusanat = NIMIVARIAATIOT[alempi]
        else:
            hakusanat = [hakusana, f"{hakusana}*"]

    if len(hakusanat) == 1:
        teksti_osa = {"match": {teksti_kentta: hakusanat[0]}}
    else:
        teksti_osa = {
            "bool": {
                "should": [{"match": {teksti_kentta: s}} for s in hakusanat],
                "minimum_should_match": 1
            }
        }

    aikasuodatin = {"range": {vuosi_kentta_alku: {"gte": vuosi_alku, "lte": vuosi_loppu}}}

    highlight = {
        "fields": {teksti_kentta: {"fragment_size": 200, "number_of_fragments": 2}},
        "pre_tags": ["**"],
        "post_tags": ["**"]
    }

    aggs = {
        "vuosittain": {
            "histogram": {"field": vuosi_kentta_alku, "interval": 10, "min_doc_count": 1}
        }
    }
    if indeksi != "df":
        aggs["aineistot"] = {
            "terms": {"field": "aineistokokonaisuus.keyword", "size": 50}
        }

    return {
        "query": {"bool": {"must": teksti_osa, "filter": aikasuodatin}},
        "highlight": highlight,
        "aggs": aggs,
        "size": 100,
        "from": 0
    }


def tee_haku(api_avain, indeksi, kysely):
    url = f"{ES_URL}/{indeksi}/_search?pretty"
    headers = {"Authorization": f"ApiKey {api_avain}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json=kysely, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("Yhteys Kansallisarkiston palvelimeen epäonnistui.")
    except requests.exceptions.HTTPError:
        if resp.status_code == 401:
            st.error("API-avain virheellinen tai puuttuu.")
        else:
            st.error(f"API-virhe {resp.status_code}")
    except Exception as e:
        st.error(f"Virhe: {e}")
    return None


def nayta_kpi_kortit(osumia, data, indeksi_avain, naytettavia):
    vuosi_kentta = "dating_start_year" if indeksi_avain == "df" else "alkuvuosi"
    vuodet = []
    for h in data:
        v = h["_source"].get(vuosi_kentta)
        try:
            vuodet.append(int(v))
        except (TypeError, ValueError):
            pass

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Osumia yhteensä", f"{osumia:,}".replace(",", " "))
    col2.metric("Näytetään", naytettavia)
    col3.metric("Vanhin asiakirja", str(min(vuodet)) if vuodet else "–")
    col4.metric("Uusin asiakirja", str(max(vuodet)) if vuodet else "–")


def nayta_visualisoinnit(resp, indeksi_avain):
    agg_vuodet = resp.get("aggregations", {}).get("vuosittain", {}).get("buckets", [])
    if agg_vuodet:
        df_aika = pd.DataFrame([
            {"Vuosikymmen": b["key"], "Osumia": b["doc_count"]}
            for b in agg_vuodet if b["doc_count"] > 0
        ])
        if not df_aika.empty:
            fig = px.bar(
                df_aika, x="Vuosikymmen", y="Osumia",
                title="Osumien jakautuminen vuosikymmenittäin",
                color="Osumia", color_continuous_scale="Teal"
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False, coloraxis_showscale=False
            )
            st.plotly_chart(fig, use_container_width=True)

    agg_aineistot = resp.get("aggregations", {}).get("aineistot", {}).get("buckets", [])
    if agg_aineistot:
        df_a = pd.DataFrame([
            {"Aineisto": b["key"], "Osumia": b["doc_count"]}
            for b in agg_aineistot
        ]).sort_values("Osumia", ascending=True)
        fig2 = px.bar(
            df_a, x="Osumia", y="Aineisto", orientation="h",
            title="Osumien jakautuminen aineistokokonaisuuksittain",
            color="Osumia", color_continuous_scale="Sunset"
        )
        fig2.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False, coloraxis_showscale=False,
            height=max(300, len(agg_aineistot) * 35)
        )
        st.plotly_chart(fig2, use_container_width=True)


def nayta_tulos(tulos, idx, indeksi_avain):
    src = tulos.get("_source", {})
    highlights = tulos.get("highlight", {})

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
        katkelmat = highlights.get(teksti_kentta, [])
        if katkelmat:
            st.markdown("**Tekstikatkelma:**")
            for k in katkelmat[:2]:
                st.markdown(f"> {k}")
        else:
            teksti = src.get(teksti_kentta, "")
            if teksti:
                st.markdown(f"> {teksti[:400]}{'...' if len(teksti) > 400 else ''}")

        cols = st.columns([2, 2])
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


def suodata_ja_jarjesta(tulokset, indeksi_avain, jarjestys, aineisto_filtteri, teksti_filtteri):
    vuosi_kentta = "dating_start_year" if indeksi_avain == "df" else "alkuvuosi"

    # Tekstifiltteri
    if teksti_filtteri:
        teksti_kentta = "transcript" if indeksi_avain == "df" else "teksti"
        tulokset = [
            t for t in tulokset
            if teksti_filtteri.lower() in t["_source"].get(teksti_kentta, "").lower()
        ]

    # Aineistofiltteri
    if aineisto_filtteri and aineisto_filtteri != "Kaikki":
        tulokset = [
            t for t in tulokset
            if t["_source"].get("aineistokokonaisuus", "") == aineisto_filtteri
        ]

    # Järjestely
    def hae_vuosi(t):
        v = t["_source"].get(vuosi_kentta)
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    if jarjestys == "Vanhin ensin":
        tulokset = sorted(tulokset, key=hae_vuosi)
    elif jarjestys == "Uusin ensin":
        tulokset = sorted(tulokset, key=hae_vuosi, reverse=True)
    # "Osuvin ensin" = alkuperäinen järjestys, ei muuteta

    return tulokset


# ── Päänäkymä ─────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Kansallisarkisto Sisältöhaku",
        page_icon="🏛️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.markdown("""
        <style>
        .main-header { font-size: 2rem; font-weight: 700; color: #1a365d; margin-bottom: 0; }
        .sub-header { color: #4a5568; font-size: 0.95rem; margin-top: 0; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="main-header">🏛️ Kansallisarkiston Sisältöhaku</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Sukututkimuksen ja historiallisen aineiston tehotyökalu · Elasticsearch-rajapinta</p>', unsafe_allow_html=True)
    st.divider()

    # ── Sivupalkki ─────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("🔍 Hakukriteerit")

        api_avain = hae_api_avain()
        if not api_avain:
            api_avain = st.text_input(
                "🔑 API-avain", type="password",
                help="Hae avain: sanna.joska@kansallisarkisto.fi"
            )
            if api_avain:
                st.success("API-avain asetettu")
        else:
            st.success("✅ API-avain ladattu ympäristöstä")

        st.divider()

        hakusana = st.text_input(
            "📝 Hakusana",
            placeholder="Esim. Koivumäki, Jurva, noita..."
        )

        indeksi_nimi = st.selectbox("📚 Aineisto", options=list(INDEKSIT.keys()), index=0)
        indeksi_avain = INDEKSIT[indeksi_nimi]

        st.subheader("📅 Aikaväli")
        vuosi_minimi = 1500 if "voudintilit" in indeksi_avain else (1100 if indeksi_avain == "df" else 1600)
        vuosi_maksimi = 1634 if "voudintilit" in indeksi_avain else (1500 if indeksi_avain == "df" else 1950)

        col1, col2 = st.columns(2)
        with col1:
            vuosi_alku = st.number_input("Alku", min_value=1100, max_value=1980, value=vuosi_minimi, step=10)
        with col2:
            vuosi_loppu = st.number_input("Loppu", min_value=1100, max_value=1980, value=vuosi_maksimi, step=10)

        st.divider()
        nimivariaatiot = st.checkbox(
            "🔤 Nimivariaatiot",
            help="Hakee automaattisesti historiallisia nimimuotoja (esim. Juho → Johan, Johannes, Juhana)"
        )
        if nimivariaatiot and hakusana:
            alempi = hakusana.lower()
            if alempi in NIMIVARIAATIOT:
                st.info(f"Hakee: {', '.join(NIMIVARIAATIOT[alempi])}")
            else:
                st.info(f"Lisätään jokerimerkki: {hakusana}*")

        st.divider()
        tulosten_maara = st.slider("Tulosten määrä", 10, 100, 50, step=10)

        haku_nappi = st.button(
            "🔎 Hae", type="primary", use_container_width=True,
            disabled=not (hakusana and api_avain)
        )
        if not hakusana:
            st.caption("Syötä hakusana aloittaaksesi.")
        if not api_avain:
            st.caption("API-avain puuttuu.")

    # ── Välilehdet ─────────────────────────────────────────────────────────────
    tab_haku, tab_ohje = st.tabs(["🔍 Hakutulokset", "ℹ️ Ohjeet"])

    with tab_haku:
        if haku_nappi and hakusana and api_avain:
            with st.spinner(f"Haetaan '{hakusana}'..."):
                kysely = rakenna_kysely(hakusana, vuosi_alku, vuosi_loppu, indeksi_avain, nimivariaatiot)
                kysely["size"] = tulosten_maara
                resp = tee_haku(api_avain, indeksi_avain, kysely)

            if resp:
                osumia = resp.get("hits", {}).get("total", {}).get("value", 0)
                tulokset_raw = resp.get("hits", {}).get("hits", [])

                if osumia == 0:
                    st.warning(f"Ei osumia haulle '{hakusana}' valituilla kriteereillä.")
                else:
                    # Tallenna tulokset session stateen filtteröintiä varten
                    st.session_state["tulokset"] = tulokset_raw
                    st.session_state["resp"] = resp
                    st.session_state["indeksi_avain"] = indeksi_avain
                    st.session_state["osumia"] = osumia
                    st.session_state["tulosten_maara"] = tulosten_maara

        # Näytä tulokset jos niitä on sessiossa
        if "tulokset" in st.session_state and st.session_state["tulokset"]:
            tulokset_raw = st.session_state["tulokset"]
            resp = st.session_state["resp"]
            indeksi_avain_sessio = st.session_state["indeksi_avain"]
            osumia = st.session_state["osumia"]
            tulosten_maara_sessio = st.session_state["tulosten_maara"]

            # ── Filtterit tulosalueen yläpuolella ──────────────────────────────
            st.subheader("🎛️ Järjestely ja suodatus")
            fcol1, fcol2, fcol3 = st.columns(3)

            with fcol1:
                jarjestys = st.selectbox(
                    "Järjestys",
                    ["Osuvin ensin", "Vanhin ensin", "Uusin ensin"]
                )

            with fcol2:
                # Kerää uniikit aineistokokonaisuudet tuloksista
                aineistot = sorted(set(
                    t["_source"].get("aineistokokonaisuus", "")
                    for t in tulokset_raw
                    if t["_source"].get("aineistokokonaisuus")
                ))
                if aineistot and indeksi_avain_sessio != "df":
                    aineisto_filtteri = st.selectbox(
                        "Aineistokokonaisuus",
                        ["Kaikki"] + aineistot
                    )
                else:
                    aineisto_filtteri = "Kaikki"
                    st.selectbox("Aineistokokonaisuus", ["Kaikki"], disabled=True)

            with fcol3:
                teksti_filtteri = st.text_input(
                    "Hae tuloksista",
                    placeholder="Rajaa sanalla...",
                    help="Suodattaa jo ladattuja tuloksia"
                )

            st.divider()

            # Suodata ja järjestä
            tulokset = suodata_ja_jarjesta(
                tulokset_raw, indeksi_avain_sessio,
                jarjestys, aineisto_filtteri, teksti_filtteri
            )

            # KPI-kortit
            nayta_kpi_kortit(osumia, tulokset_raw, indeksi_avain_sessio, len(tulokset))
            st.divider()

            # Visualisoinnit
            nayta_visualisoinnit(resp, indeksi_avain_sessio)
            st.divider()

            # Tuloslista
            if osumia > tulosten_maara_sessio:
                st.info(f"💡 Haku löysi {osumia:,} osumaa. Näytetään {tulosten_maara_sessio}, joista suodatuksen jälkeen {len(tulokset)}.")
            else:
                st.subheader(f"📋 Tulokset ({len(tulokset)} näytetään)")

            if not tulokset:
                st.warning("Ei tuloksia nykyisillä suodattimilla.")
            else:
                for idx, tulos in enumerate(tulokset):
                    nayta_tulos(tulos, idx, indeksi_avain_sessio)

        elif not haku_nappi:
            st.info("👈 Syötä hakusana sivupalkissa ja paina **Hae**.")

    with tab_ohje:
        st.subheader("ℹ️ Käyttöohjeet")
        st.markdown("""
        ### API-avaimen hankkiminen
        Ota yhteyttä Kansallisarkistoon: **sanna.joska@kansallisarkisto.fi**

        ### Aineistot
        | Aineisto | Sisältö | Aikaväli |
        |---|---|---|
        | Tuomiokirjat | Yli 7 milj. käräjäkirjasivua | 1600–1900-luvut |
        | Voudintilit | Ruotsin vallan verotusaineisto | 1537–1634 |
        | Diplomatarium Fennicum | Keskiaikaiset asiakirjat | ~1100–1540 |

        ### Järjestely ja suodatus
        Haun jälkeen voit järjestellä tuloksia kolmella tavalla ilman uutta hakua:
        - **Järjestys:** Osuvin / Vanhin / Uusin ensin
        - **Aineistokokonaisuus:** Rajaa tiettyyn arkistoaineistoon
        - **Hae tuloksista:** Kirjoita sana joka täytyy löytyä tekstistä

        ### Nimivariaatiot
        Historiallisessa aineistossa sama nimi esiintyy usein eri muodoissa.
        Esim. *Juho* → Johan, Johannes, Juhana, Juhani.

        ### Linkit Astiaan
        Tuomiokirja-aineiston tuloksissa on suora linkki Kansallisarkiston
        Astia-palveluun alkuperäisen asiakirjan tarkasteluun.
        """)


if __name__ == "__main__":
    main()
