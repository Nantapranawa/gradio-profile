import os
import glob
import re
import pandas as pd
import google.generativeai as genai
import pytesseract
from pdf2image import convert_from_path
from PIL import Image, ImageEnhance, ImageFilter
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
import warnings
from collections import defaultdict
from difflib import SequenceMatcher
from dotenv import load_dotenv 

warnings.filterwarnings('ignore')
load_dotenv()

# REMOVE or MODIFY this line:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ADD THIS instead (check if we're on Railway/Heroku):
import sys

# Check if we're in Railway/Linux environment
if sys.platform == 'linux' or 'RAILWAY_ENVIRONMENT' in os.environ:
    # Linux/Heroku/Railway path
    pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
else:
    # Windows path for local development
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def verify_ocr_installation():
    """Verify that OCR engine is properly installed"""
    try:
        # Try to get tesseract version
        version = pytesseract.get_tesseract_version()
        print(f"✓ Tesseract OCR version: {version}")
        return True
    except Exception as e:
        print(f"✗ Tesseract OCR not found or not accessible: {e}")
        print("  Please ensure tesseract-ocr is installed in Railway environment")
        return False

# Konfigurasi Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 
GEMINI_MODEL = "gemini-2.5-flash-lite"

# Inisialisasi Gemini API
genai.configure(api_key=GEMINI_API_KEY)

def similarity_ratio(a: str, b: str) -> float:
    """Menghitung similarity ratio antara dua string"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_name_match(name: str, candidate_names: List[str], threshold: float = 0.7) -> Optional[str]:
    """Mencari nama terbaik yang match dari list candidate"""
    best_match = None
    best_score = 0
    
    for candidate in candidate_names:
        score = similarity_ratio(name, candidate)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = candidate
    
    return best_match

def read_excel_competency(excel_path: str, nik_column: str = 'nik', level_column: str = 'level', 
                         min_level: int = 2, top_n: int = 15) -> Dict[str, List[Dict]]:
    """
    Membaca data competency dari Excel dan mengambil top N competency dengan level >= min_level
    """
    
    try:
        print(f"Membaca file Excel: {excel_path}")
        
        # Baca file Excel
        df = pd.read_excel(excel_path)
        print(f"Total baris data: {len(df)}")
        print(f"Kolom yang tersedia: {list(df.columns)}")
        
        # Konversi kolom level ke numeric jika perlu
        if level_column in df.columns:
            df[level_column] = pd.to_numeric(df[level_column], errors='coerce')
        
        # Filter competency dengan level >= min_level
        df_filtered = df[df[level_column] >= min_level].copy()
        print(f"Data dengan level >= {min_level}: {len(df_filtered)} baris")
        
        # Kelompokkan berdasarkan NIK
        competency_by_nik = {}
        
        for nik, group in df_filtered.groupby(nik_column):
            # Sort berdasarkan level (descending)
            sorted_group = group.sort_values(by=level_column, ascending=False)
            
            # Ambil top N competency
            top_competencies = sorted_group.head(top_n)
            
            # Format competency ke dalam list of dict
            competencies_list = []
            for _, row in top_competencies.iterrows():
                competency_dict = {
                    'competency_type': str(row.get('competency_type', '')),
                    'competency_code': str(row.get('competency_code', '')),
                    'competency': str(row.get('competency', '')),
                    'level': int(row.get(level_column, 0)),
                    'source': str(row.get('source', ''))
                }
                competencies_list.append(competency_dict)
            
            competency_by_nik[str(nik)] = competencies_list
        
        print(f"Total NIK yang ditemukan dengan competency >= level {min_level}: {len(competency_by_nik)}")
        return competency_by_nik
        
    except Exception as e:
        print(f"Error membaca Excel: {e}")
        return {}

def format_competency_string(competencies_list: List[Dict]) -> str:
    """
    Format list competency menjadi string dengan format yang diminta
    """
    if not competencies_list:
        return ""
    
    formatted_list = []
    for comp in competencies_list:
        comp_name = comp.get('competency', '')
        level = comp.get('level', 0)
        formatted = f"•\t{comp_name} (Lvl. {level}/5)"
        formatted_list.append(formatted)
    
    return "\n".join(formatted_list)

def extract_nik_and_name_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Mencoba ekstrak NIK dan Nama dari text assessment
    Returns: (nik, nama)
    """
    nik = None
    nama = None
    
    # Pattern untuk NIK
    nik_patterns = [
        r'NIK\s*[:\.]?\s*(\d+)',
        r'Nomor\s+Induk\s+Karyawan\s*[:\.]?\s*(\d+)',
        r'Employee\s+ID\s*[:\.]?\s*(\d+)',
        r'ID\s+Karyawan\s*[:\.]?\s*(\d+)',
        r'\b\d{8,15}\b'
    ]
    
    for pattern in nik_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            nik = matches[0]
            break
    
    # Pattern untuk Nama
    name_patterns = [
        r'Nama\s*[:\.]?\s*([A-Za-z\s\.]+)(?:\n|$)',
        r'Name\s*[:\.]?\s*([A-Za-z\s\.]+)(?:\n|$)',
        r'Peserta\s*[:\.]?\s*([A-Za-z\s\.]+)(?:\n|$)',
        r'Candidate\s*[:\.]?\s*([A-Za-z\s\.]+)(?:\n|$)'
    ]
    
    for pattern in name_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            nama = matches[0].strip()
            # Bersihkan nama dari karakter tidak perlu
            nama = re.sub(r'[^A-Za-z\s\.]', '', nama)
            nama = nama.title()
            break
    
    # Jika tidak ditemukan pattern tertentu, cari di awal dokumen
    if not nama:
        lines = text.split('\n')
        for line in lines[:10]:  # Cari di 10 baris pertama
            line_clean = line.strip()
            if len(line_clean) > 3 and len(line_clean.split()) <= 4:
                # Asumsi ini adalah nama
                nama = line_clean.title()
                break
    
    return nik, nama

