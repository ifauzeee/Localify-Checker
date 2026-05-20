# Localify Checker

Localify Checker adalah aplikasi desktop GUI sederhana untuk memastikan semua lagu dari CSV Spotify sudah tersedia di koleksi musik lokal.

## Fitur

- Import CSV musik lokal dengan format `folder,filename`
- Import CSV Spotify dengan auto-detect kolom seperti `track_name`, `Track name`, `Artist name`, dan `Album`
- Normalisasi nama lagu:
  - abaikan huruf besar/kecil
  - abaikan ekstensi `.mp3`, `.flac`, `.wav`, `.m4a`, `.ogg`
  - abaikan simbol umum seperti `-`, `_`, `()`, `[]`, `.`
  - abaikan teks tambahan seperti `official audio`, `lyric video`, `remastered`, `explicit`, `feat`, `ft`
  - bersihkan spasi ganda
- Fuzzy matching dengan RapidFuzz
- Tabel hasil dengan status `MATCH`, `POSSIBLE MATCH`, dan `MISSING`
- Filter status hasil
- Export laporan:
  - `matched.csv`
  - `missing.csv`
  - `possible_match.csv`
  - `full_report.csv`

## Struktur Project

```text
Localify-Checker/
├── app.py
├── requirements.txt
├── README.md
├── core/
│   ├── csv_loader.py
│   ├── normalizer.py
│   ├── matcher.py
│   └── exporter.py
├── ui/
│   └── main_window.py
└── output/
```

## Cara Install di Windows

Pastikan Python 3.10 atau lebih baru sudah terinstall.

```powershell
cd C:\Users\Ifauze\Project\Localify-Checker
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Cara Pakai

1. Klik **Pilih Lokal** dan pilih CSV musik lokal dari HP/Termux.
2. Klik **Pilih Spotify** dan pilih CSV library Spotify.
3. Klik **Analyze**.
4. Lihat statistik ringkas dan tabel hasil.
5. Gunakan filter untuk melihat semua hasil, match, possible match, atau missing.
6. Klik **Export** untuk menyimpan laporan CSV.

## Format CSV Lokal

```csv
folder,filename
"Adhitia Sofyan/8 Tahun","04. Sesuatu Di Jogja.flac"
"Alphaville/Forever Young","06. Forever Young.flac"
```

## Format CSV Spotify

Aplikasi akan mencoba mendeteksi kolom secara otomatis. Contoh format yang didukung:

```csv
track_name,artist,album
"Kasih Tak Sampai","Padi","Sesuatu Yang Tertunda"
```

atau:

```csv
Track name,Artist name,Album,Playlist name,Type
"Boulevard of Broken Dreams","Green Day","American Idiot","Favorite Songs","Favorite"
```

## Catatan Status

- `MATCH`: skor similarity tinggi, kemungkinan besar lagu sudah ada.
- `POSSIBLE MATCH`: ada kandidat lokal yang mirip, sebaiknya dicek manual.
- `MISSING`: tidak ada kandidat yang cukup mirip.

Persentase kelengkapan dihitung dari jumlah `MATCH` dibanding total lagu Spotify. `POSSIBLE MATCH` sengaja tidak dihitung sebagai lengkap agar proses validasi tetap ketat.

## Troubleshooting

- Jika muncul error kolom CSV, pastikan file lokal punya kolom `folder` dan `filename`.
- Jika CSV Spotify punya nama kolom yang tidak umum, ubah kolom nama lagu menjadi `track_name` atau `Track name`.
- Jika aplikasi tidak terbuka, pastikan virtual environment aktif dan dependency sudah terinstall.

