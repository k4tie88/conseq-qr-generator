import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. FUNKCE PRO PŘEVOD NA IBAN (Nezbytné pro QR platbu) ---
def vytvor_iban_dynamicky(account_str):
    try:
        # Odstraníme vše kromě číslic a lomítka
        clean = re.sub(r'[^\d/]', '', account_str)
        if "/" not in clean: return None
        
        number_part, bank_code = clean.split("/")
        
        # Ošetření předčíslí a čísla (Conseq mívá 10místná čísla bez předčíslí)
        if len(number_part) > 10:
            prefix = number_part[:-10]
            number = number_part[-10:]
        else:
            prefix = "0"
            number = number_part
            
        prefix = prefix.zfill(6)
        number = number.zfill(10)
        bank_code = bank_code.zfill(4)
        
        # Výpočet kontrolního součtu podle standardu CZ IBAN
        check_str = f"{bank_code}{prefix}{number}123500"
        remainder = int(check_str) % 97
        check_digits = str(98 - remainder).zfill(2)
        
        return f"CZ{check_digits}{bank_code}{prefix}{number}"
    except:
        return None

# --- 2. STREAMLIT UI ---
st.set_page_config(page_title="Conseq QR Generátor v1.0", layout="wide")
st.title("🏦 Conseq QR Generátor - Varianta 1 (Standard)")

file = st.file_uploader("Nahrajte PDF smlouvu (Varianta 1)", type="pdf")

if file:
    if "pdf_raw" not in st.session_state or st.session_state.last_file != file.name:
        with pdfplumber.open(file) as pdf:
            txt = ""
            for page in pdf.pages:
                txt += page.extract_text() + "\n"
            st.session_state.pdf_raw = txt
            st.session_state.last_file = file.name

if "pdf_raw" in st.session_state:
    raw = st.session_state.pdf_raw
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Parametry platby")
        curr = st.selectbox("Vyberte měnu:", ["CZK", "EUR", "USD"])
        
        # --- LOGIKA VYHLEDÁVÁNÍ VS (Číslo smlouvy) ---
        # Hledá "Číslo smlouvy" (i s mezerami), pak bere číslice a mezery, které hned vyčistí
        found_vs = ""
        vs_match = re.search(r'Číslo\s+smlouvy\s*[:\s]*([\d\s]+)', raw, re.IGNORECASE)
        if vs_match:
            found_vs = re.sub(r'\s+', '', vs_match.group(1))[:10]

        # --- LOGIKA VYHLEDÁVÁNÍ ÚČTU ---
        # Hledá "Číslo účtu v [Měna]", vysaje vše až k lomítku a kódu banky
        found_acc = ""
        acc_pattern = rf'Číslo\s+účtu\s+v\s+{curr}\s*[:\s]*([\d\s\/-]+)'
        acc_match = re.search(acc_pattern, raw, re.IGNORECASE)
        if acc_match:
            # Vyčistíme mezery a pomlčky z čísla účtu
            found_acc = re.sub(r'[\s-]', '', acc_match.group(1).strip())

        # --- FORMULÁŘ ---
        u_acc = st.text_input("Číslo účtu (vysáto z PDF):", value=found_acc)
        u_vs = st.text_input("Variabilní symbol (Číslo smlouvy):", value=found_vs)
        u_ss = st.text_input("Specifický symbol:", value="999")
        u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=500.0)

    with col2:
        st.subheader("QR kód pro banku")
        if u_acc and u_vs:
            iban = vytvor_iban_dynamicky(u_acc)
            if iban:
                # Sestavení standardu SPD (Short Payment Descriptor)
                pay_str = f"SPD*1.0*ACC:{iban}*AM:{u_amt:.2f}*CC:{curr}*X-VS:{u_vs}*X-SS:{u_ss}*"
                
                qr = segno.make(pay_str, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=10)
                
                st.image(out, caption=f"Cílový účet: {u_acc} ({curr})")
                st.success(f"Vypočítaný IBAN: {iban}")
                
                with st.expander("Technický detail kódu"):
                    st.code(pay_str)
            else:
                st.error("❌ Formát účtu není správný (chybí lomítko nebo kód banky).")
        else:
            st.info("Nahrajte PDF smlouvu pro automatické vyplnění údajů.")
