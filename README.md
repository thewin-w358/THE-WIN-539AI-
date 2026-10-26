# THE WIN AI V1.7 — 三彩種資料同步

- 今彩539：沿用 V1.6 內建的2026年資料（259期；仍須與官方核對）。
- 香港六合彩：已加入2026年10月3日至24日共10期、含特別號；來源 https://lottery.hk/en/mark-six/results/2026 。
- 加州 Fantasy 5：已加入2026年10月1日至24日共24期；來源 https://lotterypredictor.com/california/fantasy5/results 。
- **並非全年完整資料**：部署後 `scripts/update.py` 會嘗試補抓2026年六合彩全年頁面，以及 Fantasy 5 頁面能公開提供的期數。來源格式變動、網路封鎖或缺少歷史分頁時，無法保證補齊；不會填入虛構資料。
- `data/*.json` 是網站讀取的資料；在 GitHub Pages 發布前，需將整個資料夾內容上傳到 GitHub repo 根目錄並啟用 Actions 寫入權限、Pages。排程可能延遲。
- 管理後台展示密碼不是安全登入；正式部署前必須以 Supabase Auth / RLS 實作伺服器端驗證。
- 本次來源尚未取得可供容器下載的完整CSV，因此只有已核實的近期資料直接內建。
