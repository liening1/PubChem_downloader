import streamlit as st
import pubchempy as pcp
import pandas as pd
import os
import requests
from ase.io import read, write
from tempfile import NamedTemporaryFile
import py3Dmol
import shutil


st.set_page_config(page_title="Molecule Fetcher & Viewer", layout="wide")

st.title("🔬 Molecule Downloader, Converter & 3D Viewer")

# Input section
molecule_input = st.text_area(
    "Enter molecule names (comma-separated):",
    "acetone"
)

record_type = st.radio("Choose structure type to fetch:", ["3D", "2D"], index=0)

if st.button("Fetch Molecules"):
    molecules = [mol.strip() for mol in molecule_input.split(',')]
    sdf_dir = 'structures_sdf'
    xyz_dir = 'structures_xyz'
    os.makedirs(sdf_dir, exist_ok=True)
    os.makedirs(xyz_dir, exist_ok=True)
   
    names, formulas, weights = [], [], []
    sdf_files, xyz_files = [], []

    def get_sdf(cid):
        url = f'https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/SDF?record_type={record_type.lower()}'
        response = requests.get(url)
        return response.text

    with st.spinner("Fetching data from PubChem..."):
        for mol in molecules:
            try:
                compound = pcp.get_compounds(mol, 'name')[0]
                names.append(compound.iupac_name)
                formulas.append(compound.molecular_formula)
                weights.append(compound.molecular_weight)

                sdf = get_sdf(compound.cid)
                sdf_path = os.path.join(sdf_dir, f"{mol}.mol")
                with open(sdf_path, 'w') as f:
                    f.write(sdf)
                sdf_files.append(sdf_path)

                atoms = read(sdf_path)
                xyz_path = os.path.join(xyz_dir, f"{mol}.xyz")
                write(xyz_path, atoms)
                xyz_files.append(xyz_path)

            except Exception as e:
                st.warning(f"⚠️ Failed to process {mol}: {e}")

    # Display result
    df = pd.DataFrame({'Name': names, 'Formula': formulas, 'Weight': weights})
    st.subheader("📋 Compound Info")
    st.dataframe(df)

    csv_file = NamedTemporaryFile(delete=False, suffix=".csv")
    df.to_csv(csv_file.name, index=False)
    st.download_button("📥 Download CSV", csv_file.name, file_name="compounds.csv")

    st.subheader("⬇️ Download Files & View Structures")
    for i, mol in enumerate(molecules):
        col1, col2, col3 = st.columns([2, 2, 6])
        with col1:
            if i < len(xyz_files):
                with open(xyz_files[i], "rb") as f:
                    st.download_button(f"Download {mol}.xyz", f, file_name=f"{mol}.xyz")
        with col2:
            if i < len(sdf_files):
                with open(sdf_files[i], "rb") as f:
                    st.download_button(f"Download {mol}.mol", f, file_name=f"{mol}.mol")
        with col3:
            try:
                with open(sdf_files[i]) as f:
                    moldata = f.read()
                viewer = py3Dmol.view(width=800, height=600)
                viewer.addModel(moldata, 'sdf')
                viewer.setStyle({'stick': {}})
                viewer.zoomTo()
                viewer_html = viewer._make_html()
                st.components.v1.html(viewer_html, height=600)
            except Exception as e:
                st.warning(f"Cannot render {mol}: {e}")



