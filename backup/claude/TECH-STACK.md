# 🛠️ DETEKTO: COMPLETE TECH STACK ARCHITECTURE
**System Classification:** Decentralized Edge-Compute OSINT & CIB Engine  
**Cost Mandate:** $0.00 (100% Free-Tier, Open-Source, & Local Edge Execution)  
**Target OS Environment:** Windows 10/11 Native + Docker Desktop (Zero Linux-Config Friction)  
**Document Version:** 2.0 (Synchronized with Enterprise PRD v2.0)  

---

## 1. ARCHITECTURAL PARADIGM: HYBRID EDGE-NODE
Untuk memastikan Detekto dapat digunakan oleh jutaan pengguna secara bersamaan dengan biaya server **$0 (Nol Rupiah)** dan tanpa risiko *mass IP ban* atau *server overload*, arsitektur dibagi menjadi dua ranah:
1.  **Local Edge Engine (95% Beban Komputasi):** Berjalan langsung di PC/Laptop masing-masing pengguna (via Tauri Desktop Wrapper + Local Docker Node). Menangani OCR, *headless scraping* menggunakan IP residensial pengguna, analisis *Computer Vision*, dan inferensi *Machine Learning*.
2.  **Global Hive-Mind Cloud (5% Sinkronisasi Data):** Database pusat (Supabase Free Tier) yang hanya menerima matriks teks super ringan (< 5 KB per interogasi) untuk berbagi intelijen antar pengguna di seluruh dunia.

---

## 2. FRONTEND, DESKTOP SHELL & UI/UX (THE INTERROGATION ROOM)
Dibangun untuk kecepatan *native*, konsumsi RAM super irit, interaksi *real-time* 60-120 FPS, dan kepatuhan mutlak pada estetika **Strict Neo-Brutalism**.

*   **Desktop Wrapper (Edge Container):** **Tauri v2 (Rust-based)**
    *   *Fungsi:* Membungkus antarmuka Next.js menjadi aplikasi desktop *native* (`.exe` / `.msi`) yang memiliki akses langsung ke sistem lokal tanpa memakan RAM besar seperti Electron.
    *   *Zero-Error Fallback:* Jika saat pengembangan (*vibe coding*) instalasi *Rust toolchain* terasa berat, sistem secara otomatis dapat dijalankan sebagai **Local Web App (`localhost:3000`)** yang berkomunikasi langsung dengan Docker lokal.
*   **Core UI Framework:** **Next.js 14+ (App Router) + TypeScript**
    *   *Fungsi:* Menangani *routing* mekanis antar fase interogasi (*Context Lock* -> *Evidence Submission* -> *Parallel Verdict*) dengan keamanan tipe data yang ketat.
*   **Styling Engine:** **Tailwind CSS**
    *   *Konfigurasi Wajib:* Dikonfigurasi khusus untuk **Strict Neo-Brutalism** (Dilarang menggunakan *glassmorphism* / `backdrop-blur` atau *soft shadows*). Menggunakan utilitas kaku: `border-4` hingga `border-8` (`#000000`), sudut tajam (`rounded-none`), warna aksen kontras tinggi (`#FFE600`, `#FF0033`, `#00FF66`), dan *hard offset shadow* (`shadow-[8px_8px_0px_0px_#000000]`).
*   **Typography:** **Google Fonts (`Space Grotesk` / `Syne` + `JetBrains Mono`)**
    *   *Fungsi:* *Display font* ekstra tebal untuk header ala poster propaganda siber, dipadukan dengan *Monospace* teknis untuk *live terminal ticker*, *hash*, dan metrik persentase.
*   **Mechanical Motion Engine:** **Framer Motion**
    *   *Fungsi:* Mengeksekusi animasi fisik berkecepatan tinggi—tombol taktil yang menekan bayangan saat diklik, *staggered card deployment* (5 kartu meluncur berurutan), dan *Verdict Stamp Slam* dengan efek *screen-shake* halus.
*   **State Management:** **Zustand**
    *   *Fungsi:* Mengelola *state* paralel secara ringan (tanpa *boilerplate* Redux) ketika pengguna menginterogasi hingga 5 akun *buzzer* sekaligus dari 10 *screenshot*.
