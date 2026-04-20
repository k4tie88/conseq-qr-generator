import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. FUNKCE PRO ČIŠTĚNÍ (Všechno kromě čísel jde pryč) ---
def total_clean(text):
    if not text:
        return ""
    # Odstraní pomlčky, mezery, tečky, písmena... prostě všechno kromě 0-9
    return re.sub(r'\D', '', str(text))

# --- 2. IBAN PŘEVODNÍK ---
def czech_to_iban(account_number, bank_code):
    try:
        # Tady probíhá ta hlavní očista
        acc = total_clean(account_number)
        bank = total_clean(bank_code)
        
        if len(acc) > 10:
            prefix, main_acc = acc[:-10], acc[-10:]
        elif len(acc) > 6:
            prefix, main_acc = acc[:4], acc[4:]
        else:
            prefix, main_acc = "0", acc
            
        p_str, a_str = prefix.zfill(6), main_acc.zfill(10)
        check_str = f"{bank}{p_str}{a_str}123500"
        mod = int(check_str) % 97
        check_digits = 98 - mod
        return f"CZ{check_digits:02d}{bank}{p_str}{a_str}"
    except:
        return None

st.set_page_config(page_title="Conseq QR Fix", layout="wide")
st.title("🏦 Conseq QR Automat (VERZE BEZ POMLČEK)")

# --- 3. NAČÍTÁNÍ PDF ---
file = st.file_uploader("Nahrajte PDF", type="pdf")

if file and "pdf_vs" not in st.session_state:
    try:
        with pdfplumber.open(file) as pdf:
            txt = pdf.pages[0].extract_text() or ""
            m = re.search(r'ČÍSLO SMLOUVY:\s*(\d+)', txt)
            st.session_state.pdf_vs = m.group(1) if m else ""
    except:
        st.session_state.pdf_vs = ""

# --- 4. FORMULÁŘ ---
col1, col2 = st.columns(2)

with col1:
    typ = st.selectbox("Vyberte typ platby:", [
        "Zaměstnanec - CZK", "Zaměstnanec - EUR", 
        "Zaměstnavatel - Varianta 1 (Individuální)", 
        "Zaměstnavatel - Varianta 2 (Hromadná)"
    ])

    # Definice účtů NATVRDO BEZ POMLČEK už v základu
    if "Zaměstnanec" in typ:
        base_acc = "6850057" if "CZK" in typ else "6850081"
        ks_val, ss_val, curr = "", "999", ("CZK" if "CZK" in typ else "EUR")
    else:
        base_acc = "1388083926" # Varianta 1 i 2 má stejný účet
        ks_val = "3552" if "Varianta 1" in typ else ""
        ss_val = ""
        curr = "CZK"

    # Políčka pro uživatele
    u_acc_num = st.text_input("Číslo účtu (bez kódu banky):", value=base_acc)
    u_bank_code = st.text_input("Kód banky:", value="2700")
    u_vs = st.text_input("Variabilní symbol (smlouva):", value=st.session_state.get("pdf_vs", ""))
    
    if "Varianta 1" in typ:
        u_ss = st.text_input("Specifický symbol (IČO):", key="ss_input")
    else:
        u_ss = st.text_input("Specifický symbol:", value=ss_val)
        
    u_ks = st.text_input("Konstantní symbol:", value=ks_val)
    u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0)

with col2:
    if st.button("GENEROVAT QR KÓD", type="primary"):
        # POSLEDNÍ KONTROLA PŘED VYTVOŘENÍM
        if "Varianta 1" in typ and not u_ss:
            st.error("Chybí IČO!")
        elif not u_vs:
            st.error("Chybí číslo smlouvy!")
        else:
            # Tady probíhá ta magická očista těsně před generováním
            final_acc = total_clean(u_acc_num)
            final_bank = total_clean(u_bank_code)
            
            iban = czech_to_iban(final_acc, final_bank)
            
            if iban:
                # Sestavení platebního řetězce
                payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(u_amt)}*CC:{curr}*X-VS:{total_clean(u_vs)}"
                if u_ss: payload += f"*X-SS:{total_clean(u_ss)}"
                if u_ks: payload += f"*X-KS:{total_clean(u_ks)}"
                payload += "*"
                
                qr = segno.make(payload, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=10)
                
                st.image(out)
                st.info(f"Účet v QR kódu: {iban}") # Tady uvidíš, že tam pomlčka fakt není
                st.success("QR kód byl vygenerován čistě bez pomlček.")

# Reset
if file:
    if st.button("Nahrát jinou smlouvu"):
        st.session_state.clear()
        st.rerun()
