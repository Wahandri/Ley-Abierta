import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

# --- Sub-models for Structured Budget ---

class MinistryBreakdown(BaseModel):
    name: str
    amount_budgeted: Optional[float] = None
    amount_executed: Optional[float] = None
    pct_total: Optional[float] = None

class ProgramBreakdown(BaseModel):
    code: str
    name: str
    ministry: Optional[str] = None
    amount_budgeted: Optional[float] = None
    amount_executed: Optional[float] = None
    pct_total: Optional[float] = None

class ChapterBreakdown(BaseModel):
    chapter: str
    name: str
    amount_budgeted: Optional[float] = None
    amount_executed: Optional[float] = None

class EconomicBreakdown(BaseModel):
    code: str
    name: str
    amount: float

class FunctionalBreakdown(BaseModel):
    code: str
    name: str
    amount: float

class BudgetTotals(BaseModel):
    total_budgeted: Optional[float] = None
    total_executed: Optional[float] = None
    total_obligations_recognized: Optional[float] = None
    total_payments_made: Optional[float] = None
    variance_abs: Optional[float] = None
    variance_pct: Optional[float] = None

class BudgetBreakdowns(BaseModel):
    by_ministry: List[MinistryBreakdown] = Field(default_factory=list)
    by_program: List[ProgramBreakdown] = Field(default_factory=list)
    by_chapter: List[ChapterBreakdown] = Field(default_factory=list)
    by_economic_classification: List[EconomicBreakdown] = Field(default_factory=list)
    by_functional_classification: List[FunctionalBreakdown] = Field(default_factory=list)

class BudgetNotes(BaseModel):
    assumptions: Optional[str] = None
    caveats: Optional[str] = None
    source_table_refs: List[str] = Field(default_factory=list)

class StructuredBudget(BaseModel):
    year: int
    period: str  # "anual", "mensual", "trimestral", "acumulado"
    stage: str   # "aprobado", "prorrogado", "ejecutado", "liquidado", "modificado"
    administration_level: str  # "estado", "organismo", "empresa_publica", "mixto"
    currency: str = "EUR"
    totals: BudgetTotals = Field(default_factory=BudgetTotals)
    breakdowns: BudgetBreakdowns = Field(default_factory=BudgetBreakdowns)
    notes: BudgetNotes = Field(default_factory=BudgetNotes)

# --- Audit Models ---

class ImpactIndex(BaseModel):
    score: int  # 0-100
    reason: str
    economico: bool = False
    alcance: bool = False
    urgencia: bool = False
    opacidad: bool = False

class ExtractionMetadata(BaseModel):
    text_length: int
    pages: int
    has_tables: bool
    ocr_used: bool
    extraction_quality_score: float  # 0.0 - 1.0

class LLMMetadata(BaseModel):
    model: str
    prompt_version: str
    chunking_used: bool
    confidence: float  # 0.0 - 1.0

# --- Main Document Model ---

class DocumentoPresupuestoPublico(BaseModel):
    id: str
    source: str
    type: str  # "presupuesto", "ejecucion", "gasto", "informe", etc.
    title_original: str
    short_title: str
    date_published: str  # ISO 8601
    url_oficial: str
    filename_original: str
    summary_plain_es: str
    keywords: List[str] = Field(default_factory=list)
    topic_primary: str
    entities_detected: List[str] = Field(default_factory=list)
    
    impact_index: ImpactIndex
    transparency_notes: Optional[str] = None
    
    structured_budget: Optional[StructuredBudget] = None
    
    # Audit trail
    extracted: Optional[ExtractionMetadata] = None
    llm: Optional[LLMMetadata] = None
    
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    version: str = "1.0"

    def generate_id(self):
        """Generates a stable ID based on critical fields."""
        content = f"{self.source}{self.url_oficial}{self.date_published}{self.title_original}"
        self.id = hashlib.sha256(content.encode('utf-8')).hexdigest()
