import argparse
import json
import os
import tempfile
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def render(output: Path) -> Path:
    names = (
        "KEYCLOAK_ADMIN_PASSWORD",
        "MCP_ALLOWED_USER_PASSWORD",
        "MCP_NO_ROLE_USER_PASSWORD",
    )
    values = {}
    for name in names:
        value = os.environ.get(name)
        if not value or not value.strip():
            raise ValueError(f"{name} must be configured and nonempty")
        values[name] = value
    source = Path(__file__).with_name("realm-template.json")
    realm = json.loads(source.read_text())
    realm_name = os.getenv("KEYCLOAK_REALM", "mcp-realm")
    role = os.getenv("MCP_REQUIRED_ROLE", "mcp-user")
    audience = os.getenv("MCP_AUDIENCE", "mcp-users")
    client_id = os.getenv("MCP_CLIENT_ID", "mcp-client")
    realm["realm"] = realm_name
    realm["roles"]["realm"][0]["name"] = role
    client = realm["clients"][0]
    client["clientId"] = client_id
    client["protocolMappers"][0]["config"]["included.custom.audience"] = audience
    for user, name in zip(realm["users"], names[1:], strict=True):
        user["realmRoles"] = [role] if user["username"] == "allowed-user" else []
        user["credentials"] = [
            {"type": "password", "value": values[name], "temporary": False}
        ]
    output = output.absolute()
    if output.parent.is_symlink():
        raise ValueError("Output directory must not be a symbolic link")
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.parent.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".realm-", dir=output.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(realm, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, output)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return output


def main():
    load_dotenv(find_dotenv(usecwd=True), override=False)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("runtime") / "mcp-realm.json",
    )
    arguments = parser.parse_args()
    try:
        render(arguments.output)
    except ValueError as error:
        parser.exit(2, f"{error}\n")
    except (OSError, KeyError, TypeError):
        parser.exit(2, "Unable to render realm configuration\n")


if __name__ == "__main__":
    main()
