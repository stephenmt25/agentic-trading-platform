# Safe System Shutdown Instructions

To safely shut down the Agentic Trading Platform and ensure no data corruption or dangling processes, follow these steps in order:

## 1. Stop the Frontend Server
If you are running the Next.js frontend, navigate to the terminal window where it is running (usually displaying `npm run dev`) and press **`Ctrl + C`**. 
Confirm the termination if prompted.

## 2. Stop the Python Microservices
The backend consists of several microservices running independently. You need to stop them one by one to ensure they close their connections safely. 

Navigate to each terminal window running a microservice and press **`Ctrl + C`** to send a keyboard interrupt. 

Wait for each service to log its shutdown sequence. You should stop them in the following order (though any order works, stopping the execution/hot-path first prevents any last-minute trades):
1. Execution Agent (`services.execution.src.main`)
2. Hot-Path Processor (`services.hot_path.src.main`)
3. PnL Service (`services.pnl.src.main`)
4. Validation Agent (`services.validation.src.main`)
5. Ingestion Engine (`services.ingestion.src.main`)
6. Strategy Agent (`services.strategy.src.main`)
7. API Gateway (`services.api_gateway.src.main`)
8. Logger Service (`services.logger.src.main`)

## 3. Stop the Redis Database
If you are running Redis via Docker (as per the `docker-compose.yml` or standard `docker run`), you can stop it with the following command in any terminal:

```bash
docker stop praxis-redis
```
*(If you didn't name your container `praxis-redis`, or used `docker-compose`, navigate to the `aion-trading` directory and run `docker-compose down` instead).*

## 4. Verification
To verify all Python processes have stopped, you can run the following command in PowerShell:
```powershell
Get-Process python -ErrorAction SilentlyContinue
```
If you still see processes related to the trading platform, you can forcefully terminate them (WARNING: this skips graceful shutdown):
```powershell
Stop-Process -Name python -Force
```

To verify the frontend port (3000 or 3001) is free:
```powershell
Get-NetTCPConnection -LocalPort 3000, 3001 -ErrorAction SilentlyContinue
```
