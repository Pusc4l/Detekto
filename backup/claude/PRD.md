# 📑 PRODUCT REQUIREMENTS DOCUMENT (PRD)
**Project Name:** DETEKTO  
**System Classification:** Decentralized OSINT & Coordinated Inauthentic Behavior (CIB) Threat Intelligence Engine  
**Architecture Paradigm:** Edge-First Distributed Computing (Client-Heavy / Zero-Server-Bloat)  
**Design Language:** Strict Neo-Brutalism (Industrial Cyber-Intelligence)  
**Document Version:** 2.0 (Enterprise Release Specification)  

---

## 1. EXECUTIVE SUMMARY & VISION
**Detekto** bukanlah sekadar aplikasi web atau situs pendeteksi biasa, melainkan sebuah **Sistem Intelijen Siber Terdistribusi**. Dirancang untuk membedah, melacak, dan mengidentifikasi operasi informasi terkoordinasi (*buzzer*, *botnet*, dan *paid human trolls*) lintas platform media sosial menggunakan data publik (OSINT) secara legal, objektif, dan masif.

Untuk menangani skala jutaan pengguna tanpa membebani infrastruktur pusat (tanpa risiko *server down*, *compute bottleneck*, atau *mass IP ban* dari platform medsos), Detekto menerapkan arsitektur **Decentralized Edge-Compute**. Beban kerja berat—mulai dari *Optical Character Recognition* (OCR), *headless web scraping*, pemrosesan *Computer Vision*, hingga inferensi *Machine Learning*—dieksekusi langsung di perangkat keras (PC/Laptop) masing-masing pengguna. Server pusat (Cloud) hanya bertindak sebagai **Global Hive-Mind** yang menyimpan matriks teks ringan, bobot pembelajaran mesin (*model weights*), dan pemetaan graf jaringan.

---

## 2. SYSTEM ARCHITECTURE: DECENTRALIZED EDGE-COMPUTE
Agar sistem dapat berjalan mulus (*smooth*) pada skala jutaan pengguna dengan biaya infrastruktur mendekati nol:
1. **Local Execution Wrapper (Tauri / Local Docker Node):** Sistem didistribusikan sebagai aplikasi sistem/desktop berbasis Tauri (Rust + Next.js) yang berkomunikasi dengan *local engine* di perangkat pengguna.
2. **Distributed Residential Scraping (Swarm Network):** Saat pengguna melakukan pelacakan, *headless browser* berjalan menggunakan koneksi internet/IP masing-masing pengguna. Jutaan pengguna = jutaan IP residensial yang berbeda, membuat sistem *anti-bot* platform media sosial mustahil melakukan pemblokiran massal.
3. **Ephemeral RAM Processing (Zero-Bloat Protocol):** Tidak ada satu pun gambar (*screenshot* bukti maupun foto profil target) yang diunggah ke server pusat. Semua gambar dikonversi ke Base64, diproses di dalam RAM lokal pengguna, dan **dihancurkan secara permanen (*auto-purge*)** detik itu juga setelah keputusan (*Verdict*) keluar.
4. **The Hive-Mind Sync:** Setelah komputer pengguna selesai menginterogasi target, perangkat tersebut hanya mengirimkan payload JSON super ringan (berukuran < 5 KB berisi: `username`, `platform`, `verdict_score`, `buzzer_type`, dan `relationship_nodes`) ke database pusat (Supabase/Memgraph) agar pengguna Detekto lain di seluruh dunia mendapatkan pembaruan intelijen secara *real-time*.

---

## 3. THE 9 CORE ENGINE PILLARS (FUNCTIONAL SPECIFICATIONS)

### PILAR 1: The Interrogation Room (Frontend Workflow Engine)
Antarmuka pengguna dirancang layaknya ruang interogasi intelijen yang sistematis dan tanpa celah.
*   **Phase 1 - Context Ingestion (Ground Truth Setup):** 
    *   Pengguna wajib memasukkan konteks sebelum menuduh target. Konteks dapat diketik manual atau melalui unggahan *screenshot* berita/postingan utama.
    *   *Multi-Upload & Client-Side Compression:* Mendukung unggahan hingga **maksimal 10 gambar sekaligus**. Sistem secara otomatis memaksa kompresi di sisi *browser/client* menggunakan HTML5 Canvas API hingga ukuran tiap gambar **< 2MB** sebelum masuk ke memori pemrosesan.
