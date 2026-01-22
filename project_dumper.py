import os

# --- KONFIGURACIJA ---
# Ekstenzije fajlova koje zelimo da analiziramo
EXTENSIONS = {".py", ".spec", ".iss", ".json", ".bat", ".txt", ".md"}

# Folderi koje cemo ignorisati (da ne saljemo nepotrebne stvari)
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "venv311",
    "__pycache__",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "output",
}

# Ime izlaznog fajla
OUTPUT_FILE = "kompletan_projekat_analiza.txt"


def is_text_file(filepath):
    """Provjerava da li je fajl tekstualni na osnovu ekstenzije."""
    return os.path.splitext(filepath)[1].lower() in EXTENSIONS


def dump_project(start_path):
    """Prolazi kroz foldere i upisuje sadrzaj fajlova u jedan veliki fajl."""
    print(f"Pocinjem skeniranje foldera: {start_path}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:
        # Upisi zaglavlje
        outfile.write(
            f"=== ANALIZA PROJEKTA: {os.path.basename(os.path.abspath(start_path))} ===\n\n"
        )

        for root, dirs, files in os.walk(start_path):
            # Ukloni foldere koje ne zelimo (in-place modifikacija liste dirs)
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                if is_text_file(file):
                    filepath = os.path.join(root, file)
                    relpath = os.path.relpath(filepath, start_path)

                    print(f"Dodajem: {relpath}")

                    try:
                        with open(filepath, "r", encoding="utf-8") as infile:
                            content = infile.read()

                        # Formatiranje za lakse citanje od strane AI-a
                        outfile.write(f"\n{'='*60}\n")
                        outfile.write(f"FILE_PATH: {relpath}\n")
                        outfile.write(f"{'='*60}\n")
                        outfile.write(content + "\n")

                    except Exception as e:
                        print(f"GRESKA pri citanju {relpath}: {e}")
                        outfile.write(f"\n[GRESKA PRI CITANJU FAJLA: {e}]\n")

    print(f"\nZavrseno! Kreiran je fajl: {OUTPUT_FILE}")
    print("Molim vas otpremite taj fajl u chat za analizu.")


if __name__ == "__main__":
    # Pokrece se u trenutnom folderu
    current_dir = os.getcwd()
    dump_project(current_dir)
