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
    "Kaikki aineistot": "tuomiokirjat,voudintilit,df",
}


def on_yhdistelma(indeksi):
    """Onko kyseessä usean aineiston yhdistelmähaku (esim. Kaikki aineistot)."""
    return "," in (indeksi or "")


def tuloksen_indeksi(src, indeksi_avain):
    """Päättelee yksittäisen tuloksen aineiston. Yhdistelmähaussa DF tunnistetaan sen kentistä."""
    if not on_yhdistelma(indeksi_avain):
        return indeksi_avain
    return "df" if ("transcript" in src or "dating_start_year" in src) else "tuomiokirjat"


def teksti_kentat(indeksi):
    """Tekstikentät, joista haetaan. DF:ssä teksti on kentässä 'transcript'."""
    if indeksi == "df":
        return ["transcript"]
    if on_yhdistelma(indeksi) and "df" in indeksi.split(","):
        return ["teksti", "transcript"]
    return ["teksti"]

ASIASANAT = {
    "⚖️ Oikeudenkäynti": ["tuomio", "käräjä", "syyte", "vastaaja", "kantaja", "sakko", "rangaistus", "oikeus", "dom", "rätt", "sak", "böter", "straff"],
    "💰 Kauppa & velka": ["kauppa", "velka", "maksu", "myynti", "osto", "handel", "skuld", "betalning", "köp", "sälj", "köpman"],
    "🏠 Perintö & omaisuus": ["perintö", "testamentti", "tila", "maa", "omaisuus", "arv", "testamente", "gård", "jord", "egendom", "hemman"],
    "👤 Henkilö": ["nimeltä", "poika", "tytär", "vaimo", "mies", "leski", "son", "dotter", "hustru", "man", "änka", "enka"],
    "⛪ Kirkko & uskonto": ["kirkko", "pappi", "seurakunta", "kyrka", "präst", "församling", "noita", "taikuus", "häxeri"],
    "🔪 Väkivalta": ["tappo", "murha", "haavoitti", "löi", "mord", "dråp", "slagsmål", "sår"],
    "🌾 Maatalous": ["talo", "torppari", "ratsutila", "pelto", "heinä", "hevonen", "bonde", "torpare", "åker", "häst"],
}

