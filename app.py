import anthropic
import os
from dotenv import load_dotenv
from typing import List, Dict, Tuple, Optional
import genanki
import random
from pathlib import Path
from datetime import datetime
import hashlib
import time
import boto3  # Direct import
from core import LanguageEntry, Example  # Only import our classes

# Constants
ANKI_OUTPUT_DIR = Path("anki")
AUDIO_OUTPUT_DIR = ANKI_OUTPUT_DIR / "media"
ANKI_MODEL_ID = 1676138610  # Random but fixed number for consistent model ID

def parse_response(response: str) -> Tuple[str, str, List[Example]]:
    """
    Parses the Claude response into definition, translation and examples.
    
    Args:
        response (str): Raw response from Claude
        
    Returns:
        Tuple[str, str, List[Example]]: Dictionary form, translation and list of examples
    """
    # Split response into lines and filter out empty lines
    lines = [line.strip() for line in response.split('\n') if line.strip()]
    
    # First line contains the dictionary form and translation
    definition_line = lines[0]
    definition, translation = definition_line.split('|')
    
    # Remaining lines are examples
    examples = []
    for line in lines[1:]:
        if '|' in line:
            de, ru = line.split('|')
            examples.append(Example(
                de=de.strip(),
                ru=ru.strip()
            ))
    
    return definition.strip(), translation.strip(), examples

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
    First write a dictionary form of a word and its russian translation separated by |.
    Then provide 5 different simple usage examples of German Word and their Russian Translations.
    Examples should be short enough. Answer only with a list, without any explanations, sticking to a following format: Example | Translation.
    Don't use any line numbers."""
    
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
    definition, translation, examples = parse_response(response)
    
    # Get audio for the query word
    audio_file = get_audio(query)
    
    # Get audio for each example
    for example in examples:
        example.audio_file = get_audio(example.de)
        time.sleep(1)
    
    return LanguageEntry(
        query=query,
        definition=definition,
        translation=translation,
        examples=examples,
        audio_file=audio_file
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
            {'name': 'Audio'}
        ],
        templates=[
            {
                'name': 'German -> Definition + Examples',
                'qfmt': '''
                    {{German}}
                    <br>
                    {{#Audio}}
                    [sound:{{Audio}}]
                    {{/Audio}}
                ''',
                'afmt': '''
                    {{FrontSide}}
                    <hr>
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
    
    # List to store all media files
    media_files = []
    
    # Add notes to the deck
    for entry in entries:
        # Add main word audio to media files if it exists
        if entry.audio_file:
            media_files.append(str(AUDIO_OUTPUT_DIR / entry.audio_file))
        
        # Format examples as HTML with audio
        examples_html = []
        for ex in entry.examples:
            example_html = f"{ex.de}"
            if ex.audio_file:
                example_html += f" [sound:{ex.audio_file}]"
                media_files.append(str(AUDIO_OUTPUT_DIR / ex.audio_file))
            example_html += f"<br><i>{ex.ru}</i>"
            examples_html.append(example_html)
        
        note = genanki.Note(
            model=model,
            fields=[
                entry.query,
                entry.definition,
                '<br>'.join(examples_html),
                entry.audio_file or ''
            ]
        )
        deck.add_note(note)
    
    # Save the deck with media files
    output_path = ANKI_OUTPUT_DIR / f'{deck_name}.apkg'
    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(str(output_path))

def get_audio(text: str) -> Optional[str]:
    """
    Gets German audio for text using Amazon Polly.
    
    Args:
        text (str): Text to synthesize
        
    Returns:
        Optional[str]: Filename of the generated audio file, or None if failed
    """
    # Create output directory if it doesn't exist
    AUDIO_OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Create a unique filename based on the text content
    filename = hashlib.md5(text.encode('utf-8')).hexdigest() + '.mp3'
    output_path = AUDIO_OUTPUT_DIR / filename
    
    # Skip if file already exists
    if output_path.exists():
        return filename
    
    try:
        polly = boto3.client('polly')
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId='Vicki',  # German female voice
            LanguageCode='de-DE',
            Engine='neural'
        )
        
        # Save the audio file
        if "AudioStream" in response:
            with open(output_path, 'wb') as file:
                file.write(response['AudioStream'].read())
            print(f"✓ Successfully generated audio: {text} - {output_path}")
            return filename
            
    except Exception as e:
        print(f"⚠️ Error generating audio for '{text}': {str(e)}")
        print(f"Error Code: {e.response['Error']['Code']}")
        print(f"Error Message: {e.response['Error']['Message']}")
        print(f"Request ID: {e.response['ResponseMetadata']['RequestId']}")
        return None

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


