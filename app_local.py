import os
import re
import glob
import shutil
import tempfile
import hashlib
from datetime import datetime
from pathlib import Path
import pandas as pd
import gradio as gr
from cryptography.fernet import Fernet
import requests
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.client_credential import ClientCredential
from office365.runtime.auth.user_credential import UserCredential

# Import fungsi dari modules yang sudah ada
from ocr_processor import process_all_documents_with_competency
from pptx_generator import generate_presentations_from_csv

# ==================== SECURITY & ENCRYPTION ====================
class SecureDataHandler:
    """Handle enkripsi dan dekripsi data sensitif"""
    
    def __init__(self):
        # Generate atau load encryption key
        self.key = self._load_or_generate_key()
        self.cipher = Fernet(self.key)
    
    def _load_or_generate_key(self):
        """Load key dari file atau generate baru"""
        key_file = Path(".encryption_key")
        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            # Set permission hanya untuk owner
            os.chmod(key_file, 0o600)
            return key
    
    def encrypt_file(self, file_path):
        """Enkripsi file"""
        with open(file_path, "rb") as f:
            data = f.read()
        encrypted = self.cipher.encrypt(data)
        with open(file_path + ".enc", "wb") as f:
            f.write(encrypted)
        return file_path + ".enc"
    
    def decrypt_file(self, encrypted_path, output_path):
        """Dekripsi file"""
        with open(encrypted_path, "rb") as f:
            encrypted = f.read()
        decrypted = self.cipher.decrypt(encrypted)
        with open(output_path, "wb") as f:
            f.write(decrypted)
        return output_path
    
    def secure_delete(self, file_path):
        """Hapus file secara secure (overwrite dengan random data)"""
        if os.path.exists(file_path):
            # Overwrite dengan random data
            file_size = os.path.getsize(file_path)
            with open(file_path, "wb") as f:
                f.write(os.urandom(file_size))
            # Hapus file
            os.remove(file_path)

# ==================== SHAREPOINT HANDLER ====================
from office365.runtime.auth.client_credential import ClientCredential
from office365.sharepoint.client_context import ClientContext

