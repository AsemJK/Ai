1- open wsl terminal session
2- cd week1
3- activate venv : source venv/bin/activate
4- run uvicorn:
uvicorn main:app --reload --port 8000

http://localhost:8000/docs

streamlit run app.py --server.address 0.0.0.0 --server.port 8501

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
