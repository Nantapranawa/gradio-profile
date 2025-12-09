import os
import tempfile
import shutil
from pathlib import Path
import gradio as gr
from ocr_processor import process_all_documents_with_competency
from pptx_generator import generate_presentations_from_csv

# ==================== SIMPLIFIED PROCESSOR ====================
class SimpleCVProcessor:
    def __init__(self):
        self.temp_dirs = []
    
    def process_pipeline(self, local_folder_path, excel_file, template_file, progress=gr.Progress()):
        """
        Simplified pipeline without SharePoint
        """
        try:
            progress(0, desc="Initializing...")
            
            # Validate inputs
            if not local_folder_path or not os.path.exists(local_folder_path):
                return None, None, "❌ Local folder path tidak valid!"
            
            if excel_file is None:
                return None, None, "❌ Excel competency file tidak ditemukan!"
            
            if template_file is None:
                return None, None, "❌ Template PPT tidak ditemukan!"
            
            excel_path = excel_file.name
            template_path = template_file.name
            
            progress(0.2, desc="Creating output directory...")
            
            # Create output folder
            import datetime
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            output_folder = os.path.join(tempfile.gettempdir(), f"cv_output_{timestamp}")
            os.makedirs(output_folder, exist_ok=True)
            self.temp_dirs.append(output_folder)
            
            # Process OCR
            progress(0.4, desc="Processing PDFs with OCR...")
            df_result = process_all_documents_with_competency(
                input_folder=local_folder_path,
                excel_path=excel_path,
                output_folder=output_folder,
                output_excel=f"hasil_analisis_{timestamp}.xlsx"
            )
            
            if df_result.empty:
                return None, None, "❌ Tidak ada data yang berhasil diproses!"
            
            progress(0.6, desc=f"Processed {len(df_result)} candidates")
            
            # Find generated Excel file
            import glob
            excel_files = glob.glob(os.path.join(output_folder, "hasil_analisis_*.xlsx"))
            if not excel_files:
                return None, None, "❌ File Excel hasil tidak ditemukan!"
            
            result_excel = excel_files[-1]
            
            # Generate PowerPoint
            progress(0.8, desc="Generating presentations...")
            ppt_output_dir = os.path.join(output_folder, "presentations")
            os.makedirs(ppt_output_dir, exist_ok=True)
            
            num_ppts = generate_presentations_from_csv(
                csv_path=result_excel,
                template_path=template_path,
                output_dir=ppt_output_dir
            )
            
            # Create ZIP
            zip_path = os.path.join(output_folder, f"cv_summary_results_{timestamp}.zip")
            shutil.make_archive(zip_path.replace('.zip', ''), 'zip', output_folder)
            
            progress(1.0, desc="Complete!")
            
            summary = f"""
✅ **PROSES SELESAI!**

📊 **Statistik:**
- Total kandidat diproses: {len(df_result)}
- Presentasi PowerPoint dibuat: {num_ppts}

📁 **Output Files:**
- Excel hasil analisis: ✓
- PowerPoint presentations: ✓
"""
            return result_excel, zip_path, summary
            
        except Exception as e:
            return None, None, f"❌ Error: {str(e)}"

# ==================== SIMPLIFIED GRADIO INTERFACE ====================
def create_simple_interface():
    processor = SimpleCVProcessor()
    
    with gr.Blocks(title="CV Summary Generator - Server Version") as app:
        gr.Markdown("""
        # 📊 CV Summary Generator (Server Version)
        
        **Simplified pipeline for server deployment**
        """)
        
        with gr.Row():
            with gr.Column():
                # Local Folder Input
                local_folder = gr.Textbox(
                    label="📁 Path Folder Lokal",
                    placeholder="Path to folder containing PDF files",
                    info="Folder must contain CV (PDF) and Assessment (PDF)"
                )
                
                # Excel Competency File
                excel_file = gr.File(
                    label="📊 Excel Competency File",
                    file_types=[".xlsx", ".xls"]
                )
                
                # Template PPT File
                template_file = gr.File(
                    label="📄 Template PowerPoint",
                    file_types=[".pptx"]
                )
                
                # Process Button
                process_btn = gr.Button(
                    "🚀 Process Documents",
                    variant="primary"
                )
            
            with gr.Column():
                status_output = gr.Markdown("Waiting for input...")
                
                excel_output = gr.File(
                    label="📊 Download Excel Results",
                    visible=False
                )
                
                zip_output = gr.File(
                    label="📦 Download All Results (ZIP)",
                    visible=False
                )
        
        def process_wrapper(local_folder, excel_file, template_file):
            excel, zip_file, summary = processor.process_pipeline(
                local_folder, excel_file, template_file
            )
            
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
            inputs=[local_folder, excel_file, template_file],
            outputs=[status_output, excel_output, zip_output]
        )
    
    return app

# ==================== SERVER ENTRY POINT ====================
if __name__ == "__main__":
    import os
    
    # Create the app
    app = create_simple_interface()
    
    # Get port from environment (for Railway/Render)
    port = int(os.environ.get("PORT", 7860))
    
    # Launch for server
    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        debug=False,
        quiet=True
    )