# Port Allocation

> **环境**: 阿里 ECS Windows Server，不支持 Docker。所有服务以原生 Windows 进程方式运行。

Both tz-data and tz2.0 run on the same machine. Ports are allocated to avoid conflicts.

## Application Ports

| Service | Port | Notes |
|---------|------|-------|
| Backend API (FastAPI) | **8000** | `tzdata serve --port 8000` (default) |
| Frontend (Vite) | **3000** | `npm run dev` (proxies /api to 8000) |
| tzdata CLI serve | **8000** | Default in `__main__.py` |

## Shared Infrastructure

| Service | Port | Notes |
|---------|------|-------|
| Redis | 6379 | Celery broker/cache (shared with tz2.0) |
| QuestDB HTTP | 9000 | REST API + Web Console (shared with tz2.0) |
| QuestDB PG | 8812 | PostgreSQL Wire Protocol (shared with tz2.0) |
| QuestDB InfluxDB | 9009 | InfluxDB Line Protocol (shared with tz2.0) |

## Configuration Files

- `.env` - `BACKEND_PORT=8000`, `VITE_PORT=3000`
- `frontend/vite.config.js` - `server.port: 3000`, proxy target `localhost:8000`
- `src/tzdata_pkg/__main__.py` - `serve` command default `--port 8000`

## Port Manager

Run `port-manager.bat` from tz2.0 root (`C:\myspace\tz2.0\port-manager.bat`) to check all project ports and detect conflicts.
