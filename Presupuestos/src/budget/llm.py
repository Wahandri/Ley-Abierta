import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import DocumentoPresupuestoPublico, StructuredBudget, ImpactIndex, LLMMetadata

logger = logging.getLogger(__name__)

class BudgetLLMProcessor:
    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini" # Fast and capable enough for JSON extraction

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def process_document(self, 
                         extracted_data: Dict[str, Any], 
                         resource_info: Dict[str, Any]) -> DocumentoPresupuestoPublico:
        """
        Sends extracted text/tables to LLM and returns the structured Pydantic model.
        """
        
        # Construct the context
        text_snippet = extracted_data["text"][:20000] # Cap text to avoid token limits (rudimentary)
        tables_snippet = "\n\n".join(extracted_data["tables"][:10]) # First 10 tables
        
        system_prompt = """
        Eres un experto analista presupuestario de España. Tu tarea es analizar documentos oficiales (BOE, IGAE, Hacienda)
        y extraer información estructurada sobre presupuestos y gastos públicos.
        
        Debes generar un objeto JSON que cumpla EXACTAMENTE con un esquema específico.
        Prioriza la precisión de los números. 
        
        IMPORTANTE: El campo 'impact_index' DEBE ser un objeto, no un número. Ejemplo:
        "impact_index": {
            "score": 85,
            "reason": "Alto impacto por...",
            "economico": true,
            "alcance": true,
            "urgencia": false,
            "opacidad": false
        }
        
        El campo 'type' debe ser uno de: "presupuesto", "ejecucion", "gasto", "informe".
        El campo 'date_published' debe ser ISO 8601 (YYYY-MM-DD).
        """

        user_prompt = f"""
        Analiza el siguiente documento oficial:
        
        METADATOS:
        - Título Original: {resource_info.get('title_original')}
        - Fecha Publicación: {resource_info.get('published_date')}
        - Fuente: {resource_info.get('source_name')}
        - URL: {resource_info.get('url')}
        
        CONTENIDO TEXTO (Extracto):
        {text_snippet}
        
        CONTENIDO TABLAS (Extracto):
        {tables_snippet}
        
        Genera el JSON final alineado con el modelo DocumentoPresupuestoPublico.
        """

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            raw_content = completion.choices[0].message.content
            data_dict = json.loads(raw_content)
            
            # Enrich with missing metadata or defaults that LLM might miss or hallucinate
            # We use .get() or defaults to ensure Pydantic doesn't crash on partial LLM outputs
            data_dict['id'] = "temp" 
            data_dict['source'] = resource_info.get('source_name', 'Unknown')
            data_dict['url_oficial'] = resource_info.get('url', '')
            data_dict['filename_original'] = resource_info.get('filename', '')
            data_dict['title_original'] = resource_info.get('title_original', '')
            
            # OpenAI sometimes misses required fields on empty input. Fill defaults:
            if 'short_title' not in data_dict: data_dict['short_title'] = "Sin título corto"
            if 'summary_plain_es' not in data_dict: data_dict['summary_plain_es'] = "Resumen no disponible."
            if 'topic_primary' not in data_dict: data_dict['topic_primary'] = "general"
            if 'type' not in data_dict: data_dict['type'] = "informe"
            if 'date_published' not in data_dict: data_dict['date_published'] = datetime.utcnow().strftime('%Y-%m-%d')
            
            # Fix impact_index if it's an int (common LLM mistake)
            if isinstance(data_dict.get('impact_index'), int):
                data_dict['impact_index'] = {
                    "score": data_dict['impact_index'],
                    "reason": "Generated from score",
                }
            elif 'impact_index' not in data_dict:
                 data_dict['impact_index'] = {"score": 0, "reason": "No data"}
            
            # Validate/Parse with Pydantic
            doc = DocumentoPresupuestoPublico(**data_dict)
            
            # Regenerate deterministic ID
            doc.generate_id()
             
            # Add Audit info
            doc.llm = LLMMetadata(
                model=self.model,
                prompt_version="v1",
                chunking_used=len(extracted_data["text"]) > 20000,
                confidence=1.0 
            )
            
            if extracted_data.get("metadata"):
                # Copy extraction metadata manually since it's a Pydantic object in dict
                ext_meta = extracted_data["metadata"]
                doc.extracted = ext_meta

            return doc

        except Exception as e:
            logger.error(f"LLM Processing Error: {e}")
            raise e
