import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import base64
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import datetime

load_dotenv()


def _debug_log(message: str) -> None:
    """Best-effort diagnostics that must never break app startup."""
    try:
        with open("debug_firebase.log", "a", encoding="utf-8") as f:
            f.write(message)
    except OSError:
        pass


def _write_temp_cred_file(json_str: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as tf:
        tf.write(json_str)
        return tf.name


def _resolve_credential_path(cred_path: str) -> Path | None:
    path = Path(cred_path).expanduser()
    candidates = [path] if path.is_absolute() else [
        Path.cwd() / path,
        Path(__file__).resolve().parents[2] / path,
        Path(__file__).resolve().parents[1] / path,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def initialize_firebase():
    """Initializes Firebase Admin SDK and returns Firestore client.

    Supports:
    - Environment variables containing raw or base64 JSON (`FIREBASE_CREDENTIALS_JSON` or `FIREBASE_CREDENTIAL_JSON`).
    - File paths (`FIREBASE_CREDENTIALS_PATH`, `serviceAccountKey.json`, or secret files in `/etc/secrets/`).
    """
    # 1. Check env vars containing the JSON string
    cred_json_env = os.getenv("FIREBASE_CREDENTIALS_JSON") or os.getenv("FIREBASE_CREDENTIAL_JSON")

    # 2. Check candidate file paths
    candidate_paths = []
    env_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if env_path:
        candidate_paths.append(env_path)
    
    # Add other common paths (including Render secret file paths)
    candidate_paths.extend([
        "serviceAccountKey.json",
        "/etc/secrets/FIREBASE_CREDENTIALS_JSON",
        "/etc/secrets/FIREBASE_CREDENTIAL_JSON",
        "FIREBASE_CREDENTIALS_JSON",
        "FIREBASE_CREDENTIAL_JSON",
        "backend/serviceAccountKey.json"
    ])

    resolved_cred_path = None
    for path in candidate_paths:
        resolved = _resolve_credential_path(path)
        if resolved:
            resolved_cred_path = resolved
            break

    _debug_log(
        f"\n--- {datetime.datetime.now()} ---\n"
        f"CWD: {os.getcwd()}\n"
        f"FIREBASE_CREDENTIALS_JSON (env set): {bool(os.getenv('FIREBASE_CREDENTIALS_JSON'))}\n"
        f"FIREBASE_CREDENTIAL_JSON (env set): {bool(os.getenv('FIREBASE_CREDENTIAL_JSON'))}\n"
        f"FIREBASE_CREDENTIALS_PATH: {env_path}\n"
        f"Resolved credentials file path: {resolved_cred_path or 'not found'}\n"
    )

    try:
        if not firebase_admin._apps:
            # Try env var first
            if cred_json_env:
                try:
                    # Try base64 decode first, fall back to raw JSON
                    decoded = None
                    try:
                        decoded_bytes = base64.b64decode(cred_json_env)
                        decoded_str = decoded_bytes.decode("utf-8")
                        # validate
                        json.loads(decoded_str)
                        decoded = decoded_str
                    except Exception:
                        # treat as raw JSON
                        json.loads(cred_json_env)
                        decoded = cred_json_env

                    temp_path = _write_temp_cred_file(decoded)
                    cred = credentials.Certificate(temp_path)
                    firebase_admin.initialize_app(cred)
                    print(f"Firebase initialized successfully from env var (temp file: {temp_path})")
                except Exception as e:
                    print(f"Failed to initialize Firebase from env var: {e}")
                    return None
            elif resolved_cred_path:
                cred = credentials.Certificate(str(resolved_cred_path))
                firebase_admin.initialize_app(cred)
                print(f"Firebase initialized successfully with file {resolved_cred_path}")
            else:
                print(f"WARNING: No Firebase credential file or environment variable found. Firebase not initialized.")
                return None

        # This part only runs if initialization succeeded or already existed
        return firestore.client()
    except Exception as e:
        print(f"Firebase Critical Error: {e}")
        return None


# Initialize on module load
db = initialize_firebase()
_debug_log(f"DB Object initialized: {db is not None}\n")
