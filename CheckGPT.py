import re

def load_compounds(file_path):
    # Load compounds from a given file and return a list of compounds.
    with open(file_path, 'r', encoding='utf-8') as file:
        compounds = [line.strip() for line in file if line.strip()]
    return compounds

"""
def load_compounds(file_path):
    compounds = {}
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            original = line.strip()
            if original:
                # Normalize by removing special characters, extra spaces, and lowercasing
                normalized = re.sub(r'[^a-zA-Z0-9]+', '', original).lower().strip()
                compounds[normalized] = original
    return compounds
"""

def compare_compounds(unique_compounds, postgpt_compounds):
    """Compare two dictionaries of compounds using normalized strings for comparison."""
    not_found = []
    for uc_norm, uc_orig in unique_compounds.items():
        found = False
        for pc_norm in postgpt_compounds.keys():
            if uc_norm == pc_norm:
                found = True
                break
        if not found:
            not_found.append(uc_orig)

    if not_found:
        print("The following compounds from Unique.txt were not found in PostGPT.txt:")
        for compound in not_found:
            print(compound)
    return not_found
