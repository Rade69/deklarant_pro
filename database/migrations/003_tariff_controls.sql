-- Migration 003: Tariff controls (BiH UIO Objedinjen spisak, mart 2015)
-- Source: B-H-Objededinjeni-spisak-03-2015.pdf

CREATE TABLE IF NOT EXISTS catalogs.tariff_controls (
    id SERIAL PRIMARY KEY,
    tarifni_broj TEXT NOT NULL,      -- tarifna oznaka (npr. "0301" ili "0301 10 00 00")
    naimenovanje TEXT,               -- opis robe iz spiska
    san BOOLEAN NOT NULL DEFAULT FALSE,   -- Sanitarno uvjerenje (rubrika 5)
    vet BOOLEAN NOT NULL DEFAULT FALSE,   -- Veterinarsko uvjerenje (rubrika 6)
    fit BOOLEAN NOT NULL DEFAULT FALSE,   -- Fitosanitarna kontrola (rubrika 7)
    uvk BOOLEAN NOT NULL DEFAULT FALSE,   -- Kontrola kvaliteta (rubrika 8)
    agencija BOOLEAN NOT NULL DEFAULT FALSE, -- Agencija za lijekove (rubrika 9)
    dozvola BOOLEAN NOT NULL DEFAULT FALSE,  -- Dozvole/Prilog (rubrika 10)
    napomena TEXT,                   -- Dodatne napomene (uvjetovani znaci)
    CONSTRAINT tariff_controls_broj_unique UNIQUE (tarifni_broj)
);

CREATE INDEX IF NOT EXISTS idx_tariff_controls_broj
    ON catalogs.tariff_controls (tarifni_broj);

-- Partial index za brzo pronalazenje roba koje imaju bilo kakvu kontrolu
CREATE INDEX IF NOT EXISTS idx_tariff_controls_any
    ON catalogs.tariff_controls (tarifni_broj)
    WHERE san OR vet OR fit OR uvk OR agencija OR dozvola;

COMMENT ON TABLE catalogs.tariff_controls IS
    'Objedinjen spisak roba koje podlijezu kontroli inspekcijskih organa BiH (UIO, mart 2015)';
COMMENT ON COLUMN catalogs.tariff_controls.san IS 'Sanitarno uvjerenje';
COMMENT ON COLUMN catalogs.tariff_controls.vet IS 'Veterinarsko uvjerenje';
COMMENT ON COLUMN catalogs.tariff_controls.fit IS 'Fitosanitarna inspekcija';
COMMENT ON COLUMN catalogs.tariff_controls.uvk IS 'Kontrola kvaliteta (trzna inspekcija)';
COMMENT ON COLUMN catalogs.tariff_controls.agencija IS 'Agencija za lijekove i medicinska sredstva';
COMMENT ON COLUMN catalogs.tariff_controls.dozvola IS 'Dozvola uvoza/izvoza (Prilog odluke)';
