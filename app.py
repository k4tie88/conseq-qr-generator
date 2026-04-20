import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK (Maximální čistota) ---
def czech_to_iban(account_number, bank_code):
    try:
        # Odstraní vše, co není číslo, z celého vstupu hned na začátku
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
    except:
        return None

st.set_page_config(page_title="Conseq QR Automat", layout="wide")
st.title("🏦 Conseq QR Automat")

# --- 2. EXTRAKCE VS ---
def get_vs_from_pdf(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            text = pdf.pages[0].extract_text() or ""
            match = re.search(r'ČÍSLO SMLOUVY:\s*(\d+)', text)
            return match.group(1) if match else ""
    except:
        return ""

# --- 3. SESSION STATE (Paměť) ---
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

    # Výchozí hodnoty podle výběru
    if "Zaměstnanec" in typ:
        raw_acc = "6850057/2700" if "CZK" in typ else "6850081/2700"
        ks_def, ss_def, curr = "", "999", ("CZK" if "CZK" in typ else "EUR")
    elif "Varianta 1" in typ:
        raw_acc = "1388083926/2700"
        ks_def, ss_def, curr = "3552", "", "CZK"
    else: # Hromadná
        raw_acc = "1388083926/2700"
        ks_def, ss_def, curr = "", "", "CZK"

    # Vizuální očista políčka (vymaže pomlčku i mezeru)
    clean_acc_for_ui = raw_acc.replace("-", "").replace(" ", "")
    current_vs = st.session_state.get("pdf_vs", "")

    # FORMULÁŘ
    u_acc = st.text_input("Číslo účtu / kód banky:", value=clean_acc_for_ui)
    u_vs = st.text_input("Variabilní symbol (smlouva):", value=current_vs)
    
    if "Varianta 1" in typ:
        u_ss = st.text_input("Specifický symbol (IČO):", key="ico_field")
    elif "Hromadná" in typ:
        u_ss = ""
        st.info("SS se u hromadné platby nevyplňuje.")
    else:
        u_ss = st.text_input("Specifický symbol:", value=ss_def)

    u_ks = st.text_input("Konstantní symbol:", value=ks_def)
    u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=100.0)

with col2:
    st.subheader("Generování")
    if st.button("VYGENEROVAT QR KÓD", type="primary"):
        # Validace
        if "Varianta 1" in typ and not u_ss.strip():
            st.error("❌ Musíte zadat IČO!")
        elif not u_vs:
            st.error("❌ Chybí Variabilní symbol!")
        elif "/" not in u_acc:
            st.error("❌ Účet musí být ve formátu cislo/banka")
        else:
            try:
                # KRITICKÝ BOD: Rozdělení a odstranění pomlček i těsně před generováním
                acc_clean = u_acc.split("/")[0].replace("-", "").replace(" ", "").strip()
                bank_clean = u_acc.split("/")[1].strip()
                
                iban = czech_to_iban(acc_clean, bank_clean)
                
                if iban:
                    # Sestavení řetězce (AM musí mít 2 desetinná místa)
                    payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(u_amt)}*CC:{curr}*X-VS:{u_vs}"
                    if u_ss: payload += f"*X-SS:{u_ss.strip()}"
                    if u_ks: payload += f"*X-KS:{u_ks.strip()}"
                    payload += "*"
                    
                    qr = segno.make(payload, error='m')
                    out = BytesIO()
                    qr.save(out, kind='png', scale=10)
                    st.image(out, caption=f"VS: {u_vs}")
                    st.success(f"Vygenerováno pro účet: {iban}")
                else:
                    st.error("Selhal výpočet IBAN.")
            except Exception as e:
                st.error(f"Chyba: {e}")
