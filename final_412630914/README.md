# 期末實作 — <學號> <姓名>

## 1. 架構總覽
<Mermaid 圖 + 一段話說明>
```mermaid
graph LR
    User[User/Browser] -->|8080| App[Flask App Container]
    App -->|Internal| DB[(PostgreSQL Container)]
    App -.->|Healthcheck| DB
    subgraph Docker Network
    App
    DB
    end
    subgraph Volumes
    DB_Data[db-data]
    end
    DB --- DB_Data
```
採用 Flask 應用程式作為前端，PostgreSQL 作為資料存儲，透過 Docker Compose 定義容器間橋接網路 (bridge network) 與深度健康檢查 (deep healthcheck) 機制，實現服務相依性的邏輯隔離與自動化自癒能力。

## 2. Part A：底座與基準點
<ssh 證據 + 版本 + snapshot>
![ssh](screenshots/ssh-and-versions.png)
<img width="520" height="535" alt="snapshot" src="https://github.com/user-attachments/assets/3209106d-5981-44ef-bd56-83275a8309ea" />

## 3. Part B：Dockerfile 與快取
<Dockerfile + 兩次 build 對照>

 **Dockerfile**
```
FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8080
CMD ["python", "app.py"]
```


 **.dockerignore**
```
.env
__pycache__
*.pyc
.git
.gitignore
```

![兩次 build 對照](screenshots/build-cache-diff.png)

### 為什麼聽 8080 不聽 80？
符合 Linux 安全規範，1024 以下為特權埠 (Privileged Ports)，綁定需 root 權限。為落實最小權限原則 (Least Privilege)，容器以 appuser (UID 1000) 執行，故選用 8080 埠以避免提權攻擊。

## 4. Part C：Compose 與資料持久化
<compose.yaml 重點 + 三段對照>

 **compose.yaml重點**
```
services:
  db:
    image: postgres:16
    volumes:
      - db-data:/var/lib/postgresql/data  # 定義持久化卷
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  db-data:  # 宣告 Named Volume
```

 **.env.example**
```
POSTGRES_DB=examdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=mysecretpassword
```
   三段對照：

   | 階段 | 命令 | `SELECT * FROM exam` 結果 |
   | ---- | ---- | ------------------------- |
   | 砍容器重建 | `docker compose down && docker compose up -d` | **還在** |
   | 連 volume 一起砍 | `docker compose down -v && docker compose up -d` | **消失** |
   | 重寫 | 再 INSERT 一次 | 重新出現 |
   
![三段對照](screenshots/volume-3-stages.png)

### down vs down -v
- docker compose down：僅停止並刪除容器與網路，但 Named Volume 會保留，資料持久化。
  
- docker compose down -v：除了停止容器外，會連同 volumes 區塊定義的 Named Volume 一併抹除。這是一個破壞性的刪除動作。

**Named Volume 的生命週期：**
其生命週期獨立於容器。它不會因為容器被停止或移除而消失，只有在被顯式刪除 (docker volume rm) 或使用 down -v 時才會被回收。這保證了資料庫在容器重啟時不會丟失資料。


## 5. Part D：生產化加固
<權限驗證輸出 + cgroup 讀值對照表>
### yaml 的值怎麼對回 cgroup 檔案？


![權限驗證輸出](screenshots/hardening-verify.png)

![cgroup](screenshots/cgroup.png)

**最終版 compose.yaml**
```
services:
  app:
    build: .
    restart: always
    environment:
      DB_HOST: db
    # 資源上限
    deploy:
      resources:
        limits:
          memory: 256m
          cpus: "0.5"
        pids: 200
    # 權限加固
    user: "1000:1000"
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    # 健康檢查
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
      interval: 10s
      timeout: 3s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  db:
    image: postgres:16
    volumes:
      - db-data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    deploy:
      resources:
        limits:
          memory: 512m
          cpus: "0.5"
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  db-data:
```

## 6. Part E：故障演練
### 故障 1：<F1>
- 注入方式：docker compose stop db
- 故障前：
  1.指令：docker compose ps
  
  2.輸出：app Up (healthy), db Up (healthy)
  
- 故障中：
  1.指令：curl -v http://localhost:8080/healthz
  
  2.輸出：< HTTP/1.1 503 SERVICE UNAVAILABLE
  
  3.容器狀態：app Up (unhealthy)
  
- 回復後：
  1.指令：docker compose start db 後等待 healthcheck 週期完成
  
  2.輸出：app Up (healthy)
  
- 診斷推論：本演練證明了 unhealthy ≠ dead。當資料庫層 (DB) 斷線，應用程式雖仍在執行，但透過 healthcheck 機制主動感知依賴異常，回傳 503 錯誤。這保護了前端監控層，防止無效請求繼續湧入。
![前](screenshots/fault-A-before.png)
![中](screenshots/fault-A-during.png)
![後](screenshots/fault-A-after.png)

### 故障 2：<F3>
- 注入方式：docker run --rm --memory 128m python:3.12-slim python -c "x = bytearray(256 * 1024 * 1024)"; echo "exit code = $?"
- 故障前：環境資源正常，系統穩態。
- 故障中：
 1.輸出：exit code = 137 (即 128 + SIGKILL 9)
  
 2.Kernel 鑑定：sudo dmesg -T | grep -i "memory" 顯示 Memory cgroup out of memory:   Killed process。
- 回復後：降額配置請求 (64MB) 執行成功 (exit code = 0)。
- 診斷推論：驗證了 Linux Kernel 的 OOM Killer 機制。當容器資源配置 (Cgroup) 被強制限制時，Kernel 為保護主機記憶體不被單一進程耗盡，會採取強制 SIGKILL 終止該進程。

![前](screenshots/fault-B-before.png)
![中](screenshots/fault-B-during.png)
![後](screenshots/fault-B-after.png)

### 三症狀分層表（必答）
| 症狀 | 最可能的層 | 第一條驗證命令 |
| ---- | ---------- | -------------- |
| timeout |  |  |
| connection refused |  |  |
| HTTP 503 |  |  |

## 7. 反思（200 字）
這學期從 VM 做到 production-ready 容器，「隔離」這個概念在 VM、namespace、
cgroup、權限階梯四個地方各出現一次——它們在防的東西一樣嗎？

## 8. Bonus（選做）
