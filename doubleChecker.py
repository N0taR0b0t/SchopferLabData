import logging
import json
from config_utils import read_api_key_and_assistant_id, save_assistant_id
from openai_utils import (
    initialize_openai_client, create_or_get_assistant,
    get_potentially_misclassified_compounds, browsing_assistant
)

# Set up debug logging to file
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("debug.log", mode='w'), logging.StreamHandler()])

# Set up chat logging to file
chat_logger = logging.getLogger('chat_logger')
chat_logger.setLevel(logging.INFO)
chat_handler = logging.FileHandler("conversation.log", mode='w')  # Overwrite mode to clear the log at start
chat_handler.setFormatter(logging.Formatter('%(message)s'))
chat_logger.addHandler(chat_handler)

def clear_log():
    with open("conversation.log", "w") as f:
        f.write("")

def parse_compound_file(file_path):
    groups = {}
    with open(file_path, 'r') as file:
        sorted_compound_data = file.read()
    sections = sorted_compound_data.split('\n\n')
    for section in sections:
        lines = section.split('\n')
        if len(lines) < 2:
            logging.warning(f"Skipping improperly formatted section: {section}")
            continue
        group_name = lines[0].strip(':')
        logging.info(f"Parsing group: {group_name}")
        compounds = [compound.strip() for compound in lines[1].split(', ')]
        groups[group_name] = compounds
    return groups

def identify_compounds_to_verify(client, api_key, groups):
    logging.info("Identifying 12 compounds most likely to be misclassified.")
    prompt = "Given the current classification of the following compounds into predefined categories, identify the 12 compounds most likely to be misclassified. Provide your response as a JSON object. Here are the groups:\n"

    for group, compounds in groups.items():
        prompt += f"### {group}:\n" + "\n".join(compounds) + "\n"

    response_content = get_potentially_misclassified_compounds(client, api_key, prompt)
    
    if response_content and isinstance(response_content, dict):
        return response_content.get('misclassified_compounds', [])
    else:
        logging.error("Failed to identify compounds to verify due to incorrect response format or no response.")
        return []


def main():
    logging.info("Starting main process.")
    clear_log()

    config_file = 'config.ini'
    api_key, assistant_id = read_api_key_and_assistant_id(config_file)
    if not api_key:
        logging.error("No API key provided. Exiting.")
        return

    client = initialize_openai_client(api_key)
    if not client:
        return

    assistant_instructions = """
    You are an assistant tasked with verifying the classification of chemical compounds into predefined categories. When provided with a list of compounds and their current categories, first identify the 12 compounds most likely to be misclassified. Then, for each compound, look up reliable sources to verify its classification. If a compound is misclassified, suggest moving it to the correct category using the format 'Compound => Group'. Provide your response in JSON format. You can only move compounds to existing categories and should not create new categories.
    """

    assistant_id = create_or_get_assistant(client, config_file, assistant_instructions)

    groups = parse_compound_file('PostGPT.txt')

    # Identify the 12 compounds to verify using GPT-4o
    compounds_to_verify = identify_compounds_to_verify(client, api_key, groups)

    # Verify the compounds
    browsing_assistant(client, assistant_id, groups, compounds_to_verify)

    # Write the corrected and sorted list back to PostGPT.txt
    with open('PostGPT.txt', 'w') as file:
        for group, compounds in groups.items():
            file.write(f"{group}:\n")
            file.write(", ".join(compounds) + "\n\n")

if __name__ == "__main__":
    main()