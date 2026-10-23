# 剪報圖片文字分離編輯器

東港養殖研究中心

把「文字已經壓在圖片裡」的簡報或剪報（PPTX、PDF、JPG、PNG），拆成**去字後的乾淨背景圖**加上**可編輯的文字方塊**，在編輯器裡校對文字、更換字型後，匯出成新的 PowerPoint。

## 使用方式

1. 執行 `ClipSep-Setup-x.y.z.exe` 安裝，從開始功能表或桌面圖示開啟。
2. 按「開啟檔案」，選擇 PPTX、PDF 或圖片，可一次選多個。
3. 等辨識完成（每頁約 2–5 秒）。左側是頁面縮圖。
4. 編輯：
   - 單擊選取文字方塊，拖曳移動；可框選多個。
   - 雙擊進入編輯，修改文字。
   - 右側面板可改字型、字級、粗體、顏色。編輯中反白幾個字再按「文字顏色」，只改那幾個字。
   - 「此字型套用到全部頁面」一次換掉所有頁面的字型。
   - 「顯示原圖」切換回原始圖片對照。
5. 按「匯出 PPTX」存檔。

工具列選項：「移除浮水印」會一併抹掉 Gemini Notebook／NotebookLM 浮水印；「簡體轉繁體」修正辨識偶爾出現的簡體字。這兩項在開啟檔案前設定。

## 開發

```
pip install -r requirements.txt
python main.py                                   # 開啟編輯器
python cli.py 簡報.pptx -o 輸出.pptx              # 不開視窗，直接轉換
```

標誌放在 `assets/logo.png`。推送到 `main` 或打上 `v*` 標籤時，GitHub Actions 會在 Windows 上建置安裝檔（Actions 頁面的 Artifacts，標籤則附在 Release）。