# ── Aineistokokonaisuus → Maakunta -hakemisto ─────────────────────────────────
# Avain = sana joka esiintyy aineistokokonaisuuden alussa (ennen "tuomiokunnan" tms.)
# Arvo = maakunta
AINEISTO_MAAKUNTA = {
    # Etelä-Pohjanmaa
    "Etelä-Pohjanmaan": "Etelä-Pohjanmaa",
    "Ilmajoen": "Etelä-Pohjanmaa",
    "Kauhajoen": "Etelä-Pohjanmaa",
    "Lapuan": "Etelä-Pohjanmaa",
    "Alavuden": "Etelä-Pohjanmaa",
    "Kuortaneen": "Etelä-Pohjanmaa",
    "Lappajärven": "Etelä-Pohjanmaa",
    "Evijärven": "Etelä-Pohjanmaa",
    "Isojoen": "Etelä-Pohjanmaa",
    "Jurvan": "Etelä-Pohjanmaa",
    "Karijoen": "Etelä-Pohjanmaa",
    "Teuvan": "Etelä-Pohjanmaa",
    "Isokyrön": "Etelä-Pohjanmaa",
    "Ylistaron": "Etelä-Pohjanmaa",
    "Seinäjoen": "Etelä-Pohjanmaa",
    "Jalasjärven": "Etelä-Pohjanmaa",
    "Kurikka": "Etelä-Pohjanmaa",
    "Kurikan": "Etelä-Pohjanmaa",
    # Pohjanmaa (rannikko)
    "Pohjanmaan": "Pohjanmaa",
    "Vaasan": "Pohjanmaa",
    "Närpiön": "Pohjanmaa",
    "Uudenkaarlepyyn": "Pohjanmaa",
    "Isokaarlepyyn": "Pohjanmaa",
    "Mustasaaren": "Pohjanmaa",
    "Maalahden": "Pohjanmaa",
    "Kristiinankaupungin": "Pohjanmaa",
    "Kaskisten": "Pohjanmaa",
    "Oravaisten": "Pohjanmaa",
    # Keski-Pohjanmaa
    "Keski-Pohjanmaan": "Keski-Pohjanmaa",
    "Kokkolan": "Keski-Pohjanmaa",
    "Kruunupyyn": "Keski-Pohjanmaa",
    "Kaustisen": "Keski-Pohjanmaa",
    "Vetelin": "Keski-Pohjanmaa",
    "Kannuksen": "Keski-Pohjanmaa",
    "Toholammin": "Keski-Pohjanmaa",
    # Pirkanmaa
    "Tyrvään": "Pirkanmaa",
    "Ikaalisten": "Pirkanmaa",
    "Tampereen": "Pirkanmaa",
    "Tammelan": "Pirkanmaa",
    "Pirkkalan": "Pirkanmaa",
    "Ruoveden": "Pirkanmaa",
    "Laukaan": "Pirkanmaa",
    "Ylöjärven": "Pirkanmaa",
    "Kangasalan": "Pirkanmaa",
    "Hämeenkyrön": "Pirkanmaa",
    "Urjalan": "Pirkanmaa",
    "Vammalan": "Pirkanmaa",
    # Varsinais-Suomi
    "Turun": "Varsinais-Suomi",
    "Rauman": "Varsinais-Suomi",
    "Salon": "Varsinais-Suomi",
    "Loimaan": "Varsinais-Suomi",
    "Maskun": "Varsinais-Suomi",
    "Paimion": "Varsinais-Suomi",
    "Paraisten": "Varsinais-Suomi",
    "Mynämäen": "Varsinais-Suomi",
    "Naantalin": "Varsinais-Suomi",
    "Uudenkaupungin": "Varsinais-Suomi",
    "Halikko": "Varsinais-Suomi",
    "Halikon": "Varsinais-Suomi",
    "Perniön": "Varsinais-Suomi",
    "Vehmaan": "Varsinais-Suomi",
    # Satakunta
    "Porin": "Satakunta",
    "Ulvilan": "Satakunta",
    "Euran": "Satakunta",
    "Kokemäen": "Satakunta",
    "Huittisten": "Satakunta",
    "Harjavallan": "Satakunta",
    "Raaseporin": "Satakunta",
    # Häme
    "Hämeenlinnan": "Kanta-Häme",
    "Tammelan": "Kanta-Häme",
    "Forssan": "Kanta-Häme",
    "Riihimäen": "Kanta-Häme",
    "Janakkalan": "Kanta-Häme",
    "Hattulan": "Kanta-Häme",
    "Hausjärven": "Kanta-Häme",
    "Lopun": "Kanta-Häme",
    # Päijät-Häme
    "Lahden": "Päijät-Häme",
    "Hollolan": "Päijät-Häme",
    "Heinolan": "Päijät-Häme",
    "Nastolan": "Päijät-Häme",
    "Asikkalan": "Päijät-Häme",
    "Sysmän": "Päijät-Häme",
    # Uusimaa
    "Helsingin": "Uusimaa",
    "Espoon": "Uusimaa",
    "Vantaan": "Uusimaa",
    "Porvoon": "Uusimaa",
    "Lohjan": "Uusimaa",
    "Hyvinkään": "Uusimaa",
    "Järvenpään": "Uusimaa",
    "Nurmijärven": "Uusimaa",
    "Tuusulan": "Uusimaa",
    "Kirkkonummen": "Uusimaa",
    "Sipoon": "Uusimaa",
    "Tammisaaren": "Uusimaa",
    "Hangon": "Uusimaa",
    "Loviisan": "Uusimaa",
    # Kymenlaakso
    "Kotkan": "Kymenlaakso",
    "Kouvolan": "Kymenlaakso",
    "Haminan": "Kymenlaakso",
    "Imatran": "Kymenlaakso",
    "Elimäen": "Kymenlaakso",
    "Anjalankosken": "Kymenlaakso",
    "Iitin": "Kymenlaakso",
    # Etelä-Karjala
    "Lappeenrannan": "Etelä-Karjala",
    "Viipurin": "Etelä-Karjala",
    "Joutsenon": "Etelä-Karjala",
    "Ruokolahden": "Etelä-Karjala",
    "Savitaipaleen": "Etelä-Karjala",
    # Etelä-Savo
    "Mikkelin": "Etelä-Savo",
    "Savonlinnan": "Etelä-Savo",
    "Pieksämäen": "Etelä-Savo",
    "Heinäveden": "Etelä-Savo",
    # Pohjois-Savo
    "Kuopion": "Pohjois-Savo",
    "Iisalmen": "Pohjois-Savo",
    "Varkauden": "Pohjois-Savo",
    "Suonenjoen": "Pohjois-Savo",
    # Pohjois-Karjala
    "Joensuun": "Pohjois-Karjala",
    "Lieksan": "Pohjois-Karjala",
    "Nurmeksen": "Pohjois-Karjala",
    "Kiteen": "Pohjois-Karjala",
    "Tohmajärven": "Pohjois-Karjala",
    # Keski-Suomi
    "Jyväskylän": "Keski-Suomi",
    "Äänekosken": "Keski-Suomi",
    "Jämsän": "Keski-Suomi",
    "Saarijärven": "Keski-Suomi",
    "Viitasaaren": "Keski-Suomi",
    "Laukaan": "Keski-Suomi",
    "Liperin": "Keski-Suomi",
    # Pohjois-Pohjanmaa
    "Oulun": "Pohjois-Pohjanmaa",
    "Oulun laamannikunnan": "Pohjois-Pohjanmaa",
    "Raahen": "Pohjois-Pohjanmaa",
    "Ylivieskan": "Pohjois-Pohjanmaa",
    "Haapajärven": "Pohjois-Pohjanmaa",
    "Kalajoen": "Pohjois-Pohjanmaa",
    "Oulaisten": "Pohjois-Pohjanmaa",
    "Nivalan": "Pohjois-Pohjanmaa",
    "Pyhäjärven": "Pohjois-Pohjanmaa",
    # Lappi
    "Rovaniemen": "Lappi",
    "Kemin": "Lappi",
    "Tornion": "Lappi",
    "Sodankylän": "Lappi",
    # Kainuu
    "Kajaanin": "Kainuu",
    "Sotkamon": "Kainuu",
    "Kuhmon": "Kainuu",
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

# ── Maakunta → aineistokokonaisuuden avainsanat -hakemisto ────────────────────
# Käänteinen AINEISTO_MAAKUNTA: maakunta → lista aineistonimiä joiden alkua matchataan
def hae_maakunnan_aineistot(maakunta):
    """Palauttaa listan aineistokokonaisuuden nimien alusta jotka kuuluvat maakuntaan."""
    return [avain for avain, mk in AINEISTO_MAAKUNTA.items() if mk == maakunta]


# ── Maakunta → täydet aineistonimet (haettu API:sta) ─────────────────────────
MAAKUNTA_AINEISTOT = {
    "Etelä-Pohjanmaa": [
        "Alavuden tuomiokunnan renovoidut tuomiokirjat (HMA)",
        "Ilmajoen tuomiokunnan renovoidut tuomiokirjat (HMA)",
        "Etelä-Pohjanmaan tuomiokunnan renovoidut tuomiokirjat",
        "Ilmajoen tuomiokunnan renovoidut tuomiokirjat",
        "Alavuden tuomiokunnan renovoidut tuomiokirjat",
    ],
    "Pohjanmaa": [
        "Vaasan hovioikeuden arkisto",
        "Närpiön tuomiokunnan renovoidut tuomiokirjat (HMA)",
        "Vaasan raastuvanoikeuden renovoidut tuomiokirjat",
        "Vaasan raastuvanoikeuden arkisto (VMA)",
        "Pohjanmaan itäisen tuomiokunnan renovoidut tuomiokirjat",
        "Pohjanmaan pohjoisen tuomiokunnan renovoidut tuomiokirjat",
        "Kristiinankaupungin raastuvanoikeuden renovoidut tuomiokirjat",
        "Kaskisten raastuvanoikeuden renovoidut tuomiokirjat",
        "Vaasan laamannikunnan renovoidut tuomiokirjat",
        "Vaasan ja Oulun laamannikunnan renovoidut tuomiokirjat",
        "Kaskisten raastuvanoikeuden arkisto (VMA)",
        "Vaasan kämnerinoikeuden renovoidut tuomiokirjat",
        "Uudenkaarlepyyn tuomiokunnan renovoidut tuomiokirjat",
        "Närpiön tuomiokunnan renovoidut tuomiokirjat",
        "Uudenkaarlepyyn raastuvanoikeuden renovoidut tuomiokirjat",
        "Pohjanmaan tuomiokunnan renovoidut tuomiokirjat",
    ],
}

def hae_kaikki_maakunnat():
    """Palauttaa uniikit maakunnat aakkosjärjestyksessä."""
    return sorted(set(AINEISTO_MAAKUNTA.values()))


def etsi_paikkakunta_aineistosta(aineistokokonaisuus):
    """Pura paikkakunta ja maakunta aineistokokonaisuuden nimestä."""
    if not aineistokokonaisuus:
        return None, None

    # Irrotetaan ensimmäinen osa ennen "tuomiokunnan", "hovioikeuden" jne.
    erottimet = [
        " tuomiokunnan", " hovioikeuden", " raastuvanoikeuden",
        " laamannikunnan", " alisen ", " ylisen ", " itäisen ", " läntisen "
    ]
    paikkakunta = aineistokokonaisuus
    for erotin in erottimet:
        if erotin in paikkakunta.lower():
            paikkakunta = paikkakunta[:paikkakunta.lower().index(erotin)]
            break

    # Siivotaan sulkeet pois lopusta
    paikkakunta = paikkakunta.split("(")[0].strip()

    # Haetaan maakunta hakemistosta
    maakunta = None
    for avain, mk in AINEISTO_MAAKUNTA.items():
        if paikkakunta.lower().startswith(avain.lower()):
            maakunta = mk
            break

    return paikkakunta if len(paikkakunta) > 2 else None, maakunta

def generoi_tagit(src, indeksi_avain):
    indeksi_avain = tuloksen_indeksi(src, indeksi_avain)
    tagit = []
    teksti_kentta = "transcript" if indeksi_avain == "df" else "teksti"
    teksti = (src.get(teksti_kentta, "") or "").lower()
    aineistokokonaisuus = src.get("aineistokokonaisuus", "") or ""

    # Vuosisatatägi
    try:
        vuosi = int(src.get("alkuvuosi", src.get("dating_start_year", 0)) or 0)
        if vuosi:
            vuosisata = (vuosi // 100) * 100
            tagit.append(f"📅 {vuosisata}-luku")
    except (TypeError, ValueError):
        pass

    # Paikkakunta- ja maakuntätägi aineistokokonaisuudesta
    if indeksi_avain != "df":
        paikkakunta, maakunta = etsi_paikkakunta_aineistosta(aineistokokonaisuus)
        if paikkakunta:
            tagit.append(f"📍 {paikkakunta}")
        if maakunta:
            tagit.append(f"🗺️ {maakunta}")
    else:
        # DF: antopaikka
        paikka = src.get("issuingplace", "")
        if paikka:
            tagit.append(f"📍 {paikka}")

    # Asiasanatägit (max 2)
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


# ── Hakulogiikka ──────────────────────────────────────────────────────────────
# Tunnistetaan, onko käyttäjä kirjoittanut omaa hakusyntaksia (lainausmerkit,
# jokerimerkit, AND/OR/NOT, sulkeet). Silloin kysely annetaan sellaisenaan.
_EDISTYNYT_RE = re.compile(r'["*?~()]|\b(AND|OR|NOT)\b')


def on_edistynyt_haku(teksti):
    return bool(teksti and _EDISTYNYT_RE.search(teksti))


def pilko_sanoiksi(teksti):
    """Pilkkoo hakulauseen sanoiksi. Pilkut ja välimerkit toimivat erottimina."""
    if not teksti:
        return []
    return [s for s in re.split(r"[\s,;]+", teksti.strip()) if s]


def sanan_muodot(sana, nimivariaatiot):
    """Palauttaa sanan ja sen historialliset nimimuodot (jos käytössä)."""
    alempi = sana.lower()
    if nimivariaatiot and alempi in NIMIVARIAATIOT:
        return NIMIVARIAATIOT[alempi]
    return [sana]


def sana_lauseke(sana, kentat, nimivariaatiot, sumea):
    """Yksi hakusana: osuma mihin tahansa sen muodoista riittää."""
    lausekkeet = []
    for muoto in sanan_muodot(sana, nimivariaatiot):
        match = {"query": muoto, "fields": kentat}
        if sumea:
            # AUTO: 3–5 merkkiä → 1 virhe, yli 5 merkkiä → 2 virhettä.
            # Ensimmäinen kirjain pidetään kiinni, jotta haku ei leviä liikaa.
            match.update({"fuzziness": "AUTO", "prefix_length": 1, "max_expansions": 50})
        lausekkeet.append({"multi_match": match})
    if len(lausekkeet) == 1:
        return lausekkeet[0]
    return {"bool": {"should": lausekkeet, "minimum_should_match": 1}}


def tekstihaku_lauseke(teksti, kentat, nimivariaatiot, sumea, laaja):
    """
    Rakentaa tekstihaun:
    - Edistynyt syntaksi → query_string sellaisenaan (oletus AND, laajassa OR)
    - Tavallinen haku → jokainen sana omana lausekkeenaan (AND tai laajassa OR)
    """
    if on_edistynyt_haku(teksti):
        return {
            "query_string": {
                "query": teksti,
                "fields": kentat,
                "default_operator": "OR" if laaja else "AND",
                "analyze_wildcard": True,
                "allow_leading_wildcard": False,
            }
        }

    sanat = pilko_sanoiksi(teksti)
    if not sanat:
        return None
    lausekkeet = [sana_lauseke(s, kentat, nimivariaatiot, sumea) for s in sanat]
    if len(lausekkeet) == 1:
        return lausekkeet[0]
    if laaja:
        return {"bool": {"should": lausekkeet, "minimum_should_match": 1}}
    return {"bool": {"must": lausekkeet}}


def laheisyys_boostit(teksti, kentat, nimivariaatiot=False):
    """
    Nostaa kärkeen asiakirjat, joissa sanat ovat peräkkäin tai lähekkäin.
    Ei rajaa tuloksia, vaikuttaa vain järjestykseen.
    Nimivariaatioiden kanssa painotetaan myös esim. "Johan Mäntylä".
    """
    if on_edistynyt_haku(teksti):
        return []
    sanat = pilko_sanoiksi(teksti)
    if len(sanat) < 2:
        return []
    from itertools import islice, product
    muodot = [sanan_muodot(s, nimivariaatiot) for s in sanat]
    lauseet = [" ".join(yhd) for yhd in islice(product(*muodot), 12)]  # enintään 12 yhdistelmää
    boostit = []
    for lause in lauseet:
        boostit.append({"multi_match": {"query": lause, "fields": kentat, "type": "phrase", "boost": 5}})             # täsmälleen peräkkäin
        boostit.append({"multi_match": {"query": lause, "fields": kentat, "type": "phrase", "slop": 5, "boost": 2}})  # enintään ~5 sanan päässä
    return boostit


def kuvaa_haku(hakusana, liittyva_hakusana, nimivariaatiot, sumea, laaja):
    """Selkokielinen kuvaus siitä, mitä haku tekee (näytetään sivupalkissa)."""
    if not hakusana:
        return ""
    if on_edistynyt_haku(hakusana):
        rivit = [f"Oma hakusyntaksi: `{hakusana}`"]
    else:
        osat = []
        for s in pilko_sanoiksi(hakusana):
            muodot = sanan_muodot(s, nimivariaatiot)
            osat.append("(" + " / ".join(muodot) + ")" if len(muodot) > 1 else s)
        liitos = " TAI " if laaja else " JA "
        rivit = [liitos.join(osat)]
    if liittyva_hakusana and liittyva_hakusana.strip():
        rivit.append(f"JA lisäksi: {liittyva_hakusana.strip()}")
    if sumea:
        rivit.append("Sallii pienet kirjoitusvirheet")
    return "  \n".join(rivit)


def rakenna_kysely(hakusana, vuosi_alku, vuosi_loppu, indeksi, nimivariaatiot, maakunta_filtteri=None, liittyva_hakusana=None, teksti_filtteri_es=None, aineisto_tarkka=None, sumea=False, laaja=False):
    kentat = teksti_kentat(indeksi)
    yhdistelma = on_yhdistelma(indeksi)
    vuosi_kentta_alku = "dating_start_year" if indeksi == "df" else "alkuvuosi"

    # Päähaku: oletuksena kaikkien sanojen täytyy löytyä (AND)
    must = []
    paa = tekstihaku_lauseke(hakusana, kentat, nimivariaatiot, sumea, laaja)
    if paa:
        must.append(paa)

    # Liittyvä hakusana: aina pakollinen (AND päähaun kanssa)
    if liittyva_hakusana and liittyva_hakusana.strip():
        liit = tekstihaku_lauseke(liittyva_hakusana, kentat, nimivariaatiot, sumea, laaja=False)
        if liit:
            must.append(liit)

    # Läheisyys nostaa osuvimmat kärkeen
    should = laheisyys_boostit(hakusana, kentat, nimivariaatiot)

    if yhdistelma:
        # Aineistoilla on eri vuosikentät: kelpuutetaan kumpi tahansa
        aikasuodatin = {"bool": {"should": [
            {"range": {"alkuvuosi": {"gte": vuosi_alku, "lte": vuosi_loppu}}},
            {"range": {"dating_start_year": {"gte": vuosi_alku, "lte": vuosi_loppu}}},
        ], "minimum_should_match": 1}}
    else:
        aikasuodatin = {"range": {vuosi_kentta_alku: {"gte": vuosi_alku, "lte": vuosi_loppu}}}

    # Suodattimet ES-tasolla
    filters = [aikasuodatin]

    # Maakuntasuodatin (rajaa pois DF:n, jolla ei ole maakuntatietoa)
    if maakunta_filtteri and indeksi != "df":
        aineisto_avaimet = hae_maakunnan_aineistot(maakunta_filtteri)
        if aineisto_avaimet:
            maakunta_should = [
                {"prefix": {"aineistokokonaisuus.keyword": {"value": avain}}}
                for avain in aineisto_avaimet
            ]
            filters.append({"bool": {"should": maakunta_should, "minimum_should_match": 1}})

    # Tekstifiltteri ES-tasolla (kohdistuu koko tietokantaan, ei vain ladattuihin)
    if teksti_filtteri_es and teksti_filtteri_es.strip():
        filters.append({
            "query_string": {
                "query": teksti_filtteri_es.strip(),
                "fields": kentat,
                "default_operator": "OR",
                "analyze_wildcard": True
            }
        })

    # Tarkka aineistokokonaisuusfiltteri
    if aineisto_tarkka:
        filters.append({
            "term": {"aineistokokonaisuus.keyword": aineisto_tarkka}
        })

    highlight = {
        "fields": {k: {"fragment_size": 500, "number_of_fragments": 2} for k in kentat},
        "pre_tags": ["**"],
        "post_tags": ["**"]
    }

    aggs = {
        "vuosittain": {
            "histogram": {"field": vuosi_kentta_alku, "interval": 10, "min_doc_count": 1}
        }
    }
    if yhdistelma and "df" in indeksi.split(","):
        aggs["vuosittain_df"] = {
            "histogram": {"field": "dating_start_year", "interval": 10, "min_doc_count": 1}
        }
    if indeksi != "df":
        aggs["aineistot"] = {
            "terms": {"field": "aineistokokonaisuus.keyword", "size": 50}
        }

    bool_kysely = {"must": must, "filter": filters}
    if should:
        bool_kysely["should"] = should

    return {
        "query": {"bool": bool_kysely},
        "highlight": highlight,
        "aggs": aggs,
        "track_total_hits": True,
        "size": 100,
        "from": 0
    }


@st.cache_data(ttl=3600, show_spinner=False, max_entries=200)
def _hae_es(api_avain, indeksi, kysely_json):
    """Varsinainen rajapintakutsu. Sama haku palautetaan tunnin ajan välimuistista.
    Vain onnistuneet haut tallentuvat, koska virhe keskeyttää funktion."""
    url = f"{ES_URL}/{indeksi}/_search"
    headers = {"Authorization": f"ApiKey {api_avain}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, data=kysely_json.encode("utf-8"), timeout=20)
    resp.raise_for_status()
    return resp.json()


def tee_haku(api_avain, indeksi, kysely):
    import json
    kysely_json = json.dumps(kysely, ensure_ascii=False, sort_keys=True)
    try:
        return _hae_es(api_avain, indeksi, kysely_json)
    except requests.exceptions.ConnectionError:
        st.error("Yhteys Kansallisarkiston palvelimeen epäonnistui.")
    except requests.exceptions.Timeout:
        st.error("Haku kesti liian kauan. Kokeile rajata hakua (aikaväli, maakunta).")
    except requests.exceptions.HTTPError as e:
        koodi = e.response.status_code if e.response is not None else "?"
        if koodi == 401:
            st.error("API-avain virheellinen tai puuttuu.")
        elif koodi == 403:
            st.error("Ei käyttöoikeutta tähän aineistoon. Kokeile valita aineisto erikseen.")
        else:
            st.error(f"API-virhe {koodi}")
    except Exception as e:
        st.error(f"Virhe: {type(e).__name__}")
    return None


def nayta_kpi_kortit(osumia, data, indeksi_avain, naytettavia):
    vuodet = []
    for h in data:
        v = h["_source"].get("alkuvuosi", h["_source"].get("dating_start_year"))
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
    aggregaatit = resp.get("aggregations", {})
    vuosikymmenet = {}
    for nimi in ("vuosittain", "vuosittain_df"):  # yhdistelmähaussa kaksi vuosikenttää
        for b in aggregaatit.get(nimi, {}).get("buckets", []):
            if b["doc_count"] > 0:
                vuosikymmenet[b["key"]] = vuosikymmenet.get(b["key"], 0) + b["doc_count"]
    if vuosikymmenet:
        df_aika = pd.DataFrame([
            {"Vuosikymmen": k, "Osumia": n} for k, n in sorted(vuosikymmenet.items())
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
        # ── Maakuntakaavio ────────────────────────────────────────────────────
        maakunta_laskuri = {}
        for b in agg_aineistot:
            _, maakunta = etsi_paikkakunta_aineistosta(b["key"])
            if maakunta:
                maakunta_laskuri[maakunta] = maakunta_laskuri.get(maakunta, 0) + b["doc_count"]
            else:
                maakunta_laskuri["Muu/tuntematon"] = maakunta_laskuri.get("Muu/tuntematon", 0) + b["doc_count"]

        if maakunta_laskuri:
            df_mk = pd.DataFrame([
                {"Maakunta": mk, "Osumia": n}
                for mk, n in maakunta_laskuri.items()
            ]).sort_values("Osumia", ascending=True)

            fig_mk = px.bar(
                df_mk, x="Osumia", y="Maakunta", orientation="h",
                title="Osumien jakautuminen maakunnittain",
                color="Osumia", color_continuous_scale="Teal"
            )
            fig_mk.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False, coloraxis_showscale=False,
                height=max(300, len(maakunta_laskuri) * 40)
            )
            st.plotly_chart(fig_mk, use_container_width=True)

        # ── Aineistokaavio (expander, ei oletuksena auki) ─────────────────────
        with st.expander("Näytä jakauma aineistokokonaisuuksittain"):
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



def hae_gemini_avain():
    """Hae Gemini API-avain ympäristömuuttujista tai Streamlit secretseistä."""
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")


def selita_asiakirja_geminilla(asiakirja_teksti: str) -> str:
    """Selittää asiakirjan tekstin Google Gemini Flash -mallilla."""
    import requests as req

    gemini_avain = hae_gemini_avain()
    if not gemini_avain:
        return "⚠️ Gemini API-avain puuttuu. Lisää GEMINI_API_KEY Streamlit Secretsiin."

    katkelma = asiakirja_teksti[:3000]

    prompt = f"""Olet avustaja joka selittää Kansallisarkiston historiallisia asiakirjoja selkeällä suomen kielellä.

Vastaa ilman otsikkoa tässä järjestyksessä:

**Mistä on kyse:** Selitä lyhyesti mistä asiakirjassa on kyse. Maksimissaan 2 lausetta, ei juridista ammattikieltä.

**Henkilöt:** Lista henkilöistä ja heidän rooleistaan. Pidä nimet ja roolit yksinkertaisina.

**Tapahtumapaikka:** Missä asiakirjassa kuvatut tapahtumat sijoittuvat. Maksimissaan 1 lause. Jätä pois jos ei mainita.

**Historiallinen tausta:** Maksimissaan 2 lausetta siitä mitä Suomessa tapahtui asiakirjan aikana ja miten se liittyy tähän asiakirjaan. Jätä pois jos yhteys on epäselvä.

Asiakirja:
{katkelma}"""

    # Avain lähetetään otsakkeessa eikä URL:ssa, jotta se ei päädy lokeihin tai virheilmoituksiin
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    otsakkeet = {"x-goog-api-key": gemini_avain, "Content-Type": "application/json"}

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 1000,
            "temperature": 0.2
        }
    }

    try:
        resp = req.post(url, headers=otsakkeet, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates:
            content_block = candidates[0].get("content", {})
            parts = content_block.get("parts", [])
            if parts:
                return parts[0].get("text", "⚠️ Vastausteksti oli tyhjä.")
        return "⚠️ Gemini palautti tyhjän vastauksen tai sisältö suodatettiin."
    except req.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return "⚠️ Googlen ilmaisraja ylittyi. Odota hetki ja yritä uudelleen."
        if e.response is not None and e.response.status_code == 400:
            return "⚠️ Gemini API-avain virheellinen. Tarkista GEMINI_API_KEY."
        return f"⚠️ API-virhe: {e.response.status_code if e.response else 'Tuntematon'}"
    except Exception as e:
        return f"⚠️ Selitys epäonnistui ({type(e).__name__}). Yritä hetken päästä uudelleen."
def nayta_tulos(tulos, idx, indeksi_avain):
    src = tulos.get("_source", {})
    highlights = tulos.get("highlight", {})
    indeksi_avain = tuloksen_indeksi(src, indeksi_avain)

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

            # ── Koko teksti ───────────────────────────────────────────────────
            teksti_kentta_koko = "transcript" if indeksi_avain == "df" else "teksti"
            koko_teksti = src.get(teksti_kentta_koko, "")
            if koko_teksti:
                with st.expander("📜 Näytä koko teksti"):
                    st.markdown(
                        f"<div style='font-size:0.85rem; line-height:1.7; color:#4a5568;'>{koko_teksti}</div>",
                        unsafe_allow_html=True
                    )

            # ── Tekoälyselitys (Gemini) ────────────────────────────────────────────────
            selitys_avain = f"selitys_{idx}_{tulos.get('_id', '')}"
            teksti_kentta_selitys = "transcript" if indeksi_avain == "df" else "teksti"
            asiakirja_teksti = src.get(teksti_kentta_selitys, "")

            if st.button("✨ Selitä asiakirja tekoälyllä", key=f"btn_{selitys_avain}"):
                if asiakirja_teksti:
                    with st.spinner("Tekoäly analysoi asiakirjaa..."):
                        selitys = selita_asiakirja_geminilla(asiakirja_teksti)
                        st.session_state[selitys_avain] = selitys
                else:
                    st.warning("Asiakirjassa ei ole tekstisisältöä.")

            if selitys_avain in st.session_state:
                st.markdown("**✨ Tekoälyselitys:**")
                st.info(st.session_state[selitys_avain])

        st.divider()


def suodata_ja_jarjesta(tulokset, indeksi_avain, jarjestys, aineisto_filtteri, valitut_tagit):

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
        v = t["_source"].get("alkuvuosi", t["_source"].get("dating_start_year"))
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

        </style>
    """, unsafe_allow_html=True)

    # ── Banneri ────────────────────────────────────────────────────────────────
    st.markdown("""
        <div style="
            width: 100%;
            height: 200px;
            background-image: url('https://raw.githubusercontent.com/elakala/kansallisarkisto-haku/main/ChatGPT%20Image%2022.5.2026%20klo%2018.06.27.png');
            background-size: cover;
            background-position: center 40%;
            border-radius: 8px;
            margin-bottom: 1rem;
            position: relative;
            overflow: hidden;
        ">
            <div style="
                position: absolute; inset: 0;
                background: linear-gradient(to right, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.1) 60%, rgba(0,0,0,0) 100%);
                border-radius: 8px;
                display: flex;
                flex-direction: column;
                justify-content: flex-end;
                padding: 24px 32px;
            ">
                <p style="margin:0; font-size:1.8rem; font-weight:700; color:#ffffff; text-shadow: 0 1px 4px rgba(0,0,0,0.6);">🏛️ Kansallisarkiston Sisältöhaku</p>
                <p style="margin:4px 0 0 0; font-size:0.9rem; color:#e2e8f0; text-shadow: 0 1px 3px rgba(0,0,0,0.5);">Sukututkimuksen ja historiallisen aineiston tehotyökalu · Elasticsearch-rajapinta</p>
            </div>
        </div>
    """, unsafe_allow_html=True)
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

        hakusana = st.text_input(
            "📝 Hakusana",
            placeholder="Esim. Mäntylä, Koivumäki...",
            help="Perushaku. Voit käyttää: Mänty* (jokerimerkki), \"tarkka fraasi\" (lainausmerkit), Mäntylä OR Männylä (tai-haku)."
        )
        liittyva_hakusana = st.text_input(
            "🔗 Liittyvä hakusana (valinnainen)",
            placeholder="Esim. Jurva, lauttamus...",
            help="Tämän sanan täytyy löytyä samasta asiakirjasta päähakusanan kanssa (AND-logiikka)."
        )

        indeksi_nimi = st.selectbox("📚 Aineisto", options=list(INDEKSIT.keys()), index=0)
        indeksi_avain = INDEKSIT[indeksi_nimi]

        st.subheader("📅 Aikaväli")
        if on_yhdistelma(indeksi_avain):
            vuosi_minimi, vuosi_maksimi = 1100, 1950
        elif indeksi_avain == "voudintilit":
            vuosi_minimi, vuosi_maksimi = 1500, 1634
        elif indeksi_avain == "df":
            vuosi_minimi, vuosi_maksimi = 1100, 1500
        else:
            vuosi_minimi, vuosi_maksimi = 1600, 1950

        col1, col2 = st.columns(2)
        with col1:
            vuosi_alku = st.number_input("Alku", min_value=1100, max_value=1980, value=vuosi_minimi, step=10)
        with col2:
            vuosi_loppu = st.number_input("Loppu", min_value=1100, max_value=1980, value=vuosi_maksimi, step=10)

        # Maakuntarajaus
        st.divider()
        kaikki_maakunnat = hae_kaikki_maakunnat()
        maakunta_valinta = st.selectbox(
            "🗺️ Maakunta (rajaa hakua)",
            options=["Kaikki"] + kaikki_maakunnat,
            index=0,
            help="Rajaa haku tietyn maakunnan tuomiokirja-aineistoihin. Diplomatarium Fennicumissa ei ole maakuntatietoa, joten se jää pois rajattaessa."
        )
        maakunta_filtteri = None if maakunta_valinta == "Kaikki" else maakunta_valinta

        # Aineistokokonaisuusfiltteri – näkyy vain jos maakunta valittu ja aineistot tiedossa
        aineisto_tarkka = None
        if maakunta_filtteri and maakunta_filtteri in MAAKUNTA_AINEISTOT:
            aineistolista = MAAKUNTA_AINEISTOT[maakunta_filtteri]
            aineisto_valinta = st.selectbox(
                "📁 Aineistokokonaisuus",
                options=["Kaikki"] + aineistolista,
                index=0,
                help="Rajaa haku tiettyyn tuomiokunnan aineistoon."
            )
            aineisto_tarkka = None if aineisto_valinta == "Kaikki" else aineisto_valinta

        st.divider()
        nimivariaatiot = st.checkbox("🔤 Nimivariaatiot",
            help="Hakee jokaiselle etunimelle historialliset muodot (esim. Juho → Johan, Johannes).")
        sumea = st.checkbox("✏️ Salli kirjoitusvirheet",
            help="Löytää myös pienet poikkeamat, esim. Mäntylä → Mäntyla, Mentylä. "
                 "Hyödyllinen, koska tuomiokirjojen teksti on koneellisesti tunnistettua käsialaa. "
                 "Lisää osumia, mutta myös turhia osumia.")
        laaja = st.checkbox("🌐 Laaja haku (riittää että yksi sana löytyy)",
            help="Oletuksena kaikkien hakusanojen täytyy löytyä samasta asiakirjasta. "
                 "Laajassa haussa yksikin sana riittää.")
        if hakusana:
            st.info(kuvaa_haku(hakusana, liittyva_hakusana, nimivariaatiot, sumea, laaja))

        st.divider()
        teksti_filtteri_es = st.text_input(
            "🔎 Rajaa tekstillä (ES-taso)",
            placeholder="Esim. todistaja, lauttamus...",
            help="Hakee tällä sanalla koko tietokannasta – ei vain ladatuista tuloksista."
        )
        tulosten_maara = st.slider("Tulosten määrä", 10, 500, 100, step=10)

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
                kysely = rakenna_kysely(hakusana, vuosi_alku, vuosi_loppu, indeksi_avain, nimivariaatiot, maakunta_filtteri, liittyva_hakusana, teksti_filtteri_es, aineisto_tarkka, sumea=sumea, laaja=laaja)
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
                st.session_state["viimeisin_kysely"] = kysely

        if "tulokset" in st.session_state and st.session_state["tulokset"]:
            tulokset_raw = st.session_state["tulokset"]
            resp = st.session_state["resp"]
            indeksi_avain_sessio = st.session_state["indeksi_avain"]
            osumia = st.session_state["osumia"]
            tulosten_maara_sessio = st.session_state["tulosten_maara"]

            nayta_kpi_kortit(osumia, tulokset_raw, indeksi_avain_sessio, len(tulokset_raw))
            if "viimeisin_kysely" in st.session_state:
                with st.expander("🛠️ Näytä lähetetty kysely (vianetsintä)"):
                    st.json(st.session_state["viimeisin_kysely"])
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
                jarjestys, aineisto_filtteri, valitut_tagit
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

        st.markdown("### 🔍 Hakutyypit")
        st.markdown("""
Työkalu tukee useita erilaisia hakutapoja. Kirjoita hakusana sivupalkin kenttään.
        """)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Perushaku**")
            st.code("Mäntylä", language=None)
            st.caption("Hakee kaikki maininnat sanasta.")

            st.markdown("**Usean sanan haku**")
            st.code("Juho Mäntylä Jurva", language=None)
            st.caption("Kaikkien sanojen täytyy löytyä samasta asiakirjasta. Asiakirjat, joissa sanat ovat lähekkäin, nousevat kärkeen. Laaja haku -valinnalla yksikin sana riittää.")

            st.markdown("**Fraasihaku**")
            st.code('\"Koivumäen talo\"', language=None)
            st.caption("Sanat täytyy esiintyä tässä järjestyksessä peräkkäin.")

        with col2:
            st.markdown("**OR-haku**")
            st.code("Mäntylä OR Männylä", language=None)
            st.caption("Jompi kumpi sana riittää. Hyödyllinen vanhalle kirjoitusasulle.")

            st.markdown("**Jokerimerkkihaku**")
            st.code("Mänty*", language=None)
            st.caption("Löytää kaikki sanat jotka alkavat 'Mänty' – Mäntylä, Mäntymäki jne.")

            st.markdown("**Nimivariaatiot**")
            st.code("Juho  (+ Nimivariaatiot-checkbox)", language=None)
            st.caption("Hakee automaattisesti: Juho, Johan, Johannes, Juhana, Juhani. Toimii myös usean sanan haussa, esim. Juho Mäntylä.")

            st.markdown("**Salli kirjoitusvirheet**")
            st.code("Mäntylä  (+ Salli kirjoitusvirheet)", language=None)
            st.caption("Löytää myös Mäntyla, Mentylä jne. Ensimmäinen kirjain pidetään samana. Isommat kirjoitusasun muutokset kannattaa hakea jokerimerkillä tai OR-haulla.")

        st.divider()
        st.markdown("### 📚 Aineistot")
        st.markdown("""
| Aineisto | Sisältö | Aikaväli | Kieli |
|---|---|---|---|
| Tuomiokirjat | Yli 7 milj. käräjäkirjasivua | 1600–1900-luvut | Ruotsi/Suomi |
| Voudintilit | Ruotsin vallan verotusaineisto | 1537–1634 | Ruotsi |
| Diplomatarium Fennicum | Keskiaikaiset asiakirjat | ~1100–1540 | Latina/Ruotsi |

⚠️ Huomio: Tuomiokirjat ovat pääosin **ruotsiksi** 1600–1800-luvuilla. Hae ruotsinkielisillä muodoilla:
- Jurva → Jurva (sama), Ilmajoki → Ilmola, Vaasa → Wasa tai Vasa
        """)

        st.divider()
        st.markdown("### 🏷️ Automaattiset tägit")
        st.markdown("""
Jokainen tulos saa automaattisesti tägit jotka kertovat nopeasti asiakirjan sisällöstä:

| Tägi | Merkitys |
|---|---|
| 📅 1800-luku | Asiakirjan vuosisata |
| 📍 Närpiön | Paikkakunta aineiston nimestä |
| 🗺️ Pohjanmaa | Maakunta |
| ⚖️ Oikeudenkäynti | Asiasisältö tekstin perusteella |
| 💰 Kauppa & velka | Asiasisältö tekstin perusteella |
| 🏠 Perintö & omaisuus | Asiasisältö tekstin perusteella |
| 🌾 Maatalous | Asiasisältö tekstin perusteella |
| 🔪 Väkivalta | Asiasisältö tekstin perusteella |
| ⛪ Kirkko & uskonto | Asiasisältö tekstin perusteella |

Tägejä voi käyttää filttereinä – valitse yksi tai useampi "Suodata tägien mukaan" -valikosta.
        """)

        st.divider()
        st.markdown("### 🎛️ Järjestely ja suodatus")
        st.markdown("""
Haun jälkeen tuloksia voi rajata ilman uutta hakua:

- **Järjestys** – Osuvin ensin (oletusarvo), Vanhin ensin, Uusin ensin
- **Aineisto** – Rajaa yhteen arkistoaineistokokonaisuuteen
- **Hae tuloksista** – Kirjoita sana joka täytyy löytyä tekstikatkelmasta
- **Suodata tägien mukaan** – Valitse yksi tai useampi tägi yhdistelmäsuodatukseen
        """)

        st.divider()
        st.markdown("### 💡 Vinkkejä sukututkimukseen")
        st.markdown("""
- **Kokeile ruotsinkielisiä muotoja** – vanha aineisto on ruotsiksi. Esim. *Juho Mäntylä* esiintyy usein muodossa *Johan Mäntylä* tai *Johan Månttylä*
- **Käytä jokerimerkkiä epävarmoissa nimissä** – `Mänty*` löytää kaikki muunnokset
- **Rajaa aikaväli ensin** – jos tiedät henkilön eläneen n. 1780–1830, rajaa siihen
- **Nimivariaatiot käyttöön aina henkilönimillä** – historialliset nimet vaihtelivat paljon
- **Aineistofiltteri** on tehokas – jos tiedät pitäjän, valitse sen tuomiokunnan aineisto suoraan
- **Astia-linkki** vie alkuperäisen digitoidun asiakirjan äärelle – siellä näet käsinkirjoitetun originaalin
        """)

        st.divider()
        st.markdown("### 🔑 API-avain")
        st.markdown("Ota yhteyttä Kansallisarkistoon: **sanna.joska@kansallisarkisto.fi**")


if __name__ == "__main__":
    main()
