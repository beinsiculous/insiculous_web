"""Deterministic JSON reading/writing and well-known repository paths."""
import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = REPOSITORY_ROOT / "data"
SCHEMA_DIRECTORY = DATA_DIRECTORY / "schema"
MENUS_DIRECTORY = DATA_DIRECTORY / "menus"
SOURCE_DIRECTORY = REPOSITORY_ROOT / "source"


def read_json(path):
    with open(path, encoding="utf-8") as file_handle:
        return json.load(file_handle)


def dumps_json(value):
    """Serialize with stable formatting: 2-space indent, insertion order kept, trailing newline."""
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file_handle:
        file_handle.write(dumps_json(value))


EXAMPLES_DIRECTORY = REPOSITORY_ROOT / "examples"
WORKBOOK_EXAMPLE_DIRECTORY = EXAMPLES_DIRECTORY / "workbook"


def load_data_directory(data_directory=DATA_DIRECTORY, overlay_directory=None):
    """Load every canonical data file into one dictionary keyed by logical name.

    `data_directory` is the person-neutral canonical set (data/). `overlay_directory` (e.g.
    examples/workbook) is a sample set laid over it: a same-named file there replaces the
    canonical one, and its menus/*.json are added — how tests and demo builds see the workbook
    without data/ carrying anyone's schedule."""
    data_directory = Path(data_directory)
    overlay_directory = Path(overlay_directory) if overlay_directory else None

    def resolve(relative_path):
        if overlay_directory and (overlay_directory / relative_path).exists():
            return overlay_directory / relative_path
        return data_directory / relative_path

    loaded = {}
    for name in ("meta", "seasons", "days", "blocks", "categories", "activities"):
        loaded[name] = read_json(resolve(f"{name}.json"))
    loaded["menus"] = {}
    menu_directories = [data_directory / "menus"] + ([overlay_directory / "menus"] if overlay_directory else [])
    for menu_directory in menu_directories:
        for menu_path in sorted(menu_directory.glob("*.json")):
            menu = read_json(menu_path)
            loaded["menus"][menu["id"]] = menu
    questionnaire_path = resolve("questionnaire.json")
    loaded["questionnaire"] = read_json(questionnaire_path) if questionnaire_path.exists() else None
    weights_path = resolve("weights.baseline.json")
    loaded["weights"] = read_json(weights_path) if weights_path.exists() else None
    # Other weights files (questionnaire output dropped into data/) are validated but not bundled.
    loaded["weightsProfiles"] = {}
    for directory in [data_directory] + ([overlay_directory] if overlay_directory else []):
        for profile_path in sorted(directory.glob("weights.*.json")):
            if profile_path.name != "weights.baseline.json":
                profile = read_json(profile_path)
                loaded["weightsProfiles"][profile["id"]] = profile
    return loaded
