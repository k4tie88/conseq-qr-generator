import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK (Čistí pomlčky a vše nepotřebné) ---
def czech_to_iban(account_number, bank_code):
    try:
        clean_acc = re.sub(r'\D', '', account_number)
        if len(clean_acc) > 10:
            prefix, acc = clean_acc[:-10], clean_acc[-10:]
        elif len(clean_acc) > 6: prefix, acc = clean_acc[:4], clean_acc[4:]
        else: prefix, acc = "0", clean_acc
        p_str, a_str = prefix.zfill(6), acc.zfill(10)
        check_str = f"{bank_code}{p_str}{a_str}123500"
        mod = int(check_str) % 97
        check_digits = 98 - mod
        return f"CZ{check_digits:02d}{bank_code}{p_str}{a_str}"
    except: return None

st.set_page_config(page_title="Conseq QR Automat", layout="wide")
st.title("🏦 Conseq QR Automat")

# --- 2. EXTRAKCE VS ---
def get_vs_from_pdf(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            text = pdf.pages[0].extract_text() or ""
            match = re.search(r'ČÍSLO SMLOUVY:\s*(\d+)', text)
            return match.group(1) if match else ""
    except: return ""

# --- 3. LOGIKA PAMĚTI (Session State) ---
file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file and "pdf_vs" not in st.session_state:
    st.session_state.pdf_vs = get_vs_from_pdf(file)

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Parametry platby")
    
    typ = st.selectbox("Typ platby:", [
        "Zaměstnanec - CZK",
        "Zaměstnanec - EUR",
        "Zaměstnavatel - Varianta 1 (Individuální)",
        "Zaměstnavatel - Varianta 2 (Hromadná platba)"
    ])

    # Definice výchozích hodnot pro symboly a účty
    if "Zaměstnanec" in typ:
        acc_raw = "6850057 / 2700" if "CZK" in typ else "6850081 / 2700"
        ks_def, ss_def, curr = "", "999", ("CZK" if "CZK" in typ else "EUR")
    elif "Varianta 1" in typ:
        acc_raw = "1388083926 / 2700"
        ks_def, ss_def, curr = "3552", "", "CZK"
    else: # Hromadná
        acc_raw = "1388083926 / 2700"
        ks_def, ss_def, curr = "", "", "CZK"

    # ČIŠTĚNÍ ÚČTU (Pomlčky pryč)
    u_acc_clean = acc_raw.replace("-", "").replace(" ", "")
    
    # NAČTENÍ HODNOT (Z paměti nebo z výchozího nastavení)
    current_vs = st.session_state.get("pdf_vs", "")

    # FORMULÁŘ - Každé pole má unikátní klíč, aby se netlouklo
    final_acc = st.text_input("Číslo účtu / kód banky:", value=u_acc_clean)
    final_vs = st.text_input("Variabilní symbol (smlouva):", value=current_vs)
    
    if "Varianta 1" in typ:
        final_ss = st.text_input("Specifický symbol (IČO):", key="ss_ico")
    elif "Hromadná" in typ:
        final_ss = ""
        st.info("SS se u hromadné platby nevyplňuje.")
    else:
        final_ss = st.text_input("Specifický symbol:", value=ss_def)

    # KONSTANTNÍ SYMBOL - Teď už se neztratí
    final_ks = st.text_input("Konstantní symbol:", value=ks_def)
    final_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=100.0)

with col2:
    st.subheader("Generování")
    if st.button("VYGENEROVAT QR KÓD", type="primary"):
        # Kontrola IČO u Var 1
        if "Varianta 1" in typ and not final_ss.strip():
            st.error("❌ Musíte zadat IČO!")
        elif not final_vs:
            st.error("❌ Chybí Variabilní symbol!")
        elif not final_acc or "/" not in final_acc:
            st.error("❌ Špatný formát účtu!")
        else:
            try:
                a_part, b_part = final_acc.split("/")
                iban = czech_to_iban(a_part.strip(), b_part.strip())
                
                if iban:
                    # Sestavení platebního řetězce
                    payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(final_amt)}*CC:{curr}*X-VS:{final_vs}"
                    if final_ss: payload += f"*X-SS:{final_ss}"
                    if final_ks: payload += f"*X-KS:{final_ks}"
                    payload += "*"
                    
                    qr = segno.make(payload, error='m')
                    out = BytesIO()
                    qr.save(out, kind='png', scale=10)
                    st.image(out, caption=f"QR Platba - VS: {final_vs}")
                    st.success(f"Účet v QR: {iban}")
                else: st.error("IBAN se nepodařilo vytvořit.")
            except: st.error("Chyba v čísle účtu.")

if file:
    if st.sidebar.button("Resetovat aplikaci (nové PDF)"):
        st.session_state.clear()
        st.rerun()