def generate_competency_with_ai(competencies_list: List[Dict]) -> str:
    """
    Menggunakan AI untuk membuat Skills (Competency) dari data Excel
    """
    if not competencies_list:
        return ""
    
    # Format data competency untuk AI
    competency_data = "\n".join([
        f"- {comp['competency']} (Level {comp['level']}/5)"
        for comp in competencies_list
    ])
    
    prompt = f"""Dari data competency Excel berikut, identifikasi dan format kompetensi kandidat dalam Bahasa Indonesia. Ambil maksimal 10 kompetensi dengan level minimal 2.

        Data Competency:
        {competency_data}
        
        ATURAN SANGAT PENTING:
        1. Urutkan dari level tertinggi ke terendah
        2. Hanya ambil kompetensi dengan level >= 2
        3. Format: • [Nama Kompetensi] (Lvl. [X]/5) hanya berikan spasi setelah bullet point
        4. Maksimal 10 kompetensi
        5. Jangan ada penjelasan tambahan, langsung ke poin-poin
        6. jangan gunakan \t setelah bullet point, cukup spasi saja jadi bullet pointnya seperti ini "• Career Planning & Succession Management (Lvl. 4/5)" tanpa tab setelah bullet pointnya
        
        Format output yang diharapkan (urutkan dari level tertinggi ke terendah):
        • Career Planning & Succession Management (Lvl. 4/5)
        • Employee Performance Management (Lvl. 4/5)
        • Human Capital Strategy (Lvl. 4/5)
        • Industrial Relations Management (Lvl. 3/5)
        • Learning Management & Development (Lvl. 3/5)
        • Organization Planning & Development (Lvl. 3/5)
        • Talent Scouting & Acquisition (Lvl. 2/5)

        Output:"""
    
    try:
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config={
                "temperature": 0.2,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 1024,
            }
        )
        
        response = model.generate_content(prompt)
        
        if response.text:
            return response.text.strip()
        else:
            # Fallback ke format manual
            return format_competency_string(competencies_list[:11])
            
    except Exception as e:
        print(f"    Error generating competency with AI: {e}")
        # Fallback ke format manual
        return format_competency_string(competencies_list[:11])

