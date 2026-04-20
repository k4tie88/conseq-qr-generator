import streamlit as st
import pdfplumber
import re
import segno
from io import BytesIO

# --- 1. IBAN PŘEVODNÍK ---
def czech_to_iban(account_number, bank_code):
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

st.set_page_config(page_title="Conseq QR Automat", layout="wide")
st.title("🏦 Inteligentní Conseq QR")

# --- 2. LOGIKA EXTRAKCE Z PDF ---
def extract_data(pdf_file):
    results = {"vs": "", "is_dip": False, "client_czk": "", "client_eur": "", "emp_v1": None, "emp_v2": None}
    
    with pdfplumber.open(pdf_file) as pdf:
        # Strana 1: VS a detekce DIP
        p1_text = pdf.pages[0].extract_text()
        vs_match = re.search(r'ČÍSLO SMLOUVY:\s*(\d+)', p1_text)
        if vs_match: results["vs"] = vs_match.group(1)
        results["is_dip"] = "DIP" in p1_text or "dlouhodobý investiční produkt" in p1_text.lower()

        # Poslední strana: Účty zaměstnance
        last_page = pdf.pages[-1].extract_text()
        czk_m = re.search(r'v CZK:\s*([\d\s/]+)', last_page)
        eur_m = re.search(r'v EUR:\s*([\d\s/]+)', last_page)
        if czk_m: results["client_czk"] = czk_m.group(1).strip()
        if eur_m: results["client_eur"] = eur_m.group(1).strip()

        # Strana 5: Zaměstnavatel (jen u DIP)
        if results["is_dip"] and len(pdf.pages) >= 5:
            p5 = pdf.pages[4]
            table = p5.extract_table()
            if table and len(table) >= 3:
                # Řádek 1 (Individuální)
                results["emp_v1"] = {"acc": table[1][1], "ks": table[1][3]}
                # Řádek 2 (Hromadná)
                results["emp_v2"] = {"acc": table[2][1], "ks": table[2][3]}
                
    return results

# --- 3. UI APLIKACE ---
file = st.file_uploader("Nahrajte PDF smlouvu", type="pdf")

if file:
    try:
        d = extract_data(file)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Nastavení platby")
            options = ["Zaměstnanec - CZK", "Zaměstnanec - EUR"]
            if d["is_dip"]:
                options += ["Zaměstnavatel - Varianta 1 (Individuální)", "Zaměstnavatel - Varianta 2 (Hromadná)"]
            
            mode = st.selectbox("Typ platby:", options)
            
            # Inicializace hodnot
            final_acc, final_ks, final_ss = "", "", ""
            
            if "Zaměstnanec" in mode:
                final_acc = d["client_czk"] if "CZK" in mode else d["client_eur"]
                final_ks = ""
                final_ss = "999"
            elif "Varianta 1" in mode:
                final_acc = d["emp_v1"]["acc"] if d["emp_v1"] else ""
                final_ks = d["emp_v1"]["ks"] if d["emp_v1"] else "3552"
                final_ss = st.text_input("Zadejte IČO (Specifický symbol):")
            elif "Varianta 2" in mode:
                final_acc = d["emp_v2"]["acc"] if d["emp_v2"] else ""
                final_ks = d["emp_v2"]["ks"] if d["emp_v2"] else ""
                final_ss = "" # Dle řádku ignorovat

            # Kontrolní pole (uživatel může opravit, pokud PDF selže)
            u_acc = st.text_input("Číslo účtu / kód banky:", value=final_acc)
            u_vs = st.text_input("Variabilní symbol:", value=d["vs"])
            u_ss = st.text_input("Specifický symbol:", value=final_ss)
            u_ks = st.text_input("Konstantní symbol:", value=final_ks)
            u_amt = st.number_input("Částka:", value=0.0)
            u_curr = "EUR" if "EUR" in mode else "CZK"

        with col2:
            st.subheader("QR kód")
            if u_acc and "/" in u_acc:
                acc_p, bank_p = u_acc.split("/")
                iban = czech_to_iban(acc_p.strip(), bank_p.strip())
                
                if st.button("GENEROVAT"):
                    payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(u_amt)}*CC:{u_curr}*X-VS:{u_vs}"
                    if u_ss: payload += f"*X-SS:{u_ss}"
                    if u_ks: payload += f"*X-KS:{u_ks}"
                    payload += "*"
                    
                    qr = segno.make(payload, error='m')
                    out = BytesIO()
                    qr.save(out, kind='png', scale=10)
                    st.image(out)
                    st.success(f"Vygenerováno pro účet: {u_acc}")
            else:
                st.warning("Doplňte správné číslo účtu, aby se mohl vygenerovat QR kód.")

    except Exception as e:
        st.error(f"Nepodařilo se automaticky přečíst PDF. Zkuste to znovu nebo zadejte údaje ručně. (Chyba: {e})")