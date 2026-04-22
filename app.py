import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK (Osvědčená verze bez pomlček) ---
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

st.set_page_config(page_title="QR Generátor plateb", layout="wide")
st.title("🏦 QR generátor plateb")

# --- 2. NAČÍTÁNÍ A DETEKCE ---
file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    # Kontrola změny souboru pro okamžitý refresh políček
    if "current_file_name" not in st.session_state or st.session_state.current_file_name != file.name:
        st.session_state.current_file_name = file.name
        
        with pdfplumber.open(file) as pdf:
            txt = ""
            for page in pdf.pages[:2]: # Prohledáme první dvě strany
                txt += (page.extract_text() or "")
            
            # Hledání VS
            match = re.search(r'SMLOUVY:\s*(\d+)', txt)
            st.session_state.v_symbol = match.group(1) if match else ""
            
            # Robustnější detekce DIP (hledá klíčová slova bez ohledu na velikost písmen)
            dip_keywords = ["dip", "dlouhodobý", "dlouhodobého", "investiční produkt"]
            st.session_state.is_dip = any(kw in txt.lower() for kw in dip_keywords)

col1, col2 = st.columns(2)
with col1:
    typ = st.selectbox("Typ platby:", [
        "Zaměstnanec - CZK", 
        "Zaměstnanec - EUR", 
        "Zaměstnavatel - Varianta 1 (Individuální DIP)", 
        "Zaměstnavatel - Varianta 2 (Hromadná)"
    ])
    
    # Přednastavení hodnot
    if "Zaměstnanec" in typ:
        acc_def = "6850057" if "CZK" in typ else "6850081"
        ks_def, ss_def, curr = "", "999", ("CZK" if "CZK" in typ else "EUR")
    else:
        acc_def = "1388083926"
        ks_def = "3552" if "Varianta 1" in typ else ""
        ss_def, curr = "", "CZK"

    # Formulář
    u_acc = st.text_input("Číslo účtu:", value=acc_def)
    u_bank = st.text_input("Kód banky:", value="2700")
    # VS se bere ze session_state, který jsme nahoře aktualizovali
    u_vs = st.text_input("Variabilní symbol (č. smlouvy):", value=st.session_state.get("v_symbol", ""))
    u_ss = st.text_input("Specifický symbol (IČO):", value=ss_def)
    u_ks = st.text_input("Konstantní symbol:", value=ks_def)
    u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0)

with col2:
    st.subheader("Výsledek")
    if st.button("Generovat QR kód", type="primary"):
        error = False
        
        # Logika chybových hlášení
        if "Varianta 1" in typ:
            if not u_ss.strip():
                st.error("❌ Pro DIP platbu zaměstnavatelem musíte vyplnit IČO do Specifického symbolu!")
                error = True
            
            # Pokud v PDF není ani zmínka o DIPu, vyhodíme varování
            if not st.session_state.get("is_dip", False):
                st.warning("⚠️ Pozor: V této smlouvě nebyla nalezena zmínka o DIP. Opravdu jde o DIP smlouvu?")
                # Zde dáváme jen warning, abychom uživatele úplně nezablokovali, kdyby PDF čtečka selhala
        
        if not u_vs:
            st.error("❌ Chybí Variabilní symbol (číslo smlouvy)!")
            error = True

        if not error:
            iban = vytvor_cisty_iban(u_acc, u_bank)