def analyze_with_gemini_advanced(text_content: str, competency_data: List[Dict] = None, categories: List[str] = ['education', 'experience', 'business_impact', 'position', 'summary_executive', 'skills_competency']) -> Dict:
    """
    Menggunakan Gemini AI untuk menganalisis teks dan mengekstrak informasi
    """
    
    results = {}
    
    prompts = {
        'education': """
        Dari teks CV/penilaian berikut, ekstrak informasi tentang pendidikan dalam Bahasa Indonesia:
        1. Gelar pendidikan tertinggi
        2. Institusi pendidikan
        3. Tahun lulus
        4. Jurusan/field study
        5. Usahakan jika ada S1 maka tampilkan S1 terlebih dahulu baru S2 jika ada S2
        
        Format output yang diharapkan: "S1 Teknik Informatika, ITB | S2 Master of Business Administration, ITB"
        Hanya tampilkan yang memang ada saja, jika tidak ada jangan ditampilkan dan jika ada S1 maka tampilkan terlebih dahulu yang S1 baru S2 jika S1 tidak ada maka gunakan template seperti ini "S1 Teknik Informatika, ITB" atau pada S2 seperti ini "S2 Master of Business Administration, ITB"
        Jangan gunakan bintang atau poin-poin, langsung format string seperti contoh.
        
        Teks yang akan dianalisis:
        """,
        
        'experience': """
        Dari teks CV/penilaian berikut, ekstrak informasi tentang pengalaman kerja dalam Bahasa Indonesia:
        Ambil 4 posisi jabatan terakhir saja.
        
        Format output yang diharapkan:
        Direktur Commercial
        PT Telekomunikasi Selular
        2021 – Saat ini
        
        Head of Human Capital Management 
        PT Finnet Indonesia
        2020 – 2021
        
        VP Human Capital Management 
        PT Jalin Pembayaran Nusantara 
        2018 – 2020
        
        SO Human Capital
        PT Jalin Pembayaran Nusantara
        2017 – 2018
        
        Jangan ada preambles pada awal jawaban jadi langsung pada 4 posisi jabatan terakhirnya, jangan gunakan bintang untuk poin-poinnya, jangan tampilkan reasoning, langsung format seperti contoh dan untuk setiap posisi jabatan pergunakan huruf kapital diawalnya saja misal SO Human Capital serta nama companynya juga huruf awalnya saja untuk huruf PT tetap besar misal PT Telkom Indonesia
        
        Teks yang akan dianalisis:
        """,
        
        'business_impact': """
        Dari teks CV/penilaian berikut, identifikasi potensi dampak bisnis dalam Bahasa Inggris:
        Ambil top 5 business impact.

        ATURAN SANGAT PENTING:
        - DILARANG KERAS menulis: "Berikut adalah", "Berdasarkan teks", "Top 5", atau penjelasan apapun
        - LANGSUNG mulai dengan bullet point pertama
        - HARUS tepat 5 poin
        - Format: • [Dampak bisnis]
        - Hanya kalimat singkat pada dampak bisnis saja seperti 5-7 kata saja, tanpa tambahan konteks atau penjelasan lainnya jadi to the point saja pada business impactnya
        
        Format output yang diharapkan:
        • Led a major organizational transformation project
        • Enhanced Total Rewards framework
        • Established, updated, and standardized Human Capital policies
        • Revamped Procurement policies and procedures
        • Redesigned and enhanced workplace areas
        
        Jangan ada preambles atau penjelasan pada awal response seperti "Berikut adalah top 5 potensi dampak bisnis yang diidentifikasi dari teks CV/penilaian:" hilangkan dan tidak usah digunakan saja jadi response jawaban seperti itu sehingga langsung ke poin-poin business impactnya.
        
        Teks yang akan dianalisis:
        """,
        
        'position': """
        Dari teks CV/penilaian berikut, identifikasi POSISI TERAKHIR/JABATAN TERAKHIR dalam Bahasa Indonesia:
        Hanya ambil satu posisi terakhir saja.
        
        Contoh output:
        Direktur Commercial
        
        atau
        
        Head of Human Capital Management
        
        Hanya berikan jawaban singkat nama posisinya saja, tanpa penjelasan tambahan.
        
        Teks yang akan dianalisis:
        """,
        
        'summary_executive': """
        Dari teks CV dan Assessment berikut, buatlah Summary Executive profesional dalam Bahasa Indonesia.
        
        Persyaratan:
        1. Panjang: 3-5 kalimat
        2. Highlight: Posisi terakhir, pengalaman tahun, keahlian utama, pencapaian signifikan
        3. Tone: Profesional dan ringkas
        4. Fokus pada value dan kontribusi kandidat
        
        Contoh format:
        "Profesional berpengalaman 15+ tahun di bidang Human Capital Management dengan track record memimpin transformasi organisasi di perusahaan telekomunikasi dan fintech. Saat ini menjabat sebagai Direktur Commercial di PT Telekomunikasi Selular, sebelumnya sebagai Head of Human Capital Management di PT Finnet Indonesia. Memiliki keahlian kuat dalam strategic planning, talent management, dan organizational development. Sukses mengimplementasikan SAP-Based HCIS dan meningkatkan employee engagement hingga 85%. Pendidikan S2 Master of Business Administration dari ITB dengan spesialisasi Strategic Management."
        
        Jangan ada preambles, langsung summary executive-nya.
        
        Teks yang akan dianalisis:
        """,
        
        'skills_competency': """
        Dari data competency Excel berikut, identifikasi dan format kompetensi kandidat dalam Bahasa Indonesia. Ambil maksimal 10 kompetensi dengan level minimal 2.

        ATURAN SANGAT PENTING:
        1. Urutkan dari level tertinggi ke terendah
        2. Hanya ambil kompetensi dengan level >= 2
        3. Format: • [Nama Kompetensi] (Lvl. [X]/5) hanya berikan spasi setelah bullet point
        4. Maksimal 10 kompetensi
        5. Jangan ada penjelasan tambahan, langsung ke poin-poin
        6. jangan gunakan \t setelah bullet point, cukup spasi saja jadi bullet pointnya seperti ini "• Career Planning & Succession Management (Lvl. 4/5)" tanpa tab setelah bullet pointnya

        Format output yang diharapkan (urutkan dari level tertinggi ke terendah):
        • Career Planning & Succession Management (Lvl. 4/5)
        • Employee Performance Management (Lvl. 4/5)
        • Human Capital Strategy (Lvl. 4/5)
        • Industrial Relations Management (Lvl. 3/5)
        • Learning Management & Development (Lvl. 3/5)
        • Organization Planning & Development (Lvl. 3/5)
        • Talent Scouting & Acquisition (Lvl. 2/5)

        Output:
        """
    }
    
    generation_config = {
        "temperature": 0.3,
        "top_p": 0.8,
        "top_k": 40,
        "max_output_tokens": 1024,
    }
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
    
    try:
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
    except Exception as e:
        print(f"Error inisialisasi model Gemini: {e}")
        for category in categories:
            results[category] = f"Error inisialisasi model: {str(e)}"
        return results
    
    for category in categories:
        if category in prompts:
            print(f"  Menganalisis {category} dengan Gemini AI...")
            
            try:
                # Special handling untuk skills_competency
                if category == 'skills_competency':
                    if competency_data and len(competency_data) > 0:
                        # Format competency data untuk prompt
                        competency_list = "Data Competency:\n"
                        for comp in competency_data:
                            comp_name = comp.get('competency', '')
                            level = comp.get('level', 0)
                            competency_list += f"- {comp_name} (Level {level}/5)\n"
                        
                        # Replace placeholder dengan data actual
                        full_prompt = prompts[category].replace('{competency_list}', competency_list)
                    else:
                        print(f"    ⚠ Tidak ada data competency, menggunakan fallback")
                        results[category] = ""
                        continue
                else:
                    max_text_length = 30000
                    truncated_text = text_content[:max_text_length] + "..." if len(text_content) > max_text_length else text_content
                    full_prompt = prompts[category] + "\n\n" + truncated_text
                
                response = model.generate_content(full_prompt)
                
                if response.text:
                    results[category] = response.text.strip()
                else:
                    results[category] = "Tidak dapat menganalisis dengan AI"
                    
            except Exception as e:
                print(f"    Error dalam analisis Gemini untuk {category}: {e}")
                results[category] = f"Error: {str(e)}"
            
            time.sleep(0.5)
    
    return results