*   **Phase 2 - Evidence Submission (Target Locking):**
    *   Transisi layar mekanis menuju form unggahan bukti komentar *hate speech*, disinformasi, atau serangan terkoordinasi.
    *   *Platform Selector & Optional Deep-Link:* Dilengkapi *dropdown* wajib untuk memilih platform medsos (Instagram, X/Twitter, TikTok, Facebook, YouTube) untuk mengkalibrasi *parser* DOM, serta kolom input URL postingan ( bersifat opsional; sistem tetap bekerja 100% akurat hanya dari *screenshot* jika URL tidak diberikan, namun keberadaan URL akan mengaktifkan *deep-thread scraping*).
*   **Phase 3 - Parallel Multi-Target Extractor:**
    *   Pengguna tidak dibatasi pada satu target. Jika pengguna mengunggah 10 *screenshot* komentar yang di dalamnya terdapat (misalnya) 5 akun *buzzer* yang berbeda, mesin OCR dan parser akan otomatis mendeteksi kelima entitas tersebut, membelah proses menjadi **5 jalur interogasi paralel**, dan menyiapkan 5 kartu hasil yang berjalan beriringan.

### PILAR 2: Ground Truth & Fact-Checking Engine (Otak Netral & RAG)
Sistem tidak boleh bias dan harus memahami konteks dunia nyata sebelum menghakimi komentar target.
*   **Context Parser (Groq / Local LLM):** Menerjemahkan teks hasil ekstraksi *screenshot* konteks awal menjadi struktur masalah utama (Contoh: *"Postingan awal membahas kebijakan A yang dikritik warga karena dampak lingkungan X"*).
*   **Live Fact-Finder (Self-Hosted SearxNG):** Secara otomatis membentuk *query* pencarian dan menyisir indeks berita jurnalistik kredibel melalui *meta-search engine* lokal (SearxNG) untuk membangun pijakan fakta netral (*Ground Truth*).
*   **Bias & Disinformation Comparator:** Menyandingkan komentar target dengan *Ground Truth*. Jika fakta berita menyebutkan "A", namun target secara agresif membelokkan opini ke "B" menggunakan logika sesat (*logical fallacy*) atau serangan personal (*ad hominem*), indeks probabilitas *Buzzer* langsung melonjak.

### PILAR 3: Ingestion & Ephemeral Data Manager (Zero-Bloat Protocol)
Manajemen memori tingkat militer agar sistem tetap ringan, kencang, dan tidak pernah kehabisan ruang penyimpanan.
*   **Local OCR Engine (Tesseract):** Mengekstrak *handle/username*, waktu komentar, jumlah *likes*, dan isi teks komentar langsung dari *buffer* gambar di memori lokal.
*   **Smart Hashing (Redis + SHA-256):** Setiap gambar dan *username* yang masuk langsung diubah menjadi *cryptographic hash* SHA-256. Jika *hash* atau *username* tersebut baru saja dianalisis oleh pengguna lain di jaringan *Hive-Mind* dalam kurun waktu tertentu, sistem langsung menarik datanya secara instan tanpa memproses ulang dari nol.
*   **Strict Auto-Purge System:** Begitu ekstraksi OCR dan *Computer Vision* selesai, *Garbage Collector* langsung menimpa dan menghapus *string* Base64 gambar dari RAM. Database pusat hanya menyimpan matriks angka dan teks murni.

### PILAR 4: Distributed OSINT Scraper & Adaptive DOM Parsing
Mesin penyusup lintas platform yang kebal terhadap pembaruan antarmuka (UI) media sosial.
*   **Distributed Task Queue (RabbitMQ / Redis + Celery Workers):** Mengatur antrian *scraping* di latar belakang dengan pembagian beban kerja (*load balancing*) ke banyak *worker* paralel, memastikan kelancaran saat menarik ribuan data.
*   **Headless Stealth Swarm (Playwright):** Pasukan *browser* tanpa kepala (*headless*) yang dilengkapi *stealth plugin* dan rotasi *User-Agent* otomatis untuk membuka profil publik target dan mengekstrak informasi tanpa memicu *captcha* atau blokir.
*   **LLM-Assisted Adaptive DOM Extractor (Llama-3-8B / Phi-3):** 
    *   Setiap platform memiliki fitur transparansi yang berbeda (contoh: "About this account" di Instagram menampilkan riwayat ganti nama dan lokasi, sementara X menampilkan tanggal gabung dan sumber perangkat).
    *   Sistem **TIDAK menggunakan *hardcoded CSS/XPath selectors*** yang mudah rusak. Playwright akan menyapu bersih seluruh teks mentah (*raw DOM text*) dari halaman profil dan jendela transparansi akun, lalu menyerahkannya ke AI untuk dibaca layaknya manusia: *"Temukan Tanggal Pembuatan Akun, Jumlah Ganti Username, Lokasi Negara, dan Rasio Follower/Following dari tumpukan teks ini. Jika salah satu tidak tersedia di platform ini, abaikan dan maksimalkan data yang ada."*

