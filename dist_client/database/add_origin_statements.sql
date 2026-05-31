-- Dodavanje novih pattern-a za detekciju izjava sa jednostavnim formatom
-- Tip: EU i Turski bez liste zemalja

-- Serbian: EU preferencijalnog porekla (bez liste zemalja)
INSERT INTO catalogs.izjave_o_poreklu (jezik, tip_izjave, tekst_izjave, regex_pattern, origin_placeholder, broj_placeholder, aktivan)
VALUES (
    'serbian_simple_eu',
    'standard',
    'Izvoznik proizvoda obuhvaćenih ovom ispravom izjavljuje da su, osim ako je to drugačije izričito navedeno, ovi proizvodi EU preferencijalnog porekla.',
    '\bIzvoznik\s+proizvoda\s+obuhva[ćc]enih\s+ovom\s+ispravom\s+izjavljuje\s+da\s+su,?\s+osim\s+ako\s+je\s+to\s+druga[čc]ije\s+izri[čc]ito\s+navedeno,?\s+ovi\s+proizvodi\s+(?P<origin>EU)\s+preferencijalnog\s+porekla\.?',
    '[origin]',
    NULL,
    TRUE
);

-- Serbian: Turskog preferencijalnog porekla
INSERT INTO catalogs.izjave_o_poreklu (jezik, tip_izjave, tekst_izjave, regex_pattern, origin_placeholder, broj_placeholder, aktivan)
VALUES (
    'serbian_simple_turkish',
    'standard',
    'Izvoznik proizvoda obuhvaćenih ovom ispravom izjavljuje da su, osim ako je to drugačije izričito navedeno, ovi proizvodi Turskog preferencijalnog porekla.',
    '\bIzvoznik\s+proizvoda\s+obuhva[ćc]enih\s+ovom\s+ispravom\s+izjavljuje\s+da\s+su,?\s+osim\s+ako\s+je\s+to\s+druga[čc]ije\s+izri[čc]ito\s+navedeno,?\s+ovi\s+proizvodi\s+(?P<origin>Turskog)\s+preferencijalnog\s+porekla\.?',
    '[origin]',
    NULL,
    TRUE
);

-- Serbian: [Zemlja] preferencijalnog porekla (univerzalni pattern)
INSERT INTO catalogs.izjave_o_poreklu (jezik, tip_izjave, tekst_izjave, regex_pattern, origin_placeholder, broj_placeholder, aktivan)
VALUES (
    'serbian_simple_generic',
    'standard',
    'Izvoznik proizvoda obuhvaćenih ovom ispravom izjavljuje da su, osim ako je to drugačije izričito navedeno, ovi proizvodi [Zemlja] preferencijalnog porekla.',
    '\bIzvoznik\s+proizvoda\s+obuhva[ćc]enih\s+ovom\s+ispravom\s+izjavljuje\s+da\s+su,?\s+osim\s+ako\s+je\s+to\s+druga[čc]ije\s+izri[čc]ito\s+navedeno,?\s+ovi\s+proizvodi\s+(?P<origin>\w+)\s+preferencijalnog\s+porekla\.?',
    '[origin]',
    NULL,
    TRUE
);

-- Napomena: Pattern treba da podrži i stavke sa rasponom (npr. "Stavke 1-14 su EU preferencijalnog porekla")