def pdf_to_text_ocr_advanced(pdf_path, output_txt_path=None, lang='ind', preprocess=True, dpi=300):
    """Fungsi OCR untuk convert PDF ke text"""
    print(f"    Memproses PDF: {os.path.basename(pdf_path)}")
    
    try:
        # First verify OCR is available
        try:
            pytesseract.get_tesseract_version()
            print(f"    ✓ Tesseract tersedia")
        except Exception as ocr_err:
            print(f"    ⚠ OCR Engine not available: {ocr_err}")
            return ""
        
        # Check file size
        file_size = os.path.getsize(pdf_path) / (1024*1024)  # in MB
        print(f"    📄 File size: {file_size:.2f} MB")
        
        # Limit pages untuk mencegah hang
        max_pages = 5  # Hanya proses 5 halaman pertama
        print(f"    ⚙️  Membatasi proses ke {max_pages} halaman pertama")
        
        try:
            print(f"    🕐 Mengkonversi PDF ke gambar...")
            # Convert with limited pages
            images = convert_from_path(
                pdf_path, 
                dpi=200,  # Reduced DPI untuk kecepatan
                first_page=1, 
                last_page=max_pages,
                thread_count=1  # Single thread untuk stabilitas
            )
            
            if not images:
                print(f"    ❌ Tidak ada gambar yang dihasilkan")
                return ""
                
            print(f"    ✓ Berhasil mengkonversi {len(images)} halaman")
            
        except Exception as e:
            print(f"    ❌ Error mengkonversi PDF: {e}")
            return ""
        
    except Exception as e:
        print(f"    ❌ Error dalam setup OCR: {e}")
        return ""
    
    # Process images
    full_text = []
    
    for i, image in enumerate(images, start=1):
        print(f"    🔍 Processing page {i}/{len(images)}")
        
        if preprocess:
            # Simple preprocessing
            image = image.convert('L')  # Grayscale saja
        
        # OCR config
        custom_config = r'--oem 3 --psm 6 -l ind'
        
        try:
            text = pytesseract.image_to_string(image, lang=lang, config=custom_config)
            full_text.append(text)
            print(f"    ✓ Page {i} selesai ({len(text)} karakter)")
        except Exception as e:
            print(f"    ❌ Error OCR page {i}: {e}")
            full_text.append("")
    
    result_text = "\n".join(full_text)
    
    # Save if requested
    if output_txt_path:
        try:
            os.makedirs(os.path.dirname(output_txt_path), exist_ok=True)
            with open(output_txt_path, 'w', encoding='utf-8') as f:
                f.write(result_text)
        except Exception as e:
            print(f"    ❌ Error saving text: {e}")
    
    return result_text

def extract_name_from_filename(filename):
    """Ekstrak nama dari filename dengan berbagai pattern"""
    # Hapus ekstensi file
    name = os.path.splitext(filename)[0]
    
    print(f"  Debug - Original filename: {filename}")
    print(f"  Debug - Name after removing extension: {name}")
    
    # HAPUS SEMUA PATTERN CV (case-insensitive) TERLEBIH DAHULU
    # Pattern untuk menghapus "CV_" di awal, tengah, atau akhir
    patterns_to_remove = [
        # 1. Pattern untuk CV di awal dengan berbagai separator
        r'^cv[\s_\-]+',           # "CV_" di awal
        r'^cv$',                  # Hanya "CV"
        
        # 2. Pattern untuk CV di tengah dengan berbagai separator
        r'[\s_\-]+cv[\s_\-]+',    # "_CV_" di tengah
        
        # 3. Pattern untuk CV di akhir
        r'[\s_\-]+cv$',           # "_CV" di akhir
        
        # 4. Pattern khusus untuk "Cv_" (huruf besar C, kecil v)
        r'^Cv[\s_\-]+',           # "Cv_" di awal
        r'[\s_\-]+Cv[\s_\-]+',    # "_Cv_" di tengah
        r'[\s_\-]+Cv$',           # "_Cv" di akhir
        
        # 5. Hapus karakter khusus dan angka
        r'[\d_\-\.\(\)\[\]\{\}]+',
        
        # 6. Pattern umum lainnya
        r'resume[\s_\-]*',
        r'curriculum[\s_\-]*vitae[\s_\-]*',
        r'application[\s_\-]*',
        r'^[\s_\-]+',             # Spasi/underscore di awal
        r'[\s_\-]+$',             # Spasi/underscore di akhir
    ]
    
    for pattern in patterns_to_remove:
        name = re.sub(pattern, ' ', name, flags=re.IGNORECASE)  # Gunakan flag di luar pola
        # Debug setiap step
        # print(f"  Debug - After pattern '{pattern}': {name}")
    
    # HAPUS KHUSUS untuk kasus "CV_nama_kandidat" 
    # Split by underscore dan ambil bagian yang bukan "CV" (case-insensitive)
    parts = re.split(r'[\s_\-]+', name)
    print(f"  Debug - Parts after split: {parts}")
    
    filtered_parts = []
    for part in parts:
        part_lower = part.lower()
        # Skip jika bagian adalah "cv" dalam berbagai bentuk
        if part_lower in ['cv', 'c_v', 'c-v']:
            continue
        # Skip jika bagian terlalu pendek (kurang dari 2 karakter)
        if len(part) < 2:
            continue
        filtered_parts.append(part)
    
    name = ' '.join(filtered_parts)
    
    # Clean up: hapus spasi berlebih
    name = re.sub(r'\s+', ' ', name).strip()
    
    print(f"  Debug - Final name before title case: {name}")
    
    # Title case untuk nama
    if name:
        name = name.title()
    
    print(f"  Debug - Final name: {name}")
    
    return name

