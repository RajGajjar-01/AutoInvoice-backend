@echo off
echo ============================================
echo   AutoInvoice Backend Shutdown
echo ============================================
echo.
echo Stopping Docker database (volumes are kept, your data is safe)...
docker compose down
echo.
echo Done! Database stopped. Run start.bat to start again.
echo.
echo NOTE: If you want to WIPE all data and start fresh, run:
echo       docker compose down -v
echo.
pause
