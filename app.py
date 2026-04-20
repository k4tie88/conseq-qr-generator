import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- JEDINÁ SPRÁVNÁ FUNKCE PRO IBAN BEZ POMOČEK ---
def vytvor_cisty_iban(cislo_uctu, kod_banky):
    try:
        # 1. Totální očista - odstraní pomlčky, mezery, všechno
        ciste_cislo = "".join(filter(str.isdigit, str(cislo_uctu)))
        cisty_kod = "".join(filter(str.isdigit, str(kod_banky)))
        
        # 2. Doplnění nul PŘED celé číslo (celkem 16 pozic pro účet v IBANu)
        # Tímto zajistíme, že se číslo nesekne a George ho uvidí jako jeden celek
        ucet_pro_iban = ciste_cislo.zfill(16)
        
        # 3. Kontrolní výpočet
        check_str = f"{cisty_kod}{ucet_pro_iban}123500"
        mod = int(check_str) % 97
        check_digits = 98 - mod
        
        return f"CZ{check_digits:02d}{cisty_kod}{ucet_pro_iban}"
    except:
        return None

st.set_page_config(page_title="CONSEQ BEZ POMOČEK", layout="wide")
st.markdown("<h1 style='color: #FF4B4B;'>🏦 CONSEQ - STOP POMLČKÁM</h1>", unsafe_allow_html=True)

# --- EXTRAKCE ---
file = st.file_uploader("Nahraj PDF", type="pdf")
if file and "v_symbol" not in st.session_state:
    with pdfplumber.open(file) as pdf:
        txt = pdf.pages[0].extract_text() or ""
        match = re.search(r'SMLOUVY:\s*(\d+)', txt)
        st.session_state.v_symbol = match.group(1) if match else ""

col1, col2 = st.columns(2)
with col1:
    typ = st.selectbox("Typ platby:", ["Zaměstnanec CZK", "Zaměstnanec EUR", "DIP Var.1", "DIP Var.2"])
    
    # Předdefinované hodnoty UŽ SPOJENÉ bez pomlček
    if "Zaměstnanec" in typ:
        acc_def = "6850057" if "CZK" in typ else "6850081"
        ks_def, ss_def, curr = "", "999", ("CZK" if "CZK" in typ else "EUR")
    else:
        acc_def = "1388083926"
        ks_def = "3552" if "Var.1" in typ else ""
        ss_def, curr = "", "CZK"

    u_acc = st.text_input("Číslo účtu (bez pomlček):", value=acc_def)
    u_bank = st.text_input("Kód banky:", value="2700")
    u_vs = st.text_input("Variabilní symbol:", value=st.session_state.get("v_symbol", ""))
    u_ss = st.text_input("Specifický symbol (IČO):", value=ss_def)
    u_ks = st.text_input("Konstantní symbol:", value=ks_def)
    u_amt = st.number_input(f"Částka {curr}:", min_value=0.0)

with col2:
    if st.button("🚀 GENEROVAT QR KÓD", type="primary"):
        if "Var.1" in typ and not u_ss:
            st.error("Musíte vyplnit IČO!")
        else:
            iban = vytvor_cisty_iban(u_acc, u_bank)
            
            if iban:
                # Sestavení SPD bez pomlček v symbolech
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
                st.image(out)
                st.info(f"IBAN: {iban}")
                st.code(pay)
