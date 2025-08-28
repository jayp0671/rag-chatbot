BACKEND:

Set-Location "C:\Users\JayVe\OneDrive - NJIT\Desktop\rag-chatbot"
.\.venv\Scripts\Activate.ps1
$env:DATA_DIR = "$PWD\data"
$env:INDEX_DIR = "$PWD\data\index"
Set-Location .\apps\api
uvicorn main:app --reload --host 0.0.0.0 --port 8000
# (fallback if 'uvicorn' not found)
# python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000


FRONTEND:

nvm use 20.19.0
Set-Location "C:\Users\JayVe\OneDrive - NJIT\Desktop\rag-chatbot\apps\web"
npm run dev
# (if first time on this machine)
# npm install && npm run dev
