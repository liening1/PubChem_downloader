# Atlas Molecule Studio (PubChem Downloader)

Atlas Molecule Studio is a Streamlit web app for fetching molecule structures from PubChem, converting them to multiple file formats, and visualizing them in 3D.

Live app:
https://pubchemdownloaderxyz.streamlit.app

## What This App Does

- Searches molecules by name, synonym, formula, and CID.
- Handles uncommon and tricky names with a layered resolver.
- Downloads MOL/SDF, converts to XYZ, and generates Turbomole `coord` files.
- Provides an interactive 3D viewer and raw file inspector.
- Exports a run summary as CSV and all generated files as a ZIP bundle.

## Latest Update (April 2026)

- Redesigned the app into a professional Atlas UI with improved layout and visual hierarchy.
- Added robust PubChem resolution flow:
   - direct CID
   - name search
   - synonym search
   - formula search
   - autocomplete fallback
- Switched to `3D-only` visualization in the UI, with internal `3D-first -> 2D fallback` data retrieval when 3D coordinates are unavailable.
- Added persistent Streamlit session state so switching sections or format selectors does not lose run context.
- Reworked results into three persistent workflow sections:
   - `Deliverables`
   - `Molecule theater`
   - `Raw structure files`

## Project Structure

```
streamlit_app.py        # Main Atlas Molecule Studio app
requirements.txt        # Python dependencies
structures_sdf/         # Generated MOL/SDF files
structures_xyz/         # Generated XYZ files
structures_coord/       # Generated Turbomole coord files
```

## Local Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the app

```bash
streamlit run streamlit_app.py
```

### 3. Open in browser

Streamlit prints a local URL (usually `http://localhost:8501`).

## Deployment

### Streamlit Community Cloud

1. Push this repository to GitHub.
2. Go to Streamlit Community Cloud.
3. Create a new app and select:
    - Repository: `liening1/PubChem_downloader`
    - Branch: `main`
    - Main file path: `streamlit_app.py`
4. Deploy.

If your Streamlit Cloud app is already connected to `main`, pushing new commits automatically triggers redeploy.

## Usage Notes

- Input supports commas, semicolons, or new lines.
- Examples:
   - `sulfur hexafluoride`
   - `SF6`
   - `CID 17358`
   - `salicylic acid`

## Tech Stack

- Streamlit
- PubChemPy
- Requests
- ASE
- py3Dmol
- Pandas
