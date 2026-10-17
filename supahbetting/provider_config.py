"""Local, extensible provider credentials (JSON). Never serialize secrets via API.

Every integration reads its own entry from the same file:
    .supahbetting/providers.json
    {"providers": {"football-data": {"api_key": "..."}}}

The file lives outside Git and is created with restrictive permissions where
the operating system supports them. Environment keys remain a fallback for
existing automated deployments. A config entry alone never enables a new
third-party integration: its adapter must be implemented and audited separately.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Mapping

DEFAULT_CONFIG = Path(".supahbetting") / "providers.json"
MAX_CONFIG_BYTES = 32 * 1024
MAX_KEY_LENGTH = 512
PROVIDER_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")

# This is the exact template copied on first run; all credential fields are empty.
EMPTY_CONFIG = {
    "_uitleg": (
        "Vul je API-sleutels alleen op deze computer in. "
        "De sleutel is lokaal, niet versleuteld; deel dit bestand niet. "
        "Nieuwe providers krijgen een eigen naam onder 'providers' en "
        "een eigen adapter in SupahBetting. Herstart na aanpassen."
    ),
    "providers": {
        "football-data": {
            "api_key": ""
        }
    }
}


class ProviderConfigError(ValueError):
    """Safe, non-secret-bearing user-facing config error."""


def make_local_config(path=DEFAULT_CONFIG):
    """Create a blank config *only if absent*; never replace user's secrets.

    os.open O_EXCL ensures simultaneous app launches cannot clobber data.
    On POSIX the new file uses permission 0600 regardless of permissive umask.
    On Windows file access follows the user's inherited directory ACLs.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(EMPTY_CONFIG, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    except OSError:
        # If the newly created file cannot be written, keep no broken template.
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return True


def _read_provider_entries(path):
    path = Path(path)
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return {}
    except OSError:
        raise ProviderConfigError(
            "API-configuratie kan niet worden gelezen. Controleer bestandsrechten."
        ) from None
    if size > MAX_CONFIG_BYTES:
        raise ProviderConfigError(
            "API-configuratie is te groot (maximaal 32 KB)."
        )
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, UnicodeError, ValueError):
        # Avoid echoing JSON contents and accidental credential strings.
        raise ProviderConfigError(
            "API-configuratie bevat ongeldige JSON of is niet leesbaar. "
            "Controleer haakjes, komma's en dubbele aanhalingstekens."
        ) from None
    if not isinstance(data, dict) or not isinstance(data.get("providers"), dict):
        raise ProviderConfigError(
            "API-configuratie vereist een 'providers'-object."
        )
    result = {}
    for provider, entry in data["providers"].items():
        if not isinstance(provider, str) or not PROVIDER_NAME.fullmatch(provider):
            raise ProviderConfigError(
                "API-configuratie bevat een ongeldige providernaam."
            )
        if not isinstance(entry, dict):
            raise ProviderConfigError(
                "API-configuratie: iedere provider moet een object zijn."
            )
        key = entry.get("api_key", "")
        if not isinstance(key, str) or len(key) > MAX_KEY_LENGTH or any(
            ord(char) < 32 or ord(char) == 127 for char in key
        ):
            raise ProviderConfigError(
                "API-configuratie: een sleutel moet tekst van maximaal 512 tekens zijn, "
                "zonder regelafbrekingen."
            )
        result[provider] = key.strip()
    return result


def get_api_key(provider, *, config_path=DEFAULT_CONFIG, env_var=None, environ=None):
    """Provider-specific lookup; local file overrides legacy env when nonempty.

    Unknown providers return an empty credential until their adapter is built.
    No secret is ever put in return errors or logging.
    """
    if not isinstance(provider, str) or not PROVIDER_NAME.fullmatch(provider):
        raise ProviderConfigError("Ongeldige providernaam.")
    entries = _read_provider_entries(config_path)
    key = entries.get(provider, "")
    if key:
        return key
    if env_var is None:
        return ""
    if not isinstance(env_var, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,79}", env_var):
        raise ProviderConfigError("Ongeldige omgevingsvariabele.")
    environment = environ if environ is not None else os.environ
    raw = environment.get(env_var, "")
    if not isinstance(raw, str) or len(raw) > MAX_KEY_LENGTH or any(
        ord(char) < 32 or ord(char) == 127 for char in raw
    ):
        # Do not echo the offending value.
        raise ProviderConfigError("Ongeldige API-sleutel in omgevingsvariabele.")
    return raw.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Maak of open de lokale SupahBetting API-instellingen."
    )
    parser.add_argument("--edit", action="store_true", help="Open bestand in Kladblok op Windows")
    parser.add_argument("--file", type=Path, default=DEFAULT_CONFIG, help="Lokaal bestandspad")
    args = parser.parse_args()
    try:
        created = make_local_config(args.file)
        print("API-configuratie: " + str(args.file.resolve()))
        print("Nieuw configuratiebestand aangemaakt." if created
              else "Bestaand configuratiebestand behouden.")
        print("Vul de api_key in bij providers > football-data.")
        print("Sluit SupahBetting en start opnieuw nadat je het bestand hebt aangepast.")
        if args.edit:
            if os.name == "nt":
                subprocess.run(["notepad.exe", str(args.file.resolve())], check=False)
            else:
                print("Open bovenstaande JSON in een teksteditor.")
    except OSError:
        print("Kon geen lokaal configuratiebestand aanmaken. Controleer maprechten.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