def group_and_match_documents(pdf_files: List[str]) -> Dict[str, Dict]:
    """
    Mengelompokkan dan mencocokkan CV dengan Assessment berdasarkan nama
    """
    print("\n" + "="*60)
    print("MENGGABUNGKAN CV DENGAN ASSESSMENT BERDASARKAN NAMA")
    print("="*60)
    
    # Kelompokkan dokumen berdasarkan nama dari filename
    documents_by_filename_name = defaultdict(list)
    
    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        name_from_filename = extract_name_from_filename(filename)
        
        # Tentukan tipe dokumen
        filename_lower = filename.lower()
        if 'cv' in filename_lower:
            doc_type = 'CV'
        elif 'assessment' in filename_lower or 'penilaian' in filename_lower:
            doc_type = 'ASSESSMENT'
        else:
            doc_type = 'OTHER'
        
        documents_by_filename_name[name_from_filename].append({
            'path': pdf_path,
            'filename': filename,
            'type': doc_type
        })
    
    # Dictionary untuk menyimpan pasangan CV-Assessment
    matched_documents = {}
    unmatched_assessments = []
    assessments_with_nik = {}
    
    print(f"\nMencari NIK dari file Assessment...")
    
    # Proses semua Assessment untuk ekstrak NIK dan nama
    for name, docs in documents_by_filename_name.items():
        for doc in docs:
            if doc['type'] == 'ASSESSMENT':
                print(f"  Memproses Assessment: {doc['filename']}")
                text = pdf_to_text_ocr_advanced(doc['path'], lang='ind')
                nik, extracted_name = extract_nik_and_name_from_text(text)
                
                if nik:
                    print(f"    ✓ NIK ditemukan: {nik}")
                    assessments_with_nik[nik] = {
                        'path': doc['path'],
                        'filename': doc['filename'],
                        'extracted_name': extracted_name,
                        'name_from_filename': name
                    }
                    
                    # Tambahkan ke unmatched untuk matching nanti
                    unmatched_assessments.append({
                        'nik': nik,
                        'assessment_data': assessments_with_nik[nik],
                        'name_from_filename': name
                    })
                else:
                    print(f"    ✗ NIK tidak ditemukan")
    
    print(f"\nTotal Assessment dengan NIK: {len(assessments_with_nik)}")
    
    # Sekarang coba match CV dengan Assessment
    print(f"\nMencocokkan CV dengan Assessment...")
    
    all_cv_names = []
    cv_documents = []
    
    # Kumpulkan semua CV
    for name, docs in documents_by_filename_name.items():
        for doc in docs:
            if doc['type'] == 'CV':
                cv_documents.append({
                    'path': doc['path'],
                    'filename': doc['filename'],
                    'name_from_filename': name
                })
                all_cv_names.append(name)
    
    print(f"Total CV ditemukan: {len(cv_documents)}")
    print(f"Total Assessment dengan NIK: {len(unmatched_assessments)}")
    
    # Matching logic
    for assessment in unmatched_assessments:
        nik = assessment['nik']
        assessment_name_from_filename = assessment['name_from_filename']
        assessment_extracted_name = assessment['assessment_data']['extracted_name']
        
        best_match = None
        best_match_name = None
        best_score = 0
        
        # Cari CV yang cocok
        for cv in cv_documents:
            cv_name = cv['name_from_filename']
            
            # Cek similarity dengan nama dari filename Assessment
            score1 = similarity_ratio(cv_name, assessment_name_from_filename)
            
            # Cek similarity dengan nama yang diekstrak dari Assessment
            if assessment_extracted_name:
                score2 = similarity_ratio(cv_name, assessment_extracted_name)
            else:
                score2 = 0
            
            score = max(score1, score2)
            
            if score > best_score and score >= 0.6:  # Threshold 60%
                best_score = score
                best_match = cv
                best_match_name = cv_name
        
        if best_match:
            print(f"\n✓ Ditemukan match:")
            print(f"  NIK: {nik}")
            print(f"  Assessment: {assessment['assessment_data']['filename']}")
            print(f"  CV: {best_match['filename']}")
            print(f"  Similarity score: {best_score:.2f}")
            
            # Buat key unik
            person_key = f"{nik}_{best_match_name}"
            
            matched_documents[person_key] = {
                'NIK': nik,
                'Nama': best_match_name,
                'CV': best_match['path'],
                'CV_filename': best_match['filename'],
                'Assessment': assessment['assessment_data']['path'],
                'Assessment_filename': assessment['assessment_data']['filename'],
                'Match_Score': best_score
            }
            
            # Hapus CV yang sudah dimatch dari list
            cv_documents = [cv for cv in cv_documents if cv['path'] != best_match['path']]
        else:
            print(f"\n✗ Tidak ditemukan match untuk Assessment: {assessment['assessment_data']['filename']}")
    
    # Tambahkan CV yang tidak memiliki match
    for cv in cv_documents:
        person_key = f"NO_NIK_{cv['name_from_filename']}"
        matched_documents[person_key] = {
            'NIK': '',
            'Nama': cv['name_from_filename'],
            'CV': cv['path'],
            'CV_filename': cv['filename'],
            'Assessment': '',
            'Assessment_filename': '',
            'Match_Score': 0
        }
        print(f"\n⚠ CV tanpa match: {cv['filename']}")
    
    print(f"\n" + "="*60)
    print("HASIL MATCHING:")
    print(f"Total pasangan CV-Assessment: {len([v for v in matched_documents.values() if v['Assessment']])}")
    print(f"Total CV tanpa Assessment: {len([v for v in matched_documents.values() if not v['Assessment']])}")
    print("="*60)
    
    return matched_documents

