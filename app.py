import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- IBAN PŘEVODNÍK ---
def vytvor_iban_dynamicky(account_str):
    try:
        clean = re.sub(r'[^\d/]', '', account_str)
        if "/" not in clean: return None
        num, bank = clean.split("/")
        prefix, number = (num[:-10], num[-10:]) if len(num) > 10 else ("0", num)
        prefix, number, bank = prefix.zfill(6), number.zfill(10), bank.zfill(4)
        check_str = f"{bank}{prefix}{number}123500"
        rem = int(check_str) % 97
        return f"CZ{str(98 - rem).zfill(2)}{bank}{prefix}{number}"
    except: return None

st.set_page_config(page_title="Conseq QR Final Fix", layout="wide")
st.title("🏦 Conseq QR - Varianta 1 (EUR & CZK Fix)")

file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    with pdfplumber.open(file) as pdf:
        last_page_text = pdf.pages[-1].extract_text() or ""
        full_text = "\n".join([p.extract_text() or "" for p in pdf.pages])

    # --- VS (Číslo smlouvy) ---
    vs_matches = re.findall(r'41\d{8}', full_text)
    found_vs = vs_matches[0] if vs_matches else ""

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Parametry")
        curr = st.selectbox("Vyberte měnu (dle tabulky IZPP):", ["CZK", "EUR", "USD"])
        
        # --- PŘESNÉ HLEDÁNÍ ÚČTU (Fix pro EUR) ---
        found_acc = ""
        # Hledáme název buňky a pak libovolný text, dokud nenarazíme na formát účtu/2700
        # Přidali jsme větší toleranci pro text mezi názvem měny a číslem
        pattern = rf'účtu\s+v\s+{curr}.*?(\d[\d\s\/-]*/\s*2700)'
        acc_match = re.search(pattern, last_page_text, re.DOTALL | re.IGNORECASE)
        
        if acc_match:
            found_acc = re.sub(r'\s+', '', acc_match.group(1))
        else:
            # Záložní plán: pokud nenajde přesnou shodu, zkusí najít první účet/2700 na stránce
            fallback_matches = re.findall(r'(\d[\d\s]*/\s*2700)', last_page_text)
            if fallback_matches:
                # Pro CZK bereme většinou první, pro EUR druhý v tabulce
                idx = 1 if curr == "EUR" and len(fallback_matches) > 1 else 0
                found_acc = re.sub(r'\s+', '', fallback_matches[idx])

        u_acc = st.text_input("Číslo účtu:", value=found_acc)
        u_vs = st.text_input("Variabilní symbol:", value=found_vs)
        u_ss = st.text_input("Specifický symbol:", value="999")
        u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=500.0)

    with col2:
        st.subheader("QR Platba")
        if u_acc and u_vs:
            iban = vytvor_iban_dynamicky(u_acc)
            if iban:
                # Bezpečné generování QR bez .to_pil()
                pay_str = f"SPD*1.0*ACC:{iban}*AM:{u_amt:.2f}*CC:{curr}*X-VS:{u_vs}*X-SS:{u_ss}*"
                
                qr = segno.make(pay_str, error='m')
                buff = BytesIO()
                qr.save(buff, kind='png', scale=10)
                
                st.image(buff, caption=f"Cílový IBAN: {iban}")
                st.success(f"Úspěšně vygenerováno pro {curr}")
                st.code(pay_str)
            else:
                st.error("Chyba: Neplatný formát účtu.")
        else:
            st.warning("Nahrajte PDF a zkontrolujte, zda byl nalezen účet.")

    with st.expander("DEBUG: Text poslední strany"):
        st.text(last_page_text)
