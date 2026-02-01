import abc
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class BudgetResource(BaseModel):
    source_name: str
    url: str
    title_original: str
    filetype: str  # "pdf", "xls", "csv", "zip"
    expected_year: int
    expected_month: int
    published_date: Optional[str] = None
    metadata: dict = {}

    def get_filename(self) -> str:
        """Generates a standardized filename for storage."""
        ext = self.filetype.lower()
        if ext == "xlsx": ext = "xlsx"
        return f"{self.source_name}-{self.expected_year}-{self.expected_month:02d}-{self.title_original[:30].replace(' ', '_').lower()}.{ext}"

class BudgetSource(abc.ABC):
    def __init__(self):
        self.name = "generic_source"
        self.base_url = ""

    @abc.abstractmethod
    def list_resources(self, year: int, month: Optional[int] = None) -> List[BudgetResource]:
        """Discubre recursos disponibles para un año/mes dado."""
        pass

    @abc.abstractmethod
    def download_resource(self, resource: BudgetResource, output_path: str) -> bool:
        """Descarga el recurso a la ruta especificada."""
        pass
