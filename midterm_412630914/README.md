# 期中實作 — <412630914> <許家禎>

## 1. 架構與 IP 表
### IP 配置表
| VM | 角色 | 網卡 | 模式 | IP | 
|---|---|---|---|---|
| bastion | 跳板機 | NIC 1 | NAT | 192.168.72.137 | 
| bastion | 跳板機 | NIC 2 | Host-only | 192.168.81.130 | 
| app | 應用層 | NIC 1 | Host-only | 192.168.81.128 | 

### Mermaid 圖
![Mermaid 圖](network-diagram.png)
## 2. Part A：VM 與網路
- 在bastion執行 ping -c 3 192.168.81.128 (App) 成功
- 在app執行 ping -c 3 192.168.81.130 (Bastion) 成功

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
