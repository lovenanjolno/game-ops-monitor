# 诊断：检查当前跑的代码到底是不是新版本
Write-Host "=== 检查 detail_panel.py 是不是新版 ===" -ForegroundColor Cyan
$path = "src\gui\widgets\detail_panel.py"
if (Test-Path $path) {
    $content = Get-Content $path -Raw
    if ($content -match "font-size: 13px") {
        Write-Host "✅ 新版（v0.6.3）" -ForegroundColor Green
    } elseif ($content -match "setMinimumWidth\(56\)") {
        Write-Host "❌ 旧版（v0.6.0/v0.6.1），需要更新" -ForegroundColor Red
    } else {
        Write-Host "❓ 未知版本" -ForegroundColor Yellow
    }
    
    # 看修改时间
    $ft = (Get-Item $path).LastWriteTime
    Write-Host "   修改时间: $ft" -ForegroundColor Gray
} else {
    Write-Host "❌ 文件不存在" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== 检查 main_window.py 标题 ===" -ForegroundColor Cyan
$path = "src\gui\main_window.py"
if (Test-Path $path) {
    $line = Select-String -Path $path -Pattern "setWindowTitle" | Select-Object -First 1
    Write-Host "   $line" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=== 检查 __pycache__ 缓存 ===" -ForegroundColor Cyan
$pycs = Get-ChildItem -Path . -Include "*.pyc" -Recurse -File -ErrorAction SilentlyContinue
Write-Host "   .pyc 缓存文件数: $($pycs.Count)" -ForegroundColor Gray
