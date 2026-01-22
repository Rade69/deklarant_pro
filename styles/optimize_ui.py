#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import os

WIDGET_MAPPING = {
    "I31_2": "le_r31_oznake_br",
    "I31_4": "le_r31_paketa",
    "I31_5": "le_r31_broj",
    "I31_6": "le_r31_vrsta",
    "I31_8": "le_r31_kontejner_1",
    "I31_9": "le_r31_kontejner_2",
    "I31_10": "te_r31_opis",
    "I31_11": "le_r31_trg_naziv",
    "L31": "lbl_rubrika31",
    "I32": "le_rubrika32",
    "L32": "lbl_rubrika32",
    "I33_1": "le_rubrika33_1",
    "I33_2": "le_rubrika33_2",
    "I34a": "le_rubrika34a",
    "I35": "le_rubrika35",
    "I37_1": "le_rubrika37_1",
    "I38": "le_rubrika38",
    "I40": "le_rubrika40",
    "I44": "te_rubrika44",
    "btn_next": "btn_nav_next",
    "btn_prev": "btn_nav_prev",
    # Dodaj ostale po potrebi iz prethodne liste
}


def optimize():
    input_file = "naimenovanja_tab_from_json.ui"
    output_file = "naimenovanja_tab_OPTIMIZED.ui"

    if not os.path.exists(input_file):
        print(f"❌ Greška: Ne nalazim {input_file}")
        return

    tree = ET.parse(input_file)
    root = tree.getroot()

    # 1. Uklanjanje SVIH styleSheet atributa
    removed_styles = 0
    for prop in root.findall(".//property[@name='styleSheet']"):
        parent = None
        # Pronađi roditelja ovog property-ja da ga ukloniš
        for node in root.iter():
            if prop in list(node):
                node.remove(prop)
                removed_styles += 1
                break

    # 2. Preimenovanje widgeta
    renamed = 0
    for widget in root.iter("widget"):
        old_name = widget.get("name")
        if old_name in WIDGET_MAPPING:
            widget.set("name", WIDGET_MAPPING[old_name])
            renamed += 1

    tree.write(output_file, encoding="UTF-8", xml_declaration=True)
    print(f"✅ Obrisano {removed_styles} starih stilova.")
    print(f"✅ Preimenovano {renamed} widgeta.")
    print(f"🎉 Generisan čist fajl: {output_file}")


if __name__ == "__main__":
    optimize()
