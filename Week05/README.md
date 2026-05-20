# W05｜把容器拆開來看：Namespace / Cgroups / Union FS / OCI

## Docker 環境資訊

- **Storage Driver:** overlayfs (io.containerd.snapshotter.v1)
- **Cgroup Version:** 2
- **Cgroup Driver:** systemd
- **Default Runtime:** runc

---

## Namespace 觀察

### 六種 namespace 用途（自我語意重述）
- **PID:** 隔離行程 ID。讓容器擁有自己獨立的行程樹，保護 Host 及其他容器行程不被看見或干擾。
- **NET:** 隔離網路資源。容器擁有自己專屬的虛擬網卡、IP 位址、Port 與路由表。
- **MNT:** 隔離掛載點。容器擁有獨立的檔案系統根目錄 `/`，無法直接觸及實體主機或其他容器的檔案。
- **UTS:** 隔離主機名稱。允許容器自訂 `hostname` 與網域名稱，不與 Host 實體機衝突。
- **IPC:** 隔離行程間通訊。防止容器間跨邊界存取共享記憶體（Shared Memory）或訊息佇列。
- **USER:** 隔離使用者權限。將容器內的 UID/GID 對映到 Host 的非特權使用者，防止容器逃逸直接奪取主機 Root 權限。

### Host vs 容器 inode 對照表
以下為透過 `/proc/1/ns/` 與容器進程 `/proc/20954/ns/` 實際觀測之結果：

| Namespace | Host PID 1 inode | 容器 sleep inode | 一樣嗎？ |
|---|---|---|---|
| **pid** | `4026531836` | `4026532914` | **不一樣 (核心隔離)** |
| **net** | `4026531840` | `4026532916` | **不一樣 (核心隔離)** |
| **mnt** | `4026531841` | `4026532911` | **不一樣 (核心隔離)** |
| **uts** | `4026531838` | `4026532912` | **不一樣 (核心隔離)** |
| **ipc** | `4026531839` | `4026532913` | **不一樣 (核心隔離)** |
| **user** | `4026531837` | `4026531837` | **一樣 (預設未開啟)** |

### 容器內 `ps aux` 觀察
在容器內執行 `ps aux | wc -l` 僅顯示 **5** 條紀錄。
*   **原因：** 這是 PID Namespace 隔離產生的視角截斷效果。容器內的 `sleep 3600` 行程在該隔離區間內被賦予了 **PID 1**（Init）的特殊身份，無法看到 Host 上其他上百個正在執行的常規行程。而在 Host 視角看，該行程僅是常規的普通行程（實體 PID = `20954`）。

---

## Cgroups 實驗

### 限制數據驗證對照
當啟動參數設定 `--memory=256m --cpus=0.5` 時，實際內外控制檔數值完全一致：

*   **容器內讀取 (`/sys/fs/cgroup/`)**
    - `memory.max`: `268435456` (Bytes, 精準等於 256MB)
    - `cpu.max`: `50000 100000` (每 100ms 週期允許使用 50ms = 0.5 核)
*   **Host 端讀取 (`/sys/fs/cgroup/system.slice/docker-<CID>.scope/`)**
    - `memory.max`: `268435456`
    - `cpu.max`: `50000 100000`
    - `memory.current`: 於測試時某瞬間讀取為 `348160` Bytes。

### OOM 故障注入三階段證據

| 項目 | 故障前 | 故障中（memory=32m + dd 200m）| 回復後（memory=256m）|
|---|---|---|---|
| **容器 exit code** | 執行中 (-) | **137** (由外力 SIGKILL 終止) | 1 (實體邊界限制) |
| **OOMKilled** | false | **true** | false |
| **dmesg 關鍵字** | 無 OOM 紀錄 | `Memory cgroup out of memory: Killed process 21429 (dd)` | 無 OOM 紀錄 |

> 💡 **註：** 於回復後實驗中，容器未引發 Cgroup OOM，但因 App VM 配置之實體記憶體較小，觸及了 `/dev/shm` (tmpfs) 的實體容量上限，噴出 `No space left on device`。此為實體硬體邊界限制，非 Cgroup 掐死。

---

## Image 分層與 Copy-on-Write 觀察

### 映像層與歷史觀察
- `docker image inspect nginx:latest` 的 Layers 總數共有 **7 層**。
- `docker history nginx:latest` 證實了每一層都對應著 Dockerfile 的一條特定建置指令（如 `COPY`、`RUN` 等），其中最底層由 `debuerreotype` 產生（大小 109MB），為系統基礎層。

### `docker diff` 可寫層行為變更
在容器中寫入 `/tmp/hello.txt`、刪除預設設定檔並新增自訂設定檔後，`docker diff fs-demo` 準確捕捉到了可寫層（UpperDir）的視圖變化：
