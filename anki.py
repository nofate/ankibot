import genanki
import io
import random
import boto3
import os
import tempfile
import shutil
from jinja2 import Environment, Template
from dotenv import load_dotenv

load_dotenv()

# Constants
AUDIO_BUCKET = os.environ.get('AUDIO_BUCKET')

# Card template
EXAMPLES_TEMPLATE = """
<ul>
{% for example in examples %}
    <li>
        {{ example.de }}<br>
        {{ example.ru }}
        {% if example.audio_file %}
        <br>[sound:{{ example.audio_file }}]
        {% endif %}
    </li>
{% endfor %}
</ul>
"""

# Initialize Jinja2 template
card_template = Template(EXAMPLES_TEMPLATE)

# Define note model
MODEL = genanki.Model(
    1607392319,
    'German Word',
    fields=[
        {'name': 'Word'},
        {'name': 'Definition'},
        {'name': 'Translation'},
        {'name': 'Examples'},
        {'name': 'Audio'}
    ],
    templates=[{
        'name': 'Card 1',
        'qfmt': '{{Word}}<br>{{Audio}}',
        'afmt': '''
            {{FrontSide}}
            <hr id="answer">
            <b>{{Definition}}</b><br>
            <i>{{Translation}}</i><br>
            <br>
            {{Examples}}
        '''
    }]
)

def download_media_files(entries, temp_dir):
    """Download all media files for entries to a temporary directory"""
    media_filenames = []  # Just filenames, not full paths
    s3 = boto3.client('s3')

    for entry in entries:
        if entry.get('audio_file'):
            filename = entry['audio_file']
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'wb') as f:
                s3.download_fileobj(
                    AUDIO_BUCKET,
                    f"audio/{filename}",
                    f
                )
            media_filenames.append(filename)  # Add just the filename

        for example in entry.get('examples', []):
            if example.get('audio_file'):
                filename = example['audio_file']
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, 'wb') as f:
                    s3.download_fileobj(
                        AUDIO_BUCKET,
                        f"audio/{filename}",
                        f
                    )
                media_filenames.append(filename)  # Add just the filename

    return media_filenames

def create_anki_deck(entries):
    """Create an Anki deck from language entries"""
    try:
        print(f"Starting deck creation with {len(entries)} entries")
        print(f"Using audio bucket: {AUDIO_BUCKET}")

        # Create temporary directory for media files
        temp_dir = tempfile.mkdtemp()
        try:
            # Create Anki deck
            deck_id = random.randrange(1 << 30, 1 << 31)
            deck = genanki.Deck(
                deck_id=deck_id,
                name='German Vocabulary'
            )

            # Add notes to deck
            for entry in entries:
                # Generate examples HTML using template
                examples_html = card_template.render(examples=entry.get('examples', []))

                # Create note
                fields = [
                    entry.get('query', ''),
                    entry.get('definition', ''),
                    entry.get('translation', ''),
                    examples_html,
                    f'[sound:{entry["audio_file"]}]' if entry.get('audio_file') else ''
                ]

                note = genanki.Note(
                    model=MODEL,
                    fields=fields
                )
                deck.add_note(note)

            # Download all media files to temp directory and get filenames
            media_filenames = download_media_files(entries, temp_dir)

            # Create package
            package = genanki.Package(deck)
            
            # Set media files with full paths for writing
            package.media_files = [os.path.join(temp_dir, f) for f in media_filenames]

            # Write to temporary file first
            temp_file = tempfile.NamedTemporaryFile(suffix='.apkg', delete=False)
            package.write_to_file(temp_file.name)

            # Read the file into memory
            with open(temp_file.name, 'rb') as f:
                package_data = f.read()

            # Clean up temp file
            os.unlink(temp_file.name)

            # Return as BytesIO
            package_buf = io.BytesIO(package_data)
            print("Deck creation completed successfully")
            return package_buf

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir)

    except Exception as e:
        print(f"Error in create_anki_deck: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    from core import LanguageEntry
    
    # Load environment variables

    
    # Verify environment
    if not AUDIO_BUCKET:
        print("Error: AUDIO_BUCKET environment variable is not set")
        exit(1)
        
    try:
        print(f"Using audio bucket: {AUDIO_BUCKET}")
        
        # Get all entries from DynamoDB
        entries = LanguageEntry.get_table().scan().get('Items', [])
        
        if not entries:
            print("No entries found in DynamoDB")
            exit(1)
            
        print(f"Found {len(entries)} entries in DynamoDB")
        
        # Create deck
        deck_buf = create_anki_deck(entries)
        
        # Save to file
        with open('test_deck.apkg', 'wb') as f:
            f.write(deck_buf.getvalue())
            
        print("\nTest deck saved as 'test_deck.apkg'")
        
    except Exception as e:
        print(f"Test failed: {str(e)}") 