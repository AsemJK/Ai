## docker qdrant

docker run -d --name qdrant --restart unless-stopped -p 6333:6333 -p 6334:6334 -v D:\\qdrant_storage:/qdrant/storage qdrant/qdrant
docker run -d --name qdrant --restart unless-stopped -p 6333:6333 -p 6334:6334 -v C:\\qdrant_storage:/qdrant/storage qdrant/qdrant

### check if it is running

docker ps

### start qdrant

docker start qdrant

### stop qdrant

docker stop qdrant

## run backend

1- open wsl terminal session
2- cd week1
3- activate venv : source venv/bin/activate
4- run backend using uvicorn:
uvicorn main:app --reload --port 8000

## one command to run backend

```bash
cd /mnt/c/dev/learning/ai/week1 && source venv/bin/activate && uvicorn main:app --reload --port 8000
```

or without --reload flag

```bash
cd /mnt/c/dev/learning/ai/week1 && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000
```

_If the address already in use error_
**linux**
sudo lsof -t -i tcp:8000 | xargs kill -9
**windows**
netstat -ano | findstr :8000
taskkill /PID <PID> /F

http://localhost:8000/docs

### Streamlit Notes

streamlit running on wsl in my case so I need to make sure that the port 8501 is open for the windows host machine to access it.
I am using tailscale on windows so:

1. connectaddress=172.21.200.76 : this will make wsl machine with static ip
2. I need need a Windows port proxy
   so run this in windows powershell with admin rights

   netsh interface portproxy add v4tov4 `    
listenaddress=[IP_ADDRESS]`
   listenport=8501 `    
connectaddress=172.21.200.76`
   connectport=8501

now I can access streamlit on [IP_ADDRESS]

## example when use tailscale

```bash
wsl -d ubuntu
```

```bash
hostname -I
```

**output**

```bash
172.21.200.76
```

**connect using wsl ip on windows browser**
[IP_ADDRESS]

3. In Windows Host Machine PowerShell (run as Administrator):

```powershell
netsh interface portproxy add v4tov4 listenport=8501 listenaddress=0.0.0.0 connectport=8501 connectaddress=172.21.200.76
```

run UI using streamlit:

## on command to run streamlit

```bash
cd /mnt/c/dev/learning/ai/week1 && source venv/bin/activate && streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

3. Then allow the port through Windows Firewall

New-NetFirewallRule `    -DisplayName "Streamlit via Tailscale"`
-Direction Inbound `    -Protocol TCP`
-LocalPort 8501 `
-Action Allow

4. open http://[IP_ADDRESS] in windows browser

### Another approach for WSL2/Docker Access

To make WSL2/Docker services accessible from Windows, you need to:

1.  **Assign a Static IP to WSL2** (in WSL/Ubuntu):

    ```powershell
    # Add static IP to WSL
    ip addr add [IP_ADDRESS] dev eth0 label eth0:0
    # Make it persistent
    echo 'pre-up ip addr add [IP_ADDRESS] dev eth0 label eth0:0' | sudo tee -a /etc/network/interfaces.d/eth0:0
    ```

2.  **Add Windows Port Proxy** (Run in PowerShell as Admin):

    ```powershell
    netsh interface portproxy add v4tov4 listenaddress=[IP_ADDRESS] listenport=8000 connectaddress=[IP_ADDRESS] connectport=8000
    netsh interface portproxy add v4tov4 listenaddress=[IP_ADDRESS] listenport=8501 listenport=8000 connectaddress=[IP_ADDRESS] connectport=8501
    ```

3.  **Allow Firewall** (Run in PowerShell as Admin):

    ```powershell
    New-NetFirewallRule -DisplayName "WSL Port 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
    New-NetFirewallRule -DisplayName "WSL Port 8501" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow
    ```

## Agentic notes

1. Agentic workflow: A workflow where an AI agent makes decisions and takes actions to complete a task.
2. LangGraph: A library for building stateful, multi-agent workflows.
3. StateGraph: A graph that represents the state of the agent.
4. Nodes: Nodes in the graph represent the actions that the agent can take.
5. Edges: Edges in the graph represent the flow of control between nodes.
6. Conditional edges: Edges that are taken based on the state of the agent.

Available tools:

- "rag": Use this for questions about documents, policies, procedures, or any information that would be in uploaded files.
- "sql": Use this for questions about server inventory, GPU counts, rack status, temperatures, power usage, or any structured data center data.
- "calculator": Use this for pure math questions.
- "direct": Use this for general greetings or questions that don't need any tool.
