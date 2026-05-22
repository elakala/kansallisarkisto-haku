"""
Kansallisarkiston Sisältöhaku-työkalu
Sukututkimuksen ja historiallisen aineiston hakutyökalu
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
import re
from dotenv import load_dotenv

load_dotenv()

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

ASIASANAT = {
    "⚖️ Oikeudenkäynti": ["tuomio", "käräjä", "syyte", "vastaaja", "kantaja", "sakko", "rangaistus", "oikeus", "dom", "rätt", "sak", "böter", "straff"],
    "💰 Kauppa & velka": ["kauppa", "velka", "maksu", "myynti", "osto", "handel", "skuld", "betalning", "köp", "sälj", "köpman"],
    "🏠 Perintö & omaisuus": ["perintö", "testamentti", "tila", "maa", "omaisuus", "arv", "testamente", "gård", "jord", "egendom", "hemman"],
    "👤 Henkilö": ["nimeltä", "poika", "tytär", "vaimo", "mies", "leski", "son", "dotter", "hustru", "man", "änka", "enka"],
    "⛪ Kirkko & uskonto": ["kirkko", "pappi", "seurakunta", "kyrka", "präst", "församling", "noita", "taikuus", "häxeri"],
    "🔪 Väkivalta": ["tappo", "murha", "haavoitti", "löi", "mord", "dråp", "slagsmål", "sår"],
    "🌾 Maatalous": ["talo", "torppari", "ratsutila", "pelto", "heinä", "hevonen", "bonde", "torpare", "åker", "häst"],
}

ALUEET = {
    "Pohjanmaa": ["pohjanmaa", "österbotten", "vaasan lääni", "vasa län"],
    "Häme": ["häme", "tavastland", "hämeen lääni"],
    "Savo": ["savo", "savolax", "savonlinna", "nyslott"],
    "Varsinais-Suomi": ["varsinais-suomi", "egentliga finland"],
    "Uusimaa": ["uusimaa", "nyland"],
    "Karjala": ["karjala", "karelien", "karelen"],
    "Lappi": ["lappi", "lappland", "lapinmaa"],
    "Satakunta": ["satakunta", "björneborg"],
    "Keski-Suomi": ["keski-suomi", "mellersta finland"],
    "Kymenlaakso": ["kymenlaakso", "kymmene"],
}

# ── Kuntalistat ────────────────────────────────────────────────────────────────
# Muoto: "Näytettävä nimi": [hakusanat tekstistä, min 4 merkkiä]
# Pohjanmaa ja Etelä-Pohjanmaa erittäin kattavasti

KUNNAT = {
    # ── Etelä-Pohjanmaa ────────────────────────────────────────────────────────
    "Alajärvi":       ["alajärvi", "alajärfs", "alajerfvi"],
    "Alavus":         ["alavus", "alavo"],
    "Evijärvi":       ["evijärvi", "evijärfs"],
    "Ilmajoki":       ["ilmajoki", "ilmola"],
    "Isojoki":        ["isojoki", "storå"],
    "Isokyrö":        ["isokyrö", "storkyro", "stor-kyro"],
    "Jalasjärvi":     ["jalasjärvi"],
    "Jurva":          ["jurva"],
    "Karijoki":       ["karijoki", "bötom"],
    "Kauhajoki":      ["kauhajoki"],
    "Kauhava":        ["kauhava"],
    "Kortesjärvi":    ["kortesjärvi"],
    "Kuortane":       ["kuortane"],
    "Kurikka":        ["kurikka"],
    "Laihia":         ["laihia", "laihela", "laihiaa"],
    "Lapua":          ["lapua", "lappo"],
    "Lehtimäki":      ["lehtimäki"],
    "Lappajärvi":     ["lappajärvi", "lappajärfs"],
    "Nurmo":          ["nurmo"],
    "Peräseinäjoki":  ["peräseinäjoki"],
    "Seinäjoki":      ["seinäjoki"],
    "Soini":          ["soini"],
    "Teuva":          ["teuva", "östermark"],
    "Töysä":          ["töysä"],
    "Vimpeli":        ["vimpeli", "vindala"],
    "Ylihärmä":       ["ylihärmä"],
    "Ylistaro":       ["ylistaro"],
    "Ylänkyrö":       ["ylänkyrö"],
    "Ähtäri":         ["ähtäri", "etseri"],
    # ── Pohjanmaa (rannikko) ───────────────────────────────────────────────────
    "Vaasa":          ["vaasa", "wasa", "vasa", "nikolainkaupunki"],
    "Kokkola":        ["kokkola", "gamlakarleby", "gamla carleby"],
    "Pietarsaari":    ["pietarsaari", "jakobstad"],
    "Kristiinankaupunki": ["kristiinankaupunki", "kristinestad", "christinestad"],
    "Kaskinen":       ["kaskinen", "kaskö"],
    "Uusikaarlepyy":  ["uusikaarlepyy", "nykarleby"],
    "Isokaarlepyy":   ["isokaarlepyy", "gamalkarleby"],
    "Maalahti":       ["maalahti", "malax"],
    "Mustasaari":     ["mustasaari", "korsholm"],
    "Vähäkyrö":       ["vähäkyrö", "lillkyro"],
    "Maksamaa":       ["maksamaa", "maxmo"],
    "Raippaluoto":    ["raippaluoto", "replot"],
    "Oravainen":      ["oravainen", "oravais"],
    "Munsala":        ["munsala"],
    "Uudenkaarlepyyn mlk": ["uudenkaarlepyyn", "nykarleby lk"],
    "Jepua":          ["jepua", "jeppo"],
    "Purmo":          ["purmo"],
    "Kruunupyy":      ["kruunupyy", "kronoby"],
    "Luoto":          ["luoto", "larsmo"],
    "Kaarlela":       ["kaarlela", "karleby"],
    "Alaveteli":      ["alaveteli", "nedervetil"],
    "Kälviä":         ["kälviä", "kelviå"],
    "Ullava":         ["ullava"],
    "Lohtaja":        ["lohtaja", "lochteå"],
    "Himanka":        ["himanka"],
    "Kannus":         ["kannus"],
    "Toholampi":      ["toholampi"],
    "Veteli":         ["veteli", "vetil"],
    "Halsua":         ["halsua"],
    "Perho":          ["perho"],
    "Kaustinen":      ["kaustinen", "kaustby"],
    "Lestijärvi":     ["lestijärvi"],
    # ── Keski-Pohjanmaa ────────────────────────────────────────────────────────
    "Haapajärvi":     ["haapajärvi"],
    "Haapavesi":      ["haapavesi"],
    "Nivala":         ["nivala", "nivalax"],
    "Pyhäjärvi":      ["pyhäjärvi"],
    "Ylivieska":      ["ylivieska"],
    "Sievi":          ["sievi", "sievi"],
    "Alavieska":      ["alavieska"],
    "Kalajoki":       ["kalajoki"],
    "Merijärvi":      ["merijärvi"],
    "Oulainen":       ["oulainen"],
    "Reisjärvi":      ["reisjärvi"],
    "Vihanti":        ["vihanti"],
    # ── Muut maakunnat ─────────────────────────────────────────────────────────
    "Helsinki":       ["helsinki", "helsingfors"],
    "Turku":          ["turku", "åbo"],
    "Tampere":        ["tampere", "tammerfors"],
    "Oulu":           ["oulu", "uleåborg", "uleaborg"],
    "Kuopio":         ["kuopio"],
    "Jyväskylä":      ["jyväskylä"],
    "Lahti":          ["lahti"],
    "Pori":           ["pori", "björneborg"],
    "Hämeenlinna":    ["hämeenlinna", "tavastehus"],
    "Joensuu":        ["joensuu"],
    "Rovaniemi":      ["rovaniemi"],
    "Mikkeli":        ["mikkeli", "s:t michel", "sant michel"],
    "Savonlinna":     ["savonlinna", "nyslott"],
    "Kotka":          ["kotka"],
    "Lappeenranta":   ["lappeenranta", "villmanstrand"],
    "Viipuri":        ["viipuri", "viborg", "wyborg"],
    "Porvoo":         ["porvoo", "borgå"],
    "Rauma":          ["rauma", "raumo"],
    "Kajaani":        ["kajaani", "kajana"],
    "Raahe":          ["raahe", "brahestad"],
    "Tammisaari":     ["tammisaari", "ekenäs"],
    "Loviisa":        ["loviisa", "lovisa"],
    "Hanko":          ["hanko", "hangö"],
    "Naantali":       ["naantali", "nådendal"],
    "Uusikaupunki":   ["uusikaupunki", "nystad"],
    "Heinola":        ["heinola"],
    "Iisalmi":        ["iisalmi", "idensalmi"],
    "Lieksa":         ["lieksa"],
    "Nurmes":         ["nurmes"],
    "Kemi":           ["kemi"],
    "Tornio":         ["tornio", "torneå"],
    "Salo":           ["salo"],
    "Forssa":         ["forssa"],
    "Valkeakoski":    ["valkeakoski"],
    "Nokia":          ["nokia"],
    "Ikaalinen":      ["ikaalinen", "ikalis"],
    "Kangasala":      ["kangasala"],
    "Lempäälä":       ["lempäälä"],
    "Pirkkala":       ["pirkkala", "birkala"],
    "Ylöjärvi":       ["ylöjärvi"],
    "Hollola":        ["hollola"],
    "Nastola":        ["nastola"],
    "Asikkala":       ["asikkala"],
    "Hauho":          ["hauho"],
    "Janakkala":      ["janakkala"],
    "Loppi":          ["loppi"],
    "Riihimäki":      ["riihimäki"],
    "Hyvinkää":       ["hyvinkää", "hyvinge"],
    "Järvenpää":      ["järvenpää"],
    "Kerava":         ["kerava", "kervo"],
    "Nurmijärvi":     ["nurmijärvi"],
    "Tuusula":        ["tuusula", "tusby"],
    "Vantaa":         ["vantaa", "vanda"],
    "Espoo":          ["espoo", "esbo"],
    "Lohja":          ["lohja", "lojo"],
    "Kirkkonummi":    ["kirkkonummi", "kyrkslätt"],
    "Sipoo":          ["sipoo", "sibbo"],
    "Mäntsälä":       ["mäntsälä"],
    "Pornainen":      ["pornainen", "borgnäs"],
    "Iitti":          ["iitti", "itis"],
    "Kouvola":        ["kouvola"],
    "Hamina":         ["hamina", "fredrikshamn"],
    "Imatra":         ["imatra"],
    "Joutseno":       ["joutseno"],
    "Ruokolahti":     ["ruokolahti"],
    "Savitaipale":    ["savitaipale"],
    "Taipalsaari":    ["taipalsaari"],
    "Anjalankoski":   ["anjalankoski"],
    "Elimäki":        ["elimäki"],
    "Pälkäne":        ["pälkäne"],
    "Urjala":         ["urjala"],
    "Vesilahti":      ["vesilahti"],
    "Huittinen":      ["huittinen", "vittis"],
    "Kokemäki":       ["kokemäki", "kumo"],
    "Harjavalta":     ["harjavalta"],
    "Nakkila":        ["nakkila"],
    "Ulvila":         ["ulvila", "ulfsby"],
    "Eura":           ["eura"],
    "Eurajoki":       ["eurajoki", "euraåminne"],
    "Lieto":          ["lieto", "lundo"],
    "Masku":          ["masku"],
    "Nousiainen":     ["nousiainen", "nousis"],
    "Paimio":         ["paimio", "pemar"],
    "Parainen":       ["parainen", "pargas"],
    "Raisio":         ["raisio", "reso"],
    "Kaarina":        ["kaarina", "s:t karins"],
    "Suomusjärvi":    ["suomusjärvi"],
    "Kemiö":          ["kemiö", "kimito"],
    "Dragsfjärd":     ["dragsfjärd"],
    "Perniö":         ["perniö", "bjärnå"],
    "Halikko":        ["halikko"],
    "Pyhäranta":      ["pyhäranta"],
    "Laitila":        ["laitila", "letala"],
    "Mynämäki":       ["mynämäki", "virmo"],
    "Vehmaa":         ["vehmaa", "vehmo"],
}

def etsi_kunta(teksti):
    """Etsi kuntamaininnat tekstistä, palauta lista löydetyistä kunnista."""
    loydetyt = []
    teksti_lower = teksti.lower()
    for kunta, hakusanat in KUNNAT.items():
        for hakusana in hakusanat:
            if len(hakusana) < 4:
                continue
            # Tarkista sanarajat jotta "Ii" ei osu "siinä"-sanaan
            pattern = r'\b' + re.escape(hakusana) + r'\b'
            if re.search(pattern, teksti_lower):
                loydetyt.append(kunta)
                break
    return loydetyt[:2]  # max 2 kuntaa per tulos


def generoi_tagit(src, indeksi_avain):
    tagit = []
    teksti_kentta = "transcript" if indeksi_avain == "df" else "teksti"
    teksti = (src.get(teksti_kentta, "") or "").lower()
    aineisto = (src.get("aineistokokonaisuus", "") or "").lower()
    haku_teksti = teksti + " " + aineisto

    # Vuosisatatägi
    try:
        vuosi = int(src.get("alkuvuosi", src.get("dating_start_year", 0)) or 0)
        if vuosi:
            vuosisata = (vuosi // 100) * 100
            tagit.append(f"📅 {vuosisata}-luku")
    except (TypeError, ValueError):
        pass

    # Kuntatägit (ennen aluetta – tarkempi tieto)
    kunnat = etsi_kunta(haku_teksti)
    for kunta in kunnat:
        tagit.append(f"🏘️ {kunta}")

    # Aluetägi vain jos kuntaa ei löydy
    if not kunnat:
        for alue, hakusanat in ALUEET.items():
            if any(s in haku_teksti for s in hakusanat):
                tagit.append(f"📍 {alue}")
                break

    # Asiasanatägit
    loydetyt = []
    for tagi, hakusanat in ASIASANAT.items():
        if any(s in teksti for s in hakusanat):
            loydetyt.append(tagi)
    tagit.extend(loydetyt[:2])

    if indeksi_avain == "df":
        kieli = src.get("language", "")
        if kieli:
            tagit.append(f"🗣️ {kieli}")

    return tagit[:5]  # max 5 tägejä


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
        "fields": {teksti_kentta: {"fragment_size": 250, "number_of_fragments": 1}},
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

    with st.container():
        header_cols = st.columns([6, 1])
        with header_cols[0]:
            otsikko_str = f"**{otsikko}**"
            if paikka and paikka != otsikko:
                otsikko_str += f" · {paikka}"
            st.markdown(otsikko_str)
        with header_cols[1]:
            url = src.get("url", "")
            if url:
                st.markdown(f"[🔗 Astia]({url})")

        tagit = generoi_tagit(src, indeksi_avain)
        if tagit:
            st.markdown(" &nbsp; ".join([f"`{t}`" for t in tagit]))

        katkelmat = highlights.get(teksti_kentta, [])
        if katkelmat:
            katkelma = katkelmat[0]
            st.markdown(
                f"<div style='background:#f8f9fa; border-left:3px solid #cbd5e0; "
                f"padding:8px 12px; border-radius:4px; font-size:0.88rem; "
                f"color:#4a5568; margin:4px 0 2px 0;'>{katkelma}</div>",
                unsafe_allow_html=True
            )
        else:
            teksti = src.get(teksti_kentta, "")
            if teksti:
                st.markdown(
                    f"<div style='background:#f8f9fa; border-left:3px solid #cbd5e0; "
                    f"padding:8px 12px; border-radius:4px; font-size:0.88rem; "
                    f"color:#4a5568; margin:4px 0 2px 0;'>{teksti[:300]}{'...' if len(teksti) > 300 else ''}</div>",
                    unsafe_allow_html=True
                )

        with st.expander("Lisätiedot", expanded=False):
            mcols = st.columns(2)
            with mcols[0]:
                if indeksi_avain != "df":
                    st.caption(f"**Aineisto:** {src.get('aineistokokonaisuus', '–')}")
                    st.caption(f"**Pääsarja:** {src.get('pääsarja', '–')}")
                    st.caption(f"**Arkistoyksikkö:** {src.get('arkistoyksikkö', '–')}")
                else:
                    st.caption(f"**Antopaikka:** {src.get('issuingplace', '–')} ({src.get('issuingplacecountry', '')})")
                    st.caption(f"**Kieli:** {src.get('language', '–')}")
            with mcols[1]:
                st.caption(f"**Aikaväli:** {src.get('alkuvuosi', src.get('dating_start_year', '?'))} – {src.get('loppuvuosi', src.get('dating_end_year', '?'))}")
                if url:
                    st.markdown(f"[🔗 Avaa Astiassa]({url})")

        st.divider()


def suodata_ja_jarjesta(tulokset, indeksi_avain, jarjestys, aineisto_filtteri, valitut_tagit, teksti_filtteri):
    vuosi_kentta = "dating_start_year" if indeksi_avain == "df" else "alkuvuosi"

    if teksti_filtteri:
        teksti_kentta = "transcript" if indeksi_avain == "df" else "teksti"
        tulokset = [
            t for t in tulokset
            if teksti_filtteri.lower() in t["_source"].get(teksti_kentta, "").lower()
        ]

    if aineisto_filtteri and aineisto_filtteri != "Kaikki":
        tulokset = [
            t for t in tulokset
            if t["_source"].get("aineistokokonaisuus", "") == aineisto_filtteri
        ]

    if valitut_tagit:
        def tulos_sisaltaa_tagit(t):
            tuloksen_tagit = generoi_tagit(t["_source"], indeksi_avain)
            return all(tagi in tuloksen_tagit for tagi in valitut_tagit)
        tulokset = [t for t in tulokset if tulos_sisaltaa_tagit(t)]

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

    return tulokset


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

    with st.sidebar:
        st.header("🔍 Hakukriteerit")

        api_avain = hae_api_avain()
        if not api_avain:
            api_avain = st.text_input("🔑 API-avain", type="password",
                                       help="Hae avain: sanna.joska@kansallisarkisto.fi")
            if api_avain:
                st.success("API-avain asetettu")
        else:
            st.success("✅ API-avain ladattu ympäristöstä")

        st.divider()

        hakusana = st.text_input("📝 Hakusana", placeholder="Esim. Koivumäki, Jurva, noita...")

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
        nimivariaatiot = st.checkbox("🔤 Nimivariaatiot",
            help="Hakee automaattisesti historiallisia nimimuotoja (esim. Juho → Johan, Johannes)")
        if nimivariaatiot and hakusana:
            alempi = hakusana.lower()
            if alempi in NIMIVARIAATIOT:
                st.info(f"Hakee: {', '.join(NIMIVARIAATIOT[alempi])}")
            else:
                st.info(f"Lisätään jokerimerkki: {hakusana}*")

        st.divider()
        tulosten_maara = st.slider("Tulosten määrä", 10, 100, 50, step=10)

        haku_nappi = st.button("🔎 Hae", type="primary", use_container_width=True,
                                disabled=not (hakusana and api_avain))
        if not hakusana:
            st.caption("Syötä hakusana aloittaaksesi.")
        if not api_avain:
            st.caption("API-avain puuttuu.")

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
                    st.session_state["tulokset"] = tulokset_raw
                    st.session_state["resp"] = resp
                    st.session_state["indeksi_avain"] = indeksi_avain
                    st.session_state["osumia"] = osumia
                    st.session_state["tulosten_maara"] = tulosten_maara

        if "tulokset" in st.session_state and st.session_state["tulokset"]:
            tulokset_raw = st.session_state["tulokset"]
            resp = st.session_state["resp"]
            indeksi_avain_sessio = st.session_state["indeksi_avain"]
            osumia = st.session_state["osumia"]
            tulosten_maara_sessio = st.session_state["tulosten_maara"]

            nayta_kpi_kortit(osumia, tulokset_raw, indeksi_avain_sessio, len(tulokset_raw))
            st.divider()
            nayta_visualisoinnit(resp, indeksi_avain_sessio)
            st.divider()

            # ── Filtterit juuri ennen tuloksia ─────────────────────────────────
            st.subheader("Järjestely ja suodatus")

            fcol1, fcol2, fcol3 = st.columns(3)
            with fcol1:
                jarjestys = st.selectbox("Järjestys", ["Osuvin ensin", "Vanhin ensin", "Uusin ensin"])
            with fcol2:
                aineistot = sorted(set(
                    t["_source"].get("aineistokokonaisuus", "")
                    for t in tulokset_raw
                    if t["_source"].get("aineistokokonaisuus")
                ))
                if aineistot and indeksi_avain_sessio != "df":
                    aineisto_filtteri = st.selectbox("Aineisto", ["Kaikki"] + aineistot)
                else:
                    aineisto_filtteri = "Kaikki"
                    st.selectbox("Aineisto", ["Kaikki"], disabled=True)
            with fcol3:
                teksti_filtteri = st.text_input("Hae tuloksista", placeholder="Rajaa sanalla...")

            kaikki_tagit = sorted(set(
                tagi
                for t in tulokset_raw
                for tagi in generoi_tagit(t["_source"], indeksi_avain_sessio)
            ))
            valitut_tagit = st.multiselect(
                "Suodata tägien mukaan",
                options=kaikki_tagit,
                placeholder="Valitse yksi tai useampi tägi...",
            )

            st.divider()

            tulokset = suodata_ja_jarjesta(
                tulokset_raw, indeksi_avain_sessio,
                jarjestys, aineisto_filtteri, valitut_tagit, teksti_filtteri
            )

            if osumia > tulosten_maara_sessio:
                st.info(f"💡 Haku löysi {osumia:,} osumaa. Näytetään {tulosten_maara_sessio}, joista suodatuksen jälkeen {len(tulokset)}.")

            st.subheader(f"📋 Tulokset ({len(tulokset)})")

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

        ### Automaattiset tägit
        Jokainen tulos saa automaattisesti tägit:
        - 📅 Vuosisata
        - 🏘️ Kunta (tunnistetaan tekstistä, yli 200 kuntaa ml. lakkautetut)
        - 📍 Maakunta (jos kuntaa ei tunnisteta)
        - Asiasisältö: ⚖️ Oikeudenkäynti, 💰 Kauppa & velka, 🏠 Perintö & omaisuus jne.

        Pohjanmaa ja Etelä-Pohjanmaa ovat erityisen kattavasti mukana.

        ### Järjestely ja suodatus
        - **Järjestys:** Osuvin / Vanhin / Uusin ensin
        - **Aineisto:** Rajaa tiettyyn arkistoaineistokokonaisuuteen
        - **Hae tuloksista:** Suodattaa ladattuja tuloksia tekstin perusteella
        - **Tägifiltteri:** Valitse yksi tai useampi tägi

        ### Linkit Astiaan
        Tuomiokirja-aineiston tuloksissa on suora linkki alkuperäisen asiakirjan tarkasteluun.
        """)


if __name__ == "__main__":
    main()
