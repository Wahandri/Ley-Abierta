import logging
import os
from typing import Optional, Dict, Any, List
import pdfplumber
import pandas as pd
from .models import ExtractionMetadata

logger = logging.getLogger(__name__)

class BudgetExtractor:
    def extract(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """
        Extracts content from a file.
        Returns a dict with:
        - text: str (combined text)
        - tables: List[str] (markdown or csv representation of tables)
        - metadata: ExtractionMetadata object
        """
        if file_type == "pdf":
            return self._extract_pdf(file_path)
        elif file_type in ["xlsx", "xls"]:
            return self._extract_excel(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def _extract_pdf(self, file_path: str) -> Dict[str, Any]:
        full_text = []
        tables_repr = []
        page_count = 0
        has_tables = False
        
        try:
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    # Extract text
                    text = page.extract_text()
                    if text:
                        full_text.append(text)
                    
                    # Extract tables (basic strategy)
                    tables = page.extract_tables()
                    if tables:
                        has_tables = True
                        for table in tables:
                            # Convert table to simple CSV-like string for LLM
                            df = pd.DataFrame(table)
                            tables_repr.append(df.to_csv(index=False, header=False))

            combined_text = "\n\n".join(full_text)
            
            metadata = ExtractionMetadata(
                text_length=len(combined_text),
                pages=page_count,
                has_tables=has_tables,
                ocr_used=False, # Assuming native PDF for now
                extraction_quality_score=0.9 if combined_text else 0.1
            )

            return {
                "text": combined_text,
                "tables": tables_repr,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error extracting PDF {file_path}: {e}")
            return {
                "text": "", 
                "tables": [], 
                "metadata": ExtractionMetadata(text_length=0, pages=0, has_tables=False, ocr_used=False, extraction_quality_score=0.0)
            }

    def _extract_excel(self, file_path: str) -> Dict[str, Any]:
        text_parts = []
        tables_repr = []
        
        try:
            # Read all sheets
            xls = pd.ExcelFile(file_path)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                
                # Clean up: drop completely empty rows/cols
                df = df.dropna(how='all').dropna(axis=1, how='all')
                
                # Convert to markdown/string for LLM
                text_parts.append(f"Sheet: {sheet_name}")
                table_str = df.to_markdown(index=False)
                tables_repr.append(f"Sheet: {sheet_name}\n{table_str}")
                
            combined_text = "\n".join(text_parts)
            
            metadata = ExtractionMetadata(
                text_length=len(combined_text),
                pages=len(xls.sheet_names), # "Pages" as sheets
                has_tables=True,
                ocr_used=False,
                extraction_quality_score=1.0
            )

            return {
                "text": combined_text, # Excel "text" is just the sheet names mostly
                "tables": tables_repr, # The real data is here
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Error extracting Excel {file_path}: {e}")
            return {
                "text": "", 
                "tables": [], 
                "metadata": ExtractionMetadata(text_length=0, pages=0, has_tables=False, ocr_used=False, extraction_quality_score=0.0)
            }