### PILAR 5: Cross-Post Activity Matcher (Jaring Pukat Skala Besar)
Membuktikan sifat operasional *buzzer* dengan melacak jejak komentar mereka di seluruh internet.
*   **Automated OSINT Dorking (SearxNG):** Menjalankan *query* pencarian tingkat lanjut secara otomatis (contoh: `site:instagram.com "username_target" "kata_kunci_isu"`) untuk menemukan jejak komentar target di postingan lain yang terindeks mesin pencari.
*   **Mass-Thread Analyzer (Ribuan Postingan):** Berdasarkan kata kunci dari *Ground Truth*, *bot worker* dapat dikerahkan untuk menyapu ribuan postingan publik dan ratusan ribu komentar terkait isu tersebut di latar belakang.
*   **Cross-Reference Matrix:** Melakukan pencocokan silang di database. Jika *username* target terdeteksi menebar komentar dengan narasi serupa di 15 postingan berbeda dalam rentang waktu singkat, sistem mengunci status target sebagai bagian dari operasi terkoordinasi.

### PILAR 6: Full-Feed Computer Vision (Mata-Mata Visual)
Menganalisis keaslian akun melalui pemindaian visual menyeluruh, bukan hanya dari foto profil.
*   **Batch Feed Scraper:** Jika akun target tidak dikunci (*public*), *bot* secara otomatis mengambil sampel hingga **30 unggahan foto/visual terakhir** dari *feed* mereka ke dalam memori sementara.
*   **Visual Pattern & Deepfake Analyzer (CLIP + Local GAN Detector):**
    *   Memindai foto profil untuk mendeteksi anomali frekuensi piksel khas wajah buatan AI (*ThisPersonDoesNotExist* / *StyleGAN*) atau mencocokkannya melalui *headless reverse image search* untuk menangkap penggunaan foto curian/stock photo.
    *   Memindai 30 foto *feed* secara massal untuk menarik kesimpulan pola visual (Contoh: *"Dari 30 unggahan terakhir, 28 di antaranya adalah poster propaganda politik berdesain seragam, 0 foto aktivitas pribadi"* -> Indikasi kuat akun *Buzzer* dedikasi).

