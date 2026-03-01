#!/bin/bash
# Quickstart script for Economic Intelligence Agent

set -e

echo "🌍 Economic Intelligence Agent - Quickstart"
echo "============================================"
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""

# Check for API keys
if [ -z "$OPENROUTER_KEY" ] && [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️  WARNING: No LLM API key found!"
    echo ""
    echo "To use this agent, you need to set an API key:"
    echo ""
    echo "Option 1 - OpenRouter (recommended, free tier available):"
    echo "  export OPENROUTER_KEY='your_key_here'"
    echo "  Get key: https://openrouter.ai/"
    echo ""
    echo "Option 2 - OpenAI:"
    echo "  export OPENAI_API_KEY='your_key_here'"
    echo ""
    echo "Option 3 - Anthropic:"
    echo "  export ANTHROPIC_API_KEY='your_key_here'"
    echo ""
    echo "Or edit the .env file:"
    echo "  cp .env.example .env"
    echo "  # Then edit .env with your keys"
    echo ""
    exit 1
fi

echo "🔑 API key detected!"
echo ""
echo "🚀 Running your first analysis..."
echo ""

# Run the agent
python src/main.py "$@"
