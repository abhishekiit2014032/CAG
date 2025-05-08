import os
import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from PyPDF2 import PdfReader
from docx import Document
import streamlit as st

# Load environment variables from .env file
load_dotenv()

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    st.error("Please set the GEMINI_API_KEY environment variable.")
    st.stop()

genai.configure(api_key=API_KEY)
MODEL_RESOURCE_NAME = "models/gemini-1.5-pro-001"

# ========== Document Extraction ==========

def extract_text_from_pdf(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        text_parts = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                text_parts.append(f"[Page {i+1}]\n{text}")
        return "\n\n".join(text_parts)
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return ""

def extract_text_from_docx(docx_file):
    try:
        doc = Document(docx_file)
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text)
        return "\n\n".join(text_parts)
    except Exception as e:
        st.error(f"Error reading DOCX: {e}")
        return ""

def process_document_content(pdf_file=None, docx_file=None):
    combined_content = []
    if pdf_file is not None:
        pdf_text = extract_text_from_pdf(pdf_file)
        if pdf_text.strip():
            combined_content.append(pdf_text)
    if docx_file is not None:
        docx_text = extract_text_from_docx(docx_file)
        if docx_text.strip():
            combined_content.append(docx_text)
    final_content = "\n\n--- End of Document Section ---\n\n".join(combined_content)
    return final_content if final_content.strip() else None

# ========== Image Preview Matcher ==========

def try_show_image_preview(response_text):
    meta_images_dir = "meta_images"
    if not os.path.exists(meta_images_dir):
        return

    for filename in os.listdir(meta_images_dir):
        name, ext = os.path.splitext(filename)
        if name.lower() in response_text.lower():
            st.image(os.path.join(meta_images_dir, filename), caption=name)
            break

# ========== Chat Interface ==========

def chatbot_interface(document_content, language="English"):
    if not document_content:
        msg = "दस्तऐवज सामग्री उपलब्ध नसल्यामुळे चॅटबॉट सुरू करू शकत नाही." if language == "मराठी" else "Cannot start chatbot as document content is not available."
        st.error(msg)
        return

    try:
        model = genai.GenerativeModel(MODEL_RESOURCE_NAME)

        if language == "मराठी":
            system_message = (
                "तुम्ही एक मदतगार सहाय्यक आहात. तुमचे कार्य वापरकर्त्याच्या प्रश्नांची उत्तरे दस्तऐवजावर आधारित देणे आहे. "
                "माहिती नसल्यास सांगा: 'ही माहिती प्रदान केलेल्या दस्तऐवजांमध्ये उपलब्ध नाही.' "
                "तुम्ही मराठी भाषेत उत्तर द्या."
            )
            document_message = (
                "दस्तऐवज सामग्री सुरू\n\n"
                f"{document_content}\n\n"
                "दस्तऐवज सामग्री समाप्त\n\n"
                "फक्त वरील सामग्रीचा वापर करून उत्तर द्या."
            )
        else:
            system_message = (
                "You are a helpful assistant. Answer only based on the document content. "
                "If the info isn't there, say: 'The information is not available in the provided documents.'"
            )
            document_message = (
                "DOCUMENT CONTENT START\n\n"
                f"{document_content}\n\n"
                "DOCUMENT CONTENT END\n\n"
                "Use ONLY the above content to answer questions."
            )

        if "chat" not in st.session_state:
            chat = model.start_chat()
            chat.send_message(system_message)
            chat.send_message(document_message)
            st.session_state["chat"] = chat

        if "messages" not in st.session_state:
            st.session_state["messages"] = []

        for message in st.session_state["messages"]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        chat_placeholder = "दस्तऐवजांबद्दल प्रश्न विचारा:" if language == "मराठी" else "Ask a question about the documents:"
        if prompt := st.chat_input(chat_placeholder):
            st.session_state["messages"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                try:
                    response = st.session_state["chat"].send_message(prompt, stream=True)
                    for chunk in response:
                        full_response += (chunk.text or "")
                        message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(full_response)
                    st.session_state["messages"].append({"role": "assistant", "content": full_response})
                    try_show_image_preview(full_response)
                except Exception as e:
                    st.error(f"Error: {e}")

    except Exception as e:
        st.error(f"Error initializing chatbot: {e}")

# ========== Main App ==========

def main():
    language = st.sidebar.radio("भाषा निवडा / Select Language", ["मराठी", "English"])

    st.session_state["language"] = language

    if language == "मराठी":
        st.title("जेमिनी सह दस्तऐवज चॅटबॉट")
        processing_msg = "दस्तऐवज प्रक्रिया करत आहे..."
        details_label = "दस्तऐवज प्रक्रिया तपशील"
        success_msg = "दस्तऐवज प्रक्रिया पूर्ण झाली."
        length_msg = "एकूण लांबी: {} वर्ण"
        file_msg = "{} फाइल: {}"
        reset_btn = "चॅट रीसेट करा"
        reset_msg = "चॅट इतिहास रीसेट केला गेला आहे."
        error_msg = "दस्तऐवज प्रक्रिया अयशस्वी."
        upload_msg = "कृपया 'data_files/' मध्ये PDF किंवा DOCX फाइल्स ठेवा."
    else:
        st.title("Document Chatbot with Gemini")
        processing_msg = "Processing documents..."
        details_label = "Document Processing Details"
        success_msg = "Documents processed successfully."
        length_msg = "Total content length: {} characters"
        file_msg = "{} file: {}"
        reset_btn = "Reset Chat"
        reset_msg = "Chat history has been reset."
        error_msg = "Failed to process documents."
        upload_msg = "Please place PDF or DOCX files in the 'data_files/' folder."

    data_dir = "data_files"
    pdf_files = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.lower().endswith(".pdf")]
    docx_files = [os.path.join(data_dir, f) for f in os.listdir(data_dir) if f.lower().endswith(".docx")]

    pdf_streams = [open(f, "rb") for f in pdf_files]
    docx_streams = [open(f, "rb") for f in docx_files]

    if pdf_streams or docx_streams:
        with st.spinner(processing_msg):
            document_content = ""
            for pdf in pdf_streams:
                document_content += process_document_content(pdf_file=pdf) or ""
            for docx in docx_streams:
                document_content += process_document_content(docx_file=docx) or ""

            if document_content.strip():
                with st.expander(details_label):
                    st.write(success_msg)
                    st.write(length_msg.format(len(document_content)))
                    for f in pdf_files:
                        st.write(file_msg.format("PDF", os.path.basename(f)))
                    for f in docx_files:
                        st.write(file_msg.format("DOCX", os.path.basename(f)))
                chatbot_interface(document_content, language)

                if st.button(reset_btn):
                    st.session_state.pop("messages", None)
                    st.session_state.pop("chat", None)
                    st.info(reset_msg)
                    st.rerun()
            else:
                st.error(error_msg)
    else:
        st.info(upload_msg)

if __name__ == "__main__":
    main()