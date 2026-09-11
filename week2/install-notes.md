## 1. activate venv from week1

source ../week1/venv/bin/activate

## 2. install packages from requirements.txt

pip install -r requirements.txt

## 3. run the app

docker run -p 6333:6333 -p 6334:6334 -v /qdrant_storage:/qdrant/storage:z qdrant/qdrant

Or

docker-compose up -d

http://localhost:6333/dashboard

uvicorn main:app --reload --host [IP_ADDRESS] --port 8000
