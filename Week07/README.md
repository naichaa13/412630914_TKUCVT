# W07｜Docker Compose 與資料持久化

## 拓樸圖
（mermaid 或 ASCII，標出 app、db、default network、db-data volume）
<img width="761" height="532" alt="w7" src="https://github.com/user-attachments/assets/79e0698c-62ad-465a-9aa8-c8c7af0f6a7a" />



## 從 docker run 到 compose.yaml
（自己的話：你最有感的一個改善是什麼？）

如果使用純 docker run，我必須手動執行 docker network create、docker volume create，然後小心翼翼地輸入多條又長又醜的指令，還要手動去連結與確認環境變數順序。只要拼字或參數錯一個，整個架構就垮了。
改用 compose.yaml 之後，「基礎設施即程式碼（IaC）」 的優勢非常有感！我只需要宣告好理想的狀態（服務、網路、掛載、依賴關係），一條 docker compose up -d 就幫我把整個叢集蓋好。最方便的是，Compose 會以目錄名稱為前綴（例如 w07_）自動建立獨立的 default 網路和 volume，完全不用擔心與其他專案的資源名稱衝突
<img width="333" height="576" alt="截圖 2026-06-03 21 50 19" src="https://github.com/user-attachments/assets/b7e40666-1112-410f-b139-37ddcdbfd316" />
<img width="358" height="481" alt="截圖 2026-06-03 21 49 50" src="https://github.com/user-attachments/assets/4201b17f-f3c9-4869-bb31-f1e44cad9649" />

## 三種掛載對照
| 掛載類型 | 路徑（host） | 容器砍重起資料還在嗎 | 重啟容器資料狀態 | 適合情境 |
|---|---|---|---|---|
| named volume |/var/lib/docker/volumes/w07_db-data/_data|在 | 完好如初，資料持續累積 | 生產環境的資料庫（PostgreSQL/MySQL）、持久化資料 |
| bind mount | 專案目錄下的 ./app | 在 | 雙向即時同步，Host 改 code 容器立刻變 | 開發環境即時修改程式碼、掛載特定設定檔 |
| tmpfs | 無（直接向 Host 借記憶體 RAM） | 不在 | 徹底清空，恢復初始狀態 |敏感性高且不落地的暫存資訊（如 Session、API 金鑰、快取）  |

<img width="688" height="141" alt="截圖 2026-06-03 21 17 23" src="https://github.com/user-attachments/assets/151f86a8-a05d-4773-aace-105901a188a1" />
<img width="335" height="435" alt="截圖 2026-06-03 21 18 24" src="https://github.com/user-attachments/assets/086f9d84-e59c-46ab-a270-eb01b578498d" />
<img width="414" height="83" alt="截圖 2026-06-03 21 18 59" src="https://github.com/user-attachments/assets/6266a5e3-54cd-4119-8abe-29159c8ace5a" />


## healthcheck 前後對照
| 寫法 | curl /healthz t=1s | t=3s | t=5s | t=10s |
|---|---|---|---|---|
| 只 depends_on | 000 | 503 | 503 | 200 ok |
| service_healthy | 000 | 200 | 200 |200 ok |

-  depends_on
<img width="547" height="311" alt="截圖 2026-06-03 21 41 08" src="https://github.com/user-attachments/assets/a06e3d76-dc07-4eaf-8528-49f1d5ef9e91" />

- service_healthy 
<img width="692" height="347" alt="截圖 2026-06-03 21 43 57" src="https://github.com/user-attachments/assets/580141ad-5dbf-460d-8062-493b973aba25" />


觀察（自己的話）：

- 只用 depends_on：Docker 引擎聯絡機制不夠聰明，只要看到 db 容器進程（Process）一啟動，就誤以為它好了，立刻放行 app 起來營業。結果 App 去連線還在初始化睡覺的 DB 造成連線失敗，Flask 噴出 503 存取日誌。這在生產環境會讓使用者看到翻車畫面。

- 改用 service_healthy 長語法：Docker Compose 會化身為嚴格的守門員，死死按住 app 不准它啟動，直到 db 內部的健康檢查指令 pg_isready 成功回傳為止。前幾秒因為 App 根本還沒起來、沒監聽 Port，所以連線是 000（拒絕連線）；等到第 9-10 秒 App 被安全放行後，使用者點進去直接就是最穩定的 200 ok，完美實現啟動。

## 排錯紀錄
- 症狀：執行 sudo docker compose config 或啟動時系統崩潰，噴出語法錯誤：
service "database" refers to undefined volume database-data: invalid compose project
- 診斷：在步驟 9 為了將服務名稱從 db: 取代成 database:，使用了全域替換指令 sed -i 's/db:/database:/g'。結果地圖砲誤傷了掛載路徑，把 db-data:/var/lib/... 變成了 database-data:/var/lib/...，但最下方的 volumes: 區塊依舊宣告舊名字 db-data，導致 Compose 找不到對應的 Volume 宣告。
- 修正：手動使用 nano 修正 compose.yaml，將被誤傷的容器內掛載來源手動改回 db-data。
- 驗證：重新執行 sudo docker compose config 順利展開 YAML，且 up -d 成功建立 w07-database-1 容器。

## 設計決策
（為什麼 db 用 named volume 而不是 bind mount？為什麼不能在生產用 tmpfs 存資料庫？）

- 為什麼 db 用 named volume 而不是 bind mount？
資料庫（如 PostgreSQL）內部對底層檔案系統的權限（UID/GID）、檔案鎖（File Locking）以及區域語系（Locale）有極其嚴苛的要求。如果用 bind mount 將資料強行掛載到 Host 端的普通目錄，經常會因為 Linux 權限不相容、SELinux 阻擋或虛擬機檔案系統轉換（如 Windows/Mac 跨平台的 Shared Folders）而導致 Postgres 報錯、拒絕啟動甚至資料損毀。Named Volume 由 Docker 全權託管在內部核心安全區，效能最高且最穩定。
- 為什麼不能在生產用 tmpfs 存資料庫？
tmpfs 是純粹活在 Host 主機隨機存取記憶體（RAM）中的虛擬磁碟。雖然讀寫速度極快，但只要容器一重啟、主機斷電、或遇到突發性的記憶體崩潰（OOM），裡面的資料就會瞬間化為烏有（斷電即失）。生產環境的資料庫承載著真實用戶的寶貴資料，必須追求最高規格的 ACID 持久化防護，因此絕對不能使用 tmpfs 存資料
