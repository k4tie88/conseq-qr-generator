import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. FUNKCE PRO IBAN (Prověřená verze bez pomlček) ---
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

st.set_page_config(page_title="QR Generátor", layout="wide")
st.title("🏦 QR generátor plateb")

# --- 2. NAČÍTÁNÍ PDF A AKTUALIZACE DAT ---
file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    # Pokud je název souboru jiný než minule, okamžitě aktualizujeme VS
    if "last_file" not in st.session_state or st.session_state.last_file != file.name:
        st.session_state.last_file = file.name
        with pdfplumber.open(file) as pdf:
            txt = ""
            for page in pdf.pages[:2]: # Prohledá první 2 strany
                txt += (page.extract_text() or "")
            
            # Hledání čísla smlouvy
            match = re.search(r'SMLOUVY:\s*(\d+)', txt)
            if match:
                st.session_state.v_symbol = match.group(1)
            else:
                st.session_state.v_symbol = ""

col1, col2 = st.columns(2)
with col1:
    typ = st.selectbox("Typ platby:", [
        "Zaměstnanec - CZK", 
        "Zaměstnanec - EUR", 
        "Zaměstnavatel - Varianta 1 (Individuální DIP)", 
        "Zaměstnavatel - Varianta 2 (Hromadná)"
    ])
    
    # Nastavení výchozích hodnot polí
    if "Zaměstnanec" in typ:
        acc_def = "6850057" if "CZK" in typ else "6850081"
        ks_def, ss_def, curr = "", "999", ("CZK" if "CZK" in typ else "EUR")
    else:
        acc_def = "1388083926"
        ks_def = "3552" if "Varianta 1" in typ else ""
        ss_def, curr = "", "CZK"

    # Pole formuláře
    u_acc = st.text_input("Číslo účtu:", value=acc_def)
    u_bank = st.text_input("Kód banky:", value="2700")
    
    # Variabilní symbol se bere přímo ze session_state (vždy čerstvý z PDF)
    u_vs = st.text_input("Variabilní symbol (č. smlouvy):", value=st.session_state.get("v_symbol", ""))
    
    u_ss = st.text_input("Specifický symbol (IČO):", value=ss_def)
    u_ks = st.text_input("Konstantní symbol:", value=ks_def)
    u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0)

with col2:
    st.subheader("Výsledek")
    if st.button("Generovat QR kód", type="primary"):
        # Jediná povinná kontrola zůstává IČO u Var. 1 a prázdný VS
        if "Varianta 1" in typ and not u_ss.strip():
            st.error("❌ Pro Variantu 1 vyplňte IČO do Specifického symbolu!")
        elif not u_vs:
            st.error("❌ Chybí Variabilní symbol (číslo smlouvy)!")
        else:
            iban = vytvor_cisty_iban(u_acc, u_bank)
            if iban:
                # Očista od případných nechtěných znaků
                c_vs = "".join(filter(str.isdigit, u_vs))
                c_ss = "".join(filter(str.isdigit, u_ss))
                c_ks = "".join(filter(str.isdigit, u_ks))
                
                pay = f"SPD*1.0*ACC:{iban}*AM:{u_amt:.2f}*CC:{curr}*X-VS:{c_vs}"
                if c_ss: pay += f"*X-SS:{c_ss}"
                if c_ks: pay += f"*X-KS:{c_ks}"
                pay += "*"
                
                qr = segno.make(pay, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=10)
                st.image(out, caption=f"QR platba - VS {c_vs}")
                st.code(pay)
