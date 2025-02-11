from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class ModuleInfo(BaseModel):
    """Schema for Odoo module information"""
    name: str
    version: str
    category: str
    depends: List[str]
    description: str
    models: Dict[str, Dict[str, Any]]
    views: List[str]
    security: Dict[str, List[str]]

class OdooSearchSchema(BaseModel):
    """Schema for search operations"""
    model: str = Field(..., description="Model name (e.g., 'res.users')")
    domain: List[tuple] = Field(..., description="Search domain")
    fields: Optional[List[str]] = Field(None, description="Fields to fetch")
    limit: Optional[int] = Field(None, description="Maximum number of records")
    offset: Optional[int] = Field(None, description="Number of records to skip")
    order: Optional[str] = Field(None, description="Sort order")

class OdooCreateSchema(BaseModel):
    """Schema for create operations"""
    model: str = Field(..., description="Model name")
    values: Dict[str, Any] = Field(..., description="Values to create")

class OdooWriteSchema(BaseModel):
    """Schema for write operations"""
    model: str = Field(..., description="Model name")
    ids: List[int] = Field(..., description="Record IDs to update")
    values: Dict[str, Any] = Field(..., description="Values to write")

class OdooUnlinkSchema(BaseModel):
    """Schema for unlink operations"""
    model: str = Field(..., description="Model name")
    ids: List[int] = Field(..., description="Record IDs to delete")
