# 期中實作 — <412630914> <許家禎>

## 1. 架構與 IP 表
<Mermaid 圖 + 表格>
### IP 配置表
| 機器名稱 (Hostname) | 網卡介面 | IP 位址 (IPv4) | 網路類型 | 用途說明 |
| :--- | :--- | :--- | :--- | :--- |
| **bastion** | `ens160` | `192.168.72.137` | NAT (External) | 外部入口：供本地端 (Host) 連線的唯一通道 |
| **bastion** | `ens256` | `192.168.81.130` | Host-only (Internal) | **內部網關**：連向內網與 App 溝通的介面 |
| **app** | `ens160` | `192.168.81.128` | Host-only (Internal) | **隔離服務區**：僅限內網存取，不對外開放 |

### Mermaid 圖
![Mermaid 圖](network-diagram.png)
## 2. Part A：VM 與網路
<命令 + 關鍵輸出>

## 3. Part B：金鑰、ufw、ProxyJump
<防火牆規則表 + ssh app 成功證據>

## 4. Part C：Docker 服務
<systemctl status docker + curl 輸出>

## 5. Part D：故障演練
### 故障 1：<F1/F2/F3 擇一>
- 注入方式：
- 故障前：
- 故障中：
- 回復後：
- 診斷推論：

### 故障 2：<另一個>
（同上）

### 症狀辨識（若選 F1+F2 必答）
兩個都 timeout，我怎麼分？

## 6. 反思（200 字）
這次做完，對「分層隔離」或「timeout 不等於壞了」的理解有什麼改變？

## 7. Bonus（選做）
