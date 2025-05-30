import streamlit as st
import pubchempy as pcp
import os
import requests
from ase.io import read, write
import py3Dmol
from tempfile import NamedTemporaryFile

# Page config
st.set_page_config(page_title="Molecule Tool", layout="wide")
st.title("🔬 Molecule Fetcher, Converter & Viewer")

# Input area
molecule_input = st.text_area("Enter molecule names (comma-separated):", "acetone")
record_type = st.radio("Structure type:", ["3D", "2D"], index=0)

# Turbomole coord writer
def write_turbomole_coord(atoms, path):
    lines = ["$coord"]
    for atom in atoms:
        x, y, z = atom.position
        lines.append(f"  {x: .10f}  {y: .10f}  {z: .10f}  {atom.symbol}")
    lines.append("$end\n")
    with open(path, "w") as f:
        f.write("\n".join(lines))

# On click: Fetch
if st.button("Fetch Molecules"):
    molecules = [mol.strip() for mol in molecule_input.split(',')]
    
    # Output directories
    sdf_dir = "structures_sdf"
    xyz_dir = "structures_xyz"
    coord_dir = "structures_coord"
    os.makedirs(sdf_dir, exist_ok=True)
    os.makedirs(xyz_dir, exist_ok=True)
    os.makedirs(coord_dir, exist_ok=True)

    # Output data
    names, formulas, weights = [], [], []
    sdf_files, xyz_files, coord_files = [], [], []

    # Get SDF from PubChem
    def get_sdf(cid):
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/SDF?record_type={record_type.lower()}"
        return requests.get(url).text

    # Fetch and convert
    with st.spinner("Fetching data from PubChem..."):
        for mol in molecules:
            try:
                compound = pcp.get_compounds(mol, "name")[0]
                names.append(compound.iupac_name)
                formulas.append(compound.molecular_formula)
                weights.append(compound.molecular_weight)

                # Save .mol
                sdf = get_sdf(compound.cid)
                sdf_path = os.path.join(sdf_dir, f"{mol}.mol")
                with open(sdf_path, "w") as f:
                    f.write(sdf)
                sdf_files.append(sdf_path)

                # Read atoms, save .xyz
                atoms = read(sdf_path)
                xyz_path = os.path.join(xyz_dir, f"{mol}.xyz")
                write(xyz_path, atoms)
                xyz_files.append(xyz_path)

                # Save Turbomole coord
                coord_path = os.path.join(coord_dir, f"{mol}.coord")
                write_turbomole_coord(atoms, coord_path)
                coord_files.append(coord_path)

            except Exception as e:
                st.warning(f"⚠️ Failed to process {mol}: {e}")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📁 Download Files", "🧬 3D Viewer", "📄 File Contents"])

    # Tab 1: Download
    with tab1:
        st.subheader("Download structure files")
        for i, mol in enumerate(molecules):
            st.markdown(f"**{mol}**")
            col1, col2, col3 = st.columns(3)
            if i < len(xyz_files):
                with open(xyz_files[i], "rb") as f:
                    col1.download_button(f"⬇️ {mol}.xyz", f, file_name=f"{mol}.xyz")
            if i < len(sdf_files):
                with open(sdf_files[i], "rb") as f:
                    col2.download_button(f"⬇️ {mol}.mol", f, file_name=f"{mol}.mol")
            if i < len(coord_files):
                with open(coord_files[i], "rb") as f:
                    col3.download_button(f"⬇️ {mol}.coord", f, file_name=f"{mol}.coord")

    # Tab 2: 3D Viewer
    with tab2:
        st.subheader("3D Structure Viewer")
        for i, mol in enumerate(molecules):
            st.markdown(f"**{mol}**")
            if i < len(sdf_files):
                try:
                    with open(sdf_files[i]) as f:
                        moldata = f.read()
                    viewer = py3Dmol.view(width=500, height=350)
                    viewer.addModel(moldata, 'sdf')
                    viewer.setStyle({'stick': {}})
                    viewer.setBackgroundColor('white')
                    viewer.zoomTo()
                    st.components.v1.html(viewer._make_html(), height=350)
                except Exception as e:
                    st.warning(f"Cannot render {mol}: {e}")

    # Tab 3: File content preview
    with tab3:
        st.subheader("View & Copy File Contents")
        for i, mol in enumerate(molecules):
            st.markdown(f"### 📘 {mol}")

            if i < len(xyz_files):
                with open(xyz_files[i], "r") as f:
                    xyz_text = f.read()
                st.markdown("**XYZ Format**")
                st.code(xyz_text, language='xyz')

            if i < len(sdf_files):
                with open(sdf_files[i], "r") as f:
                    mol_text = f.read()
                st.markdown("**MOL (SDF) Format**")
                st.code(mol_text, language='sdf')

            if i < len(coord_files):
                with open(coord_files[i], "r") as f:
                    coord_text = f.read()
                st.markdown("**Turbomole coord Format**")
                st.code(coord_text, language='bash')
# Sider banner 

with st.sidebar:
    st.markdown("## ℹ️ About")
    st.markdown("**Made By:** LieNing")
    
    st.markdown("---")
    st.markdown("### ⚙️ Powered by")
    st.markdown("- Py3Dmol for Visualization\n- Open Babel & ASE for Format Conversion\n- Pymatgen for Structure Representation")

    st.markdown("---")
    st.markdown("### 🔗 GitHub")
    github_url = "https://github.com/liening1"  # Replace with your actual URL
    st.markdown(
        f'<a href="{github_url}" target="_blank"><img src="https://cdn-icons-png.flaticon.com/512/25/25231.png" width="30"/></a>',
        unsafe_allow_html=True
    )
