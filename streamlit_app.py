import os
import re
import zipfile
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import pandas as pd
import pubchempy as pcp
import py3Dmol
import requests
import streamlit as st
from ase.io import read, write

PUBCHEM_PUG_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_AUTOCOMPLETE_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound"
REQUEST_TIMEOUT = 20

# Session state keeps retrieval results stable across Streamlit reruns.
SESSION_DEFAULTS = {
    "results": [],
    "failures": [],
    "requested_count": 0,
    "has_run": False,
    "last_record_pref": "3D",
    "last_query_input": "",
    "active_result_section": "Deliverables",
}


def init_session_state() -> None:
    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            if isinstance(value, list):
                st.session_state[key] = list(value)
            elif isinstance(value, dict):
                st.session_state[key] = dict(value)
            else:
                st.session_state[key] = value


def clear_run_state() -> None:
    st.session_state["results"] = []
    st.session_state["failures"] = []
    st.session_state["requested_count"] = 0
    st.session_state["has_run"] = False
    st.session_state["active_result_section"] = "Deliverables"
    st.session_state.pop("content_selected_molecule", None)
    st.session_state.pop("content_selected_format", None)
    st.session_state.pop("viewer_selected_molecule", None)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400;500;700;800&family=Space+Mono:wght@400;700&display=swap');

        :root {
            --ink: #0f172a;
            --ink-soft: #334155;
            --mint: #1f9d8f;
            --copper: #d97745;
            --sand: #f6f4ec;
            --panel: rgba(255, 255, 255, 0.78);
            --panel-strong: rgba(255, 255, 255, 0.9);
            --stroke: rgba(15, 23, 42, 0.12);
            --shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
        }

        .stApp {
            background:
                radial-gradient(860px 450px at -6% -12%, rgba(31, 157, 143, 0.22), transparent 62%),
                radial-gradient(760px 430px at 105% -8%, rgba(217, 119, 69, 0.2), transparent 64%),
                linear-gradient(140deg, #f4f3ea 0%, #f9efe3 44%, #edf6f3 100%);
        }

        .block-container {
            max-width: 1220px;
            padding-top: 1.1rem;
            padding-bottom: 2.6rem;
        }

        .brand-shell {
            background: linear-gradient(120deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.72));
            border: 1px solid var(--stroke);
            box-shadow: var(--shadow);
            border-radius: 24px;
            padding: 1.25rem 1.3rem;
            margin-bottom: 1.1rem;
            position: relative;
            overflow: hidden;
            animation: cardIn 0.45s ease-out;
        }

        .brand-shell::before {
            content: "";
            position: absolute;
            width: 280px;
            height: 280px;
            right: -120px;
            top: -160px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(31, 157, 143, 0.24), transparent 70%);
            pointer-events: none;
        }

        .brand-grid {
            display: grid;
            grid-template-columns: 1.35fr 1fr;
            gap: 1rem;
            align-items: stretch;
        }

        .brand-kicker {
            font-family: 'Space Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-size: 0.72rem;
            color: var(--ink-soft);
            opacity: 0.82;
            margin: 0;
        }

        .brand-shell h1 {
            margin: 0.2rem 0 0.2rem 0;
            color: var(--ink);
            font-family: 'Bricolage Grotesque', sans-serif;
            font-size: clamp(1.6rem, 2.6vw, 2.5rem);
            letter-spacing: -0.02em;
            line-height: 1.06;
        }

        .brand-shell p {
            margin: 0.35rem 0 0 0;
            color: var(--ink-soft);
            font-size: 0.96rem;
            max-width: 62ch;
        }

        .signal-stack {
            display: grid;
            gap: 0.55rem;
            align-content: center;
        }

        .signal-card {
            border: 1px solid rgba(15, 23, 42, 0.12);
            background: rgba(255, 255, 255, 0.82);
            border-radius: 14px;
            padding: 0.52rem 0.72rem;
        }

        .signal-card span {
            display: block;
            font-family: 'Space Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.66rem;
            color: #4b5563;
            margin-bottom: 0.15rem;
        }

        .signal-card strong {
            color: var(--ink);
            font-family: 'Bricolage Grotesque', sans-serif;
            font-size: 0.88rem;
            font-weight: 700;
        }

        .panel-title {
            margin: 0 0 0.45rem 0;
            font-family: 'Space Mono', monospace;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            color: #334155;
            font-size: 0.72rem;
        }

        .tiny-note {
            margin-top: 0.5rem;
            color: #475569;
            font-size: 0.82rem;
            line-height: 1.4;
        }

        .metric-track {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 0.7rem;
            margin: 0.3rem 0 1rem 0;
            animation: cardIn 0.4s ease-out;
        }

        .metric-block {
            background: var(--panel-strong);
            border: 1px solid var(--stroke);
            border-radius: 16px;
            padding: 0.7rem 0.82rem;
            box-shadow: 0 9px 24px rgba(15, 23, 42, 0.06);
        }

        .metric-block .label {
            font-family: 'Space Mono', monospace;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.66rem;
        }

        .metric-block .value {
            margin-top: 0.1rem;
            color: var(--ink);
            font-family: 'Bricolage Grotesque', sans-serif;
            font-size: 1.34rem;
            font-weight: 800;
        }

        .section-head {
            margin: 0.45rem 0 0.3rem 0;
        }

        .section-head h2 {
            margin: 0;
            font-family: 'Bricolage Grotesque', sans-serif;
            color: var(--ink);
            font-size: 1.25rem;
            letter-spacing: -0.01em;
        }

        .section-head p {
            margin: 0.12rem 0 0 0;
            color: #475569;
            font-size: 0.88rem;
        }

        .molecule-card {
            background: var(--panel);
            border: 1px solid var(--stroke);
            border-radius: 14px;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
            padding: 0.72rem 0.85rem;
            margin-bottom: 0.55rem;
        }

        .molecule-card .name {
            margin: 0;
            color: var(--ink);
            font-weight: 700;
            font-size: 1.02rem;
            line-height: 1.25;
        }

        .molecule-card .meta {
            margin-top: 0.24rem;
            color: #4b5563;
            font-family: 'Space Mono', monospace;
            font-size: 0.73rem;
            line-height: 1.55;
        }

        .empty-state {
            background: var(--panel-strong);
            border: 1px dashed rgba(15, 23, 42, 0.25);
            border-radius: 14px;
            padding: 1rem;
            color: #334155;
            font-size: 0.92rem;
            margin-top: 0.5rem;
        }

        .run-status {
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid var(--stroke);
            border-radius: 12px;
            padding: 0.65rem 0.75rem;
            margin-bottom: 0.65rem;
        }

        .run-status .title {
            margin: 0;
            font-family: 'Space Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.65rem;
            color: #475569;
        }

        .run-status .summary {
            margin: 0.2rem 0 0 0;
            color: #0f172a;
            font-size: 0.9rem;
            line-height: 1.4;
            font-weight: 600;
        }

        div[data-testid="stTextArea"] textarea {
            border: 1px solid rgba(15, 23, 42, 0.2);
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.82);
            font-family: 'Space Mono', monospace;
            font-size: 0.92rem;
            line-height: 1.45;
            color: #0f172a;
        }

        div[data-testid="stTextArea"] textarea:focus {
            border-color: rgba(31, 157, 143, 0.6);
            box-shadow: 0 0 0 0.14rem rgba(31, 157, 143, 0.12);
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 999px !important;
            border: 1px solid rgba(15, 23, 42, 0.22) !important;
            background: rgba(255, 255, 255, 0.85) !important;
            color: #0f172a !important;
            font-weight: 700 !important;
            transition: transform 0.12s ease, box-shadow 0.12s ease !important;
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 16px rgba(15, 23, 42, 0.12);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.45rem;
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(255, 255, 255, 0.75);
            border: 1px solid rgba(15, 23, 42, 0.12);
            border-radius: 999px;
            height: 2.2rem;
            padding-left: 0.95rem;
            padding-right: 0.95rem;
            color: #0f172a;
            font-weight: 600;
        }

        .stTabs [aria-selected="true"] {
            background: #0f172a !important;
            border-color: #0f172a !important;
            color: #ffffff !important;
        }

        .stCodeBlock {
            border-radius: 14px;
            border: 1px solid rgba(15, 23, 42, 0.12);
            overflow: hidden;
        }

        @media (max-width: 980px) {
            .brand-grid {
                grid-template-columns: 1fr;
            }

            .signal-stack {
                grid-template-columns: 1fr;
            }
        }

        @keyframes cardIn {
            from {
                opacity: 0;
                transform: translateY(8px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_brand_header() -> None:
    st.markdown(
        """
        <div class="brand-shell">
            <div class="brand-grid">
                <div>
                    <p class="brand-kicker">Molecular workflow platform</p>
                    <h1>Atlas Molecule Studio</h1>
                    <p>
                        Search unusual compounds with a resilient multi-path resolver, convert outputs for modeling,
                        and inspect structures in an interactive theater built for research workflows.
                    </p>
                </div>
                <div class="signal-stack">
                    <div class="signal-card">
                        <span>Resolver</span>
                        <strong>Name + Synonym + Formula + CID + Autocomplete</strong>
                    </div>
                    <div class="signal-card">
                        <span>Conversion</span>
                        <strong>MOL to XYZ and Turbomole coord</strong>
                    </div>
                    <div class="signal-card">
                        <span>Resilience</span>
                        <strong>Automatic 3D and 2D record fallback</strong>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_molecule_queries(raw_input: str) -> List[str]:
    queries: List[str] = []
    for token in re.split(r"[,\n;]+", raw_input):
        cleaned = normalize_whitespace(token)
        if cleaned:
            queries.append(cleaned)
    return queries


def build_query_variants(query: str) -> List[str]:
    base = normalize_whitespace(query)
    if not base:
        return []

    variants = [
        base,
        base.lower(),
        base.title(),
        base.replace("-", " "),
        base.replace("_", " "),
        base.replace("(", " ").replace(")", " "),
    ]

    no_space = base.replace(" ", "")
    if len(no_space) >= 2:
        variants.append(no_space)

    base_lower = base.lower()
    if "sulphur" in base_lower:
        variants.append(re.sub(r"(?i)sulphur", "sulfur", base))
    if "sulfur" in base_lower:
        variants.append(re.sub(r"(?i)sulfur", "sulphur", base))

    seen = set()
    deduped: List[str] = []
    for item in variants:
        candidate = normalize_whitespace(item)
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def safe_filename(text: str) -> str:
    cleaned = re.sub(r"[^\w\s.-]", "", text, flags=re.ASCII).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned or "molecule"


def looks_like_formula(value: str) -> bool:
    token = value.replace(" ", "")
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9()+-]*", token)) and any(ch.isdigit() for ch in token)


def request_json(url: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict]:
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if response.ok:
            return response.json()
    except Exception:
        return None
    return None


def request_text(url: str, params: Optional[Dict[str, str]] = None) -> Optional[str]:
    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if response.ok:
            return response.text
    except Exception:
        return None
    return None


def extract_cids(payload: Optional[Dict]) -> List[int]:
    if not payload:
        return []
    return [int(cid) for cid in payload.get("IdentifierList", {}).get("CID", [])]


@st.cache_data(show_spinner=False, ttl=3600)
def safe_get_cids(identifier: str, namespace: str) -> List[int]:
    try:
        return [int(cid) for cid in pcp.get_cids(identifier, namespace=namespace)]
    except Exception:
        return []


@st.cache_data(show_spinner=False, ttl=3600)
def get_cids_from_name_word(query: str) -> List[int]:
    url = f"{PUBCHEM_PUG_BASE}/compound/name/{quote(query, safe='')}/cids/JSON"
    payload = request_json(url, params={"name_type": "word"})
    return extract_cids(payload)


@st.cache_data(show_spinner=False, ttl=3600)
def get_cids_from_synonym(query: str) -> List[int]:
    url = f"{PUBCHEM_PUG_BASE}/compound/synonym/{quote(query, safe='')}/cids/JSON"
    payload = request_json(url)
    return extract_cids(payload)


@st.cache_data(show_spinner=False, ttl=3600)
def get_autocomplete_suggestions(query: str, limit: int = 8) -> List[str]:
    url = f"{PUBCHEM_AUTOCOMPLETE_BASE}/{quote(query, safe='')}/JSON"
    payload = request_json(url, params={"limit": str(limit)})
    if not payload:
        return []
    return payload.get("dictionary_terms", {}).get("compound", [])


def resolve_compound_cid(query: str) -> Tuple[Optional[int], str]:
    cleaned_query = normalize_whitespace(query)
    if not cleaned_query:
        return None, "empty query"

    cid_match = re.fullmatch(r"(?i)cid[:\s-]*(\d+)", cleaned_query)
    if cleaned_query.isdigit():
        return int(cleaned_query), "direct CID"
    if cid_match:
        return int(cid_match.group(1)), "direct CID"

    variants = build_query_variants(cleaned_query)
    for candidate in variants:
        cids = safe_get_cids(candidate, "name")
        if cids:
            return cids[0], f"name match: {candidate}"

        cids = get_cids_from_synonym(candidate)
        if cids:
            return cids[0], f"synonym match: {candidate}"

        cids = get_cids_from_name_word(candidate)
        if cids:
            return cids[0], f"word match: {candidate}"

        if looks_like_formula(candidate):
            formula_candidate = candidate.replace(" ", "")
            cids = safe_get_cids(formula_candidate, "formula")
            if cids:
                return cids[0], f"formula match: {formula_candidate}"

    suggestions: List[str] = []
    for candidate in variants[:3]:
        suggestions.extend(get_autocomplete_suggestions(candidate, limit=8))

    seen = set()
    for suggestion in suggestions:
        normalized = normalize_whitespace(suggestion)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)

        cids = safe_get_cids(normalized, "name")
        if cids:
            return cids[0], f"autocomplete: {normalized}"

        cids = get_cids_from_synonym(normalized)
        if cids:
            return cids[0], f"autocomplete synonym: {normalized}"

    return None, "no PubChem match found"


def fetch_sdf_with_fallback(cid: int, preferred_record: str) -> Tuple[Optional[str], Optional[str]]:
    sequence = ["3d", "2d"] if preferred_record.lower() == "3d" else ["2d", "3d"]
    url = f"{PUBCHEM_PUG_BASE}/compound/cid/{cid}/SDF"
    for record_type in sequence:
        sdf_text = request_text(url, params={"record_type": record_type})
        if sdf_text and "M  END" in sdf_text:
            return sdf_text, record_type
    return None, None


def write_turbomole_coord(atoms, path: str) -> None:
    lines = ["$coord"]
    for atom in atoms:
        x, y, z = atom.position
        lines.append(f"  {x: .10f}  {y: .10f}  {z: .10f}  {atom.symbol}")
    lines.append("$end\n")
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read()


def build_zip_archive(records: List[Dict[str, Optional[str]]]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for record in records:
            for key in ("sdf_path", "xyz_path", "coord_path"):
                path = record.get(key)
                if path and os.path.exists(path):
                    archive.write(path, arcname=os.path.basename(path))
    buffer.seek(0)
    return buffer.read()


def build_summary_dataframe(results: List[Dict[str, Optional[str]]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Query": [item["query"] for item in results],
            "Resolved IUPAC Name": [item["iupac_name"] for item in results],
            "Formula": [item["formula"] for item in results],
            "Molecular Weight": [item["weight"] for item in results],
            "CID": [item["cid"] for item in results],
            "Search Path": [item["matched_by"] for item in results],
            "Record Used": [item["record_type_used"].upper() for item in results],
        }
    )


def label_for_item(item: Dict[str, Optional[str]]) -> str:
    return f"{item['query']} (CID {item['cid']})"


def render_metric_strip(requested: int, resolved: int, failed: int, fallback_count: int) -> None:
    st.markdown(
        f"""
        <div class="metric-track">
            <div class="metric-block">
                <div class="label">Requested</div>
                <div class="value">{requested}</div>
            </div>
            <div class="metric-block">
                <div class="label">Resolved</div>
                <div class="value">{resolved}</div>
            </div>
            <div class="metric-block">
                <div class="label">Unresolved</div>
                <div class="value">{failed}</div>
            </div>
            <div class="metric-block">
                <div class="label">3D to 2D fallback</div>
                <div class="value">{fallback_count}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_viewer_from_sdf(moldata: str, height: int = 430) -> None:
    viewer = py3Dmol.view(width=760, height=height)
    viewer.addModel(moldata, "sdf")
    viewer.setStyle(
        {
            "stick": {"radius": 0.2, "colorscheme": "Jmol"},
            "sphere": {"scale": 0.25},
        }
    )
    viewer.setBackgroundColor("#f6faf8")
    viewer.zoomTo()

    html = viewer._make_html()
    html = re.sub(r"width:\s*\d+px;", "width: 100%;", html, count=1)
    st.components.v1.html(html, height=height + 24)


def process_queries(
    requested_queries: List[str],
    preferred_record: str,
) -> Tuple[List[Dict[str, Optional[str]]], List[Dict[str, str]]]:
    sdf_dir = "structures_sdf"
    xyz_dir = "structures_xyz"
    coord_dir = "structures_coord"
    os.makedirs(sdf_dir, exist_ok=True)
    os.makedirs(xyz_dir, exist_ok=True)
    os.makedirs(coord_dir, exist_ok=True)

    results: List[Dict[str, Optional[str]]] = []
    failures: List[Dict[str, str]] = []
    used_stems = set()

    progress_slot = st.empty()
    progress_bar = st.progress(0.0)

    with st.spinner("Resolving PubChem entries and generating structures..."):
        total = len(requested_queries)
        for idx, query in enumerate(requested_queries, start=1):
            progress_slot.info(f"Resolving {query} ({idx}/{total})")
            progress_bar.progress(idx / total)

            cid, matched_by = resolve_compound_cid(query)
            if not cid:
                failures.append({"query": query, "error": matched_by})
                continue

            sdf_text, record_type_used = fetch_sdf_with_fallback(cid, preferred_record)
            if not sdf_text or not record_type_used:
                failures.append({"query": query, "error": "SDF record unavailable from PubChem"})
                continue

            try:
                compound = pcp.Compound.from_cid(cid)
            except Exception:
                compound = None

            base_stem = safe_filename(query)
            stem = base_stem
            serial = 2
            while stem in used_stems:
                stem = f"{base_stem}_{serial}"
                serial += 1
            used_stems.add(stem)

            sdf_path = os.path.join(sdf_dir, f"{stem}.mol")
            with open(sdf_path, "w", encoding="utf-8") as file:
                file.write(sdf_text)

            xyz_path: Optional[str] = None
            coord_path: Optional[str] = None
            conversion_warning = ""
            try:
                atoms = read(sdf_path)
                xyz_path = os.path.join(xyz_dir, f"{stem}.xyz")
                write(xyz_path, atoms)
                coord_path = os.path.join(coord_dir, f"{stem}.coord")
                write_turbomole_coord(atoms, coord_path)
            except Exception as exc:
                conversion_warning = f"SDF downloaded, but XYZ/coord conversion failed: {exc}"

            iupac_name = query
            molecular_formula = "N/A"
            molecular_weight = "N/A"
            if compound is not None:
                iupac_name = compound.iupac_name or query
                molecular_formula = compound.molecular_formula or "N/A"
                molecular_weight = str(compound.molecular_weight or "N/A")

            results.append(
                {
                    "query": query,
                    "cid": str(cid),
                    "iupac_name": iupac_name,
                    "formula": molecular_formula,
                    "weight": molecular_weight,
                    "matched_by": matched_by,
                    "record_type_used": record_type_used,
                    "sdf_path": sdf_path,
                    "xyz_path": xyz_path,
                    "coord_path": coord_path,
                    "conversion_warning": conversion_warning,
                }
            )

    progress_bar.empty()
    progress_slot.empty()
    return results, failures


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## Mission Log")
        if st.session_state["has_run"]:
            resolved = len(st.session_state["results"])
            failed = len(st.session_state["failures"])
            requested = st.session_state["requested_count"]
            st.markdown(
                f"""
                <div class="run-status">
                    <p class="title">Last run snapshot</p>
                    <p class="summary">Requested: {requested}<br/>Resolved: {resolved}<br/>Unresolved: {failed}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("No run yet. Start with a molecule list to generate structures.")

        st.markdown("### Input Examples")
        st.code("sulfur hexafluoride\nSF6\nCID 17358\nsalicylic acid", language="text")

        st.markdown("### Search Pipeline")
        st.markdown("- direct CID")
        st.markdown("- name and synonym")
        st.markdown("- formula")
        st.markdown("- autocomplete fallback")

        st.markdown("### Output Suite")
        st.markdown("- MOL or SDF")
        st.markdown("- XYZ")
        st.markdown("- Turbomole coord")
        st.markdown("- CSV and ZIP")

        st.markdown("### Latest Update")
        st.markdown("- Robust uncommon-molecule search pipeline")
        st.markdown("- Persistent section and format switching")
        st.markdown("- Upgraded Atlas UI and workflow layout")

        st.markdown("---")
        st.markdown("Made by LieNing")
        st.markdown("[GitHub](https://github.com/liening1)")


st.set_page_config(page_title="Atlas Molecule Studio", page_icon=":microscope:", layout="wide")
inject_styles()
init_session_state()
render_brand_header()

input_default = st.session_state["last_query_input"] or "acetone\nsulfur hexafluoride"

left_col, right_col = st.columns([2.7, 1.3], gap="large")

with left_col:
    st.markdown('<p class="panel-title">Compound intake</p>', unsafe_allow_html=True)
    molecule_input = st.text_area(
        "Molecule list",
        value=input_default,
        key="query_input_area",
        height=140,
        help="Use commas, semicolons, or new lines. Examples: SF6, sulfur hexafluoride, CID 24555.",
    )

with right_col:
    st.markdown('<p class="panel-title">Run controls</p>', unsafe_allow_html=True)
    record_type = st.segmented_control(
        "Preferred structure",
        ["3D", "2D"],
        selection_mode="single",
        default=st.session_state["last_record_pref"],
        key="preferred_record_radio",
    )
    if record_type is None:
        record_type = st.session_state["last_record_pref"]

    fetch_clicked = st.button("Run retrieval pipeline", type="primary", use_container_width=True)
    clear_clicked = st.button("Clear current results", use_container_width=True)
    st.markdown(
        '<div class="tiny-note">Results stay in session state, so changing molecule or format selectors will not reset your run.</div>',
        unsafe_allow_html=True,
    )

render_sidebar()

if clear_clicked:
    clear_run_state()
    st.rerun()

if fetch_clicked:
    requested_queries = parse_molecule_queries(molecule_input)
    if not requested_queries:
        st.warning("Please enter at least one molecule name, formula, synonym, or CID.")
    else:
        results, failures = process_queries(requested_queries, record_type)
        st.session_state["results"] = results
        st.session_state["failures"] = failures
        st.session_state["requested_count"] = len(requested_queries)
        st.session_state["has_run"] = True
        st.session_state["last_record_pref"] = record_type
        st.session_state["last_query_input"] = molecule_input

        st.session_state.pop("content_selected_molecule", None)
        st.session_state.pop("content_selected_format", None)
        st.session_state.pop("viewer_selected_molecule", None)

if st.session_state["has_run"]:
    results = st.session_state["results"]
    failures = st.session_state["failures"]
    requested = st.session_state["requested_count"]
    preferred = st.session_state["last_record_pref"].lower()

    fallback_count = sum(1 for item in results if item["record_type_used"] != preferred)
    render_metric_strip(
        requested=requested,
        resolved=len(results),
        failed=len(failures),
        fallback_count=fallback_count,
    )

    if results:
        summary_df = build_summary_dataframe(results)

        st.markdown(
            """
            <div class="section-head">
                <h2>Compound Manifest</h2>
                <p>Verified compounds and retrieval trace for reproducible structure workflows.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.dataframe(summary_df, use_container_width=True, height=min(420, 86 + 35 * len(summary_df)))

        export_col_1, export_col_2 = st.columns(2)
        export_col_1.download_button(
            "Download summary CSV",
            data=summary_df.to_csv(index=False).encode("utf-8"),
            file_name="compound_summary.csv",
            mime="text/csv",
            key="download_summary_csv",
            use_container_width=True,
        )
        export_col_2.download_button(
            "Download structure bundle ZIP",
            data=build_zip_archive(results),
            file_name="structures_bundle.zip",
            mime="application/zip",
            key="download_structure_zip",
            use_container_width=True,
        )

        section_options = ["Deliverables", "Molecule theater", "Raw structure files"]
        if st.session_state["active_result_section"] not in section_options:
            st.session_state["active_result_section"] = section_options[0]

        active_section = st.segmented_control(
            "Result section",
            section_options,
            selection_mode="single",
            default=st.session_state["active_result_section"],
            key="active_result_section",
            label_visibility="collapsed",
        )
        if active_section is None:
            active_section = st.session_state["active_result_section"]

        if active_section == "Deliverables":
            st.markdown(
                """
                <div class="section-head">
                    <h2>Per Molecule Package</h2>
                    <p>Download each generated format and inspect the exact match path.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            for idx, item in enumerate(results, start=1):
                st.markdown(
                    f"""
                    <div class="molecule-card">
                        <p class="name">{item['query']}</p>
                        <p class="meta">
                            CID {item['cid']} | Formula: {item['formula']} | Weight: {item['weight']}<br/>
                            Matched by: {item['matched_by']} | Record: {item['record_type_used'].upper()}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                col_mol, col_xyz, col_coord = st.columns(3)
                with open(item["sdf_path"], "rb") as mol_file:
                    col_mol.download_button(
                        "Download MOL",
                        data=mol_file.read(),
                        file_name=os.path.basename(item["sdf_path"]),
                        key=f"download_mol_{idx}_{item['cid']}",
                        use_container_width=True,
                    )

                if item["xyz_path"]:
                    with open(item["xyz_path"], "rb") as xyz_file:
                        col_xyz.download_button(
                            "Download XYZ",
                            data=xyz_file.read(),
                            file_name=os.path.basename(item["xyz_path"]),
                            key=f"download_xyz_{idx}_{item['cid']}",
                            use_container_width=True,
                        )
                else:
                    col_xyz.caption("XYZ unavailable")

                if item["coord_path"]:
                    with open(item["coord_path"], "rb") as coord_file:
                        col_coord.download_button(
                            "Download coord",
                            data=coord_file.read(),
                            file_name=os.path.basename(item["coord_path"]),
                            key=f"download_coord_{idx}_{item['cid']}",
                            use_container_width=True,
                        )
                else:
                    col_coord.caption("coord unavailable")

                if item["conversion_warning"]:
                    st.warning(item["conversion_warning"])

        elif active_section == "Molecule theater":
            st.markdown(
                """
                <div class="section-head">
                    <h2>Interactive Molecule Theater</h2>
                    <p>Focus on one structure and rotate the model in a dedicated viewport.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            viewer_labels = [label_for_item(item) for item in results]
            if (
                "viewer_selected_molecule" not in st.session_state
                or st.session_state["viewer_selected_molecule"] not in viewer_labels
            ):
                st.session_state["viewer_selected_molecule"] = viewer_labels[0]

            viewer_label = st.selectbox(
                "Choose molecule for 3D view",
                viewer_labels,
                key="viewer_selected_molecule",
            )
            selected_item = results[viewer_labels.index(viewer_label)]

            st.markdown(
                f"""
                <div class="molecule-card">
                    <p class="name">{selected_item['query']}</p>
                    <p class="meta">CID {selected_item['cid']} | Record used: {selected_item['record_type_used'].upper()} | Search path: {selected_item['matched_by']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            try:
                mol_text = read_text_file(selected_item["sdf_path"])
                render_viewer_from_sdf(mol_text)
            except Exception as exc:
                st.warning(f"Cannot render {selected_item['query']}: {exc}")

        else:
            st.markdown(
                """
                <div class="section-head">
                    <h2>Raw File Inspector</h2>
                    <p>Read exact structure text and switch formats without resetting your run.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            content_labels = [label_for_item(item) for item in results]
            if (
                "content_selected_molecule" not in st.session_state
                or st.session_state["content_selected_molecule"] not in content_labels
            ):
                st.session_state["content_selected_molecule"] = content_labels[0]

            selected_label = st.selectbox(
                "Choose molecule",
                content_labels,
                key="content_selected_molecule",
            )
            selected_item = results[content_labels.index(selected_label)]

            available_formats: List[Tuple[str, str]] = [("MOL", selected_item["sdf_path"])]
            if selected_item["xyz_path"]:
                available_formats.append(("XYZ", selected_item["xyz_path"]))
            if selected_item["coord_path"]:
                available_formats.append(("coord", selected_item["coord_path"]))

            format_options = [fmt for fmt, _ in available_formats]
            if (
                "content_selected_format" not in st.session_state
                or st.session_state["content_selected_format"] not in format_options
            ):
                st.session_state["content_selected_format"] = format_options[0]

            selected_format = st.segmented_control(
                "Choose file format",
                format_options,
                selection_mode="single",
                default=st.session_state["content_selected_format"],
                key="content_selected_format",
            )
            if selected_format is None:
                selected_format = st.session_state["content_selected_format"]

            selected_path = dict(available_formats)[selected_format]
            raw_text = read_text_file(selected_path)
            language_map = {"MOL": "text", "XYZ": "text", "coord": "bash"}
            st.code(raw_text, language=language_map.get(selected_format, "text"))

    if failures:
        with st.expander(f"Unresolved molecules ({len(failures)})", expanded=False):
            failure_df = pd.DataFrame(
                {
                    "Input": [item["query"] for item in failures],
                    "Reason": [item["error"] for item in failures],
                }
            )
            st.dataframe(failure_df, use_container_width=True)

    if not results:
        st.error("No molecules were resolved in this run. Try formula notation like SF6, a synonym, or a CID.")
else:
    st.markdown(
        """
        <div class="empty-state">
            Paste molecules in the intake area and run the pipeline to generate structure files,
            visual previews, and export packages.
        </div>
        """,
        unsafe_allow_html=True,
    )
