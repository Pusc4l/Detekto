# 🤖 AGENT-WORKFLOW: DETEKTO SYSTEM
**Document Version:** 2.0 (Synchronized with Enterprise PRD v2.0 & Tech Stack v2.0)  
**System Architecture:** Hybrid Edge-Node (Local Edge Compute + Global Hive-Mind Sync)  
**Target Environment:** Windows 10/11 Native + Docker Desktop (Zero Linux-Config Friction)  
**Cost Mandate:** $0.00 (100% Free-Tier, Open-Source, & Auto-Fallback Ready)  

---

## 🚨 AI MASTER DIRECTIVES (WAJIB DIPATUHI OLEH CLAUDE / CURSOR)
1. **Phase-Gated Execution:** Baca dan eksekusi setiap fase secara berurutan. **DILARANG KERAS** menuliskan kode untuk Fase $N+1$ sebelum pengguna mengonfirmasi bahwa *Checkpoint* pada Fase $N$ telah berjalan 100% tanpa *error*.
2. **Windows First & Zero-Error Fallback:** Semua skrip *setup* dan terminal harus kompatibel dengan Windows PowerShell/CMD dan Docker Desktop. Setiap komponen eksternal wajib disertai kode *Auto-Fallback* (sesuai matriks di `TECH-STACK.md`) agar aplikasi tidak pernah *crash* jika salah satu *container* atau *binary* belum terinstal.
3. **Strict Neo-Brutalism Enforcement:** Pada seluruh fase UI, dilarang menggunakan *glassmorphism* (`backdrop-blur`), gradasi lembut, atau sudut membulat (`rounded-md`/`lg`). Wajib menggunakan `rounded-none`, `border-4` hingga `border-8` (`#000000`), dan *hard offset shadow* (`shadow-[8px_8px_0px_0px_#000000]`).
4. **Zero-Bloat RAM Guarantee:** Tidak boleh ada satu baris kode pun yang menyimpan *file* gambar (`.jpg`/`.png`) ke dalam *hardisk/SSD* (`fs.writeFile` atau `open(..., 'wb')`). Semua pemrosesan visual harus dilakukan di memori (Base64 / `io.BytesIO`) dan langsung dihapus setelah selesai.

---

## 🏁 PHASE 1: INFRASTRUCTURE, DOCKER & SHELL FOUNDATION
**Tujuan:** Membangun fondasi *container* lokal, menginisialisasi *backend* FastAPI dengan sistem *fallback*, dan menyiapkan antarmuka Next.js (siap untuk Web Lokal & Tauri Desktop Wrapper).

- [ ] **Task 1.1: Master Docker Compose (`docker-compose.yml`).**
  - Konfigurasi **Redis** (Port `6379`) untuk *Ephemeral RAM Buffer* (`TTL = 300s`) dan *Task Broker*.
  - Konfigurasi **SearxNG** (Port `8080`) dengan format output JSON diaktifkan untuk *Ground Truth RAG* & *OSINT Dorking*.
  - Konfigurasi **Memgraph Platform** (Port `7687` untuk Bolt, `3001` untuk Lab) untuk pemetaan graf relasi *buzzer*.
- [ ] **Task 1.2: Backend Initialization & Auto-Fallback Core (`/backend`).**
  - Inisialisasi lingkungan Python 3.11+ (`requirements.txt` / `uv`).
  - Buat struktur modular: `/api`, `/core`, `/services`, `/models`, `/workers`.
  - Buat modul `core/config.py` yang secara otomatis mendeteksi ketersediaan *service*:
    - Jika Memgraph *offline* $\rightarrow$ aktifkan mode **NetworkX In-Memory Graph**.
    - Jika Supabase belum dikonfigurasi $\rightarrow$ aktifkan mode **Local SQLite3 (`detekto_hive.db`)**.
  - Buat *endpoint* `GET /api/health` yang melaporkan status aktif dari Redis, SearxNG, Memgraph, dan SQLite/Supabase, serta `WebSocket /ws/interrogation` untuk *live terminal log streaming*.
- [ ] **Task 1.3: Frontend & Tauri Wrapper Init (`/frontend`).**
  - Inisialisasi Next.js 14+ (App Router, TypeScript, Tailwind CSS) dan instal `framer-motion`, `zustand`, `lucide-react`, `browser-image-compression`, serta `react-force-graph-2d`.
  - Siapkan konfigurasi opsional `src-tauri` (Tauri v2) dengan *fallback* instan ke `localhost:3000` agar pengguna dapat langsung melakukan *vibe coding* tanpa menunggu kompilasi Rust jika diinginkan.
