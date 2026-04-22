import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. FUNKCE PRO IBAN (Verze 4.0 - prověřená bez pomlček) ---
def vytvor_cisty_iban(cislo_uctu, kod_banky):
    try:
        ciste_cislo = "".join(filter(str.isdigit, str(cislo_uctu)))
        cisty_kod = "".join(filter(str.isdigit, str(kod_banky)))
        ucet_pro_iban = ciste_cislo.zfill(16)
        check_str = f"{cisty_kod}{ucet_pro_iban}123500"
        mod = int(check_str) % 97
        check_digits = 98 - mod
        return f"CZ{check_digits:02d}{cisty_kod}{ucet_pro_iban}"
    except:
        return None

# --- 2. NASTAVENÍ STRÁNKY ---
st.set_page_config(page_title="QR Generátor plateb", layout="wide")
st.title("🏦 QR generátor plateb")

# --- TADY JE TEN SIDEBAR (RESET) ---
with st.sidebar:
    st.header("Nastavení")
    if st.button("Nahrát jinou smlouvu (Reset)"):
        st.session_state.clear()
        st.rerun()

# --- 3. NAČÍTÁNÍ PDF A AKTUALIZACE DAT ---
file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    # Pokud je název souboru jiný, přepíšeme paměť
    if "last_file" not in st.session_state or st.session_state.last_file != file.name:
        st.session_state.last_file = file.name
        with pdfplumber.open(file) as pdf:
            txt = ""
            for page in pdf.pages[:2]:
                txt += (page.extract_text() or "")
            
            # 1. Hledání VS (Smlouva)
            vs_match = re.search(r'SMLOUVY:\s*(\d+)', txt)
            st.session_state.v_symbol = vs_match.group(1) if vs_match else ""
            
            # 2. Hledání KS (pro hromadnou platbu)
            ks_match = re.search(r'[Ss]ymbol[:\s]+(\d{4})', txt)
            st.session_state.ks_hromadna = ks_match.group(1) if ks_match else "3558"

# --- 4. FORMULÁŘ ---
col1, col2 = st.columns(2)

with col1:
    typ = st.selectbox("Typ platby:", [
        "Zaměstnanec - CZK", 
        "Zaměstnanec - EUR", 
        "Zaměstnavatel - Varianta 1 (Individuální DIP)", 
        "Zaměstnavatel - Varianta 2 (Hromadná)"
    ])
    
    # Dynamické nastavení výchozích hodnot
    if "Zaměstnanec" in typ:
        acc_def = "6850057" if "CZK" in typ else "6850081"
        ks_def, ss_def, curr = "", "999", ("CZK" if "CZK" in typ else "EUR")
    elif "Varianta 1" in typ:
        acc_def = "1388083926"
        ks_def, ss_def, curr = "3552", "", "CZK"
    else: # Varianta 2 - Hromadná
        acc_def = "1388083926"
        ks_def = st.session_state.get("ks_hromadna", "3558")
        ss_def, curr = "", "CZK"

    # Vstupní pole
    u_acc = st.text_input("Číslo účtu:", value=acc_def)
    u_bank = st.text_input("Kód banky:", value="2700")
    u_vs = st.text_input("Variabilní symbol (č.
