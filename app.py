import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. MATEMATICKY PŘESNÝ IBAN ---
def vytvor_iban_dynamicky(account_str):
    try:
        account_str = re.sub(r'[^\d\/-]', '', account_str)
        if "/" not in account_str: return None
        full_number, bank_code = account_str.split("/")
        prefix = "0"
        number = full_number
        if "-" in full_number: prefix, number = full_number.split("-")
        prefix, number, bank_code = prefix.zfill(6), number.zfill(10), bank_code.zfill(4)
        check_str = f"{bank_code}{prefix}{number}123500"
        remainder = int(check_str) % 97
        return f"CZ{str(98 - remainder).zfill(2)}{bank_code}{prefix}{number}"
    except: return None

st.set_page_config(page_title="DIP QR Generátor v6.4", layout="wide")
st.title("🏦 DIP QR Generátor (Zaměstnanec & Zaměstnavatel)")

with st.sidebar:
    if st.button("Vymazat paměť / Nové PDF"):
        st.session_state.clear()
        st.rerun()

file = st.file_uploader("1. NAHRÁT PDF SMLOUVU (DIP i Standard)", type="pdf")

if file:
    if "pdf_text" not in st.session_state or st.session_state.get("last_file") != file.name:
        with pdfplumber.open(file) as pdf:
            pages = [p.extract_text() for p in pdf.pages]
            st.session_state.pdf_pages = pages
            st.session_state.last_file = file.name

if "pdf_pages" in st.session_state:
    pages = st.session_state.pdf_pages
    txt_all = "\n".join(pages)
    
    col1, col2 = st.columns(2)
    with col1:
        # Volba typu platby
        typ_platby = st.selectbox("Vyberte typ platby:", [
            "Zaměstnanec (Instrukce IZPP)",
            "Zaměstnavatel - A) Individuální příspěvek na DIP (IČO)",
            "Zaměstnavatel - B) Platba klienta hrazená zam-telem (Bez SS)"
        ])
        
        curr = st.selectbox("Měna:", ["CZK", "EUR", "USD"])
        
        # --- EXTRAKCE DAT ---
        found_acc, found_vs, found_ks, found_ss, found_amt = "", "", "", "", 0.0

        # 1. Variabilní symbol (Číslo smlouvy) - Vždy z první strany pod CONSEQ
        vs_m = re.search(r'ČÍSLO\s+SMLOUVY:\s*(\d+)', pages[0], re.IGNORECASE)
        if vs_m: found_vs = vs_m.group(1)

        # 2. Logika pro Zaměstnance (IZPP tabulka - předposlední/poslední strana)
        if "Zaměstnanec" in typ_platby:
            found_ss = "999"
            # Hledáme v celém textu řádek s měnou
            acc_pattern = rf'účtu\s+v\s+{curr}[:\s]*([\d\s\/-]+)'
            acc_m = re.search(acc_pattern, txt_all, re.IGNORECASE)
            if acc_m:
                found_acc = re.sub(r'[^\d\/-]', '', acc_m.group(1))

        # 3. Logika pro Zaměstnavatele (DIP tabulka na straně 5)
        else:
            # Hledáme sekci zaměstnavatele (často strana 5, index 4)
            dip_txt = ""
            for p in pages:
                if "INSTRUKCE K ZASÍLÁNÍ PENĚŽNÍCH PROSTŘEDKŮ ZAMĚSTNAVATELEM" in p:
                    dip_txt = p
                    break
            
            if dip_txt:
                # Rozdělení na řádky pod nadpisem
                lines = dip_txt.split('\n')
                relevant_lines = []
                start_collecting = False
                for line in lines:
                    if "INSTRUKCE K ZASÍLÁNÍ" in line:
                        start_collecting = True
                        continue
                    if start_collecting and len(line.strip()) > 20: # Hledáme řádky s obsahem
                        relevant_lines.append(line)
                
                # Varianta A (1. řádek tabulky)
                if "A)" in typ_platby and len(relevant_lines) >= 1:
                    row = relevant_lines[0]
                    acc_m = re.search(r'(\d[\d\s\/-]*\/\d{4})', row)
                    if acc_m: found_acc = re.sub(r'[^\d\/-]', '', acc_m.group(1))
                    
                    ks_m = re.findall(r'\s(\d{4})\s', row)
                    if ks_m: found_ks = ks_m[-1] # Poslední sloupec
                    
                    u_ico = st.text_input("Zadejte IČO zaměstnavatele (pro SS):", max_chars=8)
                    found_ss = re.sub(r'\D', '', u_ico)

                # Varianta B (2. řádek tabulky)
                elif "B)" in typ_platby and len(relevant_lines) >= 2:
                    row = relevant_lines[1]
                    acc_m = re.search(r'(\d[\d\s\/-]*\/\d{4})', row)
                    if acc_m: found_acc = re.sub(r'[^\d\/-]', '', acc_m.group(1))
                    
                    ks_m = re.findall(r'\s(\d{4})\s', row)
                    if ks_m: found_ks = ks_m[-1] # Poslední sloupec
                    found_ss = "" # Dle tabulky NEVYPLŇOVAT

        st.divider()
        u_acc = st.text_input("Účet (z PDF):", value=found_acc)
        u_vs = st.text_input("VS (číslo smlouvy):", value=found_vs)
        u_ks = st.text_input("KS (z PDF):", value=found_ks)
        u_ss = st.text_input("SS (IČO/999):", value=found_ss)
        u_amt = st.number_input(f"Částka ({curr}):", min_value=0.0, step=100.0)

    with col2:
        st.subheader("Výsledek")
        if u_acc and u_vs:
            iban = vytvor_iban_dynamicky(u_acc)
            if iban:
                parts = [f"SPD*1.0*ACC:{iban}", f"AM:{u_amt:.2f}", f"CC:{curr}", f"X-VS:{u_vs}"]
                if u_ks: parts.append(f"X-KS:{u_ks}")
                if u_ss: parts.append(f"X-SS:{u_ss}")
                pay = "*".join(parts) + "*"
                
                qr = segno.make(pay, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=10)
                st.image(out, caption=f"QR Platba - {typ_platby}")
                st.success(f"IBAN: {iban}")
                st.code(pay)
        else:
            st.warning("⚠️ Nahrajte PDF a vyberte typ platby.")