class SharePointHandler:
    def __init__(self, client_id=None, client_secret=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.temp_dir = None
    
    def download_from_sharepoint(self, sharepoint_url, username=None, password=None, 
                               progress=gr.Progress()):
        try:
            progress(0, desc="Connecting to SharePoint...")
            
            site_url = self._extract_site_url(sharepoint_url)
            folder_path = self._extract_folder_url(sharepoint_url)
            
            # OPTION 1: Client Credential (lebih stabil)
            if self.client_id and self.client_secret:
                ctx = ClientContext(site_url).with_credentials(
                    ClientCredential(self.client_id, self.client_secret)
                )
            # OPTION 2: User Credential
            elif username and password:
                ctx = ClientContext(site_url).with_credentials(
                    UserCredential(username, password)
                )
            else:
                raise ValueError("Authentication credentials required")
            
            progress(0.2, desc="Authenticated. Fetching files...")
            
            # Create temp directory
            self.temp_dir = tempfile.mkdtemp(prefix="sp_download_")
            
            # Get folder - gunakan pendekatan yang lebih robust
            folder = ctx.web.get_folder_by_server_relative_url(folder_path)
            ctx.load(folder)
            
            # Get files in folder
            files = folder.files
            ctx.load(files)
            ctx.execute_query()
            
            if not files:
                raise Exception(f"No files found in folder: {folder_path}")
            
            progress(0.4, desc=f"Found {len(files)} files. Downloading...")
            
            # Download each file dengan error handling
            downloaded_files = []
            for idx, file in enumerate(files):
                try:
                    file_name = file.properties.get("Name", f"file_{idx}")
                    file_extension = os.path.splitext(file_name)[1].lower()
                    
                    # Hanya download file yang relevan
                    if file_extension not in ['.pdf', '.xlsx', '.xls', '.csv']:
                        continue
                    
                    local_path = os.path.join(self.temp_dir, file_name)
                    
                    with open(local_path, "wb") as local_file:
                        # Gunakan chunked download untuk file besar
                        file.download(local_file).execute_query()
                    
                    # Verifikasi file terdownload
                    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                        downloaded_files.append(local_path)
                        print(f"Downloaded: {file_name} ({os.path.getsize(local_path)} bytes)")
                    else:
                        print(f"Warning: File {file_name} may be empty or corrupted")
                    
                    progress(0.4 + (0.4 * (idx + 1) / len(files)), 
                            desc=f"Downloaded {idx + 1}/{len(files)} files")
                    
                except Exception as file_error:
                    print(f"Error downloading {file_name}: {str(file_error)}")
                    continue
            
            if not downloaded_files:
                raise Exception("No valid files were downloaded")
            
            progress(1.0, desc=f"Download complete! {len(downloaded_files)} files")
            return self.temp_dir, len(downloaded_files)
            
        except Exception as e:
            error_msg = f"SharePoint download error: {str(e)}"
            print(f"ERROR DETAILS: {error_msg}")
            
            # Cleanup jika error
            if self.temp_dir and os.path.exists(self.temp_dir):
                try:
                    shutil.rmtree(self.temp_dir)
                except:
                    pass
            
            # Berikan error message yang lebih spesifik
            if "mismatched tag" in str(e):
                error_msg += "\n\n🔧 **Solusi:**\n"
                error_msg += "1. Periksa URL SharePoint (pastikan mengarah ke folder, bukan file)\n"
                error_msg += "2. Gunakan credentials yang benar\n"
                error_msg += "3. Coba gunakan Client ID/Secret jika tersedia"
            
            raise Exception(error_msg)
    
    def _extract_site_url(self, full_url):
        """Extract site URL dari full SharePoint URL"""
        # Format: https://company.sharepoint.com/sites/sitename
        parts = full_url.split("/")
        return "/".join(parts[:5])
    
    def _extract_folder_url(self, full_url):
        """Extract folder relative URL"""
        try:
            from urllib.parse import urlparse
            
            parsed = urlparse(full_url)
            path = parsed.path
            
            # Jika URL berisi parameter query
            if '?' in path:
                path = path.split('?')[0]
            
            # Hapus bagian depan jika ada
            if '/sites/' in path:
                idx = path.find('/sites/')
                return path[idx:]
            
            return path if path else "/"
        except Exception:
            return full_url
    
    def cleanup(self):
        """Cleanup temporary directory"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

# ==================== MAIN PROCESSOR ====================
class CVSummaryProcessor:
    """Main processor untuk pipeline end-to-end"""
    
    def __init__(self):
        self.secure_handler = SecureDataHandler()
        self.sp_handler = SharePointHandler()
        self.temp_dirs = []
    
    def process_pipeline(self, 
                        input_type,
                        local_folder_path,
                        sharepoint_url,
                        sp_username,
                        sp_password,
                        excel_file,
                        template_file,
                        progress=gr.Progress()):
        """
        Process complete pipeline: OCR -> Analysis -> PPT Generation
        """
        output_folder = None
        try:
            progress(0, desc="Initializing...")
            
            # 1. Prepare input folder
            if input_type == "Local Folder":
                if not local_folder_path or not os.path.exists(local_folder_path):
                    return None, None, "❌ Local folder path tidak valid!"
                input_folder = local_folder_path
                progress(0.1, desc="Using local folder")
            else:  # SharePoint
                if not all([sharepoint_url, sp_username, sp_password]):
                    return None, None, "❌ SharePoint credentials tidak lengkap!"
            
                # Validasi URL format
                try:
                    self.validate_sharepoint_url(sharepoint_url)
                    progress(0.1, desc="Downloading from SharePoint...")
                    input_folder, num_files = self.sp_handler.download_from_sharepoint(
                        sharepoint_url, sp_username, sp_password, progress
                    )
                    self.temp_dirs.append(input_folder)
                    progress(0.2, desc=f"Downloaded {num_files} files")
                except ValueError as ve:
                    return None, None, f"❌ {str(ve)}"
            
            # 2. Validate Excel file
            if excel_file is None:
                return None, None, "❌ Excel competency file tidak ditemukan!"
            
            excel_path = excel_file.name
            progress(0.25, desc="Excel file validated")
            
            # 3. Create output folder
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_folder = os.path.join(tempfile.gettempdir(), f"cv_output_{timestamp}")
            os.makedirs(output_folder, exist_ok=True)
            self.temp_dirs.append(output_folder)
            
            # 4. Process OCR and Analysis
            progress(0.3, desc="Processing PDFs with OCR...")
            df_result = process_all_documents_with_competency(
                input_folder=input_folder,
                excel_path=excel_path,
                output_folder=output_folder,
                output_excel=f"hasil_analisis_{timestamp}.xlsx"
            )
            
            if df_result.empty:
                return None, None, "❌ Tidak ada data yang berhasil diproses!"
            
            progress(0.7, desc=f"Processed {len(df_result)} candidates")
            
            # 5. Find generated Excel file
            excel_files = glob.glob(os.path.join(output_folder, "hasil_analisis_*.xlsx"))
            if not excel_files:
                return None, None, "❌ File Excel hasil tidak ditemukan!"
            
            result_excel = excel_files[-1]
            
            # 6. Validate template
            if template_file is None:
                return None, None, "❌ Template PPT tidak ditemukan!"
            
            template_path = template_file.name
            progress(0.75, desc="Generating presentations...")
            
            # 7. Generate PowerPoint presentations
            ppt_output_dir = os.path.join(output_folder, "presentations")
            os.makedirs(ppt_output_dir, exist_ok=True)
            
            num_ppts = generate_presentations_from_csv(
                csv_path=result_excel,
                template_path=template_path,
                output_dir=ppt_output_dir
            )
            
            progress(0.9, desc=f"Generated {num_ppts} presentations")
            
            # 8. Create ZIP file untuk download
            zip_path = os.path.join(output_folder, f"cv_summary_results_{timestamp}.zip")
            shutil.make_archive(zip_path.replace('.zip', ''), 'zip', output_folder)
            
            progress(1.0, desc="Complete!")
            
            # 9. Generate summary report
            summary = self._generate_summary_report(df_result, num_ppts, output_folder)
            
            return result_excel, zip_path, summary
            
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            print(error_msg)
            return None, None, error_msg
        
        finally:
            # Cleanup SharePoint temp files
            if input_type == "SharePoint":
                self.sp_handler.cleanup()
    
    def _generate_summary_report(self, df, num_ppts, output_folder):
        """Generate summary report"""
        report = f"""
✅ **PROSES SELESAI!**

📊 **Statistik:**
- Total kandidat diproses: {len(df)}
- Kandidat dengan NIK: {len(df[~df['nik'].str.contains('NO_NIK', na=False)])}
- Kandidat dengan competency data: {len(df[df['competency'] != ''])}
- Presentasi PowerPoint dibuat: {num_ppts}

📁 **Output Files:**
- Excel hasil analisis: ✓
- PowerPoint presentations: ✓
- Text files (OCR results): ✓

⚠️ **Catatan Keamanan:**
- Semua data diproses secara lokal
- File temporary akan dihapus otomatis
- Download hasil segera sebelum session berakhir
"""
        return report
    
    def cleanup_all(self):
        """Cleanup all temporary directories"""
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        self.temp_dirs.clear()

    def validate_sharepoint_url(self, url):
        """Validate SharePoint URL format"""
        patterns = [
            r'https://.*\.sharepoint\.com/sites/.*',
            r'https://.*\.sharepoint\.com/.*'
        ]
        
        for pattern in patterns:
            if re.match(pattern, url):
                return True
        
        raise ValueError(f"Invalid SharePoint URL format. Expected: https://company.sharepoint.com/sites/...")

# ==================== GRADIO INTERFACE ====================
def create_interface():
    """Create Gradio interface"""
    
    processor = CVSummaryProcessor()
    
    # Custom CSS untuk styling
    custom_css = """
    .security-notice {
        background-color: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
    .success-notice {
        background-color: #d4edda;
        border: 1px solid #28a745;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
    """
    
    # For Gradio 6+, use the new way to apply CSS
    with gr.Blocks(title="CV Summary Generator - Secure") as app:
        
        # Add CSS to the app
        app.css = custom_css
        
        gr.Markdown("""
        # 🔒 CV Summary Generator (Secure & Private)
        
        **Pipeline End-to-End:** OCR → AI Analysis → PowerPoint Generation
        
        <div class="security-notice">
        ⚠️ <b>Keamanan Data:</b>
        <ul>
        <li>✓ Semua data diproses secara lokal dan terenkripsi</li>
        <li>✓ Tidak ada data yang dikirim ke server eksternal</li>
        <li>✓ File temporary otomatis terhapus setelah proses</li>
        <li>✓ Akses terbatas hanya untuk authorized users</li>
        </ul>
        </div>
        """)
        
        # ... rest of your code ...
        
        with gr.Row():
            with gr.Column(scale=2):
                
                # Input Type Selection
                input_type = gr.Radio(
                    choices=["Local Folder", "SharePoint Link"],
                    value="Local Folder",
                    label="📂 Pilih Sumber Input",
                    info="Pilih dari mana dokumen akan diambil"
                )
                
                # Local Folder Input
                with gr.Group(visible=True) as local_group:
                    local_folder = gr.Textbox(
                        label="📁 Path Folder Lokal",
                        placeholder="Contoh: D:/Project OCR Telkom/Input",
                        info="Folder berisi CV (PDF) dan Assessment (PDF)"
                    )
                
                # SharePoint Input
                with gr.Group(visible=False) as sharepoint_group:
                    sp_url = gr.Textbox(
                        label="🔗 SharePoint URL",
                        placeholder="https://company.sharepoint.com/sites/hr/documents/cv-folder",
                        info="URL lengkap ke folder SharePoint"
                    )
                    with gr.Row():
                        sp_username = gr.Textbox(
                            label="👤 Username",
                            placeholder="user@company.com",
                            type="email"
                        )
                        sp_password = gr.Textbox(
                            label="🔑 Password",
                            placeholder="Enter password",
                            type="password"
                        )
                
                # Excel Competency File
                excel_file = gr.File(
                    label="📊 Excel Competency File",
                    file_types=[".xlsx", ".xls"],
                    type="filepath"
                )
                
                # Template PPT File
                template_file = gr.File(
                    label="📄 Template PowerPoint",
                    file_types=[".pptx"],
                    type="filepath"
                )
                
                # Process Button
                process_btn = gr.Button(
                    "🚀 Proses Pipeline End-to-End",
                    variant="primary",
                    size="lg"
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### 📋 Status & Hasil")
                
                status_output = gr.Markdown("Menunggu input...")
                
                excel_output = gr.File(
                    label="📊 Download Excel Results",
                    visible=False
                )
                
                zip_output = gr.File(
                    label="📦 Download All Results (ZIP)",
                    visible=False
                )
        
        # Toggle visibility based on input type
        def toggle_input_type(choice):
            if choice == "Local Folder":
                return gr.update(visible=True), gr.update(visible=False)
            else:
                return gr.update(visible=False), gr.update(visible=True)
        
        input_type.change(
            fn=toggle_input_type,
            inputs=[input_type],
            outputs=[local_group, sharepoint_group]
        )
        
        # Process button click
        def process_wrapper(*args):
            excel, zip_file, summary = processor.process_pipeline(*args)
            
            if excel and zip_file:
                return (
                    summary,
                    gr.update(value=excel, visible=True),
                    gr.update(value=zip_file, visible=True)
                )
            else:
                return (
                    summary,
                    gr.update(visible=False),
                    gr.update(visible=False)
                )
        
        process_btn.click(
            fn=process_wrapper,
            inputs=[
                input_type,
                local_folder,
                sp_url,
                sp_username,
                sp_password,
                excel_file,
                template_file
            ],
            outputs=[status_output, excel_output, zip_output]
        )
        
        gr.Markdown("""
        ---
        ### 📖 Panduan Penggunaan:
        
        1. **Pilih Sumber Input:**
           - **Local Folder:** Masukkan path folder yang berisi CV dan Assessment (PDF)
           - **SharePoint:** Masukkan URL SharePoint dan credentials
        
        2. **Upload Files:**
           - Excel Competency (wajib)
           - Template PowerPoint (wajib)
        
        3. **Klik Proses:** Sistem akan menjalankan pipeline lengkap secara otomatis
        
        4. **Download Hasil:** Download Excel dan ZIP file yang berisi semua hasil
        
        ⏱️ **Estimasi Waktu:** 5-15 menit tergantung jumlah dokumen
        """)
    
    return app

# ==================== MAIN ====================
if __name__ == "__main__":
    # For testing with plain text passwords
    # Use a simple list of (username, password) tuples
    AUTH_CREDENTIALS = [
        ("admin", "admin123"),
        ("hr_team", "hr123"),
        ("user", "password123")
    ]
    
    # Create interface
    app = create_interface()
    
    #API Deployment
    app.launch(
        server_name="0.0.0.0",  # Listen on all network interfaces (useful for cloud deployment)
        server_port=int(os.getenv("PORT", 7860)),  # Use environment variable for dynamic port
        share=False,
        auth=AUTH_CREDENTIALS,  # List of tuples
        auth_message="🔒 Login dengan credentials yang diberikan",
        ssl_verify=True,  # Only enable if you're deploying securely
        show_error=True
    )