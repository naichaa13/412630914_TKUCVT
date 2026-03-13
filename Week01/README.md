# W01｜虛擬化概論、環境建置與 Snapshot 機制

## 環境資訊
- Host OS： macOS 14
- VM 名稱：vct-w01-412630914
- Ubuntu 版本： 24.04.4 LTS
- Docker 版本：29.3.0
- Docker Compose 版本：v5.1.0

## VM 資源配置驗證

| 項目 | VMware 設定值 | VM 內命令 | VM 內輸出 |
|---|---|---|---|
| CPU | 2 vCPU | `lscpu \| grep "^CPU(s)"` | 4 |
| 記憶體 | 4 GB | `free -h \| grep Mem` | 3.8Gi |
| 磁碟 | 40 GB | `df -h /` | 50G |
| Hypervisor | VMware | `lscpu \| grep Hypervisor` | vmware |

## 四層驗收證據
- [x] ① Repository：`cat /etc/apt/sources.list.d/docker.list` 輸出：deb [arch=arm64 signed-by=/etc/apt/keyrings/docker.gpg]   https://download.docker.com/linux/ubuntu   noble stable
- [x] ② Engine：`dpkg -l | grep docker-ce` 輸出:5:29.3.0-1~ubuntu.24.04~noble
- [x] ③ Daemon：`sudo systemctl status docker` 顯示 active
- [x] ④ 端到端：`sudo docker run hello-world` 成功輸出:Hello from Docker!
- [x] Compose：`docker compose version` 可執行

## 容器操作紀錄
- [x] nginx：`sudo docker run -d -p 8080:80 nginx` + `curl localhost:8080` 輸出:Welcome to nginx!
- [x] alpine：`sudo docker run -it --rm alpine /bin/sh` 內部命令與輸出
- [x] 映像列表：`sudo docker images` 輸出

## Snapshot 清單

| 名稱 | 建立時機 | 用途說明 | 建立前驗證 |
|---|---|---|---|
| clean-baseline | （時間點） | （此節點代表的狀態） | （列出建點前做了哪些驗證） |
| docker-ready | （時間點） | （此節點代表的狀態） | （列出建點前做了哪些驗證） |

## 故障演練三階段對照

| 項目 | 故障前（基線） | 故障中（注入後） | 回復後 |
|---|---|---|---|
| docker.list 存在 | 是 | 否 | （填入） |
| apt-cache policy 有候選版本 | 是 | 否 | （填入） |
| docker 重裝可行 | 是 | 否 | （填入） |
| hello-world 成功 | 是 | N/A | （填入） |
| nginx curl 成功 | 是 | N/A | （填入） |

## 手動修復 vs Snapshot 回復

| 面向 | 手動修復 | Snapshot 回復 |
|---|---|---|
| 所需時間 | （你的實測） | （你的實測） |
| 適用情境 | （你的判斷） | （你的判斷） |
| 風險 | （你的判斷） | （你的判斷） |

## Snapshot 保留策略
- 新增條件：
- 保留上限：
- 刪除條件：

## 最小可重現命令鏈
（列出讓他人能重現故障注入與回復驗證的命令序列）

## 排錯紀錄
- 症狀：
- 診斷：（你首先查了什麼？）
- 修正：（做了什麼改動？）
- 驗證：（如何確認修正有效？）

## 設計決策
（說明本週至少 1 個技術選擇與取捨）
