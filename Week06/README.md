# W06｜Docker Image 與 Dockerfile

## 映像組成
- Layers 是什麼？：Docker 映像檔的「唯讀層」。Dockerfile 中的每一行特定指令（如 `RUN`、`COPY`）都會堆疊出一個唯讀的檔案系統層（Layer）。它們透過聯合文件系統（UnionFS）組合在一起。相同的 Layer 可以在不同 Image 之間共享，用來節省空間和加速建置。
- Config 是什麼？：映像檔的「中介資料與設定說明書」。裡面記錄了這個容器啟動時預設要執行的指令（`CMD`）、環境變數（`ENV`）、預設工作目錄（`WORKDIR`）以及系統架構（Architecture）等非檔案系統的執行期設定。
- Manifest 是什麼？：映像檔的「清單／索引檔」。它是一個 JSON 檔案，負責把 Config 和所有 Layers的雜湊值（Digest）串聯並綁定在一起。當執行 `docker pull` 時，Docker 就是先讀取 Manifest，才知道要下載哪些對應的 Layers。

## python:3.12-slim inspect 摘錄
- Config.Cmd：python3
- Config.Env：
```
json
  [
      "PATH=/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
      "LANG=C.UTF-8",
      "GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305",
      "PYTHON_VERSION=3.12.13",
      "PYTHON_SHA256=c08bc65a81971c1dd5783182826503369466c7e67374d1646519adf05207b684"
  ]
```
- Config.WorkingDir：“”
- RootFS.Layers 數量：4
<img width="507" height="595" alt="截圖 2026-05-27 16 41 26" src="https://github.com/user-attachments/assets/00e796f0-a157-4cd1-a91f-49c063ac5f09" />



