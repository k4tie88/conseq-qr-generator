# 1. Nejdříve najdeme, kde v textu začíná sekce pro zaměstnavatele
    employer_section_start = full_text.find("Instrukce pro platby příspěvků zaměstnavatele")
    
    # 2. Rozdělíme text na část pro klienta a část pro zaměstnavatele
    client_text = full_text[:employer_section_start] if employer_section_start != -1 else full_text
    employer_text = full_text[employer_section_start:] if employer_section_start != -1 else ""

    # 3. Najdeme účty v každé sekci zvlášť
    client_accounts = re.findall(r'([\d\s-]{5,16})\s*/\s*(\d{4})', client_text)
    employer_accounts = re.findall(r'([\d\s-]{5,16})\s*/\s*(\d{4})', employer_text)

    # Vyčištění
    c_accs = [f"{m[0].strip()} / {m[1].strip()}" for m in client_accounts]
    e_accs = [f"{m[0].strip()} / {m[1].strip()}" for m in employer_accounts]

    # --- LOGIKA VÝBĚRU ---
    detected_acc = None
    if rezim == "Zaměstnanec":
        # Standard: 1. účet v sekci klienta je CZK, 2. je EUR
        if len(c_accs) > 2:
            detected_acc = c_accs[1] if currency == "CZK" else c_accs[2]
        else:
            detected_acc = c_accs[1] if len(c_accs) > 1 else None
            
    elif rezim == "Zaměstnavatel - Var 1 (Příspěvek)":
        # První účet nalezený V SEKCI ZAMĚSTNAVATELE
        detected_acc = e_accs[0] if len(e_accs) > 0 else None
        
    elif rezim == "Zaměstnavatel - Var 2 (Hromadná)":
        # Druhý účet nalezený V SEKCI ZAMĚSTNAVATELE
        detected_acc = e_accs[1] if len(e_accs) > 1 else None