def process_matched_documents(matched_docs: Dict, competency_data: Dict, output_folder: str) -> List[Dict]:
    """
    Proses dokumen yang sudah dimatch
    """
    print("\n" + "="*60)
    print("MEMPROSES DOKUMEN YANG SUDAH DIMATCH")
    print("="*60)
    
    all_results = []
    
    for i, (person_key, person_data) in enumerate(matched_docs.items(), 1):
        nik = person_data['NIK']
        nama = person_data['Nama']
        
        print(f"\n[{i}/{len(matched_docs)}] Memproses: {nama}")
        print(f"  NIK: {nik if nik else 'Tidak ditemukan'}")
        
        # Gabungkan teks dari CV dan Assessment jika ada
        all_text = ""
        source_files = []
        
        # Proses CV
        if person_data['CV']:
            print(f"  Memproses CV: {person_data['CV_filename']}")
            cv_txt_path = os.path.join(output_folder, f"hasil_cv_{nama.replace(' ', '_')}.txt")
            cv_text = pdf_to_text_ocr_advanced(
                pdf_path=person_data['CV'],
                output_txt_path=cv_txt_path,
                lang='ind',
                preprocess=True,
                dpi=400
            )
            all_text += f"\n\n=== CV ===\n{cv_text}"
            source_files.append({
                'type': 'CV',
                'filename': person_data['CV_filename'],
                'output_path': cv_txt_path
            })
        
        # Proses Assessment
        if person_data['Assessment']:
            print(f"  Memproses Assessment: {person_data['Assessment_filename']}")
            ass_txt_path = os.path.join(output_folder, f"hasil_assessment_{nama.replace(' ', '_')}.txt")
            assessment_text = pdf_to_text_ocr_advanced(
                pdf_path=person_data['Assessment'],
                output_txt_path=ass_txt_path,
                lang='ind',
                preprocess=True,
                dpi=400
            )
            all_text += f"\n\n=== ASSESSMENT ===\n{assessment_text}"
            source_files.append({
                'type': 'ASSESSMENT',
                'filename': person_data['Assessment_filename'],
                'output_path': ass_txt_path
            })
            
            # Coba ekstrak NIK lagi dari Assessment jika belum ada
            if not nik:
                extracted_nik, _ = extract_nik_and_name_from_text(assessment_text)
                if extracted_nik:
                    nik = extracted_nik
                    print(f"  ✓ NIK ditemukan dari Assessment: {nik}")
        
        # Analisis dengan Gemini AI
        print(f"  Menganalisis dengan Gemini AI...")
        ai_analysis = analyze_with_gemini_advanced(
            all_text, 
            categories=['education', 'experience', 'business_impact', 'position', 'summary_executive']
        )
        
        # Ambil competency berdasarkan NIK dan generate dengan AI
        skills_competency = ""
        if nik and nik in competency_data:
            competencies = competency_data[nik]
            print(f"  ✓ Found {len(competencies)} competencies for NIK {nik}")
            # Gunakan AI untuk generate competency
            skills_competency = generate_competency_with_ai(competencies)
        else:
            print(f"  ✗ No competency data found for NIK: {nik}")
        
        # Buat hasil
        result = {
            'nik': nik if nik else f"NO_NIK_{nama}",
            'nama': nama,
            'jabatan terakhir': ai_analysis.get('position', ''),
            'summary executive': ai_analysis.get('summary_executive', ''),
            'education': ai_analysis.get('education', ''),
            'competency': skills_competency,
            'experience': ai_analysis.get('experience', ''),
            'business impact': ai_analysis.get('business_impact', ''),
            #'Source_Files': source_files,
            'Match_Score': person_data.get('Match_Score', 0),
            #'CV_File': person_data.get('CV_filename', ''),
            #'Assessment_File': person_data.get('Assessment_filename', '')
        }
        
        all_results.append(result)
        print(f"  ✓ Selesai: {nama}")
    
    return all_results

def process_all_documents_with_competency(input_folder: str, excel_path: str, 
                                         output_folder: str, output_excel: str = None) -> pd.DataFrame:
    """
    Proses utama: membaca dokumen PDF, matching CV-Assessment, baca Excel competency
    """
    
    # Buat output folder jika belum ada
    os.makedirs(output_folder, exist_ok=True)
    
    # 1. Baca data competency dari Excel
    print("="*60)
    print("MEMBACA DATA COMPETENCY DARI EXCEL")
    print("="*60)
    competency_data = read_excel_competency(excel_path, min_level=2, top_n=15)
    
    # 2. Cari semua file PDF
    print("\n" + "="*60)
    print("MENCARI DOKUMEN PDF")
    print("="*60)
    pdf_files = glob.glob(os.path.join(input_folder, "*.pdf"))
    
    if not pdf_files:
        print(f"Tidak ditemukan file PDF di folder: {input_folder}")
        return pd.DataFrame()
    
    print(f"Total {len(pdf_files)} file PDF ditemukan")
    
    # 3. Kelompokkan dan match CV dengan Assessment
    matched_documents = group_and_match_documents(pdf_files)
    
    # 4. Proses dokumen yang sudah dimatch
    all_results = process_matched_documents(matched_documents, competency_data, output_folder)
    
    # 5. Buat DataFrame dan simpan ke Excel
    print("\n" + "="*60)
    print("MENYIMPAN HASIL KE EXCEL")
    print("="*60)
    
    # Buat DataFrame
    df = pd.DataFrame(all_results)
    
    if df.empty:
        print("Tidak ada data yang diproses")
        return df
    
    # Cek nama kolom yang ada
    print(f"Kolom yang tersedia: {list(df.columns)}")
    
    # PERBAIKAN: Gunakan lowercase untuk semua kolom untuk konsistensi
    df.columns = [col.lower() for col in df.columns]
    
    # Tentukan kolom yang akan disimpan - PERBAIKAN
    required_columns = ['nik', 'nama', 'jabatan terakhir', 'summary executive', 
                       'education', 'competency', 'experience', 'business impact', 'match_score']
    
    # Tambahkan kolom yang hilang
    for col in required_columns:
        if col not in df.columns:
            df[col] = ''
            print(f"⚠ Menambahkan kolom kosong: {col}")
    
    # Hanya ambil kolom yang diperlukan
    df = df[required_columns]
    
    # Urutkan berdasarkan Match Score (descending) dan Nama
    df = df.sort_values(['match_score', 'nama'], ascending=[False, True])
    
    # Tentukan nama file output
    if not output_excel:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_excel = f"hasil_analisis_terintegrasi_{timestamp}.xlsx"
    
    output_excel_path = os.path.join(output_folder, output_excel)
    
    # Simpan ke Excel - PERBAIKAN dengan try-except detail
    try:
        with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Hasil Analisis')
            
            # Auto-adjust column width
            worksheet = writer.sheets['Hasil Analisis']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        cell_value = str(cell.value) if cell.value else ""
                        if len(cell_value) > max_length:
                            max_length = len(cell_value)
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print(f"\n✓ Hasil berhasil disimpan ke: {output_excel_path}")
        print(f"✓ Total data: {len(df)} orang")
        print(f"✓ Kolom: {', '.join(df.columns.tolist())}")
        
        # Statistik
        if 'nik' in df.columns:
            with_nik = df[~df['nik'].astype(str).str.contains('NO_NIK', na=False)].shape[0]
            print(f"✓ Orang dengan NIK: {with_nik}/{len(df)}")
        
        if 'competency' in df.columns:
            with_competency = df[df['competency'] != ''].shape[0]
            print(f"✓ Orang dengan competency data: {with_competency}/{len(df)}")
        
        if 'summary executive' in df.columns:
            with_summary = df[df['summary executive'] != ''].shape[0]
            print(f"✓ Orang dengan summary executive: {with_summary}/{len(df)}")
        
        # Tampilkan preview
        print("\nPreview hasil (3 pertama):")
        if 'nama' in df.columns and 'jabatan terakhir' in df.columns:
            print(df[['nama', 'jabatan terakhir']].head(3))
        
    except Exception as e:
        print(f"❌ Error menyimpan ke Excel: {e}")
        print(f"   DataFrame shape: {df.shape}")
        print(f"   DataFrame columns: {df.columns.tolist()}")
        print(f"   Data types: {df.dtypes.to_dict()}")
        
        # Debug: tampilkan beberapa baris
        print("\nSample data (first row):")
        if not df.empty:
            print(df.iloc[0].to_dict())
    
    return df

