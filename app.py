import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. FUNKCE PRO IBAN ---
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
st.set_page_config(page_title="QR Generátor", layout="wide")
st.title("🏦 QR generátor plateb")

# --- 3. SIDEBAR S RESETEM ---
with st.sidebar:
    st.header("Nastavení")
    if st.button("Vymazat paměť a nahrát nové PDF"):
        st.session_state.clear()
        st.rerun()

# --- 4. NAČÍTÁNÍ PDF ---
file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    if "last_file" not in st.session_state or st.session_state.last_file != file.name:
        st.session_state.last_file = file.name
        with pdfplumber.open(file) as pdf:
            txt = ""
            for page in pdf.pages[:2]:
                txt += (page.extract_text() or "")
            
            # Hledání Variabilního symbolu
            vs_match = re.search(r'SMLOUVY:\s*(\d+)', txt)
            st.session_state.v_symbol = vs_match.group(1) if vs_match else ""
            
            # Hledání Konstantního symbolu (pro Var 2)
            ks_match = re.search(r'[Ss]ymbol[:\s]+(\d{4})', txt)
            st.session_state.ks_hromadna = ks_match.group(1) if ks_match else "3558"

# --- 5. FORMULÁŘ ---
col1, col2 = st.columns(2)

with col1:
    typ = st.selectbox("Typ platby:", [
        "Zaměstnanec - CZK", 
        "Zaměstnanec - EUR", 
        "Zaměstnavatel - Varianta 1 (Individuální DIP)", 
        "Zaměstnavatel - Varianta 2 (Hromadná)"
    ])
    
    if "Zaměstnanec" in typ:
        acc_def = "6850057" if "CZK" in typ else "6850081"
        ks_def, ss_def, curr = "", "999", ("CZK" if "CZK" in typ else "EUR")
    elif "Varianta 1" in typ:
        acc_def = "1388083926"
        ks_def, ss_def, curr = "3552", "", "CZK"
    else: # Varianta 2
        acc_def = "1388083926"
        ks_def = st.session_state.get("ks_hromadna", "3558")
        ss_def, curr = "", "CZK"

    u_acc = st.text_input("Číslo účtu:", value=acc_def)
    u_bank = st.text_input("Kód banky:", value="2700")
    
    # Tady byla ta chyba (SyntaxError) - teď je to opravené:
    u_vs = st.text_input("Variabilní symbol (č. smlouvy):", value=st.session_state.get("v_symbol", ""))
    
    u_ss = st.text_input("Specifický symbol (IČO):", value=ss_def)
    u_ks = st.text_input("Konstantní symbol:", value=ks_def)
    u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=100.0)

with col2:
    st.subheader("Výsledek")
    if st.button("Generovat QR kód", type="primary"):
        if "Varianta 1" in typ and not u_ss.strip():
            st.error("❌ Pro Variantu 1 vyplňte IČO!")
        elif not u_vs:
            st.error("❌ Chybí Variabilní symbol!")
        else:
            iban = vytvor_cisty_iban(u_acc, u_bank)
            if iban:
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
                st.success("Hotovo!")
                st.code(pay)
