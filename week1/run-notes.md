1- open wsl terminal session
2- cd week1
3- activate venv : source venv/bin/activate
4- run uvicorn:
uvicorn main:app --reload --port 8000

http://localhost:8000/docs

streamlit run app.py --server.address 0.0.0.0 --server.port 8501