*   **Client-Side Image Compressor:** **HTML5 Canvas API (`browser-image-compression`)**
    *   *Fungsi:* Memaksa kompresi setiap gambar unggahan (maksimal 10 gambar) menjadi **< 2MB** dan mengonversinya langsung ke *string* Base64 di memori browser sebelum dikirim ke *backend* lokal.
*   **Interactive Graph Renderer:** **`react-force-graph-2d` (HTML5 Canvas)**
    *   *Fungsi:* Merender jaring laba-laba relasi *buzzer* hingga ribuan *node* dengan kalkulasi fisika yang mulus di atas kanvas 2D bergaya Brutalist.

---

## 3. LOCAL BACKEND & ORCHESTRATION API (THE CENTRAL NERVOUS SYSTEM)
Menjadi jembatan lokal yang mengatur lalu lintas data antara UI, antrian *scraper*, model ML, dan memori sementara.

*   **Core Language:** **Python 3.11+**
    *   *Alasan:* Ekosistem paling matang dan stabil untuk integrasi *Open-Source Intelligence* (OSINT), *Data Science*, dan *Machine Learning*.
*   **API Framework:** **FastAPI + Uvicorn (ASGI)**
    *   *Fungsi:* Menangani permintaan *asynchronous* berkecepatan tinggi dari *frontend* tanpa memblokir *thread* utama.
*   **Real-Time Telemetry:** **Native FastAPI WebSockets**
    *   *Fungsi:* Mengirimkan *stream log* interogasi secara *live* (detik demi detik) dari *worker* Python langsung ke komponen *Terminal Log Ticker* di layar Next.js tanpa perlu me-*refresh* halaman.
*   **Data Validation:** **Pydantic v2**
    *   *Fungsi:* Memastikan semua *input* dan *output* JSON (terutama dari LLM dan *scraper*) sesuai skema ketat dan bebas dari celah injeksi.

---

## 4. DISTRIBUTED OSINT & ADAPTIVE SCRAPING SWARM
Mesin penyusup lintas platform yang berjalan di atas IP residensial masing-masing pengguna (100% gratis, tanpa perlu sewa *proxy* atau beli API medsos).

*   **Asynchronous Task Queue & Broker:** **Celery + Redis (via Docker)**
    *   *Fungsi:* Memecah tugas berat (misal: menganalisis 5 target + menyapu ribuan komentar) menjadi *task* kecil yang dieksekusi paralel di latar belakang agar UI dan PC tidak *freeze*.
    *   *Windows Zero-Error Rule:* Jika Celery dijalankan secara *native* di Windows (di luar Docker) saat *debugging*, wajib menggunakan flag `--pool=solo` atau `--pool=threads` untuk menghindari *bug multiprocessing* bawaan Windows.
    *   *Zero-Error Fallback:* **FastAPI `BackgroundTasks` + Python `asyncio.Queue`** (Opsi tanpa konfigurasi jika pengguna ingin menjalankan mode ringan tanpa menyalakan *worker* Celery).
*   **Headless Stealth Browser:** **Playwright for Python + `playwright-stealth`**
    *   *Fungsi:* Membuka profil publik dan halaman transparansi akun ("About this account") secara tersembunyi dengan rotasi *User-Agent* otomatis untuk melewati deteksi *anti-bot* standar.
*   **Local Meta-Search & Fact-Finder:** **SearxNG (Self-Hosted via Docker)**
    *   *Fungsi:* Menggantikan Google Search API yang berbayar. Digunakan untuk dua hal:
        1.  **Ground Truth RAG:** Mencari berita jurnalistik kredibel terkait konteks postingan.
        2.  **Automated OSINT Dorking:** Menjalankan *query* `site:instagram.com "username_target" "isu"` untuk melacak jejak komentar target di ribuan postingan lain secara gratis.
    *   *Zero-Error Fallback:* **`duckduckgo-search` (Python Library)** — Bekerja 100% gratis dan instan langsung dari Python jika *container* SearxNG sedang tidak aktif.

---

