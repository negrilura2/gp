import zipfile
import xml.etree.ElementTree as ET
import os
import sys

def extract_text_from_docx(docx_path):
    try:
        with zipfile.ZipFile(docx_path) as zf:
            xml_content = zf.read('word/document.xml')
            tree = ET.fromstring(xml_content)
            
            # XML namespace for Word
            namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            
            text_parts = []
            # Find all text nodes (w:t) within paragraphs (w:p)
            for p in tree.findall('.//w:p', namespaces):
                p_text = []
                for t in p.findall('.//w:t', namespaces):
                    if t.text:
                        p_text.append(t.text)
                if p_text:
                    text_parts.append(''.join(p_text))
            
            return '\n'.join(text_parts)
    except Exception as e:
        return f"Error reading docx: {e}"

if __name__ == "__main__":
    # Find the docx file in the current directory or specific path
    target_dir = r"d:\traepg\gp"
    docx_file = None
    
    for file in os.listdir(target_dir):
        if file.endswith(".docx") and "郭亚宁" in file:
            docx_file = os.path.join(target_dir, file)
            break
            
    if not docx_file:
        print("Docx file not found")
        sys.exit(1)
        
    print(f"Extracting from: {docx_file}")
    try:
        content = extract_text_from_docx(docx_file)
        # Print content, handle potential encoding issues for console output
        sys.stdout.buffer.write(content.encode('utf-8'))
    except Exception as e:
        print(f"Error: {e}")
