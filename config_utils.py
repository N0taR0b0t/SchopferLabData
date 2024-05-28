import configparser
import logging

def read_api_key_and_assistant_id(config_file):
    logging.info("Reading API key and assistant ID from config file.")
    config = configparser.ConfigParser()
    try:
        config.read(config_file)
        api_key = config.get('openai', 'apikey', fallback=None)
        assistant_id = config.get('openai', 'assistant_id', fallback=None)
        
        if not api_key or not assistant_id:
            logging.error("API key or assistant ID not found in the config file.")
            return None, None
        
        return api_key, assistant_id
    except Exception as e:
        logging.error(f"Failed to read from the config file: {e}")
        return None, None

def save_assistant_id(config_file, assistant_id):
    logging.info("Saving assistant ID to config file.")
    config = configparser.ConfigParser()
    try:
        config.read(config_file)
        config['openai']['assistant_id'] = assistant_id
        with open(config_file, 'w') as configfile:
            config.write(configfile)
    except Exception as e:
        logging.error(f"Failed to save assistant ID: {e}")