## 5. MACHINE LEARNING, NLP & COMPUTER VISION (THE TRUE LEARNER)
Seluruh pemrosesan kecerdasan buatan dirancang agar tidak memungut biaya sepeser pun dan terus bertambah pintar seiring pemakaian.

*   **Context RAG & Adaptive DOM Parser:** **Groq Cloud API (Free Tier: `llama-3.3-70b-versatile` / `llama-3.1-8b-instant`)**
    *   *Fungsi:* 
        1. Membaca teks mentah (*raw DOM*) dari Playwright untuk mengekstrak Tanggal Pembuatan, Riwayat Ganti Username, dan Lokasi tanpa bergantung pada *CSS selector* yang mudah rusak.
        2. Menyusun kesimpulan *Ground Truth* dan membandingkannya dengan komentar target.
    *   *Zero-Cost & Fallback:* Groq menyediakan *Free Tier* yang sangat cepat dan membebaskan beban GPU laptop. Jika sedang *offline* atau melampaui *rate-limit* gratis, sistem otomatis beralih (*fallback*) ke **Ollama Lokal (`phi3:mini` atau `llama3.2:3b`)** yang berjalan 100% gratis di PC pengguna.
*   **Local OCR Engine:** **Tesseract OCR (`pytesseract`)**
    *   *Fungsi:* Mengekstrak *username*, isi komentar, dan jumlah *likes* langsung dari *buffer* gambar Base64.
    *   *Zero-Error Fallback:* **EasyOCR (PyTorch)** — Tidak memerlukan instalasi *binary* sistem eksternal, otomatis terunduh lewat `pip`, dan sangat akurat membaca *font* media sosial.
*   **Indonesian NLP & Toxicity Engine:** **IndoBERT (`indobenchmark/indobert-base-p1` via HuggingFace `transformers`)**
    *   *Fungsi:* Menganalisis sentimen dan mendeteksi *hate speech* atau pola bahasa *buzzer* berbahasa Indonesia (termasuk *slang*).
    *   *Zero-Bloat Optimization:* Berjalan menggunakan **ONNX Runtime (`optimum`)** agar inferensi di CPU laptop berjalan 3x lebih cepat dan hemat RAM.
*   **Copy-Paste & Narrative Matcher:** **Scikit-Learn (`TfidfVectorizer` + `cosine_similarity`)**
    *   *Fungsi:* Menghitung persentase kemiripan struktur kalimat antar akun secara matematis untuk membuktikan adanya *copy-paste briefing*.
*   **Online Incremental Learning Engine:** **Scikit-Learn `SGDClassifier` (Stochastic Gradient Descent with `loss='log_loss'`)**
    *   *Fungsi:* Otak pembelajaran aktif. Setiap kali pengguna menekan tombol validasi ("Akurat" / "Meleset") pada kartu hasil, sistem mengeksekusi fungsi `.partial_fit()` secara instan. Bobot matriks langsung diperbarui detik itu juga dan disimpan menggunakan `joblib`.
    *   *Strict Dictator Rule:* Menerapkan ambang batas mutlak di kode: Skor $\ge 65\%$ = **MUTLAK BUZZER (Type A: Bot Script / Type B: Paid Human Troll)**. Skor $< 65\%$ = **MUTLAK ORGANIK (Type C)**.
*   **Full-Feed Computer Vision & Deepfake Detector:** **OpenAI CLIP (`sentence-transformers/clip-ViT-B-32`) + Local Frequency Analyzer (OpenCV FFT)**
    *   *Fungsi:* Memindai hingga 30 gambar terakhir dari *feed* publik target untuk mendeteksi keseragaman poster propaganda, serta menganalisis spektrum frekuensi piksel (*Fast Fourier Transform*) dan *reverse image search* (via Playwright ke Yandex/Google Lens Web) untuk menangkap wajah buatan AI (*StyleGAN/ThisPersonDoesNotExist*) atau foto curian.

---

## 6. DATABASE, GRAPH & EPHEMERAL STORAGE (ZERO-BLOAT VAULT)
Manajemen memori ketat yang menjamin penyimpanan lokal maupun server pusat tidak pernah penuh oleh sampah gambar.

