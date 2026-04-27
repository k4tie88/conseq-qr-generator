import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- IBAN FUNKCE ---
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

st.set_page_config(page_title="Conseq QR Debugger", layout="wide")
st.title("🏦 Conseq QR + 🔍 Debugger")

file = st.file_uploader("1. NAHRAJTE PDF", type="pdf")

if file:
    # --- DEBUG INFO ---
    st.sidebar.header("🔍 Debugger (Co vidí robot)")
    
    with pdfplumber.open(file) as pdf:
        full_text = ""
        for i, page in enumerate(pdf.pages):
            p_txt = page.extract_text() or ""
            full_text += p_txt + "\n"
            st.sidebar.write(f"Strana {i+1}: Načteno {len(p_txt)} znaků")
        
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Parametry")
        curr = st.selectbox("Měna:", ["CZK", "EUR", "USD"])
        
        # --- LOGIKA VS (Číslo smlouvy) ---
        # Hledáme 10místné číslo začínající na 41
        vs_matches = re.findall(r'41\d{8}', full_text)
        found_vs = vs_matches[0] if vs_matches else ""
        st.sidebar.info(f"Nalezené VS kandidáty: {vs_matches}")

        # --- LOGIKA ÚČTU ---
        found_acc = ""
        # Hledáme text za 'Číslo účtu v [Měna]'
        # Používáme flexibilní regex pro různé formáty zápisu
        acc_pattern = rf'účtu\s+v\s+{curr}[:\s]*([\d\s/]+)'
        acc_match = re.search(acc_pattern, full_text, re.IGNORECASE)
        
        if acc_match:
            raw_acc = acc_match.group(1).strip()
            # Očistíme jen na číslice a lomítko
            acc_final = re.search(r'(\d[\d\s]*/\s*\d{4})', raw_acc)
            if acc_final:
                found_acc = re.sub(r'\s+', '', acc_final.group(1))
        
        st.sidebar.info(f"Surový nález účtu ({curr}): {found_acc}")

        u_acc = st.text_input("Účet:", value=found_acc)
        u_vs = st.text_input("VS:", value=found_vs)
        u_ss = st.text_input("SS:", value="999")
        u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=100.0)

    with col2:
        st.subheader("Výsledek")
        if u_acc and u_vs:
            iban = vytvor_iban_dynamicky(u_acc)
            if iban:
                pay = f"SPD*1.0*ACC:{iban}*AM:{u_amt:.2f}*CC:{curr}*X-VS:{u_vs}*X-SS:{u_ss}*"
                st.image(segno.make(pay).to_pil(scale=10))
                st.success(f"IBAN OK: {iban}")
                st.code(pay)
            else:
                st.error("Nepodařilo se sestavit IBAN z účtu.")
        else:
            st.warning("Doplňte zbývající údaje (viz Debugger vlevo/vpravo).")

    # Zobrazení celého textu pro kontrolu v případě chyby
    with st.expander("Zobrazit kompletní text z PDF (pro kontrolu)"):
        st.text(full_text)
