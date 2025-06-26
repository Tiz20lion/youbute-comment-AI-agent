# PowerShell script to fix docker-entrypoint.sh encoding
Write-Host "🔧 Fixing docker-entrypoint.sh encoding issues..." -ForegroundColor Cyan

# Check if file exists
if (-not (Test-Path "docker-entrypoint.sh")) {
    Write-Host "❌ docker-entrypoint.sh not found!" -ForegroundColor Red
    exit 1
}

# Backup original
Copy-Item "docker-entrypoint.sh" "docker-entrypoint.sh.backup"
Write-Host "✅ Created backup" -ForegroundColor Green

try {
    # Read file content as bytes to handle encoding properly
    $bytes = [System.IO.File]::ReadAllBytes("docker-entrypoint.sh")
    
    # Convert bytes to string, handling BOM
    $content = [System.Text.Encoding]::UTF8.GetString($bytes)
    
    # Remove BOM if present
    if ($content.StartsWith([char]0xFEFF)) {
        $content = $content.Substring(1)
        Write-Host "✅ Removed UTF-8 BOM" -ForegroundColor Green
    }
    
    # Replace CRLF with LF (Windows to Unix line endings)
    $content = $content -replace "`r`n", "`n"
    $content = $content -replace "`r", "`n"
    Write-Host "✅ Fixed line endings" -ForegroundColor Green
    
    # Ensure proper shebang
    if (-not $content.StartsWith("#!/bin/bash")) {
        if ($content.StartsWith("#!")) {
            # Replace existing shebang
            $content = $content -replace "^#![^\n]*", "#!/bin/bash"
        } else {
            # Add shebang
            $content = "#!/bin/bash`n" + $content
        }
        Write-Host "✅ Fixed shebang" -ForegroundColor Green
    }
    
    # Write back with UTF-8 encoding without BOM
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText("docker-entrypoint.sh", $content, $utf8NoBom)
    
    Write-Host "✅ Encoding fixed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "🐳 Now rebuild your Docker image:" -ForegroundColor Yellow
    Write-Host "   docker build -t tiz20lion/youbute-comment-ai-agent:latest ." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "🚀 Then run:" -ForegroundColor Yellow
    Write-Host "   docker run -it --rm -p 8080:8080 --env-file .env tiz20lion/youbute-comment-ai-agent" -ForegroundColor Cyan
    
} catch {
    Write-Host "❌ Error fixing encoding: $_" -ForegroundColor Red
    exit 1
} 