*   **Ephemeral RAM Buffer & Cache:** **Redis (via Docker)**
    *   *Smart Hashing:* Menyimpan *hash* SHA-256 dari gambar dan *username* agar target yang baru saja dianalisis tidak perlu diproses ulang.
    *   *Zero-Bloat Auto-Purge:* Menyimpan *string* Base64 gambar hanya di dalam RAM dengan aturan *Time-To-Live* (`TTL = 300 detik`) dan dieksekusi perintah `DEL` + Python `gc.collect()` detik itu juga setelah *Verdict* keluar. **Nol byte gambar yang disimpan ke hardisk/SSD.**
*   **Network Graph Database:** **Memgraph Platform (via Docker)**
    *   *Fungsi:* Database graf berbasis C++ (jauh lebih ringan dan hemat RAM dibanding Neo4j) untuk memetakan relasi `(Akun_Buzzer)-[:AMPLIFIES / :CO_COMMENTED]->(Central_Boss_Node)` dan menjalankan algoritma *PageRank / Centrality*.
    *   *Zero-Error Fallback:* **NetworkX (Pure Python In-Memory Graph)** — Jika *container* Memgraph tidak diaktifkan pada laptop berspesifikasi rendah, Python otomatis menghitung graf jaringan di dalam memori menggunakan `networkx` dan mengirimkan output JSON yang 100% kompatibel ke komponen visualisasi `react-force-graph`.
*   **Global Hive-Mind & Persistence:** **Supabase (PostgreSQL Free Tier) + Local SQLite Fallback**
    *   *Fungsi:* Menyimpan hasil akhir berupa teks murni (< 5 KB: `username_hash`, `platform`, `verdict_score`, `buzzer_type`, `ml_weights_snapshot`) untuk dibagikan ke seluruh pengguna Detekto.
    *   *Zero-Error Fallback:* **SQLite3 Lokal** — Terintegrasi langsung di Python tanpa instalasi tambahan, menjamin aplikasi tetap bekerja 100% meskipun tanpa koneksi ke cloud Supabase.

---

## 7. INFRASTRUCTURE & ZERO-FRICTION DEPLOYMENT (WINDOWS + DOCKER)
Dirancang khusus agar pengembang maupun pengguna di sistem operasi Windows tidak perlu berurusan dengan konfigurasi Linux/VMware yang rumit.

*   **Container Orchestration:** **Docker Desktop for Windows (`docker-compose.yml`)**
    *   *Fungsi:* Membungkus Redis, SearxNG, dan Memgraph (beserta *worker* opsional) ke dalam satu *file* konfigurasi otomatis. Cukup jalankan satu perintah `docker-compose up -d`, dan seluruh infrastruktur pendukung langsung menyala.
*   **Package & Environment Managers:**
    *   **Python:** `uv` (atau `pip` + `venv` standar) untuk instalasi *dependency* super cepat tanpa konflik versi.
    *   **Node.js:** `npm` atau `pnpm` untuk ekosistem Next.js dan Tauri.

---

## 📊 RINGKASAN MATRIKS ANTI-ERROR & ZERO-COST

| Komponen Sistem | Teknologi Utama ($0 Cost) | Fallback Otomatis (Anti-Error / Low-Spec) |
| :--- | :--- | :--- |
| **Desktop / UI Shell** | Tauri v2 + Next.js 14 (Tailwind) | Localhost Web App (`localhost:3000`) |
| **Task Queue** | Celery + Redis (Docker) | FastAPI `BackgroundTasks` + `asyncio` |
| **Fact-Finder & Dorking** | SearxNG (Self-Hosted Docker) | `duckduckgo-search` (Pure Python Package) |
| **LLM Reasoning & DOM** | Groq API (Free Tier) | Ollama Local (`phi3:mini` / `llama3.2`) |
| **OCR Engine** | Tesseract OCR (`pytesseract`) | EasyOCR (Pure Python/PyTorch) |
| **Graph Database** | Memgraph (C++ Docker) | `NetworkX` (Pure Python In-Memory Graph) |
| **Database & Hive-Mind** | Supabase PostgreSQL (Free Tier) | Native Python `sqlite3` (Local File) |