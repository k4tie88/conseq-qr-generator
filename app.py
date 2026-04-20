import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK (Opraveno: čistí pomlčky) ---
def czech_to_iban(account_number, bank_code):
    try:
        # Odstraní vše kromě číslic (včetně pomlček, mezer atd.)
        clean_acc = re.sub(r'\D', '', account_number)
        
        if len(clean_acc) > 10:
            prefix, acc = clean_acc[:-10], clean_acc[-10:]
        elif len(clean_acc) > 6:
            prefix, acc = clean_acc[:4], clean_acc[4:]
        else:
            prefix, acc = "0", clean_acc
            
        p_str, a_str = prefix.zfill(6), acc.zfill(10)
        check_str = f"{bank_code}{p_str}{a_str}123500"
        mod = int(check_str) % 97
        check_digits = 98 - mod
        return f"CZ{check_digits:02d}{bank_code}{p_str}{a_str}"
    except Exception as e:
        st.error(f"Chyba při výpočtu IBAN: {e}")
        return None

st.set_page_config(page_title="Conseq QR Generator", layout="wide")
st.title("🏦 Conseq QR Automat")

# --- 2. EXTRAKCE ČÍSLA SMLOUVY ---
def get_vs_from_pdf(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            text = pdf.pages[0].extract_text() or ""
            match = re.search(r'ČÍSLO SMLOUVY:\s*(\d+)', text)
            if match: return match.group(1)
    except:
        pass
    return ""

# --- 3. UI ---
file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

found_vs = ""
if file:
    found_vs = get_vs_from_pdf(file)
    st.success(f"Smlouva {found_vs} načtena.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Parametry platby")
    
    # Výběr režimu - VŠECHNY VARIANTY
    typ = st.selectbox("Typ platby:", [
        "Zaměstnanec - CZK",
        "Zaměstnanec - EUR",
        "Zaměstnavatel - Varianta 1 (Individuální)",
        "Zaměstnavatel - Varianta 2 (Hromadná platba)"
    ])

    # Logika předvyplnění
    if "Zaměstnanec" in typ:
        default_acc = "6850057 / 2700" if "CZK" in typ else "6850081 / 2700"
        default_ks = ""
        default_ss = "999"
        curr = "CZK" if "CZK" in typ else "EUR"
    elif "Varianta 1" in typ:
        default_acc = "1388083926 / 2700"
        default_ks = "3552"
        default_ss = "" # Zde uživatel dopíše IČO
        curr = "CZK"
    else: # Hromadná platba
        default_acc = "1388083926 / 2700"
        default_ks = ""
        default_ss = ""
        curr = "CZK"

    # Pole pro úpravu
    u_acc = st.text_input("Číslo účtu / kód banky:", value=default_acc)
    u_vs = st.text_input("Variabilní symbol (smlouva):", value=found_vs)
    
    # SS pole podle varianty
    if "Varianta 1" in typ:
        u_ss = st.text_input("Specifický symbol (IČO):")
    elif "Hromadná" in typ:
        u_ss = "" # U hromadné se nevyplňuje
        st.caption("U hromadné platby se Specifický symbol nevyplňuje.")
    else:
        u_ss = st.text_input("Specifický symbol:", value=default_ss)
        
    u_ks = st.text_input("Konstantní symbol:", value=default_ks)
    u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=100.0)

with col2:
    st.subheader("Generování")
    if st.button("VYGENEROVAT QR KÓD", type="primary"):
        if not u_acc or "/" not in u_acc:
            st.error("Chybné číslo účtu!")
        elif not u_vs:
            st.error("Chybí Variabilní symbol!")
        else:
            acc_part, bank_part = u_acc.split("/")
            iban = czech_to_iban(acc_part.strip(), bank_part.strip())
            
            if iban:
                # Tvorba platebního řetězce (X- parametry pro CZ standard)
                payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(u_amt)}*CC:{curr}*X-VS:{u_vs}"
                if u_ss: payload += f"*X-SS:{u_ss}"
                if u_ks: payload += f"*X-KS:{u_ks}"
                payload += "*"
                
                qr = segno.make(payload, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=10)
                st.image(out, caption="QR platba Conseq")
                # Zobrazení kódu pro kontrolu (zda tam není pomlčka)
                st.info(f"IBAN v kódu: {iban}")
            else:
                st.error("Nepodařilo se vygenerovat IBAN.")
