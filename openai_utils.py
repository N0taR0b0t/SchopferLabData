import re
import logging
import json
import time
import requests
import configparser
from openai import OpenAI
from requests.auth import HTTPBasicAuth

chat_logger = logging.getLogger('chat_logger')

def initialize_openai_client(api_key):
    logging.info("Initializing OpenAI client.")
    try:
        client = OpenAI(api_key=api_key)
        return client
    except Exception as e:
        logging.error(f"Failed to initialize OpenAI client: {e}")
        return None

def create_or_get_assistant(client, config_file, instructions):
    logging.info("Checking for existing assistant ID.")
    config = configparser.ConfigParser()
    config.read(config_file)
    assistant_id = config['openai'].get('assistant_id', None)
    
    if assistant_id:
        logging.info(f"Using existing assistant ID: {assistant_id}")
        return assistant_id

    logging.info("Creating new assistant with instructions.")
    try:
        assistant = client.beta.assistants.create(
            name="Compound Verification Assistant",
            instructions=instructions,
            # model="gpt-4o",
            model="gpt-3.5-turbo",
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "getSearchResult",
                        "description": "Get search results for a given query",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query string"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                }
            ],
            response_format="json"
        )
        assistant_id = assistant.id
        config['openai']['assistant_id'] = assistant_id
        with open(config_file, 'w') as configfile:
            config.write(configfile)
        logging.info(f"New assistant created with ID: {assistant_id}")
        return assistant_id
    except Exception as e:
        logging.error(f"Failed to create assistant: {str(e)}")
        raise

def extract_json_from_response(content):
    start_idx = content.find("```json")
    if start_idx != -1:
        start_idx += len("```json")
        end_idx = content.find("```", start_idx)
        if end_idx != -1:
            json_str = content[start_idx:end_idx].strip()
            return json_str
    return None

def get_potentially_misclassified_compounds(client, api_key, prompt):
    logging.info("Using GPT-4o to identify potentially misclassified compounds.")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            # model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an assistant tasked with verifying the classification of chemical compounds into predefined categories."},
                {"role": "user", "content": prompt}
            ]
        )
        logging.debug(f"GPT-4o response: {response}")

        content = response.choices[0].message.content
        chat_logger.info(f"User: {prompt}")
        chat_logger.info(f"Assistant: {content}")

        if not content:
            logging.error("Empty response content received.")
            return None

        # Extract JSON string between ```
        start_idx = content.find("```json")
        end_idx = content.find("```", start_idx + 7)  # Adjust the offset to skip past "```json\n"
        
        print("Start Index:", start_idx)
        print("End Index:", end_idx)

        if start_idx != -1 and end_idx != -1:
            start_idx += len("```json\n")  # Skip past the json marker and newline
            json_str = content[start_idx:end_idx].strip()
            print("Extracted JSON String:", json_str)

            try:
                response_json = json.loads(json_str)
                return response_json
            except json.JSONDecodeError as e:
                logging.error(f"Failed to decode JSON response GPMC: {e}")
                return None
        else:
            logging.error("Failed to find JSON object between ```json and ```")
            return None

    except Exception as e:
        logging.error(f"Failed to get misclassified compounds from GPT-4o: {e}")
        return None

def perform_search(query, config_file='config.ini'):
    logging.info(f"Performing search with query: {query}")
    config = configparser.ConfigParser()
    try:
        config.read(config_file)
        username = config['credentials'].get('username', None)
        password = config['credentials'].get('password', None)
        
        if not username or not password:
            logging.error("Username or password not found in the config file.")
            return {'error': 'Authentication credentials are not provided in config file.'}
        
        response = requests.get(f"http://prototype.ddns.net:4603/search?query={query}", 
                                auth=HTTPBasicAuth(username, password))
        response.raise_for_status()
        logging.debug(f"Search response: {response.json()}")
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Search request failed: {str(e)}")
        return {'error': f'Failed to retrieve search results: {str(e)}'}

def process_results(results):
    logging.info("Processing search results.")
    if 'error' in results:
        logging.error(f"Error in search results: {results['error']}")
        return results['error']
    return "\n" + "\n".join([f"Title: {item['title']}, URL: {item['link']}" for item in results])

def create_thread_and_run(client, assistant_id, user_input):
    logging.info("Creating a new thread and running the assistant.")
    try:
        thread = client.beta.threads.create()
        logging.debug(f"Thread created with ID: {thread.id}")
        client.beta.threads.messages.create(thread_id=thread.id, role="user", content=user_input)
        run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant_id)
        logging.debug(f"Run created with ID: {run.id}")
        
        # Log the user input to conversation log
        chat_logger.info(f"User: {user_input}")
        
        return thread, run  # Return both thread and run
    except Exception as e:
        logging.error(f"Failed to create thread and run: {str(e)}")
        raise

def handle_required_action(client, run, thread_id):
    tool_outputs = []
    required_action = run.required_action.submit_tool_outputs

    for tool_call in required_action.tool_calls:
        if tool_call.function.name == "getSearchResult":
            arguments = tool_call.function.arguments
            if isinstance(arguments, str):
                arguments = json.loads(arguments)  # Parse the string into a dictionary if necessary
            query = arguments['query']
            results = perform_search(query)
            results_str = json.dumps(results)  # Convert results to a string
            tool_outputs.append({
                "tool_call_id": tool_call.id,
                "output": results_str
            })

    try:
        run = client.beta.threads.runs.submit_tool_outputs_and_poll(
            thread_id=thread_id,
            run_id=run.id,
            tool_outputs=tool_outputs
        )
        logging.info("Tool outputs submitted successfully.")
        return run
    except Exception as e:
        logging.error(f"Failed to submit tool outputs: {str.e}")
        raise

def wait_on_run(client, run, thread_id):
    logging.info("Waiting for the assistant run to complete.")
    try:
        while run.status in ["queued", "in_progress", "requires_action"]:
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            logging.debug(f"Run status: {run.status}")
            if run.status == "requires_action":
                run = handle_required_action(client, run, thread_id)
            time.sleep(0.5)
        return run
    except Exception as e:
        logging.error(f"Error while waiting for run to complete: {str(e)}")
        raise

def browsing_assistant(client, assistant_id, groups, compounds_to_verify):
    logging.info("Starting browsing assistant process.")
    existing_categories = list(groups.keys())

    for compound in compounds_to_verify:
        prompt = f"Please classify the compound: {compound}. Choose the correct group from the following categories: {', '.join(existing_categories)}. Provide your answer as a 'classification' json object."
        thread, run = create_thread_and_run(client, assistant_id, prompt)
        run = wait_on_run(client, run, thread_id=thread.id)

        if run.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            for message in messages.data:
                if message.role == 'assistant':
                    content = message.content[0].text.value
                    chat_logger.info(f"Assistant: {content}")
                    print(f"Assistant's response for {compound}:\n{content}")
                    # Parse the JSON response and check if the suggested group is among the existing categories
                    try:
                        response_json = json.loads(content)
                        suggested_group = response_json.get('classification')
                        if suggested_group in existing_categories:
                            print(f"Compound '{compound}' classified correctly as '{suggested_group}'.")
                        else:
                            print(f"Suggested group '{suggested_group}' is not a valid category for compound '{compound}'.")
                    except json.JSONDecodeError:
                        logging.error(f"Failed to decode JSON response: {content}")
                        print(f"Failed to interpret the response correctly for compound '{compound}'.")
        else:
            logging.error(f"Run did not complete successfully for {compound}.")
