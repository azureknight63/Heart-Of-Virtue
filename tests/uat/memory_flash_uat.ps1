# UAT Quick Launch Script for Memory Flash System
# Run this to test the memory flash feature

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Memory Flash System - UAT" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Choose testing mode:`n" -ForegroundColor Yellow

Write-Host "1. Quick Demo (Standalone memory flash only - 2 minutes)" -ForegroundColor Green
Write-Host "2. Full Integration Test (Play through to trigger point - 10-15 minutes)" -ForegroundColor Green
Write-Host "3. Exit`n" -ForegroundColor Gray

$choice = Read-Host "Enter choice (1-3)"

switch ($choice) {
    "1" {
        Write-Host "`nLaunching standalone memory flash demo..." -ForegroundColor Cyan
        Write-Host "This will show you the memory sequence without playing the game.`n" -ForegroundColor White
        python run_uat_memory.py
    }
    "2" {
        Write-Host "`nLaunching full game..." -ForegroundColor Cyan
        Write-Host "`nInstructions:" -ForegroundColor Yellow
        Write-Host "1. Create a new character or load a save" -ForegroundColor White
        Write-Host "2. Navigate to the chest room (starting area, go east twice)" -ForegroundColor White
        Write-Host "3. Open the wooden chest to trigger Rock Rumbler battle" -ForegroundColor White
        Write-Host "4. Defeat the first Rock Rumbler" -ForegroundColor White
        Write-Host "5. Memory flash will trigger automatically after victory`n" -ForegroundColor White
        
        Read-Host "Press Enter to start game"
        python src/game.py
    }
    "3" {
        Write-Host "Exiting...`n" -ForegroundColor Gray
        exit
    }
    default {
        Write-Host "Invalid choice. Exiting.`n" -ForegroundColor Red
        exit
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "UAT Session Complete" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Please provide feedback on:" -ForegroundColor Yellow
Write-Host "- Animation quality and visual appeal" -ForegroundColor White
Write-Host "- Memory text readability and emotional impact" -ForegroundColor White
Write-Host "- Pacing and timing" -ForegroundColor White
Write-Host "- Integration with gameplay flow" -ForegroundColor White
Write-Host "- Any bugs or issues encountered`n" -ForegroundColor White