### PILAR 7: True Machine Learning Engine (Sistem yang Beneran Belajar)
Otak analitik yang berevolusi secara waktu nyata dari setiap interaksi pengguna.
*   **Local NLP & Copy-Paste Detector (IndoBERT + Cosine Similarity):** Menganalisis tingkat toksisitas/*hate speech* dalam bahasa Indonesia (termasuk bahasa gaul/slang) dan menghitung persentase kemiripan struktur kalimat antar akun untuk menangkap pola *copy-paste briefing*.
*   **Online Incremental Learning (Scikit-Learn `SGDClassifier` / PyTorch):** 
    *   Bukan model AI statis. Setiap kali kartu hasil interogasi muncul, pengguna memiliki tombol validasi ("Akurat" / "Meleset").
    *   Saat tombol diklik, sistem mengeksekusi fungsi `partial_fit()` secara instan. Bobot matriks (*weights*) pada model *Machine Learning* langsung diperbarui detik itu juga, membuat insting Detekto semakin tajam seiring bertambahnya jumlah pengguna.
*   **Strict Threshold Dictator (Zero Grey-Area):**
    *   Sistem **DILARANG KERAS** memberikan jawaban abu-abu atau ragu-ragu (seperti *"Mungkin Buzzer"*).
    *   Menggunakan ambang batas mutlak (*Hard Threshold* di angka **65%**). Skor $\ge 65\%$ dikunci mutlak sebagai **TERINDIKASI BUZZER/BOT**. Skor $< 65\%$ dikunci mutlak sebagai **PENGGUNA ORGANIK**.
    *   **3-Tier Classification Output:**
        1.  **TYPE A: AUTOMATED BOT SCRIPT** (Eksekusi mesin, jeda waktu milidetik, *copy-paste* identik, profil kosong/AI).
        2.  **TYPE B: PAID HUMAN TROLL / BUZZER** (Digerakkan manusia, bahasa dinamis namun membelokkan fakta *Ground Truth* secara agresif, akun hasil beli/sering ganti *username*, terhubung dengan *cluster* serangan).
        3.  **TYPE C: ORGANIC CITIZEN** (Manusia asli yang kebetulan berbeda pendapat atau pro-pemerintah secara organik, memiliki riwayat akun wajar dan jejak aktivitas personal yang natural).

### PILAR 8: Graph Database Mapping (Pemeta Jaringan & Benang Merah)
Mengungkap siapa dalang atau simpul utama di balik serangan keroyokan.
*   **Memgraph / Neo4j Integration:** Setiap interaksi publik yang berhasil ditarik (siapa me-*repost* siapa, akun mana saja yang selalu muncul bersamaan di kolom komentar yang sama, kesamaan waktu *posting*) dipetakan ke dalam *Graph Database*.
*   **Centrality & Cluster Algorithm (PageRank / Louvain):** Algoritma secara otomatis menghitung titik pusat gravitasi jaringan. Visualisasi graf akan menarik garis penghubung (benang merah) dari ratusan akun *bot/buzzer* kroco menuju satu atau beberapa **"Akun Bos / Influencer Koordinator" (Central Node)** yang menjadi sumber narasi.

---

## 4. UI/UX SPECIFICATIONS: STRICT NEO-BRUTALISM & HIGH-CRAFT MOTION

### 🚫 DESIGN BANS (MUTLAK DILARANG)
1.  **NO GLASSMORPHISM:** Dilarang menggunakan efek kaca buram (`backdrop-blur`), transparansi lembut, atau gradasi warna pastel yang mengambang.
2.  **NO "AI-SLOP" SAAS TEMPLATES:** Dilarang menggunakan desain standar template web AI modern (kartu putih dengan `border-radius` bulat lembut, bayangan abu-abu tipis `shadow-sm`, latar belakang ungu/biru gelap bergradasi neon halus, atau ikon-ikon generik).
3.  **NO AMBIGUOUS DATA DISPLAY:** Semua metrik harus terpampang tegas dalam kotak berbatas tebal.

### ⚡ STRICT NEO-BRUTALISM MANDATE (PILAR 9)
Estetika Detekto adalah **Industrial Cyber-Intelligence** yang mentah, berani, tajam, namun sangat terstruktur:
*   **Structural Borders:** Setiap kontainer, kartu, tombol, *input field*, dan panel graf wajib menggunakan garis tepi hitam pekat yang tebal (`border-4` hingga `border-8` dengan warna `#000000`). Sudut komponen harus tajam (`rounded-none`) atau memiliki potongan industrial tegas.
*   **Hard Offset Shadows:** Bayangan tidak boleh memiliki efek *blur* sama sekali. Gunakan bayangan blok padat yang bergeser secara diagonal (contoh CSS: `box-shadow: 8px 8px 0px 0px #000000;`).
*   **High-Contrast Raw Palette:**
    *   *Canvas Background:* Off-White Kertas Arsip (`#F4F0EA`) atau Industrial Concrete (`#E5E5E0`) agar garis hitam dan warna peringatan meledak secara visual.
    *   *Primary Accents:* Cyber Acid Yellow (`#FFE600`), Hazard Orange (`#FF4D00`), Radar Neon Green (`#00FF66`), dan Shocking Magenta (`#FF007A`).
    *   *Verdict Stamps:* Crimson Red (`#FF0033`) untuk mutlak Buzzer, Solid Emerald (`#00CC66`) untuk Organik.
*   **Typography:** Kombinasi huruf *Display Sans-Serif* ekstra tebal dan mengotak (seperti *Space Grotesk* atau *Syne* `font-black uppercase`) untuk judul, dipadukan dengan huruf *Monospace* teknis (*JetBrains Mono* atau *IBM Plex Mono*) untuk semua angka, *log* proses *scraping*, *hash*, dan persentase.

### 🎬 RICH & SMOOTH MECHANICAL ANIMATIONS
Meskipun desainnya kasar dan tegas (Brutalist), pergerakan antarmukanya harus **sangat mulus (60-120 FPS), responsif, dan kaya akan *micro-interactions*** menggunakan **Framer Motion**:
1.  **Tactile Mechanical Buttons:** Saat tombol di-*hover* atau diklik, tombol bergerak secara fisik menekan bayangan hitamnya (translasi posisi $X$ dan $Y$ sebesar `4px` hingga `8px` dengan *spring physics* yang kaku dan presisi, memberikan sensasi menekan tombol mesin fisik).
2.  **Live Terminal Log Ticker:** Saat *bot* sedang melakukan *scraping* dan OCR, tampilkan panel terminal bergaya Neo-Brutalist yang menggulirkan teks *log* eksekusi secara cepat dan mulus (*smooth auto-scroll*), lengkap dengan indikator *progress bar* bergaris-garis (*hazard stripes*) yang bergerak dinamis.
3.  **Multi-Card Staggered Deployment:** Ketika 5 tersangka selesai dianalisis, 5 "Kartu Interogasi" (*The Verdict Panels*) akan meluncur masuk ke layar secara berurutan (*staggered spring animation*) seperti map dokumen rahasia yang dibanting ke atas meja interogasi.
4.  **The Verdict Stamp Slam:** Keputusan akhir ("100% PAID BUZZER - TYPE B") tidak muncul begitu saja, melainkan memiliki animasi stempel besar yang menghantam kartu dari skala besar ke ukuran normal disertai efek getaran mikro (*screen-shake* halus) pada kartu tersebut.
5.  **Interactive Physics Graph:** Peta jaringan *Memgraph* dapat digeser, diperbesar (*zoom*), dan ditarik-tarik (*drag*) dengan pantulan fisika yang sangat mulus. Saat satu *node* akun diklik, *node* lain yang tidak berhubungan langsung meredup secara elegan, menyoroti jalur benang merah dengan animasi garis putus-putus yang mengalir menuju "Akun Bos".

---

## 5. END-TO-END USER FLOW (THE INTERROGATION PIPELINE)
1.  **Launch System:** Pengguna membuka Detekto. Layar langsung menampilkan **Stage 1: Context Lock** dengan estetika Neo-Brutalist penuh.
2.  **Input Ground Truth:** Pengguna mengunggah 3 *screenshot* berita asli (otomatis dikompresi < 2MB di memori) atau mengetikkan ringkasan topik. Sistem langsung menjalankan *Live Fact-Finder* (SearxNG) di latar belakang untuk mengunci fakta netral.
3.  **Input Target Evidence:** Layar bergeser secara mekanis ke **Stage 2: Target Evidence**. Pengguna memilih platform (misal: Instagram), memasukkan link postingan (opsional), dan mengunggah 5 *screenshot* berisi keroyokan komentar *buzzer*.
4.  **Execute Swarm:** Pengguna menekan tombol raksasa **"EXECUTE INTERROGATION"**.
5.  **Parallel Processing View:** Layar membelah menjadi panel *monitoring*. Terlihat 5 jalur *progress* berjalan beriringan:
    *   *OCR membaca teks & memisahkan 5 username...*
    *   *Playwright Swarm menyusup ke 5 profil & menarik teks About This Account...*
    *   *SearxNG & Mass-Thread Analyzer menyisir ribuan komentar di postingan lain...*
    *   *CLIP memindai 30 foto feed publik...*
6.  **The Verdict Deployment:** Dalam hitungan detik, 5 **Verdict Cards** menghantam layar. Masing-masing menampilkan:
    *   Stempel Mutlak (**BUZZER** / **ORGANIK**) + Klasifikasi (**Type A / B / C**).
    *   Skor Probabilitas & Bukti Dosa (*"Bergabung 12 hari lalu, ganti username 4x, komentar 98% identik ditemukan di 14 postingan lain, menyimpang total dari fakta Ground Truth"*).
    *   Peta Jaringan Interaktif yang memperlihatkan kelima akun tersebut ternyata bermuara pada satu akun koordinator yang sama.
7.  **Active Learning Feedback & Purge:** Pengguna menekan tombol validasi pada kartu. Bobot ML lokal dan *Hive-Mind* langsung ter-update detik itu juga, dan seluruh data gambar di RAM langsung dihancurkan tanpa sisa.