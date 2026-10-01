"""Single source of item and image identifiers, shared with the Watch bundle."""
import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).resolve().parents[2] / 'watch/HabitPet/Assets/catalog.json').read_text())
ITEMS = {item['id']: item for item in CATALOG['items']}
