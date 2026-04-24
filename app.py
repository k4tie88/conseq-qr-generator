import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. MATEMATICKY PŘESNÝ IBAN (Vylepšená verze) ---
def vytvor_iban_dynamicky(account_str):
    try:
        # Odstranění mezer a nepovolených znaků
        account_str = re.sub(r'[^\d\/-]', '', account_str)
        if "/" not in account_str:
            return None
        
        full_number, bank_code = account_str.split("/")
        prefix = "0"
        number = full_number
        
        if "-" in full_number:
            prefix, number = full_number.split("-")
        
        # Doplnění nul podle bankovních standardů
        prefix = prefix.zfill(6)
        number = number.zfill(10)
        bank_code = bank_code.zfill(4)
        
        check_str = f"{bank_code}{prefix}{number}123500"
        remainder = int(check_str) % 97
        check_digits = str(98 - remainder).zfill(2)
        
        return f"CZ{check_digits}{bank_code}{prefix}{number}"
    except:
        return None

# --- 2. NASTAVENÍ STRÁNKY ---
st.set_page_config(page_title="DIP QR Generátor v6.1", layout="wide")
st.title("🏦 DIP QR Generátor (Dynamický)")

with st.sidebar:
    st.header("Nastavení")
    if st.button("Vymazat paměť / Nové PDF"):
        st.session_state.clear()
        st.rerun()

# --- 3. NAČÍTÁNÍ PDF ---
file = st.file_uploader("1. NAHRÁT PDF S INSTRUKCEMI", type="pdf")

if file:
    if "pdf_text" not in st.session_state or st.session_state.get("last_file") != file.name:
        with pdfplumber.open(file) as pdf:
            full_text = ""
            for page in pdf.pages:
                # Normalizujeme text (odstraníme vícenásobné mezery)
                page_text = page.extract_text() or ""
                full_text += " ".join(page_text.split()) + "\n"
            st.session_state.pdf_text = full_text
            st.session_state.last_file = file.name

# --- 4. ANALÝZA A FORMULÁŘ ---
if "pdf_text" in st.session_state:
    txt = st.session_state.pdf_text
    
    col1, col2 = st.columns(2)
    with col1:
        curr = st.selectbox("2. MĚNA", ["CZK", "EUR", "USD"])
        
        # Detekce typů platby podle textu v PDF
        has_type_a = "Individuální platba příspěvku zaměstnavatele na DIP" in txt
        has_type_b = "Individuální platba příspěvku Klienta na DIP hrazená zaměstnavatelem" in txt
        
        options = ["Standard (Klient)"]
        if has_type_a: options.append("A) Zaměstnavatel (IČO)")
        if has_type_b: options.append("B) Zaměstnavatel (Bez SS)")
        
        p_type = st.selectbox("3. TYP PLATBY", options)
        
        emp_ico = ""
        if "A)" in p_type:
            emp_ico = st.text_input("Zadejte IČO zaměstnavatele (pro SS):", max_chars=8)

        # --- EXTRAKCE DAT ---
        found_acc = ""
        found_vs = ""
        found_ss = ""
        found_ks = ""
        found_amt = 0.0

        # 1. Hledání VS (vždy)
        vs_match = re.search(r'SMLOUVY[:\s]*(\d+)', txt, re.IGNORECASE)
        found_vs = vs_match.group(1) if vs_match else ""

        # 2. Hledání účtu a částky pro Standard
        if "Standard" in p_type:
            found_ss = "999"
            # Mnohem volnější regex pro hledání účtu
            acc_pattern = rf'účtu\s+v\s+{curr}\s*:\s*([\d\s\/-]+)'
            acc_match = re.search(acc_pattern, txt, re.IGNORECASE)
            if acc_match:
                found_acc = re.sub(r'[^\d\/-]', '', acc_match.group(1))
            
            # Hledání částky (např. 1 000,00 CZK)
            c_label = "CZK|Kč" if curr == "CZK" else curr
            amt_pattern = rf'([\d\s,.]+)\s*(?:{c_label})'
            amt_match = re.search(amt_pattern, txt, re.IGNORECASE)
            if amt_match:
                val = re.sub(r'[^\d,.]', '', amt_match.group(1)).replace(',', '.')
                try: found_amt = float(val)
                except: found_amt = 0.0
        
        # 3. Logika pro DIP varianty
        else:
            if "A)" in p_type:
                pattern = r'zaměstnavatele\s+na\s+DIP\s*([\d\s\/-]+)'
                ks_m = re.search(r'IČ\s+zaměstnavatele\s+(\d{4})', txt, re.IGNORECASE)
                if ks_m: found_ks = ks_m.group(1)
                found_ss = "".join(filter(str.isdigit, emp_ico))
            else:
                pattern = r'hrazená\s+zaměstnavatelem\s*([\d\s\/-]+)'
                ks_m = re.search(r'NEVYPLŇOVAT\s+(\d{4})', txt, re.IGNORECASE)
                if ks_m: found_ks = ks_m.group(1)

            acc_match = re.search(pattern, txt, re.IGNORECASE)
            if acc_match:
                found_acc = re.sub(r'[^\d\/-]', '', acc_match.group(1))

        # --- ZOBRAZENÍ POLÍ (Možnost ruční opravy) ---
        st.divider()
        u_acc = st.text_input("Účet (z PDF):", value=found_acc)
        u_vs = st.text_input("VS (z PDF):", value=found_vs)
        u_ks = st.text_input("KS (z PDF):", value=found_ks)
        u_ss = st.text_input("SS (IČO/999):", value=found_ss)
        u_amt = st.number_input(f"Částka ({curr}):", value=found_amt, step=100.0)

    with col2:
        st.subheader("Výsledek")
        if not u_acc or not u_vs:
            st.error("❌ Nepodařilo se automaticky dohledat Číslo účtu nebo VS.")
            st.info("Zkuste údaje vlevo doplnit ručně nebo zkontrolujte, zda jste vybrali správnou měnu.")
        else:
            iban = vytvor_iban_dynamicky(u_acc)
            if iban:
                # Sestavení SPD řetězce
                parts = [f"SPD*1.0*ACC:{iban}", f"AM:{u_amt:.2f}", f"CC:{curr}", f"X-VS:{u_vs}"]
                if u_ks: parts.append(f"X-KS:{u_ks}")
                if u_ss: parts.append(f"X-SS:{u_ss}")
                pay = "*".join(parts) + "*"
                
                qr = segno.make(pay, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=10)
                
                st.image(out, caption=f"QR Platba pro {u_acc}")
                st.success(f"IBAN: {iban}")
                st.code(pay)
else:
    st.info("Nahrajte PDF smlouvu pro analýzu.")
