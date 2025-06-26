#!/bin/bash

# Fix encoding issues for docker-entrypoint.sh (Docker build version)
echo "🔧 Fixing docker-entrypoint.sh encoding issues during Docker build..."

# Check if docker-entrypoint.sh exists
if [ ! -f "docker-entrypoint.sh" ]; then
    echo "❌ docker-entrypoint.sh not found!"
    exit 1
fi

# Backup original file
cp docker-entrypoint.sh docker-entrypoint.sh.backup
echo "✅ Created backup: docker-entrypoint.sh.backup"

# Convert to Unix line endings and remove BOM
# Remove carriage returns manually (works in all environments)
sed -i 's/\r$//' docker-entrypoint.sh
echo "✅ Removed carriage returns"

# Remove UTF-8 BOM (EF BB BF) if present
sed -i '1s/^\xEF\xBB\xBF//' docker-entrypoint.sh
echo "✅ Removed UTF-8 BOM if present"

# Remove any other Unicode BOMs
sed -i '1s/^\xFF\xFE//' docker-entrypoint.sh  # UTF-16 LE BOM
sed -i '1s/^\xFE\xFF//' docker-entrypoint.sh  # UTF-16 BE BOM
echo "✅ Removed Unicode BOMs"

# Make executable
chmod +x docker-entrypoint.sh
echo "✅ Made docker-entrypoint.sh executable"

# Verify the shebang line
FIRST_LINE=$(head -n 1 docker-entrypoint.sh)
if echo "$FIRST_LINE" | grep -q "^#!/bin/bash$"; then
    echo "✅ Shebang line is correct: $FIRST_LINE"
else
    echo "⚠️  Warning: Shebang line might have issues"
    echo "First line: '$FIRST_LINE'"
    # Try to fix common shebang issues
    if echo "$FIRST_LINE" | grep -q "bash"; then
        sed -i '1s|.*|#!/bin/bash|' docker-entrypoint.sh
        echo "🔧 Fixed shebang line to: #!/bin/bash"
    fi
fi

# Final verification
if [ -x "docker-entrypoint.sh" ]; then
    echo "✅ docker-entrypoint.sh is executable"
else
    echo "❌ Failed to make docker-entrypoint.sh executable"
    exit 1
fi

echo ""
echo "🎉 Encoding fix complete! docker-entrypoint.sh is ready for Docker container." 