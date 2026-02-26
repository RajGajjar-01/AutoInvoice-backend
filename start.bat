@echo off
echo ============================================
echo   AutoInvoice Backend Startup
echo ============================================
echo.

REM --- Step 1: Start the PostgreSQL database via Docker Compose ---
echo [1/3] Starting PostgreSQL database (Docker)...
docker compose up -d
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Failed to start Docker. Make sure Docker Desktop is running!
    pause
    exit /b 1
)

REM --- Step 2: Wait for PostgreSQL to be ready (health check) ---
echo [2/3] Waiting for database to be ready...
set RETRIES=30
:wait_loop
docker compose ps db | findstr "healthy" >nul 2>&1
if %ERRORLEVEL% EQU 0 goto db_ready
set /a RETRIES-=1
if %RETRIES% EQU 0 (
    echo.
    echo ERROR: Database did not become healthy in time.
    echo Try running: docker compose logs db
    pause
    exit /b 1
)
echo     Still waiting... (%RETRIES% retries left)
timeout /t 2 /nobreak >nul
goto wait_loop

:db_ready
echo     Database is ready!
echo.

REM --- Step 3: Start FastAPI ---
echo [3/3] Starting FastAPI backend...
echo     The app will auto-create all database tables on first run.
echo     API docs available at: http://localhost:8000/docs
echo.
echo Press CTRL+C to stop the backend (then run stop.bat to shut down Docker).
echo.

REM Activate virtual environment and run uvicorn
call .venv\Scripts\activate.bat
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
