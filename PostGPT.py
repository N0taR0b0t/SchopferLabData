#!/Users/matias/anaconda3/bin/python3
import CheckGPT
from openai import OpenAI
import configparser
import os
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("debug.log", mode='w'), logging.StreamHandler()])

def normalize_compound_name(name):
    """Normalize the compound names to improve matching reliability."""
    return ''.join(e for e in name if e.isalnum()).lower()

def normalize_group_name(name):
    """Normalize group names to ensure consistency."""
    return name.lower().strip()

def prompt_gpt(client, prompt):
    """Prompt GPT with a given text and return the response using the chat completions endpoint."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are sorting significant compounds from a mass spectrometer analysis."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def setup_logs():
    """Setup a directory for logs and return the path."""
    log_directory = 'logs'
    os.makedirs(log_directory, exist_ok=True)
    return log_directory

def write_to_file(path, content):
    """Write a given content to a specified file."""
    with open(path, 'w') as file:
        file.write(content)

def read_api_key(config_file):
    """Read API key from a config file."""
    config = configparser.ConfigParser()
    config.read(config_file)
    return config['openai']['apikey']

def create_prompt(groups, compounds_to_sort):
    prompt = "Here are the compounds already sorted into groups:\n"
    for group, compounds in groups.items():
        prompt += f"### {group}:\n- " + "\n- ".join(compounds) + "\n"
    prompt += ("""\nMeticulously group these compounds based on their names, by specifying the group name next to each compound.
    Create new groups if necessary or, if you notice a mistake, move compounds between groups using the format 'move <compound> from <old_group> to <new_group>'.
    Format your response as 'Compound => Group' for sorting.
    Group each compound into the most precise category based on its chemical structure, biological function, and standard biochemical classifications.
    Take a nuanced approach to ensure that similar compounds like fatty acids, glycerolipids, glycerophospholipids, eicosanoids, vitamins, steroids, quinones, and lactones are identified and grouped together.
    You will likely need a group called 'Other', but make an effort to find an accurate group for all compounds.
    Do not include comments or explanations in your commands.
    Do not include words like 'New' or 'Group' while sorting, and avoid mistakes such as attempting the command 'from none to new group'.
    Group these compounds for now:\n""")
    prompt += "\n".join(f"- {comp}" for comp in compounds_to_sort)
    return prompt

def parse_gpt_output(output, groups, compounds_to_sort, already_sorted, normalized_compounds):
    sorted_compounds = []
    lines = output.strip().split('\n')
    print("Starting to parse GPT output...")  # Debug statement
    for line in lines:
        original_line = line  # Keep the original line for debugging
        line = line.strip()
        print(f"Processing line: '{line}'")  # Debug: show the line being processed
        if "=>" in line:
            parts = line.split("=>")
            if len(parts) == 2:
                raw_compound, group = parts[0].strip(), parts[1].strip()
                normalized_name = normalize_compound_name(raw_compound)
                if normalized_name in normalized_compounds:
                    compound = normalized_compounds[normalized_name]
                    if compound not in already_sorted:
                        if group not in groups:
                            groups[group] = []
                        groups[group].append(compound)
                        sorted_compounds.append(compound)
                        already_sorted.add(compound)
                        print(f"Added '{compound}' to '{group}'")  # Debug success
                    else:
                        print(f"Skipping '{compound}'; already sorted into a group.")  # Debug skip
                else:
                    print(f"Compound '{raw_compound}' ({normalized_name}) not found in list.")  # Debug fail
            else:
                print(f"Could not split the line into compound and group: '{original_line}'")  # Debug format issue
        elif "move" in line.lower():
            parts = line.lower().split("move")[1].strip().split("from")
            if len(parts) == 2:
                move_parts = parts[1].strip().split("to")
                if len(move_parts) == 2:
                    compound_name = parts[0].strip()
                    old_group, new_group = move_parts[0].strip(), move_parts[1].strip()
                    normalized_name = normalize_compound_name(compound_name)
                    normalized_old_group = normalize_group_name(old_group)
                    normalized_new_group = normalize_group_name(new_group)
                    if normalized_name in normalized_compounds:
                        compound = normalized_compounds[normalized_name]
                        if normalized_old_group in groups and compound in groups[normalized_old_group]:
                            groups[normalized_old_group].remove(compound)
                            if normalized_new_group not in groups:
                                groups[normalized_new_group] = []
                            groups[normalized_new_group].append(compound)
                            print(f"Moved '{compound}' from '{old_group}' to '{new_group}'")  # Debug move
                        else:
                            print(f"Move failed; compound '{compound_name}' not found in group '{old_group}'.")  # Debug move fail
                    else:
                        print(f"Move failed; compound '{compound_name}' not recognized.")  # Debug move fail
        else:
            print(f"No valid command found in line: '{original_line}'")  # Debug invalid line
    return sorted_compounds

def main():
    unique_file_path = 'Unique.txt'
    config_file = 'config.ini'
    api_key = read_api_key(config_file)
    client = OpenAI(api_key=api_key)
    compounds = CheckGPT.load_compounds(unique_file_path)
    groups = {}
    already_sorted = set()
    log_contents = []

    # Create a mapping from normalized names to original names
    normalized_compounds = {normalize_compound_name(comp): comp for comp in compounds}

    while compounds:
        batch_to_sort = compounds[:10] if len(compounds) > 10 else compounds[:]
        prompt = create_prompt(groups, batch_to_sort)
        gpt_output = prompt_gpt(client, prompt)
        sorted_compounds = parse_gpt_output(gpt_output, groups, batch_to_sort, already_sorted, normalized_compounds)
        
        log_contents.append(f"Prompt:\n{prompt}\n")
        log_contents.append(f"GPT Output:\n{gpt_output}\n")
        
        # Update the list of compounds by removing those that have been sorted
        compounds = [comp for comp in compounds if comp not in sorted_compounds]

        if not sorted_compounds:  # Check if no compounds were sorted in this iteration
            print("Warning: No compounds were sorted in this iteration.")
            break  # Optionally break to avoid infinite loop if nothing is being sorted

    log_file_path = os.path.join(setup_logs(), "conversation.log")
    write_to_file(log_file_path, "\n".join(log_contents))

    with open("PostGPT.txt", 'w') as file:
        for group, members in groups.items():
            file.write(f"{group}:\n")
            file.write(", ".join(members) + "\n\n")

if __name__ == "__main__":
    main()
