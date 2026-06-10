# W08｜容器生產實踐

## Healthcheck 故障測試
- 停 db 後幾秒被標 unhealthy：db 停止後約 9 秒業務層開始回傳 503（09:43:13 最後一次 200 → 09:43:22 第一次 503）；Docker health status 在 retries × interval = 25 秒倒數耗盡後切為 unhealthy
- 對應的 log 訊息：
```
app-1  | 127.0.0.1 - - [10/Jun/2026 09:43:22] "GET /healthz HTTP/1.1" 503 -
app-1  | 127.0.0.1 - - [10/Jun/2026 09:43:30] "GET /healthz HTTP/1.1" 503 -
app-1  | 127.0.0.1 - - [10/Jun/2026 09:43:38] "GET /healthz HTTP/1.1" 503 -
app-1  | 127.0.0.1 - - [10/Jun/2026 09:43:46] "GET /healthz HTTP/1.1" 503 -
```
<img width="680" height="182" alt="截圖 2026-06-10 20 46 38" src="https://github.com/user-attachments/assets/903f59d5-be27-4ea7-b46e-0ac291e0d139" />


## Log 失控估算
- noisy 容器 30s log 大小：9.6 GiB（10,316,841,265 bytes）
- 預估 24h 大小：27,672 GB（≈ 27 TB）
- 套 rotation 後穩定上限：6 MiB（max-size: 2m × max-file: 3；實測目錄 4.9M，含 73K 當前檔 + 2 × 2.0M 歷史檔）


## 資源限制實驗
| 實驗 | 命令 | 觀察結果 | 對應 cgroup 檔 | 值 |
|---|---|---|---|---|
| OOM | stress-ng --vm 1 --vm-bytes 200m | exit 137, OOMKilled=true | memory.max | 134217728 |
| CPU throttle | stress-ng --cpu 4 | docker stats CPU% ≈ 50% | cpu.max | 50000 100000 |


<img width="686" height="33" alt="截圖 2026-06-10 20 47 40" src="https://github.com/user-attachments/assets/0c028c3b-63c0-4ccd-8590-90a60119a601" />


## 權限四階對照
| 階梯 | id | CapEff | NoNewPrivs | curl /healthz |
|---|---|---|---|---|
| 0 | uid=0(root) | `0000003fffffffff` | 0 | ok |
| 1 | uid=1000(appuser) | `0000000000000000` | 0 | ok |
| 2 | uid=1000(appuser) | `0000000000000000` | 1 | ok |
| 3 | uid=1000(appuser) | `0000000000000000` | 1 | ok |
| 4 | uid=1000(appuser) | `0000000000000000` | 1 | ok |

<img width="686" height="631" alt="四階權限對照" src="https://github.com/user-attachments/assets/70e2653a-3fc7-4d81-8811-6acdc690964b" />
## 排錯紀錄
- 症狀：`cat: write error: No space left on device`，compose.yaml 無法寫入
- 診斷：noisy 容器無 rotation，30 秒噴出 9.6 GiB 撐爆磁碟，`df -h /` 顯示 Use% = 100%
- 修正：`sudo sh -c "truncate -s 0 /var/lib/docker/containers/*/*-json.log"` 清空所有 log；在 compose.yaml 每個服務加上 `logging.driver: json-file` + `max-size / max-file`
- 驗證：`df -h /` 顯示 Avail 恢復 9.1G；重啟後 noisy 目錄穩定在 4.9M


## 設計決策
（你選的 mem_limit / cpus 數值理由是什麼？read_only 之後你補了哪些 tmpfs，為什麼？）
**mem_limit / cpus 數值理由**
- `app: mem_limit: 256m`：空載實測 22 MiB，保留約 10× 餘量應對請求突發，低於此值有 OOM 風險
- `db: mem_limit: 512m`：PostgreSQL `shared_buffers` 預設 128m，加上 WAL 緩衝與連線 overhead，512m 是不影響查詢效能的安全下限
- `stress: mem_limit: 128m, cpus: "0.5"`：刻意設低，使 OOM 與 CPU throttle 現象在實驗中清晰可見；`cpu.max = 50000 100000` 代表每 100ms 週期最多使用 50ms，對應 `docker stats` 的 50% 上限

**read_only: true 後補的 tmpfs**
Python 標準庫 `tempfile` 與 Flask/werkzeug 的請求處理都預設寫入 `/tmp`；設為 `read_only: true` 後根檔案系統全部唯讀，若不掛 `tmpfs`，容器在執行期會因無法寫 `/tmp` 而崩潰。`tmpfs` 資料僅存於記憶體、重啟即清空，不落磁碟，符合最小權限設計原則。

