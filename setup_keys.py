#!/usr/bin/env python3
"""
Setup script for API keys
Helps configure API keys for the Economic Intelligence Agent
"""

import os
import sys
from pathlib import Path


def print_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60 + "\n")


def check_existing_keys():
    """Check which API keys are already configured"""
    keys = {
        'OPENROUTER_KEY': os.getenv('OPENROUTER_KEY'),
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
        'NEWSAPI_KEY': os.getenv('NEWSAPI_KEY'),
        'ALPHA_VANTAGE_KEY': os.getenv('ALPHA_VANTAGE_KEY'),
        'EXCHANGERATE_KEY': os.getenv('EXCHANGERATE_KEY'),
    }
    return {k: bool(v) for k, v in keys.items()}


def load_env_file():
    """Load existing .env file"""
    env_path = Path('.env')
    if env_path.exists():
        env_vars = {}
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        return env_vars
    return {}


def save_env_file(env_vars):
    """Save API keys to .env file"""
    # Read existing template
    template_path = Path('.env')
    if template_path.exists():
        with open(template_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = []
    
    # Update with new values
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key = stripped.split('=', 1)[0].strip()
            if key in env_vars:
                new_lines.append(f"{key}={env_vars[key]}\n")
                continue
        new_lines.append(line)
    
    # Write back
    with open('.env', 'w') as f:
        f.writelines(new_lines)
    
    print("✅ API keys saved to .env file\n")


def setup_llm_key():
    """Guide user through LLM API key setup"""
    print_header("LLM API KEY SETUP (Required for AI Analysis)")
    
    print("You need an API key from an LLM provider to enable AI analysis.")
    print("Choose your preferred provider:\n")
    print("1. OpenRouter (RECOMMENDED) - Free tier, access to multiple models")
    print("   URL: https://openrouter.ai/")
    print("   Pros: Free credits, Claude/GPT access, no credit card needed")
    print()
    print("2. OpenAI - GPT-4 models")
    print("   URL: https://platform.openai.com/")
    print("   Pros: Best reasoning, fast")
    print("   Cons: Requires payment method")
    print()
    print("3. Anthropic - Claude models")
    print("   URL: https://console.anthropic.com/")
    print("   Pros: Excellent analysis, large context")
    print("   Cons: Requires payment method")
    print()
    print("4. Skip for now (run in demo mode)")
    print()
    
    choice = input("Enter your choice (1-4): ").strip()
    
    env_vars = load_env_file()
    
    if choice == '1':
        print("\n1. Go to https://openrouter.ai/")
        print("2. Sign up for a free account")
        print("3. Get your API key from the dashboard")
        print()
        key = input("Enter your OpenRouter API key: ").strip()
        if key:
            env_vars['OPENROUTER_KEY'] = key
            save_env_file(env_vars)
            return True
    
    elif choice == '2':
        print("\n1. Go to https://platform.openai.com/")
        print("2. Create an account and add payment method")
        print("3. Get your API key from the dashboard")
        print()
        key = input("Enter your OpenAI API key: ").strip()
        if key:
            env_vars['OPENAI_API_KEY'] = key
            save_env_file(env_vars)
            return True
    
    elif choice == '3':
        print("\n1. Go to https://console.anthropic.com/")
        print("2. Create an account and add payment method")
        print("3. Get your API key from the dashboard")
        print()
        key = input("Enter your Anthropic API key: ").strip()
        if key:
            env_vars['ANTHROPIC_API_KEY'] = key
            save_env_file(env_vars)
            return True
    
    elif choice == '4':
        print("\n⚠️  You'll need to set up an API key later for live analysis.")
        print("   The agent will run in demo mode for now.")
        return False
    
    print("\n❌ Invalid choice. Please run setup again.")
    return False


def setup_optional_keys():
    """Guide user through optional API key setup"""
    print_header("OPTIONAL DATA SOURCE KEYS")
    
    print("These keys enhance data quality but are NOT required.")
    print("The agent works with free data sources (CoinGecko, etc.)\n")
    
    env_vars = load_env_file()
    
    print("1. NewsAPI (100 requests/day FREE)")
    print("   Get news articles for analysis")
    print("   URL: https://newsapi.org/")
    
    add_newsapi = input("\nAdd NewsAPI key? (y/n): ").strip().lower()
    if add_newsapi == 'y':
        key = input("Enter NewsAPI key: ").strip()
        if key:
            env_vars['NEWSAPI_KEY'] = key
    
    print("\n2. Alpha Vantage (25 requests/day FREE)")
    print("   Get stock market data")
    print("   URL: https://www.alphavantage.co/support/#api-key")
    
    add_alpha = input("\nAdd Alpha Vantage key? (y/n): ").strip().lower()
    if add_alpha == 'y':
        key = input("Enter Alpha Vantage key: ").strip()
        if key:
            env_vars['ALPHA_VANTAGE_KEY'] = key
    
    save_env_file(env_vars)


def test_configuration():
    """Test if the configuration works"""
    print_header("TESTING CONFIGURATION")
    
    # Reload .env
    from src.config_loader import setup_environment
    setup_environment()
    
    # Check keys
    llm_keys = [
        ('OPENROUTER_KEY', 'OpenRouter'),
        ('OPENAI_API_KEY', 'OpenAI'),
        ('ANTHROPIC_API_KEY', 'Anthropic'),
    ]
    
    has_llm = False
    for env_var, name in llm_keys:
        if os.getenv(env_var):
            print(f"✅ {name}: Configured")
            has_llm = True
    
    if not has_llm:
        print("⚠️  No LLM provider configured (demo mode only)")
    
    print()
    
    data_keys = [
        ('NEWSAPI_KEY', 'NewsAPI'),
        ('ALPHA_VANTAGE_KEY', 'Alpha Vantage'),
    ]
    
    for env_var, name in data_keys:
        if os.getenv(env_var):
            print(f"✅ {name}: Configured")
        else:
            print(f"⚠️  {name}: Not configured (optional)")
    
    print()
    
    if has_llm:
        print("✅ Ready to run with AI analysis!")
        print("   Run: python src/main.py")
    else:
        print("⚠️  Running in demo mode (no AI analysis)")
        print("   Run: python src/demo.py")


def main():
    print_header("ECONOMIC INTELLIGENCE AGENT - API KEY SETUP")
    
    # Check if .env exists
    if not Path('.env').exists():
        print("Creating .env file from template...")
        if Path('.env.example').exists():
            import shutil
            shutil.copy('.env.example', '.env')
        else:
            print("❌ .env.example not found!")
            sys.exit(1)
    
    # Check existing keys
    existing = check_existing_keys()
    has_llm = existing.get('OPENROUTER_KEY') or existing.get('OPENAI_API_KEY') or existing.get('ANTHROPIC_API_KEY')
    
    if has_llm:
        print("✅ LLM API key already configured!")
        show = input("\nShow configuration status? (y/n): ").strip().lower()
        if show == 'y':
            test_configuration()
        
        change = input("\nChange API key? (y/n): ").strip().lower()
        if change != 'y':
            print("\n✅ Setup complete!")
            print("   Run: python src/main.py")
            return
    
    # Setup LLM key
    setup_llm_key()
    
    # Setup optional keys
    add_optional = input("\nAdd optional data source keys? (y/n): ").strip().lower()
    if add_optional == 'y':
        setup_optional_keys()
    
    # Test configuration
    test_configuration()
    
    print("\n" + "="*60)
    print("✅ SETUP COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Run analysis: python src/main.py")
    print("  2. Run demo: python src/demo.py")
    print("  3. Edit .env anytime to change keys")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Setup cancelled")
        sys.exit(0)
