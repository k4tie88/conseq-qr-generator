import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- OPRAVENÝ IBAN PŘEVODNÍK PRO ÚČTY S PŘEDČÍSLÍM ---
def vytvor_iban_conseq(acc_input, bank_code):
    try:
        # 1. Rozdělení na předčíslí a hlavní číslo (podle pomlčky)
        if "-" in acc_input:
            prefix_raw, main_raw = acc_input.split("-")
        else:
            prefix_raw, main_raw = "0", acc_input
            
        # 2. Očištění od všeho kromě čísel
        prefix = "".join(filter(str.isdigit, prefix_raw)).zfill(6)
        main = "".join(filter(str.isdigit, main_raw)).zfill(10)
        bank = "".join(filter(str.isdigit, bank_code))
        
        # 3. Výpočet kontrolního součtu
        check_str = f"{bank}{prefix}{main}123500"
        mod = int(check_str) % 97
        check_digits = 98 - mod
        
        return f"CZ{check_digits:02d}{bank}{prefix}{main}"
    except:
        return None

st.set_page_config(page_title="CONSEQ FIX 3.0", layout="wide")
st.markdown("<h1 style='color: #FF4B4B;'>🏦 CONSEQ FIX (VERZE 3.0)</h1>", unsafe_allow_html=True)

# --- EXTRAKCE ---
file = st.file_uploader("Nahraj PDF", type="pdf")
if file and "v_symbol" not in st.session_state:
    with pdfplumber.open(file) as pdf:
        txt = pdf.pages[0].extract_text() or ""
        match = re.search(r'SMLOUVY:\s*(\d+)', txt)
        st.session_state.v_symbol = match.group(1) if match else ""

col1, col2 = st.columns(2)
with col1:
    typ = st.selectbox("Typ:", ["Zaměstnanec CZK", "Zaměstnanec EUR", "DIP Var.1", "DIP Var.2"])
    
    # Tady necháme pomlčku jen pro logiku rozdělení, ale v UI ji uživatel uvidí
    if "Zaměstnanec" in typ:
        acc_def = "685-0057" if "CZK" in typ else "685-0081"
        ks_def, ss_def, curr = "", "999", ("CZK" if "CZK" in typ else "EUR")
    else:
        acc_def = "1388083926" # Tady předčíslí není
        ks_def = "3552" if "Var.1" in typ else ""
        ss_def, curr = "", "CZK"

    u_acc = st.text_input("Číslo účtu (včetně pomlčky, pokud ji má):", value=acc_def)
    u_bank = st.text_input("Kód banky:", value="2700")
    u_vs = st.text_input("Var. symbol:", value=st.session_state.get("v_symbol", ""))
    u_ss = st.text_input("Spec. symbol (IČO u Var.1):", value=ss_def)
    u_ks = st.text_input("Konst. symbol:", value=ks_def)
    u_amt = st.number_input(f"Částka {curr}:", min_value=0.0)

with col2:
    if st.button("🚀 GENEROVAT QR KÓD", type="primary"):
        if "Var.1" in typ and not u_ss:
            st.error("Doplň IČO!")
        else:
            # Voláme novou funkci
            iban = vytvor_iban_conseq(u_acc, u_bank)
            
            if iban:
                # Očištění symbolů pro řetězec
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
                st.write(f"Vypočtený IBAN: {iban}")
                st.code(pay)
