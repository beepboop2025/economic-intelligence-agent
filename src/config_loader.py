"""
Configuration loader with .env file support
"""

import os
import yaml
from pathlib import Path


def _default_env_path() -> str:
    """Resolve .env relative to the project root (parent of src/)"""
    return str(Path(__file__).parent.parent / ".env")


def load_env_file(env_path: str = None) -> dict:
    """Load environment variables from .env file"""
    env_vars = {}
    env_file = Path(env_path) if env_path else Path(_default_env_path())

    if not env_file.exists():
        return env_vars
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Parse KEY=VALUE
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars


def setup_environment(env_path: str = None):
    """Load .env file and set environment variables"""
    env_vars = load_env_file(env_path)
    
    for key, value in env_vars.items():
        # Only set if not already set in environment
        if key not in os.environ and value:
            os.environ[key] = value
    
    return env_vars


def get_config_with_env(config_path: str = "config/settings.yaml") -> dict:
    """Load config and inject environment variables"""
    # First load .env file
    setup_environment()
    
    # Then load YAML config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Expand environment variables in config
    def expand_env_vars(obj):
        if isinstance(obj, str):
            # Handle ${VAR} syntax
            if obj.startswith('${') and obj.endswith('}'):
                env_var = obj[2:-1]
                return os.getenv(env_var, obj)
            # Handle $VAR syntax
            elif obj.startswith('$'):
                env_var = obj[1:]
                return os.getenv(env_var, obj)
            return obj
        elif isinstance(obj, dict):
            return {k: expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [expand_env_vars(item) for item in obj]
        return obj
    
    return expand_env_vars(config)


def check_api_keys() -> dict:
    """Check which API keys are available"""
    keys = {
        'OpenRouter': bool(os.getenv('OPENROUTER_KEY')),
        'OpenAI': bool(os.getenv('OPENAI_API_KEY')),
        'Anthropic': bool(os.getenv('ANTHROPIC_API_KEY')),
        'NewsAPI': bool(os.getenv('NEWSAPI_KEY')),
        'Alpha Vantage': bool(os.getenv('ALPHA_VANTAGE_KEY')),
        'ExchangeRate': bool(os.getenv('EXCHANGERATE_KEY')),
        'FRED': bool(os.getenv('FRED_API_KEY')),
        'Finnhub': bool(os.getenv('FINNHUB_KEY')),
    }
    return keys


def validate_config(config: dict) -> list:
    """Validate configuration and return list of warnings"""
    warnings = []

    # Check LLM config
    llm = config.get("llm", {})
    if not llm:
        warnings.append("No LLM configuration found")
    else:
        provider = llm.get("provider", "")
        if provider not in ("openrouter", "openai", "anthropic", "ollama"):
            warnings.append(f"Unknown LLM provider: {provider}")
        api_key = llm.get("api_key", "")
        if api_key and api_key.startswith("${"):
            warnings.append(f"LLM API key appears to be an unresolved template: {api_key}")

    # Check data sources
    ds = config.get("data_sources", {})
    for name, src in ds.items():
        if isinstance(src, dict) and src.get("enabled"):
            api_key = src.get("api_key", "")
            if api_key and isinstance(api_key, str) and api_key.startswith("${"):
                warnings.append(f"Data source '{name}' has unresolved API key template: {api_key}")

    # Check report config
    report = config.get("report", {})
    fmt = report.get("format", "markdown")
    if fmt not in ("markdown", "html", "json"):
        warnings.append(f"Unknown report format: {fmt}")

    return warnings


if __name__ == "__main__":
    # Test loading
    setup_environment()
    keys = check_api_keys()
    print("API Key Status:")
    for name, available in keys.items():
        status = "✅" if available else "❌"
        print(f"  {status} {name}")
