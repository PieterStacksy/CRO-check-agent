# CRO Landing Page AI Agent (met jouw checklist)

Deze versie gebruikt standaard jouw meegeleverde Excel (`checklist.xlsx`), gebaseerd op *Landingspagina CRO checklist.xlsx*.

## Snel starten
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Checklist-formaat
De Excel moet minimaal de volgende kolommen bevatten (exacte naam, Nederlands):
- `Categorie`
- `Tip`
- `Prioriteit`
- `Moeilijkheidsgraad`
- `Uitleg`

Niet-herkende tips worden als **REVIEW (handmatig)** gemarkeerd. Voor bekende tips (zoals *Logische URL*, *Mobiele responsiviteit*, *Favicon*, *Inhoud boven de vouw*) voert de tool een automatische check uit.

## Gebruik
- Voer een **URL** in
- Upload optioneel een **eigen Excel-checklist** (anders wordt `checklist.xlsx` gebruikt)
- Klik **Analyze**

Je krijgt:
- Samenvatting met score
- Tabel met alle checks (PASS/WARN/FAIL/REVIEW + evidence)
- Downloads: Markdown/HTML/JSON-rapport

> Wil je meer checks automatisch laten beoordelen? Stuur je checklist (met gewenste regels) en ik breid de mapping uit.
