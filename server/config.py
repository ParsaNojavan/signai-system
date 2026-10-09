import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / "server" / ".env")


def get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


def get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value is not None else default


def get_env_required(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise RuntimeError(
            f"❌ متغیر محیطی حیاتی '{name}' تعریف نشده است! لطفاً آن را در فایل .env قرار دهید."
        )
    return value.strip()


@dataclass(frozen=True)
class Settings:
    # Paths
    base_dir: Path
    model_path: Path
    actions_file: Path
    training_dir: Path

    # Database
    database_url: str

    # Inference
    sequence_length: int
    input_size: int
    confidence_threshold: float
    margin_threshold: float
    max_frame_bytes: int
    model_complexity: int

    # Security
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int

    # App
    app_name: str
    app_version: str
    debug: bool

    # CORS
    allowed_origins: tuple[str, ...]


def load_settings() -> Settings:
    origins_raw = os.getenv(
        "ALLOWED_ORIGINS",
        "*,http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5500,http://127.0.0.1:5500",
    )
    allowed_origins = tuple(
        origin.strip()
        for origin in origins_raw.split(",")
        if origin.strip()
    )

    return Settings(
        base_dir=BASE_DIR,
        model_path=Path(
            os.getenv("MODEL_PATH", str(BASE_DIR / "models" / "best_model.pth"))
        ),
        actions_file=Path(
            os.getenv("ACTIONS_FILE", str(BASE_DIR / "dataset" / "actions.json"))
        ),
        training_dir=BASE_DIR / "training",

        database_url=get_env_required("DATABASE_URL"),

        sequence_length=get_env_int("SEQUENCE_LENGTH", 30),
        input_size=get_env_int("INPUT_SIZE", 218),
        confidence_threshold=get_env_float("CONFIDENCE_THRESHOLD", 0.75),
        margin_threshold=get_env_float("MARGIN_THRESHOLD", 0.15),
        max_frame_bytes=get_env_int("MAX_FRAME_BYTES", 2_000_000),
        model_complexity=get_env_int("MODEL_COMPLEXITY", 1),

        jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-this-in-production"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        access_token_expire_minutes=get_env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60),

        app_name=os.getenv("APP_NAME", "SignAI Server"),
        app_version=os.getenv("APP_VERSION", "1.0.0"),
        debug=get_env_bool("DEBUG", True),

        allowed_origins=allowed_origins,
    )


settings = load_settings()