- [ ] **🔒 CHECKPOINT 1 & PHANTOM AUDIT:**
  - *User Action:* Jalankan `docker-compose up -d`, nyalakan FastAPI (`uvicorn main:app --reload`), dan Next.js (`npm run dev`).
  - *Verification:* Pastikan `localhost:3000` dan `localhost:8000/api/health` merespons `200 OK` dan koneksi WebSocket berhasil tersambung.

---

## 🎨 PHASE 2: THE INTERROGATION ROOM (STRICT NEO-BRUTALISM UI)
**Tujuan:** Membangun alur kerja ruang interogasi 2 tahap di *frontend* dengan estetika **Strict Neo-Brutalism**, animasi fisik Framer Motion 60-120 FPS, dan kompresi gambar sisi-klien.

- [ ] **Task 2.1: Neo-Brutalist Design System (`tailwind.config.ts` & `globals.css`).**
  - Konfigurasi *font* Google: **Space Grotesk / Syne** (Display/Headers, `uppercase font-black`) dan **JetBrains Mono** (Log Terminal, Hash, Metrik).
  - Konfigurasi palet warna wajib: Canvas Background (`#F4F0EA`), Cyber Acid Yellow (`#FFE600`), Hazard Orange (`#FF4D00`), Radar Neon Green (`#00FF66`), Shocking Magenta (`#FF007A`), Verdict Crimson (`#FF0033`), dan Organic Emerald (`#00CC66`).
  - Buat komponen dasar **Tactile Mechanical Button** dengan Framer Motion (translasi tekan $X: 4\text{px}, Y: 4\text{px}$ hingga $8\text{px}$ yang menghilangkan bayangan hitam saat diklik).
- [ ] **Task 2.2: Client-Side Ephemeral Image Compressor (`utils/imageCompressor.ts`).**
  - Bangun fungsi pemrosesan unggahan (maksimal 10 gambar sekaligus) menggunakan HTML5 Canvas API / `browser-image-compression`.
  - Paksa kompresi setiap gambar menjadi **$< 2\text{MB}$** di memori browser dan konversi langsung ke *string* `Base64` lengkap dengan *hash* SHA-256 klien. Tolak otomatis jika melebihi batas kuota.
- [ ] **Task 2.3: Two-Stage Interrogation UI & Zustand Store (`store/useInterrogationStore.ts`).**
  - **Stage 1 (Context Lock Panel):** Input teks manual dan *dropzone* unggah *screenshot* berita/postingan utama (maks 10 gambar) untuk mengunci *Ground Truth*.
  - **Stage 2 (Evidence & Target Lock Panel):** Transisi layar mekanis menuju form bukti komentar *buzzer* (maks 10 gambar), *dropdown* wajib pemilih platform (`Instagram`, `X/Twitter`, `TikTok`, `Facebook`, `YouTube`), dan kolom input URL postingan (opsional).
  - **Live Terminal Log Ticker:** Panel terminal hitam-kuning bergaris *hazard stripes* yang siap menerima *stream log* eksekusi detik demi detik dari WebSocket FastAPI.
- [ ] **🔒 CHECKPOINT 2 & PHANTOM AUDIT:**
  - *User Action:* Uji unggah 10 gambar berukuran besar di browser dan coba transisi antar *Stage 1* dan *Stage 2*.
  - *Verification:* Gambar terkompresi $< 2\text{MB}$ secara instan menjadi pratinjau Base64 di dalam kartu berbatas hitam tebal (`border-4 border-black`) tanpa *lag* memori.

---

## 🧠 PHASE 3: ZERO-BLOAT INGESTION, OCR & GROUND TRUTH RAG
**Tujuan:** Menerima bukti di memori RAM sementara, mengekstrak multi-target dari *screenshot* komentar, dan membangun pijakan fakta netral (*Ground Truth*).

- [ ] **Task 3.1: Ephemeral Redis Buffer & Smart Hashing (`services/ephemeral_vault.py`).**
  - Buat *endpoint* `POST /api/interrogate/init`.
  - Hitung *hash* SHA-256 untuk setiap gambar dan *username*. Cek apakah hasil interogasi sudah ada di *cache* Redis atau *Hive-Mind DB*.
  - Simpan *string* Base64 gambar hanya di dalam RAM Redis dengan `TTL = 300 detik`. Sediakan fungsi `purge_session_media(session_id)` yang mengeksekusi `redis.delete()` + `gc.collect()`.
