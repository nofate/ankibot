import anthropic
import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import List, Dict, Tuple
import genanki
import random
from pathlib import Path

# Constants
ANKI_OUTPUT_DIR = Path("anki")
ANKI_MODEL_ID = 1676138610  # Random but fixed number for consistent model ID

@dataclass
class LanguageEntry:
    query: str
    definition: str
    examples: List[Dict[str, str]]  # List of dicts with language codes as keys

def parse_response(response: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Parses the Claude response into definition and examples.
    
    Args:
        response (str): Raw response from Claude
        
    Returns:
        Tuple[str, List[Dict[str, str]]]: Dictionary form and list of examples with language codes
    """
    # Split response into lines and filter out empty lines
    lines = [line.strip() for line in response.split('\n') if line.strip()]
    
    # First line contains the dictionary form
    definition = lines[0]
    
    # Remaining lines are examples
    examples = []
    for line in lines[1:]:
        if '|' in line:
            german, russian = line.split('|')
            examples.append({
                'de': german.strip(),
                'ru': russian.strip()
            })
    
    return definition, examples

def get_language_entry(query: str) -> LanguageEntry:
    """
    Creates a LanguageEntry for the given query string using Anthropic API.
    
    Args:
        query (str): The word or phrase to look up
        
    Returns:
        LanguageEntry: Contains the definition and examples for the query
    """
    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    system_prompt = """You are a german language assistant for a B1 student learning B2 Niveau.
    Provide 5 different simple usage examples of German Word and a russian Translations.
    Examples should be short enough. Answer only with a list, without any explanations, sticking to a following format: Example | Translation.
    Don't use any line numbers.
    Before examples write a dictionary form of a word if applicable (singular and plural with a definite article for a single noun, main verb forms for a single verb or verb with a preposition"""
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": query
            }
        ]
    )
    
    response = message.content[0].text
    definition, examples = parse_response(response)
    
    # TODO: Parse the response to extract definition and examples
    # For now, returning with raw response as definition
    return LanguageEntry(
        query=query,
        definition=definition,
        examples=examples
    )

def create_anki_deck(entries: List[LanguageEntry], deck_name: str = "German B2 Vocabulary") -> None:
    """
    Creates an Anki deck from a list of LanguageEntries.
    
    Args:
        entries (List[LanguageEntry]): List of language entries to convert to cards
        deck_name (str): Name of the deck to create
    """
    # Create output directory if it doesn't exist
    ANKI_OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Use constant model ID instead of random
    model = genanki.Model(
        ANKI_MODEL_ID,
        'German B2 Model',
        fields=[
            {'name': 'German'},
            {'name': 'Definition'},
            {'name': 'Examples'},
        ],
        templates=[
            {
                'name': 'German -> Definition + Examples',
                'qfmt': '{{German}}',
                'afmt': '''
                    <div class="definition">{{Definition}}</div>
                    <hr>
                    <div class="examples">{{Examples}}</div>
                ''',
            },
        ],
        css='''
        .card {
            font-family: arial;
            font-size: 20px;
            text-align: center;
            color: black;
            background-color: white;
        }
        .definition {
            margin: 20px;
        }
        .examples {
            text-align: left;
            margin: 20px;
        }
        '''
    )

    # Create a deck
    deck_id = random.randrange(1 << 30, 1 << 31)
    deck = genanki.Deck(deck_id, deck_name)

    # Add notes to the deck
    for entry in entries:
        # Format examples as HTML
        examples_html = '<br>'.join(
            f"{ex['de']}<br><i>{ex['ru']}</i>" 
            for ex in entry.examples
        )
        
        note = genanki.Note(
            model=model,
            fields=[
                entry.query,
                entry.definition,
                examples_html
            ]
        )
        deck.add_note(note)

    # Update the save path to use the output directory
    output_path = ANKI_OUTPUT_DIR / f'{deck_name}.apkg'
    genanki.Package(deck).write_to_file(str(output_path))

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # List of interesting B2 level German words
    german_words = [
        "gemütlich",      # cozy
        "ausgerechnet",   # of all things
        "zuverlässig",    # reliable
        "Voraussetzung",  # prerequisite
        "allerdings",     # however
        "Zusammenhang",   # connection/context
        "übrigens",       # by the way
        "Aufwand",        # effort/expense
        "beeindrucken",   # to impress
        "Unterlagen"      # documents
    ]
    
    # Fetch entries for all words
    entries = []
    for word in german_words:
        print(f"\nFetching data for: {word}")
        try:
            entry = get_language_entry(word)
            entries.append(entry)
            print(f"✓ Successfully processed: {word}")
        except Exception as e:
            print(f"✗ Error processing {word}: {str(e)}")
    
    # Create Anki deck
    if entries:
        create_anki_deck(entries, "vocab")
        print(f"\nAnki deck has been created in {ANKI_OUTPUT_DIR}/vocab.apkg")
        print(f"Successfully processed {len(entries)} words")


