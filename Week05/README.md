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

## Image 分層

### `docker image inspect nginx:1.27-alpine` layer 數量
（7層）

### 兩個同源 image 共享 layer 的證據
（前幾個 sha256 是否相同？）前幾層的 sha256 雜湊值會完全相同

### `docker diff` 輸出範例與解讀
（貼上 A/C/D 實例並說明）
執行 `docker diff fs-demo` 得到的實體輸出：
C /etc
C /etc/nginx
C /etc/nginx/conf.d
A /etc/nginx/conf.d/custom.conf
D /etc/nginx/conf.d/default.conf
C /tmp
A /tmp/hello.txt

- **`A` (Added):** 新增。例如 `/tmp/hello.txt` 與 `/etc/nginx/conf.d/custom.conf`。這代表這些新檔案是直接寫入該容器專屬的「可寫層（Upperdir）」，對底層的唯讀鏡像完全無影響。
- **`C` (Changed):** 變更。例如 `/etc`、`/tmp` 等目錄。因為其底下的子檔案或目錄結構被修改、新增或刪除，導致目錄的元數據（Metadata）或內容發生變化。
- **`D` (Deleted):** 刪除。例如 `/etc/nginx/conf.d/default.conf`。這體現了 **Copy-on-Write (CoW)** 的白頭翁（Whiteout）機制——底層鏡像中的該檔案其實完好無損，Docker 只是在可寫層放了一個特殊標記，告訴容器的掛載視圖（Merged）隱藏此檔案，營造出「已被刪除」的假象。

## OCI 呼叫鏈

（用自己的話說明 dockerd → containerd → containerd-shim → runc 各自負責什麼，以及 OCI Runtime Spec `config.json` 裡哪些欄位對應到 namespace / cgroup 設定）
當我們在 Host 輸入 `docker run` 到容器 Process 真正啟動，中間穿過了以下四層角色：

1. **dockerd:** 負責高層邏輯與使用者 API。它處理我們輸入的 CLI 指令、處理網路橋接、Volume 掛載，並把使用者的意圖轉譯為具體的容器規格，透過 gRPC 傳給下一層。
2. **containerd:** 負責容器與快照的生命週期管理。它不理會複雜的網路或高層業務，專注於管理 Image 的拉取、儲存解壓，以及追蹤容器的運作狀態。
3. **containerd-shim:** 每個容器專屬的守護墊片（常駐行程）。它的存在是為了將容器的 `stdio`（標準輸入輸出）接住、收集容器退出碼（Exit Code），更重要的是**將 containerd 與 runc 解耦**——即使 `dockerd` 或 `containerd` 服務重啟或崩潰，容器行程也能在 shim 的守護下繼續正常運行。
4. **runc:** 真正幹髒活的 OCI Runtime 標準實作。它是一支短命行程，被 shim 喚醒後，會去讀取符合 OCI 規範的規格書 `config.json`，然後直接向 Linux Kernel 呼叫 `clone()` / `unshare()` 建立各種 Namespace、把限制值寫入 Cgroups 控制檔案，最後執行 `exec` 把容器內的目標程式（如 sleep 或 nginx）跑起來，隨後 runc 功成身退。

### `config.json` 欄位與 Kernel 機制的對應
在 OCI Runtime Spec 的 `config.json` 中：
- **Namespace 對應：** 位於 `"linux.namespaces"` 陣列欄位。裡面明確指定了 `"type": "pid"`、`"type": "network"`、`"type": "mount"` 等項目，這直接指導了 `runc` 在啟動時要幫 Process 隔離出哪些系統視角。
- **Cgroup 對應：** 位於 `"linux.resources"` 欄位。底下的 `"memory": { "limit": 268435456 }` 和 `"cpu": { "quota": 50000, "period": 100000 }`，直接對應並決定了 `runc` 要往主機的 `/sys/fs/cgroup/` 實體檔案系統裡寫入什麼限制值。


## 排錯紀錄
- 症狀：輸入 `docker info` 噴出 `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`。
- 診斷：當前登入的使用者 `xjz` 權限不足，不屬於 `docker` 使用者群組，無法讀寫該 Unix Socket 檔案。
- 修正：執行 `sudo usermod -aG docker xjz` 將使用者加入群組，並透過 `newgrp docker` 使群組權限在當前 shell 立即生效。
- 驗證：重新執行 `docker info` 成功讀取到完整的 Server 端配置。

## 想一想（回答 3 題）
1. 容器裡的 PID 1 跟 host PID 1 是同一支 process 嗎？`kill -9 1`（在容器內）會發生什麼？
- **不是同一支。** 它們在 Kernel 內處於不同的 PID Namespace 階層。容器內的 PID 1 只是該隔離視角下的起點；在 Host 視角下，它只是一個普通的大數字 PID（例如 `22167`）。Host 的 PID 1 則是掌控整台主機初始化系統的 `systemd`。
- 在容器內執行 `kill -9 1` **什麼都不會發生（毫無反應）**。因為 Linux Kernel 的 `pid_namespaces(7)` 規範為每個 Namespace 的 `PID 1`（Init 行程）設計了「信號免疫權」。Kernel 為了保障容器不意外崩潰，會自動忽略來自同一個 Namespace 內部發送給 PID 1 的 `SIGKILL` 等強制終止信號。

2. 兩個容器都基於 `ubuntu:24.04`，磁碟空間是吃兩份還是共用？怎麼驗證？
- **完全共用，磁碟空間只吃一份。** 因為 Docker 底層的 Overlay2 採用內容定址儲存機制（Content-Addressable Storage）。不論開了多少容器或拉了多少相關鏡像，只要該層的 SHA256 雜湊值一致，在實體磁碟上就只會保留一份唯讀的 Lowerdir 目錄。
- **驗證方式：** 先用 `docker images` 查看所有本地鏡像的邏輯大小（會看到每個基礎相似鏡像都宣稱自己有上百 MB）；接著使用 `sudo du -sh` 去量測 Docker 快照與鏡像存放的實體目錄（在 Snapshotter 模型下為 `/var/lib/docker/containerd/daemon/snapshots/`）。會發現實體目錄佔用的總容量**遠遠小於**邏輯大小的直接加總，差額即是被 Union FS 完美共用省下的空間。

3. 如果 host 的 kernel 爆漏洞，容器還能稱為「隔離」嗎？這個限制跟 VM 的隔離差在哪？
- **不能稱為隔離。一旦 Host Kernel 被攻破，容器的隔離邊界會瞬間瓦解。** 因為容器本質上只是 Host 上的常規 Process，它沒有自己的 Kernel，所有在容器內發出的系統呼叫（Syscall）都是直接由 Host Kernel 執行。如果 Kernel 爆發漏洞（如 Dirty COW、Dirty Pipe 等特權提升漏洞），惡意程式就能透過特定 Syscall 修改 Kernel 記憶體，直接實施「容器逃逸（Container Escape）」，拿到 Host 主機的 Root 權限。
- **與 VM 隔離的本質差別：** VM 具備硬體級虛擬化屏障，每個 VM 都擁有**完全獨立的 Guest Kernel**。VM 內部的 Syscall 是由自己的 Kernel 響應，黑客如果想逃逸，必須攻破極其狹窄且由 Hypervisor 控制的實體模擬層，難度極高。這也是為什麼在安全要求極高的多租戶雲端環境中，會需要 Kata Containers 或 Firecracker 這類「微型虛擬化（MicroVM）」技術存在——用 VM 的獨立核心安全邊界，去包裝容器的輕量與速度。
