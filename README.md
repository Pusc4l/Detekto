# 🛡️ DETEKTO: Decentralized OSINT & CIB Threat Intelligence Engine

![Detekto Version](https://img.shields.io/badge/Version-0.1.0-FFE600?style=for-the-badge&logoColor=black)
![Platform](https://img.shields.io/badge/Platform-Windows_10%2F11-0078D4?style=for-the-badge&logo=windows)
![Architecture](https://img.shields.io/badge/Architecture-Edge--First-00CC66?style=for-the-badge)
![License](https://img.shields.io/badge/License-Strict_Copyright-FF0033?style=for-the-badge)

**Detekto** adalah Sistem Intelijen Siber terdistribusi berbasis *Edge-Computing* yang dirancang untuk melacak, membedah, dan mengidentifikasi operasi informasi terkoordinasi (*Buzzer*, *Botnet*, dan *Paid Human Trolls*) di media sosial.

Sistem ini berjalan 100% di mesin lokal Anda menggunakan konsep **Zero-Bloat Protocol**. Tidak ada satu pun gambar atau tangkapan layar bukti yang disimpan ke dalam *hard disk*. Semua pemrosesan (OCR, *Scraping*, *Computer Vision*, dan *Machine Learning*) dilakukan murni di dalam RAM (*Ephemeral Vault*) dan langsung dihancurkan setelah vonis (*Verdict*) dikeluarkan.

---

## ⚙️ CORE ARCHITECTURE & PIPELINE

Aplikasi ini bukan sekadar antarmuka web, melainkan gabungan 6 mesin yang bekerja paralel:
1. **Context RAG (SearxNG + Groq 120B):** Mencari landasan fakta netral (*Ground Truth*) dari berita jurnalistik.
2. **Local OCR Engine (Tesseract):** Mengekstrak *username* dan teks dari tangkapan layar (*screenshot*) secara otomatis.
3. **The Swarm (Playwright + Celery):** Mengerahkan *browser headless* secara siluman untuk menyusup dan menarik metadata profil target.
4. **Vision Analyzer (FFT + CLIP):** Mendeteksi anomali *Deepfake* pada foto profil dan keseragaman visual *feed*.
5. **Verdict Dictator (SGDClassifier):** Menghitung skor kemiripan *copy-paste* dan menjatuhkan vonis mutlak (Organik vs Buzzer).
6. **Graph Centrality (Memgraph):** Memetakan jaring relasi antar akun untuk menemukan dalang ("Akun Bos") penyebar narasi.

---

## ⚠️ SYSTEM REQUIREMENTS (PRASYARAT WAJIB)

Karena sistem ini memindahkan beban komputasi berat ke laptop Anda, pastikan PC Anda memenuhi spesifikasi berikut:

* **OS:** Windows 10 / 11 (Dioptimalkan murni untuk Windows).
* **RAM:** Minimal 16 GB (Sangat direkomendasikan agar The Swarm tidak *crash*).
* **Aplikasi Latar Belakang Wajib:**
  1. [**Docker Desktop**](https://www.docker.com/products/docker-desktop/) (Harus sudah *running* dan indikatornya berwarna HIJAU).
  2. [**Python 3.12+**](https://www.python.org/downloads/) (⚠️ **SANGAT PENTING:** Saat instalasi, wajib centang *"Add python.exe to PATH"*).
  3. [**Node.js v20+**](https://nodejs.org/) (Untuk menjalankan antarmuka Next.js).
  4. [**Tesseract OCR**](https://github.com/UB-Mannheim/tesseract/wiki) (Instal aplikasinya secara lokal di Windows Anda).

---

## 🚀 INSTALLATION & SETUP GUIDE

Ikuti langkah-langkah ini secara berurutan untuk menyalakan Detekto di mesin Anda:

### 1. Kloning Repositori
```cmd
git clone https://github.com/Pusc4l/Detekto.git
cd Detekto
```

### 2. Konfigurasi Kunci Mesin (.env)
Buka folder `backend`, lalu duplikat file `.env.example` dan ubah namanya menjadi `.env`. Buka file `.env` tersebut dan isi bagian yang wajib:
* `GROQ_API_KEY=` (Dapatkan API Key gratis di [console.groq.com](https://console.groq.com/keys)).
* `TESSERACT_CMD=` (Pastikan jalurnya sesuai dengan lokasi Anda menginstal Tesseract, misalnya: `C:\Program Files\Tesseract-OCR\tesseract.exe`).

### 3. Eksekusi Peluncuran (Satu Klik)
Pastikan **Docker Desktop** Anda sudah menyala di latar belakang. Kemudian, dari dalam folder utama `Detekto`, cukup klik dua kali file peluncur otomatis:

👉 **`start-detekto.bat`**

Skrip cerdas ini akan secara otomatis:
1. Membangun *Virtual Environment* Python (`.venv`).
2. Mengunduh seluruh mesin *Machine Learning* dan *Scraper* (Playwright).
3. Menyambungkan jaringan kontainer Docker (Redis, SearxNG, Memgraph).
4. Menyalakan API FastAPI dan antarmuka Next.js.

### 4. Mulai Interogasi
Jika instalasi berhasil, *browser* Anda akan otomatis membuka **`http://localhost:3000`** dengan status indikator **ONLINE** berwarna hijau.

---

## 🎯 CARA PENGGUNAAN (THE INTERROGATION ROOM)

1. **STAGE 01 (Context Lock):** Masukkan ringkasan isu yang mau diinvestigasi atau seret *screenshot* berita utama agar AI memahami "Fakta Sebenarnya".
2. **STAGE 02 (Target Evidence):** Pilih Platform, lalu seret maksimal 10 *screenshot* kolom komentar yang berisi akun-akun tersangka *buzzer*. Mesin OCR akan mendeteksi seluruh *username* secara otomatis.
3. **EXECUTE:** Tekan tombol interogasi dan pantau **Live Terminal Log Ticker**. Biarkan mesin The Swarm mencari rekam jejak mereka.
4. **TAKEDOWN DOSSIER:** Setelah vonis keluar, Anda dapat melihat peta graf jaringan (*Patient Zero*) dan mengekspor laporan forensiknya.

---

## ⚖️ COPYRIGHT & LICENSE NOTICE

**Copyright © 2026 by Pascal ([@Pusc4l](https://github.com/Pusc4l)). All Rights Reserved.**

Proyek **Detekto** ini merupakan hasil riset, arsitektur *engineering*, dan kekayaan intelektual (HAKI) eksklusif yang dikembangkan oleh **Pascal**.

⚠️ **STRICT USAGE & CREDIT POLICY:**
1. Anda diizinkan untuk mengunduh, menginstal, dan menggunakan aplikasi ini untuk keperluan investigasi OSINT personal.
2. **DILARANG KERAS** menyalin, memodifikasi, menjual ulang (*resell*), atau mengklaim arsitektur *source code* ini sebagai milik Anda, baik secara keseluruhan maupun sebagian.
3. Jika Anda melakukan *fork*, membahas, atau menampilkan sistem ini di publik (YouTube, Blog, Makalah Akademis, dll), Anda **MUTLAK WAJIB** memberikan kredit penuh kepada **Pascal (@Pusc4l)** dengan mencantumkan tautan ke repositori asli ini.
4. Pelanggaran terhadap hak cipta, pencurian kode tanpa atribusi, atau komersialisasi ilegal dari *core-engine* ini akan ditindak tegas secara hukum dan pelanggar akan dikenakan sanksi *takedown*.

*Developed with raw logic, strict Neo-Brutalism, and zero tolerance for cyber-manipulation.*