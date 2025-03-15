"""
Localization module for AnkiBot using a single YAML file
"""
import yaml
import os
from pathlib import Path

# Load translations
TRANSLATIONS = {}
try:
    yaml_path = os.path.join(os.path.dirname(__file__), 'messages.yml')
    with open(yaml_path, 'r', encoding='utf-8') as f:
        TRANSLATIONS = yaml.safe_load(f)
except Exception as e:
    print(f"Error loading translations: {e}")

# Global language setting
CURRENT_LANGUAGE = 'ru'

def set_language(language):
    """Set the global language"""
    global CURRENT_LANGUAGE
    if language in TRANSLATIONS:
        CURRENT_LANGUAGE = language
    else:
        CURRENT_LANGUAGE = 'ru'  # Default to Russian

def t(key):
    """Get a message in the current language (t for translate)"""
    # Get the message
    try:
        return TRANSLATIONS[CURRENT_LANGUAGE][key]
    except:
        # Try English as fallback
        try:
            return TRANSLATIONS['en'][key]
        except:
            # Return key if all else fails
            return f"Missing translation: {key}" 