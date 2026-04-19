# W03｜多 VM 架構：分層管理與最小暴露設計

## 網路配置

| VM | 角色 | 網卡 | 模式 | IP | 開放埠與來源 |
|---|---|---|---|---|---|
| bastion | 跳板機 | NIC 1 | NAT | 192.168.72.137 | SSH from any |
| bastion | 跳板機 | NIC 2 | Host-only | 192.168.81.130 | — |
| app | 應用層 | NIC 1 | Host-only | 192.168.81.128 | SSH from 192.168.56.0/24 |
| db | 資料層 | NIC 1 | Host-only | 192.168.81.132 | SSH from app + bastion |

![bastion](./pic/b-set.png)
![app](./pic/a-set.png)
![db](./pic/db-set.png)

分層架構與最小暴露原則：
- 這週的實驗讓我體會到，不應該讓所有的伺服器都直接暴露在網際網路上。透過跳板機作為唯一入口，可以將重要的App和DB放在沒有外網IP的內網區域。
- 最小暴露原則：就是只給予必要的存取權限。例如DB就不需要對全世界開放SSH，只需要對內網的跳板機或應用程式開放，這樣即使外網有人攻擊，也摸不到最核心的資料庫

## SSH 金鑰認證

- 金鑰類型：ed25519
- 公鑰部署到：xjz@app 和 xjz@db 的 ~/.ssh/authorized_keys
- 免密碼登入驗證：
  - bastion → app：金鑰認證成功
  - bastion → db：金鑰認證成功
![部署](./pic/b-copykey.png)
![回傳](./pic/b-keycheck.png)

## 防火牆規則

### app 的 ufw status
![app](./pic/a-ufw.png)
### db 的 ufw status
![db](./pic/db-ufw.png)
### 防火牆確實在擋的證據
![curl](./pic/b-timeout.png)
## ProxyJump 跳板連線
- 指令：Host app
    HostName 192.168.81.128
    User xjz
    ProxyJump bastion
- 驗證輸出：xujiazhen@MacBook-Pro-2 ~ % ssh app "hostname" 輸出 app
- SCP 傳檔驗證：scp /tmp/proxy-test.txt db:/tmp/ 傳輸成功，且 cat 驗證內容一致
![ProxyJump](./pic/ProxyJump.png)
![scp](./pic/scp.png)

## 故障場景一：防火牆全封鎖

| 項目 | 故障前 | 故障中 | 回復後 |
|---|---|---|---|
| app ufw status | active + rules | deny all | active (allow 22) |
| bastion ping app | 成功 | Request timeout | 成功 |
| bastion SSH app | 成功 | **timed out** | 成功 |

![故障前](./pic/b-故障前.png)
![故障中](./pic/b-故障中.png)
![回復後](./pic/b-回復後.png)
## 故障場景二：SSH 服務停止

| 項目 | 故障前 | 故障中 | 回復後 |
|---|---|---|---|
| ss -tlnp grep :22 | 有監聽 | 無監聽 | 有監聽 |
| bastion ping app | 成功 | 成功 | 成功 |
| bastion SSH app | 成功 | **refused** | 成功 |

![故障前](./pic/a-故障前.png)
![故障中](./pic/b-故障中ssh.png)
![回復後](./pic/b-ssh回復後.png)
## timeout vs refused 差異
- Connection timed out：通常是網路層 (L3/L4 防火牆) 的問題。封包被直接丟棄（Drop），主機裝死不回應，導致發送端等太久而逾時

- Connection refused：通常是應用層 (L4 服務) 的問題。網路是通的，但目標主機的該埠口沒有程式在監聽（例如 SSH 沒開），主機主動回傳拒絕連線的封包
## 網路拓樸圖
![網路拓樸圖](./pic/network-diagram.png)

## 排錯紀錄
- 症狀：在 Bastion 執行 ssh app 時出現 Connection timed out
- 診斷：在 App 機器檢查 sudo ufw status，發現雖然開了22port，但來源網段寫錯了（寫成 .56.0/24）
- 修正：執行 sudo ufw allow from 192.168.81.0/24 to any port 22
- 驗證：回到 Bastion 再次執行 ssh app，成功看到 app 主機名稱

## 設計決策
決策內容：將 app 與 db 放置於 Host-only 私有網路，僅允許透過 bastion 進行 SSH 轉發 (ProxyJump)

技術考量：
- 安全性：減少攻擊面。只有一台機器（Bastion）暴露在外，大幅降低了黑客掃描埠口的風險。
- 管理便利性：透過 SSH Config 的 ProxyJump 設定，雖然物理上是兩跳，但在操作層面依然可以實現「一鍵登入」

取捨：雖然增加了 Bastion 這個單一故障點（SPOF），但換取了核心資料庫與應用程式的絕對隱私