def create_detailed_report(df: pd.DataFrame, output_folder: str):
    """Buat laporan detail dengan informasi matching"""
    report_path = os.path.join(output_folder, f"detailed_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("LAPORAN DETAIL ANALISIS TERINTEGRASI\n")
        f.write("="*60 + "\n\n")
        
        f.write(f"Tanggal: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total data: {len(df)} orang\n")
        f.write(f"Model AI: {GEMINI_MODEL}\n\n")
        
        # Statistik
        with_nik = df[df['nik'].str.contains('NO_NIK', na=False) == False].shape[0]
        without_nik = len(df) - with_nik
        good_matches = df[df['Match_Score'] >= 0.7].shape[0]
        poor_matches = len(df) - good_matches
        
        f.write("STATISTIK MATCHING:\n")
        f.write("-"*40 + "\n")
        f.write(f"Orang dengan NIK: {with_nik}\n")
        f.write(f"Orang tanpa NIK: {without_nik}\n")
        f.write(f"Match score >= 0.7: {good_matches}\n")
        f.write(f"Match score < 0.7: {poor_matches}\n\n")
        
        f.write("STATISTIK DATA:\n")
        f.write("-"*40 + "\n")
        with_competency = df[df['competency'] != ''].shape[0]
        without_competency = len(df) - with_competency
        with_summary = df[df['summary executive'] != ''].shape[0]
        f.write(f"Dengan competency data: {with_competency}\n")
        f.write(f"Tanpa competency data: {without_competency}\n")
        f.write(f"Dengan summary executive: {with_summary}\n\n")
        
        # List orang tanpa NIK
        no_nik_df = df[df['nik'].str.contains('NO_NIK', na=False)]
        if not no_nik_df.empty:
            f.write("ORANG TANPA NIK (perlu pengecekan manual):\n")
            f.write("-"*40 + "\n")
            for _, row in no_nik_df.iterrows():
                f.write(f"- {row['Nama']} (CV: {row['CV_File']})\n")
            f.write("\n")
        
        # List orang dengan match score rendah
        low_match_df = df[(df['Match_Score'] < 0.7) & (df['Match_Score'] > 0)]
        if not low_match_df.empty:
            f.write("ORANG DENGAN MATCH SCORE RENDAH (<0.7):\n")
            f.write("-"*40 + "\n")
            for _, row in low_match_df.iterrows():
                f.write(f"- {row['Nama']} (Score: {row['Match_Score']:.2f})\n")
                f.write(f"  CV: {row['CV_File']}\n")
                f.write(f"  Assessment: {row['Assessment_File']}\n\n")
    
    print(f"✓ Detailed report disimpan ke: {report_path}")

def main():
    print("="*80)
    print("SISTEM ANALISIS TERINTEGRASI: CV + ASSESSMENT + EXCEL COMPETENCY + AI")
    print("="*80)
    
    # ADD THIS: Verify OCR installation
    print("\n🔍 VERIFIKASI SISTEM")
    print("-"*60)
    
    # Check OCR installation
    if not verify_ocr_installation():
        print("⚠ OCR engine tidak tersedia. Program mungkin tidak dapat membaca PDF.")
        print("⚠ Pastikan environment Railway memiliki:")
        print("   - tesseract-ocr")
        print("   - tesseract-ocr-ind (untuk bahasa Indonesia)")
        print("   - libtesseract-dev")
        print("   - poppler-utils")
        
        if 'RAILWAY_ENVIRONMENT' in os.environ:
            print("\n⚠ Railway Environment detected")
            print("⚠ Jika OCR tidak berjalan, periksa:")
            print("   1. Railway.json build configuration")
            print("   2. Package installation logs")
        
        continue_anyway = input("\nLanjutkan tanpa OCR? (y/n): ").strip().lower()
        if continue_anyway != 'y':
            print("Program dihentikan.")
            return None
    
    # Rest of your main function remains the same...
    print("\n📁 KONFIGURASI PATH")
    print("-"*60)
    
    INPUT_FOLDER = input("Masukkan path folder input (berisi CV & Assessment PDF): ").strip()
    if not INPUT_FOLDER or not os.path.exists(INPUT_FOLDER):
        print("❌ Folder tidak ditemukan!")
        INPUT_FOLDER = input("Coba lagi, masukkan path folder input: ").strip()
        if not os.path.exists(INPUT_FOLDER):
            print("❌ Folder masih tidak ditemukan. Program dihentikan.")
            return None
    
    #print(f"✓ Folder input: {INPUT_FOLDER}")
    
    EXCEL_PATH = input("Masukkan path file Excel competency: ").strip()
    if not EXCEL_PATH or not os.path.exists(EXCEL_PATH):
        print("❌ File Excel tidak ditemukan!")
        EXCEL_PATH = input("Coba lagi, masukkan path file Excel: ").strip()
        if not os.path.exists(EXCEL_PATH):
            print("❌ File Excel masih tidak ditemukan. Program dihentikan.")
            return None
    
    #print(f"✓ File Excel: {EXCEL_PATH}")
    
    OUTPUT_FOLDER = input("Masukkan path folder output (kosongkan untuk otomatis): ").strip()
    if not OUTPUT_FOLDER:
        OUTPUT_FOLDER = os.path.join(INPUT_FOLDER, "Result")
        print(f"✓ Menggunakan folder output otomatis: {OUTPUT_FOLDER}")
    
    OUTPUT_EXCEL = input("Masukkan nama file output Excel (kosongkan untuk default): ").strip()
    
    # Konfirmasi
    print("\n📋 RINGKASAN KONFIGURASI:")
    print("-"*60)
    print(f"Folder Input    : {INPUT_FOLDER}")
    print(f"File Excel      : {EXCEL_PATH}")
    print(f"Folder Output   : {OUTPUT_FOLDER}")
    print(f"File Output     : {OUTPUT_EXCEL if OUTPUT_EXCEL else 'Auto-generated'}")
    print("-"*60)
    
    confirm = input("\nMulai proses? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Program dibatalkan.")
        return None
    
    # Proses semua dokumen
    start_time = time.time()
    
    df = process_all_documents_with_competency(
        input_folder=INPUT_FOLDER,
        excel_path=EXCEL_PATH,
        output_folder=OUTPUT_FOLDER,
        output_excel=OUTPUT_EXCEL if OUTPUT_EXCEL else None
    )
    
    # Buat detailed report
    if not df.empty:
        create_detailed_report(df, OUTPUT_FOLDER)
    
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*80)
    print("PROSES SELESAI!")
    print("="*80)
    print(f"⏱ Waktu proses: {duration/60:.2f} menit")
    
    # Tampilkan path hasil
    print(f"\n📁 Hasil disimpan di:")
    print(f"  Folder output: {OUTPUT_FOLDER}")
    if not df.empty:
        excel_files = glob.glob(os.path.join(OUTPUT_FOLDER, "hasil_analisis_*.xlsx"))
        if excel_files:
            print(f"  File Excel: {excel_files[-1]}")
    
    return df

