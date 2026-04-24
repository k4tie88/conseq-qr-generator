import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. MATEMATICKY PŘESNÝ IBAN (Převod z PHP czAccountToIban) ---
def vytvor_iban_dynamicky(account_str):
    try:
        # Očištění vstupu
        account_str = account_str.replace(" ", "")
        if "/" not in account_str:
            return account_str
        
        full_number, bank_code = account_str.split("/")
        prefix = "0"
        number = full_number
        
        if "-" in full_number:
            prefix, number = full_number.split("-")
        
        prefix = prefix.zfill(6)
        number = number.zfill(10)
        bank_code = bank_code.zfill(4)
        
        check_str = f"{bank_code}{prefix}{number}123500"
        
        # Výpočet zbytku (modulo 97)
        remainder = int(check_str) % 97
        check_digits = str(98 - remainder).zfill(2)
        
        return f"CZ{check_digits}{bank_code}{prefix}{number}"
    except:
        return None

# --- 2. NASTAVENÍ STRÁNKY ---
st.set_page_config(page_title="DIP QR Generátor v6", layout="wide")
st.title("🏦 DIP QR Generátor (Dynamický)")

with st.sidebar:
    st.header("Nastavení")
    if st.button("Vymazat paměť / Nové PDF"):
        st.session_state.clear()
        st.rerun()

# --- 3. NAČÍTÁNÍ PDF A ANALÝZA (Podle PHP vzoru) ---
file = st.file_uploader("1. NAHRÁT PDF S INSTRUKCEMI", type="pdf")

if file:
    if "pdf_text" not in st.session_state or st.session_state.get("last_file") != file.name:
        with pdfplumber.open(file) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
            st.session_state.pdf_text = full_text
            st.session_state.last_file = file.name

# --- 4. FORMULÁŘ ---
if "pdf_text" in st.session_state:
    txt = st.session_state.pdf_text
    
    col1, col2 = st.columns(2)
    with col1:
        curr = st.selectbox("2. MĚNA", ["CZK", "EUR", "USD"])
        
        # Detekce dostupných možností (pro zašednutí v PHP)
        has_type_a = "Individuální platba příspěvku zaměstnavatele na DIP" in txt
        has_type_b = "Individuální platba příspěvku Klienta na DIP hrazená zaměstnavatelem" in txt
        
        options = ["Standard (Klient)"]
        if has_type_a: options.append("A) Zaměstnavatel (IČO)")
        if has_type_b: options.append("B) Zaměstnavatel (Bez SS)")
        
        p_type = st.selectbox("3. TYP PLATBY", options)
        
        emp_ico = ""
        if "A)" in p_type:
            emp_ico = st.text_input("Zadejte IČO zaměstnavatele (pro SS):", max_chars=8)

        # --- EXTRAKČNÍ LOGIKA (PŘESNĚ PODLE PHP) ---
        found_acc = ""
        found_vs = ""
        found_ss = ""
        found_ks = ""
        found_amt = 0.0

        # Vždy hledáme VS
        vs_match = re.search(r'SMLOUVY[:\s]*(\d+)', txt, re.IGNORECASE)
        found_vs = vs_match.group(1) if vs_match else ""

        if "Standard" in p_type:
            found_ss = "999"
            # Hledání účtu: Číslo účtu v [Měna] :
            acc_pattern = rf'Číslo\s+účtu\s+v\s+{curr}\s*:\s*([\d\s\/-]+)'
            acc_match = re.search(acc_pattern, txt, re.IGNORECASE | re.UNICODE)
            if acc_match:
                found_acc = re.sub(r'[^\d\/-]', '', acc_match.group(1))
            
            # Hledání částky
            c_search = "CZK|Kč" if curr == "CZK" else curr
            amt_pattern = rf'([\d\s,.]+)\s*(?:{c_search})'
            amt_match = re.search(amt_pattern, txt, re.IGNORECASE | re.UNICODE)
            if amt_match:
                val = re.sub(r'[^\d,.]', '', amt_match.group(1)).replace(',', '.')
                try: found_amt = float(val)
                except: found_amt = 0.0

        else:
            # DIP Varianty
            regex = (r'Individuální\s+platba\s+příspěvku\s+zaměstnavatele\s+na\s+DIP' 
                     if "A)" in p_type else 
                     r'Individuální\s+platba\s+příspěvku\s+Klienta\s+na\s+DIP\s+hrazená\s+zaměstnavatelem')
            
            dip_match = re.search(rf'{regex}([\d\s\/-]+)', txt, re.IGNORECASE | re.UNICODE)
            if dip_match:
                found_acc = re.sub(r'[^\d\/-]', '', dip_match.group(1))
                
                if "A)" in p_type:
                    # KS z IČ zaměstnavatele textu
                    ks_m = re.search(r'IČ\s+zaměstnavatele\s+(\d{4})', txt, re.IGNORECASE)
                    if ks_m: found_ks = ks_m.group(1)
                    found_ss = "".join(filter(str.isdigit, emp_ico))
                else:
                    # KS z NEVYPLŇOVAT textu
                    ks_m = re.search(r'NEVYPLŇOVAT\s+(\d{4})', txt, re.IGNORECASE)
                    if ks_m: found_ks = ks_m.group(1)

        # --- ZOBRAZENÍ VÝSLEDKŮ ---
        st.divider()
        u_acc = st.text_input("Účet (z PDF):", value=found_acc)
        u_vs = st.text_input("VS (z PDF):", value=found_vs)
        u_ks = st.text_input("KS (z PDF):", value=found_ks)
        u_ss = st.text_input("SS (IČO/999):", value=found_ss)
        u_amt = st.number_input(f"Částka ({curr}):", value=found_amt, step=100.0)

    with col2:
        st.subheader("Výsledek")
        if not found_acc or not found_vs:
            st.warning("⚠️ Čekám na nahrání PDF nebo dohledání údajů...")
        else:
            iban = vytvor_iban_dynamicky(u_acc)
            if iban:
                # Sestavení SPD
                parts = [f"SPD*1.0*ACC:{iban}", f"AM:{u_amt:.2f}", f"CC:{curr}", f"X-VS:{u_vs}"]
                if u_ks: parts.append(f"X-KS:{u_ks}")
                if u_ss: parts.append(f"X-SS:{u_ss}")
                pay = "*".join(parts) + "*"
                
                qr = segno.make(pay, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=10)
                
                st.image(out, caption=f"QR Platba")
                st.info(f"IBAN: {iban}")
                st.code(pay)
else:
    st.info("Nahrajte PDF smlouvu pro spuštění analýzy.")
