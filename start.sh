#!/usr/bin/env bash
# Quick-start script for local development (no Docker)
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Maritime Crew Orchestrator — Dev Start      ${NC}"
echo -e "${BLUE}══════════════════════════════════════════════${NC}"

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ] && [ ! -f backend/.env ]; then
    echo -e "${RED}ERROR: ANTHROPIC_API_KEY not set.${NC}"
    echo "Set it via: export ANTHROPIC_API_KEY=sk-ant-..."
    echo "Or create backend/.env from backend/.env.example"
    exit 1
fi

# ── Backend ────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}[1/3] Starting Backend...${NC}"
cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt -q

# Copy env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${RED}Created backend/.env — please add your ANTHROPIC_API_KEY${NC}"
fi

uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo -e "${GREEN}Backend started (PID: $BACKEND_PID) → http://localhost:8000${NC}"

cd ..

# ── Frontend ───────────────────────────────────────────────────────────────
echo -e "\n${GREEN}[2/3] Starting Frontend...${NC}"
cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing npm packages..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!
echo -e "${GREEN}Frontend started (PID: $FRONTEND_PID) → http://localhost:3000${NC}"

cd ..

echo -e "\n${BLUE}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Application running!${NC}"
echo -e "  Frontend:  http://localhost:3000"
echo -e "  Backend:   http://localhost:8000"
echo -e "  API Docs:  http://localhost:8000/docs"
echo -e "${BLUE}══════════════════════════════════════════════${NC}"
echo -e "\nPress Ctrl+C to stop all services"

# Wait and cleanup
trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