## Layer 快取實驗
| 情境 | build 時間 |
|---|---|
| v1 首次 build | 5.474s |
| v1 改 app.py 後 rebuild | 4.996s (RUN pip install 耗時 4.3s) |
| v2 首次 build | 5.063s (RUN pip install 耗時 4.3s） |
| v2 改 app.py 後 rebuild | 0.211s (CACHED) |

觀察（用自己的話寫）：為什麼 v2 的 rebuild 這麼快？
- 在 Docker 的快取機制中，遵循「某層 Miss 則其後全 Miss」的嚴格規則。只要任何一層 Layer 因為檔案變動或指令修改導致快取失效，其後續的所有 Dockerfile 指令都必須放棄快取、強迫重新執行。
v1 的反模式：將時常變動的 COPY app/ . 放在 RUN pip install 之前。當 app.py 透過 sed 改動一行，COPY 層判定 miss，害得後面最耗時的 pip install 每次都要重跑（耗時 4.3 秒）。
v2 的最佳實踐：將不容易變動的 requirements.txt 獨立出來優先 COPY 并執行 pip install。由於相依清單沒變，這兩層會牢牢鎖在 CACHED 中。後續修改 app.py 時，只會觸發最後一層 COPY app/ . 的重算，因此 rebuild 只要 0.211 秒。

<img width="685" height="288" alt="截圖 2026-05-27 16 59 52" src="https://github.com/user-attachments/assets/0bd086b3-3d02-4239-856b-737148b7c9be" />
<img width="683" height="299" alt="截圖 2026-05-27 16 47 37" src="https://github.com/user-attachments/assets/f1499b0e-fd03-490b-b1be-c3f91d21aa7e" />
<img width="692" height="617" alt="截圖 2026-05-27 16 48 34" src="https://github.com/user-attachments/assets/32f55dee-fcbf-48ea-be7b-3760ea677031" />


## CMD vs ENTRYPOINT 實驗
| 寫法 | `docker run <img>` 輸出 | `docker run <img> extra1 extra2` 輸出 |
|---|---|---|
| CMD shell form | argv = ['show_args.py', 'default1', 'default2']

PID = 7 | argv = ['show_args.py', 'default1', 'default2']

PID = 7 (參數被完全忽略) |
| CMD exec form | argv = ['show_args.py', 'default1', 'default2']

PID = 1 | executable file not found in $PATH |
| ENTRYPOINT + CMD | argv = ['show_args.py', 'default1', 'default2']

PID = 1 | argv = ['show_args.py', 'extra1', 'extra2']

PID = 1 (成功覆蓋預設引數) |

結論（用自己的話寫）：
- Shell Form 的隱患：使用 CMD python ... 時，底層是以 /bin/sh -c 喚起，導致 Python 進程的 PID 變為 7 而非主進程 1，這會使應用程式無法接收 Linux 關機訊號（SIGTERM），造成容器超時強殺。
- Exec Form 的覆蓋特性：在 docker run 後方帶參數時，如果是 CMD 寫法，參數會整條取代原本的陣列，導致 Docker 誤將 extra1 當成指令執行而報錯。
- 最佳搭配：用 ENTRYPOINT 固定不變的主程式，用 CMD 存放彈性預設參數。外傳參數能完美取代 CMD 並當成引數傳遞（如實測成功印出 extra1 與 extra2），最適合開發 CLI 彈性工具。

<img width="688" height="244" alt="截圖 2026-05-27 16 51 01" src="https://github.com/user-attachments/assets/5e2ca82c-7129-4b0b-bec6-3f4c31223ad1" />

## Multi-stage 大小對照
| Image | SIZE |
|---|---|
| python:3.12（builder base） | ~900 MB |
| python:3.12-slim（runtime base） | 205 MB |
| myapp:v2（單階段） | 223 MB |
| myapp:multi（多階段） | 210 MB |

解釋（用自己的話寫）：builder stage 的 layer 去哪了？
- 經 docker history myapp:multi 證實，最終鏡像裡完全找不到 builder stage 裡任何編譯、安裝套件的指令與 Layer 歷史。
多階段建置（Multi-stage）的原理是：前方的 Stage 僅作為暫存的「工具人環境」，負責下載、編譯等髒活。當走到最後一個 FROM 時，Docker 會開闢全新的 Runtime 空間，我們只透過 COPY --from=builder 像手術刀一樣精準地將「純淨產物（我們優化後的用戶目錄 .local）」複製過來。其餘在編譯階段產生的肥大 Layer、快取與工具，在建置結束後會被徹底拋棄，成功幫鏡像減肥 13MB。

## .dockerignore 故障注入
| 項目 | 故障前 | 故障中 | 回復後 |
|---|---|---|---|
| du -sh . | 44 KB | 151 MB | （151 MB |
| build context 傳輸大小 | 129B | 151 MB | 129B |
| build 時間 | <0.5s |8.331s） | 2.071s |

<img width="382" height="167" alt="截圖 2026-05-27 16 53 10" src="https://github.com/user-attachments/assets/0c5264bd-823c-421b-a79e-185c8bccaa39" />
<img width="690" height="505" alt="截圖 2026-05-27 16 53 47" src="https://github.com/user-attachments/assets/dc1c179a-5e91-4f63-938f-23b9f3995282" />
<img width="693" height="419" alt="截圖 2026-05-27 16 53 57" src="https://github.com/user-attachments/assets/abaec974-c2b7-4dc2-9e4a-d060de4c3b52" />

## 排錯紀錄
- 症狀：多階段建置（myapp:multi）容器啟動後，執行 curl http://localhost:8081/ 遭遇 Connection reset by peer
- 診斷：
  1.檢查 docker logs 發現 Flask 應用程式有成功啟動並監聽 80 埠。
  
  2.深入排查發現，這是一個由於「殘留容器衝突」與「服務啟動時間差」交織引發的假象。
  
  3.第一次執行 docker run --name myapp-multi 時，因為忘記清理上一次實驗殘留的舊容器，導致新容器命名衝    突、根本沒有建立成功。此時發送 curl 戳到的是正在初始化（還沒完全醒過來）的舊容器，因而被網路層丟出重置訊號（Connection Reset）。
- 修正：先明確執行 docker stop myapp-multi && docker rm myapp-multi 徹底清理乾淨。接著不帶任何尾隨參數（避免覆蓋路徑）進行乾淨啟動，並靜候 1 秒
- 驗證：重新執行後，curl http://localhost:8081/ 完美噴出 Hey from d71a3b82b205 | version=multi，且透過 whoami 證實容器是以安全、限權的非 Root 使用者 appuser 在背景運行。




## 設計決策
（說明本週至少 1 個技術選擇與取捨，例如：為什麼 runtime 選 `python:3.12-slim` 而不是 `alpine`？）
- **技術選擇**：Runtime 選擇 python:3.12-slim 而非 alpine
雖然 alpine 體積極小（約 5MB），但它使用的是輕量化的 musl libc，而 Python 生態系中絕大數科學計算與資料處理套件（如 NumPy、Pandas）的預編譯 Wheel 檔都是基於標準 Linux 的 glibc。
若在 Python 專案中盲目選擇 alpine，會導致容器在建置時無法直接使用 Wheel 檔，必須被迫「從原始碼現場編譯」，這會讓建置時間從數秒暴增到數十分鐘，且極易因缺少 C 語言相依套件而報錯。因此取捨之下，選擇基於 Debian 的 slim 作為 Runtime Base，是兼顧「體積輕量」與「生產環境建置穩定性」的最佳商業取捨。
