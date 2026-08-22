import os
from PyPDF2 import PdfReader
import logging

class DocumentStore:
    def __init__(self):
        self.documents = {}

    def add_document(self, doc_id, document):
        """
        Add a document to the store.
        
        :param doc_id: Unique identifier for the document.
        :param document: The document content.
        """
        self.documents[doc_id] = document
        print(f"Document with ID {doc_id} added to the store.")

    def get_document(self, doc_id):
        """
        Retrieve a document from the store.
        
        :param doc_id: Unique identifier for the document.
        :return: The document content or None if not found.
        """
        return self.documents.get(doc_id, None)
    
    def delete_document(self, doc_id):
        """
        Delete a document from the store.
        
        :param doc_id: Unique identifier for the document.
        """
        if doc_id in self.documents:
            del self.documents[doc_id]
            print(f"Document with ID {doc_id} deleted from the store.")
        else:
            print(f"Document with ID {doc_id} not found in the store.")

    def list_documents(self):
        """
        List all documents in the store.
        
        :return: A list of document IDs.
        """
        return list(self.documents.keys())
    
    def clear_store(self):
        """
        Clear all documents from the store.
        """
        self.documents.clear()
        logging.info("All documents have been cleared from the store.")

    
    def load_documents_from_directory(self, directory_path):
        """
        Load documents from a specified directory into the store.
        
        :param directory_path: Path to the directory containing documents.
        """
        if not os.path.isdir(directory_path):
            print(f"Error: {directory_path} is not a valid directory. Please provide a valid directory path, e.g., '/path/to/documents' or 'C:\\Users\\User\\Documents'.")
            return
        
        for filename in os.listdir(directory_path):
            if filename.startswith('.'):
                continue
            file_path = os.path.join(directory_path, filename)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                        self.add_document(filename, content)
                except Exception as e:
                    logging.info(f"Error reading {filename}: {type(e).__name__} - {e}")
        logging.info(f"All documents from {directory_path} have been loaded into the store.")

    def load_pdf_documents_from_directory(self, directory_path):
        """
        Load PDF documents from a specified directory into the store.
        
        :param directory_path: Path to the directory containing PDF documents.
        """

        if not os.path.isdir(directory_path):
            logging.info(f"Error: {directory_path} is not a valid directory.")
            return

        for filename in os.listdir(directory_path):
            if filename.lower().endswith('.pdf'):
                file_path = os.path.join(directory_path, filename)
                if os.path.isfile(file_path):
                    try:
                        reader = PdfReader(file_path)
                        content = ""
                        for page in reader.pages:
                            content += page.extract_text()
                        self.add_document(filename, content)
                    except Exception as e:
                        logging.info(f"Error reading {filename}: {e}")
        logging.info(f"All PDF documents from {directory_path} have been loaded into the store.")


    def split_document_into_chunks(self, doc_id, chunk_size=1000, overlap=200):
        """
        Split a document into smaller text chunks with overlaps. Each chunk will have a maximum size of `chunk_size` characters, and consecutive chunks will overlap by `overlap` characters. The overlap is applied at the end of one chunk and the beginning of the next.
        
        :param doc_id: Unique identifier for the document.
        :param chunk_size: The maximum size of each chunk in characters.
        :param overlap: The number of overlapping characters between consecutive chunks. Must be smaller than `chunk_size`.
        :return: A generator yielding text chunks or None if the document is not found.
        """
        document = self.get_document(doc_id)
        if document is None:
            logging.info(f"Document with ID {doc_id} not found in the store.")
            return None
        
        if overlap >= chunk_size:
            logging.info("Error: Overlap must be smaller than the chunk size.")
            return None

        def chunk_generator():
            for i in range(0, len(document), chunk_size - overlap):
                yield document[i:i + chunk_size]
        
        return chunk_generator()