if __name__ == "__main__":
    # Jalankan program
    df_result = main()
    
    if df_result is not None and not df_result.empty:
        # Tampilkan menu akhir
        print("\n" + "="*60)
        print("MENU AKHIR")
        print("="*60)
        print("1. Tampilkan statistik lengkap")
        print("2. Export data ke JSON")
        print("3. Lihat orang tanpa NIK")
        print("4. Lihat sample summary executive")
        print("5. Keluar")
        
        try:
            choice = input("\nPilih opsi (1-5): ").strip()
            
            if choice == "1":
                print("\n📊 STATISTIK LENGKAP:")
                print("-"*50)
                print(f"Total data: {len(df_result)}")
                print(f"Data dengan NIK: {df_result[~df_result['ID'].str.contains('NO_NIK', na=False)].shape[0]}")
                print(f"Data dengan competency: {df_result[df_result['Skills (Competency)'] != ''].shape[0]}")
                print(f"Data dengan summary executive: {df_result[df_result['Summary Executive'] != ''].shape[0]}")
                print(f"Match score rata-rata: {df_result['Match_Score'].mean():.2f}")
                print(f"Match score >= 0.8: {(df_result['Match_Score'] >= 0.8).sum()}")
                
            elif choice == "2":
                output_folder = os.path.dirname(glob.glob("Result/*.xlsx")[0]) if glob.glob("Result/*.xlsx") else "Result"
                json_path = os.path.join(output_folder, 
                                       f"hasil_analisis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                df_result.to_json(json_path, orient='records', indent=2, force_ascii=False)
                print(f"✓ Data disimpan ke JSON: {json_path}")
                
            elif choice == "3":
                no_nik = df_result[df_result['ID'].str.contains('NO_NIK', na=False)]
                if not no_nik.empty:
                    print("\n👥 ORANG TANPA NIK:")
                    for _, row in no_nik.iterrows():
                        print(f"- {row['Nama']} (CV: {row.get('CV_File', '')})")
                else:
                    print("✓ Semua data memiliki NIK")
            
            elif choice == "4":
                print("\n📝 SAMPLE SUMMARY EXECUTIVE:")
                print("-"*50)
                samples = df_result[df_result['Summary Executive'] != ''].head(3)
                for idx, row in samples.iterrows():
                    print(f"\n{row['Nama']}:")
                    print(f"{row['Summary Executive']}")
                    print("-"*50)
                    
        except Exception as e:
            print(f"Error: {e}")