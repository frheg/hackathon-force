import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile


def sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_json(path: Path, artifact: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        try:
            json.dump(artifact, f, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
