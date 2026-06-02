#!/bin/bash
#
# Deploy script for HeatSeek
#
# Usage:
#   ./deploy.sh [web-root-path]
#
# Examples:
#   ./deploy.sh /var/www/html
#   ./deploy.sh /usr/share/nginx/html
#   ./deploy.sh ~/public_html

set -e  # Exit on error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="heatseek.html"
DEFAULT_WEB_ROOT="/var/www/html"
TARGET_FILENAME="coverage.html"

# Check arguments
WEB_ROOT="${1:-$DEFAULT_WEB_ROOT}"

echo "=========================================="
echo "HeatSeek Deployment"
echo "=========================================="
echo ""

# Step 1: Activate virtualenv
echo "📦 Activating virtual environment..."
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "❌ Virtual environment not found. Creating one..."
    python3 -m venv "$SCRIPT_DIR/venv"
    source "$SCRIPT_DIR/venv/bin/activate"
    pip install -q -r "$SCRIPT_DIR/requirements.txt"
else
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Step 2: Check .env file
echo "🔐 Checking configuration..."
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "❌ Error: .env file not found!"
    echo "   Copy .env.example to .env and configure your OpenSearch credentials"
    echo "   cp .env.example .env"
    exit 1
fi

# Step 3: Generate visualization
echo "🔄 Generating coverage visualization..."
cd "$SCRIPT_DIR"
python3 visualize_test_coverage.py

if [ ! -f "$SCRIPT_DIR/$OUTPUT_FILE" ]; then
    echo "❌ Error: Failed to generate $OUTPUT_FILE"
    exit 1
fi

# Step 4: Deploy to web root
echo "🚀 Deploying to web server..."

if [ ! -d "$WEB_ROOT" ]; then
    echo "⚠️  Warning: Web root directory does not exist: $WEB_ROOT"
    echo "   Creating directory..."
    mkdir -p "$WEB_ROOT" || {
        echo "❌ Error: Cannot create directory. You may need sudo permissions."
        echo "   Try: sudo ./deploy.sh $WEB_ROOT"
        exit 1
    }
fi

# Copy file
cp "$SCRIPT_DIR/$OUTPUT_FILE" "$WEB_ROOT/$TARGET_FILENAME" || {
    echo "❌ Error: Cannot copy file to $WEB_ROOT"
    echo "   You may need sudo permissions."
    echo "   Try: sudo cp $SCRIPT_DIR/$OUTPUT_FILE $WEB_ROOT/$TARGET_FILENAME"
    exit 1
}

# Set permissions
chmod 644 "$WEB_ROOT/$TARGET_FILENAME" 2>/dev/null || true

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "File deployed to: $WEB_ROOT/$TARGET_FILENAME"
echo ""

# Try to detect web server and show URL
if [ -f "/etc/httpd/conf/httpd.conf" ] || [ -f "/etc/apache2/apache2.conf" ]; then
    echo "📊 View at: http://$(hostname)/$(basename $TARGET_FILENAME)"
elif [ -f "/etc/nginx/nginx.conf" ]; then
    echo "📊 View at: http://$(hostname)/$(basename $TARGET_FILENAME)"
else
    echo "📊 Access via your web server: /$(basename $TARGET_FILENAME)"
fi

echo ""
echo "💡 Tips:"
echo "   - Set up weekly regeneration: Add to crontab"
echo "   - Example cron (every Sunday 2am):"
echo "     0 2 * * 0 $SCRIPT_DIR/deploy.sh $WEB_ROOT"
echo ""
