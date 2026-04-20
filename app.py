import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# 1. FUNKCE, KTERÁ S JISTOTOU ODSTRANÍ POMOČKY
def bez_pomlcek(text):
    if not text: return ""
    return "".join(filter(str.isdigit, str(text)))

# 2. IBAN PŘEVODNÍK
def vytvor_iban(acc, bank):
    try:
        a = bez_pomlcek(acc)
        b = bez_pomlcek(bank)
        if len(a) > 10: prefix, acc_num = a[:-10], a[-10:]
        elif len(a) > 6: prefix, acc_num = a[:4], a[4:]
        else: prefix, acc_num = "0", a
        p_str, a_str = prefix.zfill(6), acc_num.zfill(10)
        check = f"{b}{p_str}{a_str}123500"
        mod = int(check) % 97
        return f"CZ{98 - mod:02d}{b}{p_str}{a_str}"
    except: return None

st.set_page_config(page_title="FINAL FIX", layout="wide")
st.markdown("<h1 style='color: #FF4B4B;'>🏦 CONSEQ FIX (VERZE 2.0)</h1>", unsafe_allow_html=True)

# 3. EXTRAKCE SMLOUVY
file = st.file_uploader("Nahraj PDF", type="pdf")
if file and "v_symbol" not in st.session_state:
    with pdfplumber.open(file) as pdf:
        txt = pdf.pages[0].extract_text() or ""
        match = re.search(r'SMLOUVY:\s*(\d+)', txt)
        st.session_state.v_symbol = match.group(1) if match else ""

# 4. ROZHRANÍ
col1, col2 = st.columns(2)
with col1:
    typ = st.selectbox("Typ:", ["Zaměstnanec CZK", "Zaměstnanec EUR", "DIP Var.1", "DIP Var.2"])
    
    # Nastavení účtů BEZ POMOČEK přímo v textu
    if "Zaměstnanec" in typ:
        acc_def = "6850057" if "CZK" in typ else "6850081"
        ks_def, ss_def, curr = "", "999", ("CZK" if "CZK" in typ else "EUR")
    else:
        acc_def = "1388083926"
        ks_def = "3552" if "Var.1" in typ else ""
        ss_def, curr = "", "CZK"

    u_acc = st.text_input("Číslo účtu (BEZ POMLČKY):", value=acc_def)
    u_bank = st.text_input("Kód banky:", value="2700")
    u_vs = st.text_input("Var. symbol:", value=st.session_state.get("v_symbol", ""))
    u_ss = st.text_input("Spec. symbol (IČO u Var.1):", value=ss_def)
    u_ks = st.text_input("Konst. symbol:", value=ks_def)
    u_amt = st.number_input(f"Částka {curr}:", min_value=0.0)

with col2:
    # Tlačítko má jiný text, abys poznala, že běží nová verze
    if st.button("🚀 GENEROVAT ČISTÝ QR KÓD", type="primary"):
        if "Var.1" in typ and not u_ss:
            st.error("Doplň IČO!")
        else:
            # TOTÁLNÍ ČIŠTĚNÍ PŘED GENEROVÁNÍM
            c_acc = bez_pomlcek(u_acc)
            c_bank = bez_pomlcek(u_bank)
            c_vs = bez_pomlcek(u_vs)
            c_ss = bez_pomlcek(u_ss)
            c_ks = bez_pomlcek(u_ks)
            
            iban = vytvor_iban(c_acc, c_bank)
            if iban:
                # Sestavení SPD řetězce - Všechny hodnoty prohnány filtrem bez_pomlcek
                pay = f"SPD*1.0*ACC:{iban}*AM:{u_amt:.2f}*CC:{curr}*X-VS:{c_vs}"
                if c_ss: pay += f"*X-SS:{c_ss}"
                if c_ks: pay += f"*X-KS:{c_ks}"
                pay += "*"
                
                qr = segno.make(pay, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=10)
                st.image(out)
                st.code(pay) # TADY UVIDÍŠ SLOŽENÍ KÓDU - HLEDEJ POMOČKU
                st.write(f"IBAN: {iban}")