- [ ] **Task 3.2: Multi-Target Local OCR Engine (`services/ocr_engine.py`).**
  - Implementasikan ekstraksi teks langsung dari *buffer* memori Base64 menggunakan `pytesseract`.
  - **Zero-Error Fallback:** Jika *binary* Tesseract belum terinstal di Windows pengguna, otomatis beralih ke **EasyOCR** (pure Python) tanpa menghentikan proses.
  - Buat logika **Parallel Multi-Target Splitter**: Pisahkan hasil pembacaan OCR dari 10 *screenshot* menjadi daftar entitas target unik (misal terdeteksi 5 akun berbeda: `[@target1, @target2, ...]`), lengkap dengan isi teks komentar dan jumlah *likes* masing-masing.
- [ ] **Task 3.3: Ground Truth Fact-Checker RAG (`services/ground_truth_rag.py`).**
  - Gunakan **Groq API (`llama-3.3-70b-versatile`)** (dengan *auto-fallback* ke **Ollama Lokal** jika *offline*/*rate-limited*) untuk mengekstrak inti klaim dari teks/gambar *Stage 1*.
  - Jalankan pencarian fakta jurnalistik secara otomatis melalui **SearxNG Docker** (dengan *auto-fallback* ke *library* Python `duckduckgo-search` jika container SearxNG mati).
  - Hasilkan objek terstruktur `GroundTruthContext`: ringkasan fakta objektif, daftar kata kunci pencarian (*dorking keywords*), dan *baseline* netral untuk diadu dengan komentar para *buzzer*.
- [ ] **🔒 CHECKPOINT 3 & PHANTOM AUDIT:**
  - *User Action:* Kirimkan 1 *screenshot* berita dan 2 *screenshot* komentar lewat UI.
  - *Verification:* Terminal Log Ticker di UI menampilkan hasil pembacaan OCR secara *real-time*, memisahkan *username* komentator, dan menampilkan kesimpulan *Ground Truth* dari berita terkait.

---

## 🕷️ PHASE 4: THE SWARM (OSINT SCRAPER, ADAPTIVE DOM & FULL-FEED VISION)
**Tujuan:** Mengerahkan pasukan *scraper* paralel melalui IP residensial pengguna untuk menguliti metadata akun, melacak jejak komentar lintas postingan, dan memindai visual *feed* target.

- [ ] **Task 4.1: Parallel Swarm Queue (`workers/swarm_manager.py`).**
  - Konfigurasikan **Celery + Redis** (menggunakan flag `--pool=threads` atau `--pool=solo` agar 100% stabil di Windows).
  - **Zero-Error Fallback:** Sediakan eksekutor paralel berbasis **FastAPI `BackgroundTasks` + `asyncio.gather`** sehingga sistem tetap dapat memproses 5 target secara bersamaan meskipun pengguna tidak menyalakan *terminal worker* Celery terpisah.
- [ ] **Task 4.2: Stealth Playwright & LLM Adaptive DOM Parser (`services/osint_scraper.py`).**
  - Gunakan `playwright` + `playwright-stealth` dengan rotasi *User-Agent* otomatis untuk membuka profil publik target dan jendela transparansi akun (seperti *"About this account"*).
  - **Zero Hardcoded Selector:** Tarik seluruh teks mentah (*raw visible DOM text*) dari halaman profil dan kirim ke Groq/Ollama untuk mengekstrak JSON baku: `account_creation_date`, `username_change_count`, `account_location`, `follower_following_ratio`, dan `bio_text`. Jika salah satu metrik tidak disediakan oleh platform terkait, AI otomatis mengadaptasi bobot dari metrik yang tersedia.
- [ ] **Task 4.3: Cross-Post Activity Matcher / Jaring Pukat (`services/cross_post_matcher.py`).**
  - Jalankan *Automated OSINT Dorking* via SearxNG / `duckduckgo-search` dengan *query* `site:{platform}.com "{username}" "{ground_truth_keyword}"`.
  - Jika URL postingan diberikan pada *Stage 2*, kerahkan Playwright untuk menyapu komentar pada *thread* tersebut dan mencocokkan jejak *copy-paste* target di berbagai postingan lain.
- [ ] **Task 4.4: Full-Feed Computer Vision & Deepfake Analyzer (`services/vision_analyzer.py`).**
  - Jika akun publik, ambil sampel *buffer* memori hingga **30 gambar terakhir** dari *feed* target + foto profil.
  - Analisis foto profil menggunakan **OpenCV Fast Fourier Transform (FFT)** untuk mendeteksi anomali spektrum frekuensi wajah AI (*StyleGAN / ThisPersonDoesNotExist*).
  - Analisis keseragaman visual 30 gambar *feed* menggunakan **CLIP (`sentence-transformers/clip-ViT-B-32`)** atau *Perceptual Hashing* untuk mendeteksi akun yang 90% isinya hanya berupa *spam* poster propaganda seragam tanpa aktivitas organik.
- [ ] **🔒 CHECKPOINT 4 & PHANTOM AUDIT:**
  - *User Action:* Masukkan *username* target uji coba dan jalankan interogasi.
  - *Verification:* Sistem berhasil mengekstrak metadata profil tanpa terblokir *selector* yang berubah, menemukan jejak komentar di mesin pencari, memindai anomali visual di memori, dan langsung menghapus semua gambar dari RAM.

---

## 🎓 PHASE 5: THE TRUE LEARNER ENGINE (ML, NLP & STRICT DICTATOR)
**Tujuan:** Menghitung tingkat toksisitas, kemiripan narasi *copy-paste*, dan mengunci keputusan mutlak (0% area abu-abu) dengan kemampuan belajar instan (*Online Incremental Learning*).

- [ ] **Task 5.1: Indonesian NLP & Copy-Paste Matcher (`services/nlp_engine.py`).**
  - Integrasikan **IndoBERT (`indobenchmark/indobert-base-p1`)** (dioptimalkan dengan ONNX Runtime / fallback ringan) untuk menilai skor *hate speech*, sentimen agresif, dan *logical fallacy* terhadap *Ground Truth*.
  - Gunakan `TfidfVectorizer` + `cosine_similarity` dari Scikit-Learn untuk menghitung persentase kemiripan struktur kalimat antar komentar target (menangkap pola *copy-paste briefing*).
- [ ] **Task 5.2: Strict Threshold Dictator (`services/verdict_dictator.py`).**
  - Bangun matriks ekstraksi fitur numerik (`feature_vector`): `[umur_akun_norm, frekuensi_ganti_nama, rasio_anomali_engagement, skor_kemiripan_copas, skor_penyimpangan_ground_truth, skor_anomali_visual_feed]`.
  - Terapkan **Aturan Mutlak (Zero Grey-Area)**:
    - Skor Probabilitas Gabungan **$\ge 65\%$** $\rightarrow$ **MUTLAK TERINDIKASI BUZZER / BOT**.
    - Skor Probabilitas Gabungan **$< 65\%$** $\rightarrow$ **MUTLAK PENGGUNA ORGANIK**.
  - Klasifikasikan ke dalam 3 Tier Absolut:
    1. **TYPE A: AUTOMATED BOT SCRIPT** (Eksekusi milidetik, *copy-paste* identik $\ge 90\%$, profil kosong/wajah AI).
    2. **TYPE B: PAID HUMAN TROLL / BUZZER** (Bahasa dinamis namun membelokkan fakta *Ground Truth* secara agresif, riwayat ganti *username* tinggi, terhubung ke *cluster* serangan).
    3. **TYPE C: ORGANIC CITIZEN** (Manusia asli dengan riwayat akun wajar dan jejak aktivitas personal yang natural).
- [ ] **Task 5.3: Online Incremental Learning (`services/online_learner.py`).**
  - Inisialisasi model **Scikit-Learn `SGDClassifier(loss='log_loss')`**.
  - Buat *endpoint* `POST /api/interrogate/feedback`. Setiap kali pengguna menekan tombol validasi **"AKURAT"** atau **"MELESET"** pada kartu hasil di UI, sistem langsung memanggil fungsi `model.partial_fit(X, y)` detik itu juga, memperbarui bobot matriks (`joblib` snapshot), dan menyinkronkannya ke database.
  - Segera setelah *Verdict* selesai dihitung, panggil `purge_session_media()` untuk menghancurkan seluruh *string* Base64 gambar di Redis dan RAM.
- [ ] **🔒 CHECKPOINT 5 & PHANTOM AUDIT:**
  - *User Action:* Uji perhitungan *Verdict* pada sampel data dan tekan tombol *Feedback* ("Akurat"/"Meleset").
  - *Verification:* Model memperbarui bobot `.partial_fit()` dalam hitungan milidetik, menghasilkan prediksi baru yang lebih tajam, dan memastikan penggunaan RAM kembali bersih (0 byte gambar tersisa).

---

## 🕸️ PHASE 6: GRAPH MAPPING, HIVE-MIND SYNC & VERDICT STAMP DEPLOYMENT
**Tujuan:** Memetakan benang merah jaringan menuju "Akun Bos", merender kartu interogasi dengan animasi stempel Neo-Brutalist, dan menyinkronkan matriks ringan ke *Global Hive-Mind*.

- [ ] **Task 6.1: Network Graph & Centrality Engine (`services/graph_mapper.py`).**
  - Petakan seluruh entitas hasil interogasi ke **Memgraph** menggunakan *query* Cypher (atau otomatis menggunakan **NetworkX** jika *container* Memgraph tidak aktif): `(Buzzer_Node)-[:CO_COMMENTED / :AMPLIFIES]->(Central_Coordinator_Node)`.
  - Jalankan algoritma **PageRank / Degree Centrality** untuk menemukan simpul pusat gravitasi jaringan ("Akun Bos / Sumber Narasi") dan kembalikan struktur JSON `{ nodes: [...], links: [...] }`.
- [ ] **Task 6.2: The Verdict Cards & Interactive Graph UI (`components/VerdictDashboard.tsx`).**
  - **Multi-Card Staggered Deployment:** Gunakan Framer Motion untuk meluncurkan hingga 5 "Kartu Interogasi" secara berurutan seperti map dokumen rahasia yang dibanting ke meja.
  - **The Verdict Stamp Slam:** Animasi stempel raksasa (`100% PAID BUZZER - TYPE B` berwarna Crimson `#FF0033` atau `ORGANIC CITIZEN - TYPE C` berwarna Emerald `#00CC66`) yang menghantam kartu disertai efek getaran mikro (*screen-shake*).
  - **Interactive Physics Graph:** Render peta jaringan menggunakan `react-force-graph-2d` di atas kanvas bergaya Neo-Brutalist. Ketika satu *node* diklik, sorot jalur benang merah dengan garis putus-putus mengalir menuju *Central Boss Node*.
- [ ] **Task 6.3: Global Hive-Mind Sync (`services/hivemind_sync.py`).**
  - Kirimkan *payload* teks super ringan ($< 5\text{KB}$: `username_hash`, `platform`, `verdict_score`, `buzzer_type`, `relationship_edges`, `ml_weights_version`) ke **Supabase PostgreSQL** (dengan *fallback* otomatis ke **Local SQLite3**).
- [ ] **🔒 CHECKPOINT 6 (FINAL END-TO-END VERIFICATION):**
  - *User Action:* Lakukan simulasi interogasi penuh dari *Stage 1* (Konteks) $\rightarrow$ *Stage 2* (5 Target di *Screenshot*) $\rightarrow$ *Execute Interrogation* $\rightarrow$ *Graph Exploration* $\rightarrow$ *Active Learning Feedback*.
  - *Verification:* Seluruh alur berjalan mulus 60 FPS, tanpa *error*, 0 byte sampah gambar di penyimpanan, dan hasil akhir terpampang tegas sesuai standar *Enterprise*.

---

## 🛡️ BUILT-IN PHANTOM-TEST PROTOCOL (WAJIB DIEKSEKUSI AI DI SETIAP FASE)
Sebelum AI menyerahkan kode pada setiap *Checkpoint* di atas, AI **WAJIB** menjalankan simulasi pengujian mandiri terhadap 3 profil penyerang/pengguna ekstrem berikut dan menuliskan laporannya:
1. **Phantom A (The Heavy Multi-Target User):** Mengunggah batas maksimal 10 gambar konteks dan 10 gambar bukti yang berisi 5 akun berbeda sekaligus. *(Memastikan antrian paralel dan kompresi Canvas tidak membuat UI freeze).*
2. **Phantom B (The Edge-Case Breaker):** Mengunggah gambar buram/tanpa teks, memasukkan akun yang dikunci (*private*), atau menjalankan aplikasi saat Docker Memgraph/SearxNG mati. *(Memastikan seluruh Auto-Fallback bekerja mulus tanpa crash).*
3. **Phantom C (The Adversarial Injector):** Mencoba menyisipkan teks *Prompt Injection* atau skrip XSS di dalam gambar *screenshot* komentar untuk menipu LLM dan UI. *(Memastikan sanitasi Pydantic v2 dan prompt isolation bekerja sempurna).*