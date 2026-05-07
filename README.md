# Coryl

Coryl is a small Python library for managing application resources from a single root folder.

It helps developers work with:

- configuration files
- runtime data files
- asset folders
- images, documents, and other bundled resources

## Goals

- keep every managed path inside a safe project root
- create missing files and folders when desired
- provide a clean API for text, JSON, and binary data
- stay compatible with a legacy `paths.files` / `paths.directories` manifest layout

## Quick Start

```python
from coryl import Coryl, ResourceSpec

app = Coryl(
    root=".",
    resources={
        "config": ResourceSpec.file("config/settings.json"),
        "assets": ResourceSpec.directory("assets"),
        "docs": ResourceSpec.directory("docs", create=False),
    },
)

app.write_content("config", {"theme": "light", "language": "it"})
settings = app.content("config")

logo = app.directory("assets").joinpath("images", "logo.png", create=False)
print(app.path("config"))
print(settings)
print(logo.path)
```

## Manifest Support

Coryl supports both a new `resources` format and your older schema.

Legacy format:

```json
{
  "paths": {
    "files": {
      "settings": "config/settings.json"
    },
    "directories": {
      "cache": "runtime/cache"
    }
  }
}
```

Modern format:

```json
{
  "resources": {
    "settings": {
      "path": "config/settings.json",
      "kind": "file"
    },
    "cache": {
      "path": "runtime/cache",
      "kind": "directory"
    }
  }
}
```

## Main API

- `Coryl(...)` or `ResourceManager(...)` creates a manager bound to one root folder.
- `register_file()` and `register_directory()` add resources programmatically.
- `content(name)` reads a resource automatically as JSON or text.
- `write_content(name, value)` writes JSON, text, or bytes.
- `directory(name).joinpath(...)` creates safe child resources inside managed folders.

## Migration Notes

If you are migrating from your older `FileManager`, these convenience aliases are available:

- `root_folder_path`
- `config_file_path`
- `config`
- `load_config()`
- `content()`
- `write_content()`
- dynamic attributes like `settings_file_path` and `cache_directory_path`
