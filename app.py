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
st.title("🏦 Plně automatický Conseq QR")

# --- 2. LOGIKA EXTRAKCE ---
def extract_data(pdf_file):
    results = {"vs": "", "is_dip": False, "client_czk": "", "client_eur": "", "emp_acc": ""}
    
    with pdfplumber.open(pdf_file) as pdf:
        p1_text = pdf.pages[0].extract_text() or ""
        vs_match = re.search(r'ČÍSLO SMLOUVY:\s*(\d+)', p1_text)
        if vs_match: results["vs"] = vs_match.group(1)
        results["is_dip"] = "DIP" in p1_text or "dlouhodobý investiční produkt" in p1_text.lower()

        # Účty zaměstnance (poslední strana)
        last_page = pdf.pages[-1].extract_text() or ""
        czk_m = re.search(r'v CZK:\s*([\d\s/]+)', last_page)
        eur_m = re.search(r'v EUR:\s*([\d\s/]+)', last_page)
        results["client_czk"] = czk_m.group(1).strip() if czk_m else "6850057 / 2700"
        results["client_eur"] = eur_m.group(1).strip() if eur_m else "6850081 / 2700"

        # Účet zaměstnavatele (strana 5)
        if results["is_dip"] and len(pdf.pages) >= 5:
            p5 = pdf.pages[4]
            table = p5.extract_table()
            if table and len(table) >= 2:
                results["emp_acc"] = table[1][1] if table[1][1] else "1388083926 / 2700"
            else:
                results["emp_acc"] = "1388083926 / 2700"
                
    return results

# --- 3. UI ---
file = st.file_uploader("Nahrajte smlouvu", type="pdf")

if file:
    d = extract_data(file)
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Parametry")
        mode = st.selectbox("Typ platby:", 
                            ["Zaměstnanec - CZK", "Zaměstnanec - EUR"] + 
                            (["Zaměstnavatel - Příspěvek DIP"] if d["is_dip"] else []))
        
        # Automatické nastavení podle volby
        if "Zaměstnanec" in mode:
            current_acc = d["client_czk"] if "CZK" in mode else d["client_eur"]
            current_ks = ""
            current_ss = "999"
        else:
            current_acc = d["emp_acc"] if d["emp_acc"] else "1388083926 / 2700"
            current_ks = "3552"
            current_ss = "" # Zde se musí dopsat IČO

        # TADY JSOU TY AUTOMATICKY VYPLNĚNÁ POLE
        u_acc = st.text_input("Číslo účtu:", value=current_acc)
        u_vs = st.text_input("Variabilní symbol:", value=d["vs"])
        
        if "Zaměstnavatel" in mode:
            u_ss = st.text_input("Specifický symbol (IČO):", value="")
        else:
            u_ss = st.text_input("Specifický symbol:", value=current_ss)
            
        u_ks = st.text_input("Konstantní symbol:", value=current_ks)
        u_amt = st.number_input("Částka:", value=0.0)

    with col2:
        st.subheader("QR kód")
        if u_acc and "/" in u_acc:
            acc_p, bank_p = u_acc.split("/")
            iban = czech_to_iban(acc_p.strip(), bank_p.strip())
            
            if st.button("GENEROVAT"):
                curr = "EUR" if "EUR" in mode else "CZK"
                payload = f"SPD*1.0*ACC:{iban}*AM:{'{:.2f}'.format(u_amt)}*CC:{curr}*X-VS:{u_vs}"
                if u_ss: payload += f"*X-SS:{u_ss}"
                if u_ks: payload += f"*X-KS:{u_ks}"
                payload += "*"
                
                qr = segno.make(payload, error='m')
                out = BytesIO()
                qr.save(out, kind='png', scale=10)
                st.image(out)
                st.success("QR kód je hotový!")
