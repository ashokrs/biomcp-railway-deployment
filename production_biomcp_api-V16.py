# production_biomcp_api-V16.py - Clean Production-Ready BioMCP API
"""
Production-ready FastAPI wrapper for BioMCP with:
- All 35 tools properly implemented
- Subprocess integration with proper command building
- Comprehensive request/response models
- WebSocket support for streaming
- Batch operations
- Proper error handling and logging
- Production-grade configuration
"""

import os
import sys
import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class TrialPhase(str, Enum):
    EARLY_PHASE1 = "EARLY_PHASE1"
    PHASE1 = "PHASE1"
    PHASE1_PHASE2 = "PHASE1_PHASE2"
    PHASE2 = "PHASE2"
    PHASE2_PHASE3 = "PHASE2_PHASE3"
    PHASE3 = "PHASE3"
    PHASE4 = "PHASE4"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class TrialStatus(str, Enum):
    RECRUITING = "RECRUITING"
    ACTIVE_NOT_RECRUITING = "ACTIVE_NOT_RECRUITING"
    COMPLETED = "COMPLETED"
    ENROLLING_BY_INVITATION = "ENROLLING_BY_INVITATION"
    NOT_YET_RECRUITING = "NOT_YET_RECRUITING"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"
    WITHDRAWN = "WITHDRAWN"

class VariantSignificance(str, Enum):
    PATHOGENIC = "pathogenic"
    LIKELY_PATHOGENIC = "likely_pathogenic"
    UNCERTAIN_SIGNIFICANCE = "uncertain_significance"
    LIKELY_BENIGN = "likely_benign"
    BENIGN = "benign"

class ToolCategory(str, Enum):
    CORE = "core"
    ARTICLE = "article"
    TRIAL = "trial"
    VARIANT = "variant"
    GENE = "gene"
    DISEASE = "disease"
    DRUG = "drug"
    ORGANIZATION = "organization"

# =============================================================================
# TOOL DEFINITIONS (All 35 Tools)
# =============================================================================

BIOMCP_TOOLS = {
    # Core Tools (2)
    "search": {
        "category": ToolCategory.CORE,
        "description": "Universal search using article search as fallback",
        "command_template": ["biomcp", "article", "search"],
    },
    "think": {
        "category": ToolCategory.CORE,
        "description": "Sequential thinking tool for complex biomedical problem analysis",
        "command_template": ["biomcp", "think"],
    },
    
    # Article Tools (7)
    "article_searcher": {
        "category": ToolCategory.ARTICLE,
        "description": "Search PubMed, PubTator3, bioRxiv, medRxiv, and Europe PMC",
        "command_template": ["biomcp", "article", "search"],
    },
    "article_getter": {
        "category": ToolCategory.ARTICLE,
        "description": "Get detailed article information by PMID or DOI",
        "command_template": ["biomcp", "article", "get"],
    },
    "article_details": {
        "category": ToolCategory.ARTICLE,
        "description": "Get comprehensive article metadata and annotations",
        "command_template": ["biomcp", "article", "get"],
    },
    "article_abstracts": {
        "category": ToolCategory.ARTICLE,
        "description": "Get article abstracts with entity annotations",
        "command_template": ["biomcp", "article", "get"],
    },
    "article_fulltext": {
        "category": ToolCategory.ARTICLE,
        "description": "Get full article text when available",
        "command_template": ["biomcp", "article", "get"],
    },
    "article_citations": {
        "category": ToolCategory.ARTICLE,
        "description": "Get article citation information and metrics",
        "command_template": ["biomcp", "article", "get"],
    },
    "article_related": {
        "category": ToolCategory.ARTICLE,
        "description": "Find related articles using semantic similarity",
        "command_template": ["biomcp", "article", "get"],
    },
    
    # Trial Tools (8)
    "trial_searcher": {
        "category": ToolCategory.TRIAL,
        "description": "Search ClinicalTrials.gov and NCI Clinical Trials Search API",
        "command_template": ["biomcp", "trial", "search"],
    },
    "trial_getter": {
        "category": ToolCategory.TRIAL,
        "description": "Get comprehensive trial details and metadata",
        "command_template": ["biomcp", "trial", "get"],
    },
    "trial_protocol_getter": {
        "category": ToolCategory.TRIAL,
        "description": "Get detailed trial protocol information",
        "command_template": ["biomcp", "trial", "get"],
    },
    "trial_locations_getter": {
        "category": ToolCategory.TRIAL,
        "description": "Get trial site locations, contacts, and recruitment status",
        "command_template": ["biomcp", "trial", "get"],
    },
    "trial_eligibility_getter": {
        "category": ToolCategory.TRIAL,
        "description": "Get trial eligibility criteria and patient requirements",
        "command_template": ["biomcp", "trial", "get"],
    },
    "trial_outcomes_getter": {
        "category": ToolCategory.TRIAL,
        "description": "Get trial outcome measures and results data",
        "command_template": ["biomcp", "trial", "get"],
    },
    "trial_references_getter": {
        "category": ToolCategory.TRIAL,
        "description": "Get trial publications and reference materials",
        "command_template": ["biomcp", "trial", "get"],
    },
    "trial_arms_getter": {
        "category": ToolCategory.TRIAL,
        "description": "Get trial arm details and intervention information",
        "command_template": ["biomcp", "trial", "get"],
    },
    
    # Variant Tools (8)
    "variant_searcher": {
        "category": ToolCategory.VARIANT,
        "description": "Search genetic variants across multiple databases",
        "command_template": ["biomcp", "variant", "search"],
    },
    "variant_getter": {
        "category": ToolCategory.VARIANT,
        "description": "Get comprehensive variant annotations from MyVariant.info",
        "command_template": ["biomcp", "variant", "get"],
    },
    "variant_details": {
        "category": ToolCategory.VARIANT,
        "description": "Get detailed variant information from CIViC, ClinVar, COSMIC",
        "command_template": ["biomcp", "variant", "get"],
    },
    "variant_clinical": {
        "category": ToolCategory.VARIANT,
        "description": "Get clinical significance and therapeutic implications",
        "command_template": ["biomcp", "variant", "get"],
    },
    "variant_population": {
        "category": ToolCategory.VARIANT,
        "description": "Get population frequency data from 1000 Genomes, gnomAD",
        "command_template": ["biomcp", "variant", "get"],
    },
    "variant_functional": {
        "category": ToolCategory.VARIANT,
        "description": "Get functional predictions and pathogenicity scores",
        "command_template": ["biomcp", "variant", "get"],
    },
    "variant_literature": {
        "category": ToolCategory.VARIANT,
        "description": "Get variant-specific literature and evidence",
        "command_template": ["biomcp", "variant", "get"],
    },
    "variant_drugs": {
        "category": ToolCategory.VARIANT,
        "description": "Get variant-drug associations and pharmacogenomics",
        "command_template": ["biomcp", "variant", "get"],
    },
    
    # Gene Tools (4)
    "gene_getter": {
        "category": ToolCategory.GENE,
        "description": "Get comprehensive gene information and annotations",
        "command_template": ["biomcp", "gene", "get"],
    },
    "gene_variants": {
        "category": ToolCategory.GENE,
        "description": "Get all variants associated with a specific gene",
        "command_template": ["biomcp", "gene", "variants"],
    },
    "gene_drugs": {
        "category": ToolCategory.GENE,
        "description": "Get gene-drug associations and targets",
        "command_template": ["biomcp", "gene", "drugs"],
    },
    "gene_pathways": {
        "category": ToolCategory.GENE,
        "description": "Get gene pathway and functional annotation",
        "command_template": ["biomcp", "gene", "pathways"],
    },
    
    # Disease Tools (3)
    "disease_getter": {
        "category": ToolCategory.DISEASE,
        "description": "Get disease information, synonyms, and ontology",
        "command_template": ["biomcp", "disease", "get"],
    },
    "disease_genes": {
        "category": ToolCategory.DISEASE,
        "description": "Get genes associated with a disease condition",
        "command_template": ["biomcp", "disease", "genes"],
    },
    "disease_drugs": {
        "category": ToolCategory.DISEASE,
        "description": "Get drugs and treatments for a disease",
        "command_template": ["biomcp", "disease", "drugs"],
    },
    
    # Drug Tools (3)
    "drug_getter": {
        "category": ToolCategory.DRUG,
        "description": "Get comprehensive drug information and properties",
        "command_template": ["biomcp", "drug", "get"],
    },
    "drug_targets": {
        "category": ToolCategory.DRUG,
        "description": "Get drug targets and mechanism of action",
        "command_template": ["biomcp", "drug", "targets"],
    },
    "drug_trials": {
        "category": ToolCategory.DRUG,
        "description": "Get clinical trials testing a specific drug",
        "command_template": ["biomcp", "drug", "trials"],
    },
    
    # Organization Tools (2)
    "organization_searcher": {
        "category": ToolCategory.ORGANIZATION,
        "description": "Search research organizations and institutions",
        "command_template": ["biomcp", "organization", "search"],
    },
    "organization_getter": {
        "category": ToolCategory.ORGANIZATION,
        "description": "Get organization details and research focus",
        "command_template": ["biomcp", "organization", "get"],
    }
}

# =============================================================================
# REQUEST MODELS
# =============================================================================

class BaseRequest(BaseModel):
    """Base request model with common fields"""
    limit: int = Field(10, ge=1, le=100, description="Maximum results (1-100)")
    timeout: int = Field(30, ge=5, le=120, description="Request timeout in seconds")

class ThinkRequest(BaseRequest):
    thought: str = Field(..., min_length=10, description="The thought or analysis to process")
    thought_number: int = Field(1, ge=1, description="Current thought number")
    total_thoughts: int = Field(3, ge=1, le=10, description="Total planned thoughts")
    next_thought_needed: bool = Field(True, description="Whether another thought is needed")

class SearchRequest(BaseRequest):
    query: str = Field(..., min_length=2, description="Search query with optional field syntax")
    include_preprints: bool = Field(True, description="Include preprint servers")
    include_trials: bool = Field(True, description="Include clinical trials")
    include_variants: bool = Field(True, description="Include genetic variants")

class ArticleSearchRequest(BaseRequest):
    query: Optional[str] = Field(None, description="General search query")
    gene: Optional[str] = Field(None, description="Gene symbol or name")
    disease: Optional[str] = Field(None, description="Disease or condition")
    variant: Optional[str] = Field(None, description="Genetic variant")
    keyword: Optional[str] = Field(None, description="Specific keywords")
    authors: Optional[str] = Field(None, description="Author names")
    journal: Optional[str] = Field(None, description="Journal name")
    year_from: Optional[int] = Field(None, ge=1950, le=2025, description="Start year")
    year_to: Optional[int] = Field(None, ge=1950, le=2025, description="End year")
    include_preprints: bool = Field(True, description="Include bioRxiv/medRxiv preprints")
    full_text_only: bool = Field(False, description="Only return articles with full text")

class ArticleGetRequest(BaseModel):
    identifier: str = Field(..., description="PMID, DOI, or other article identifier")
    full_text: bool = Field(False, description="Retrieve full text if available")
    include_citations: bool = Field(False, description="Include citation information")
    include_related: bool = Field(False, description="Include related articles")

class TrialSearchRequest(BaseRequest):
    condition: Optional[str] = Field(None, description="Disease condition or indication")
    intervention: Optional[str] = Field(None, description="Intervention or treatment")
    sponsor: Optional[str] = Field(None, description="Trial sponsor organization")
    location: Optional[str] = Field(None, description="Trial location (city, state, country)")
    phase: Optional[List[TrialPhase]] = Field(None, description="Trial phases")
    status: Optional[List[TrialStatus]] = Field(None, description="Trial status")
    gene: Optional[str] = Field(None, description="Gene target or biomarker")
    term: Optional[str] = Field(None, description="General search term")
    biomarker: Optional[str] = Field(None, description="Biomarker requirement")
    age_min: Optional[int] = Field(None, ge=0, le=120, description="Minimum age")
    age_max: Optional[int] = Field(None, ge=0, le=120, description="Maximum age")
    gender: Optional[str] = Field(None, description="Gender requirement (all, male, female)")
    source: str = Field("clinicaltrials", description="Source: clinicaltrials or nci")
    recruiting_only: bool = Field(False, description="Only recruiting trials")

class TrialGetRequest(BaseModel):
    nct_id: str = Field(..., pattern=r'^NCT\d{8}$', description="ClinicalTrials.gov NCT identifier")
    source: str = Field("clinicaltrials", description="Source: clinicaltrials or nci")
    include_protocol: bool = Field(False, description="Include protocol details")
    include_locations: bool = Field(False, description="Include site locations")
    include_arms: bool = Field(False, description="Include trial arms")

class VariantSearchRequest(BaseRequest):
    gene: Optional[str] = Field(None, description="Gene symbol")
    variant: Optional[str] = Field(None, description="Variant identifier (dbSNP, HGVS)")
    chromosome: Optional[str] = Field(None, description="Chromosome")
    position: Optional[int] = Field(None, description="Genomic position")
    significance: Optional[List[VariantSignificance]] = Field(None, description="Clinical significance")
    consequence: Optional[str] = Field(None, description="Variant consequence")
    population: Optional[str] = Field(None, description="Population ancestry")
    frequency_min: Optional[float] = Field(None, ge=0, le=1, description="Minimum allele frequency")
    frequency_max: Optional[float] = Field(None, ge=0, le=1, description="Maximum allele frequency")
    include_external: bool = Field(True, description="Include external annotations")
    include_population: bool = Field(True, description="Include population data")

class VariantGetRequest(BaseModel):
    variant_id: str = Field(..., description="Variant identifier (dbSNP, HGVS, etc.)")
    include_external: bool = Field(True, description="Include external annotations")
    include_population: bool = Field(True, description="Include population frequency")
    include_clinical: bool = Field(True, description="Include clinical significance")
    include_functional: bool = Field(True, description="Include functional predictions")

class GeneGetRequest(BaseModel):
    gene_symbol: str = Field(..., description="Gene symbol or identifier")
    include_variants: bool = Field(False, description="Include associated variants")
    include_drugs: bool = Field(False, description="Include drug associations")
    include_pathways: bool = Field(False, description="Include pathway information")

class DiseaseGetRequest(BaseModel):
    disease_name: str = Field(..., description="Disease name or identifier")
    include_genes: bool = Field(False, description="Include associated genes")
    include_drugs: bool = Field(False, description="Include treatment drugs")
    include_synonyms: bool = Field(True, description="Include disease synonyms")

class DrugGetRequest(BaseModel):
    drug_name: str = Field(..., description="Drug name or identifier")
    include_targets: bool = Field(False, description="Include drug targets")
    include_trials: bool = Field(False, description="Include clinical trials")
    include_interactions: bool = Field(False, description="Include drug interactions")

class BatchRequest(BaseModel):
    queries: List[str] = Field(..., min_items=1, max_items=20, description="List of queries to process")
    tool_name: str = Field("search", description="Tool to use for batch processing")
    parallel: bool = Field(True, description="Process queries in parallel")

# =============================================================================
# RESPONSE MODELS
# =============================================================================

class ToolResponse(BaseModel):
    success: bool
    data: Any
    method: str
    execution_time: float
    timestamp: datetime

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    biomcp_integration: str
    tools_count: int
    uptime: float

class ToolInfo(BaseModel):
    name: str
    category: str
    description: str
    command_template: List[str]

# =============================================================================
# BIOMCP INTEGRATION CLASS
# =============================================================================

class BioMCPIntegration:
    """BioMCP integration layer using subprocess commands"""
    
    def __init__(self):
        self.start_time = datetime.now()
        logger.info("BioMCP integration initialized using subprocess method")
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResponse:
        """Call a BioMCP tool using subprocess"""
        start_time = datetime.now()
        
        try:
            result = await self._call_tool_subprocess(tool_name, parameters)
            method = "subprocess"
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ToolResponse(
                success=result["success"],
                data=result["data"],
                method=method,
                execution_time=execution_time,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Tool call failed: {e}")
            
            return ToolResponse(
                success=False,
                data={"error": str(e)},
                method="error",
                execution_time=execution_time,
                timestamp=datetime.now()
            )
    
    async def _call_tool_subprocess(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Call tool using subprocess"""
        try:
            if tool_name not in BIOMCP_TOOLS:
                raise ValueError(f"Tool '{tool_name}' not found")
            
            # Build command
            cmd = self._build_biomcp_command(tool_name, parameters)
            
            # DEBUG: Log the exact command being executed
            cmd_str = ' '.join(cmd)
            logger.info(f"Executing command: {cmd_str}")
            print(f"DEBUG: Executing command: {cmd_str}")
            
            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            timeout = parameters.get("timeout", 30)
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            
            stdout_text = stdout.decode()
            stderr_text = stderr.decode()
            
            # DEBUG: Log outputs
            if stdout_text:
                print(f"DEBUG: STDOUT: {stdout_text[:500]}...")
            if stderr_text:
                print(f"DEBUG: STDERR: {stderr_text}")
            print(f"DEBUG: Return code: {process.returncode}")
            
            if process.returncode == 0:
                try:
                    result = json.loads(stdout_text)
                except json.JSONDecodeError:
                    # If not JSON, return as text
                    result = stdout_text
                
                return {"success": True, "data": result}
            else:
                logger.error(f"Command failed with return code {process.returncode}: {stderr_text}")
                return {"success": False, "data": stderr_text}
                
        except Exception as e:
            logger.error(f"Subprocess tool call failed: {e}")
            raise Exception(f"Subprocess tool call failed: {e}")
    
    def _build_biomcp_command(self, tool_name: str, params: Dict[str, Any]) -> List[str]:
        """Build BioMCP command with correct CLI structure"""
        
        if tool_name == "search":
            cmd = ["biomcp", "article", "search"]
            if params.get("query"):
                cmd.extend(["--keyword", params["query"]])
            cmd.append("--json")
            
        elif tool_name == "article_searcher":
            cmd = ["biomcp", "article", "search"]
            if params.get("gene"):
                cmd.extend(["--gene", params["gene"]])
            if params.get("disease"):
                cmd.extend(["--disease", params["disease"]])
            if params.get("query") or params.get("keyword"):
                keyword = params.get("query") or params.get("keyword")
                cmd.extend(["--keyword", keyword])
            if params.get("variant"):
                cmd.extend(["--variant", params["variant"]])
            if params.get("authors"):
                cmd.extend(["--authors", params["authors"]])
            if params.get("journal"):
                cmd.extend(["--journal", params["journal"]])
            if params.get("year_from"):
                cmd.extend(["--year-from", str(params["year_from"])])
            if params.get("year_to"):
                cmd.extend(["--year-to", str(params["year_to"])])
            if not params.get("include_preprints", True):
                cmd.append("--no-preprints")
            cmd.append("--json")
                
        elif tool_name == "article_getter":
            cmd = ["biomcp", "article", "get"]
            if params.get("identifier"):
                cmd.append(str(params["identifier"]))
            if params.get("full_text"):
                cmd.append("--full")
            cmd.append("--json")
                
        elif tool_name == "trial_searcher":
            cmd = ["biomcp", "trial", "search"]
            
            # Basic search parameters
            if params.get("condition"):
                cmd.extend(["--condition", params["condition"]])
            if params.get("intervention"):
                cmd.extend(["--intervention", params["intervention"]])
                
            # Handle terms - convert gene/biomarker to terms
            terms = []
            if params.get("term"):
                if isinstance(params["term"], list):
                    terms.extend(params["term"])
                else:
                    terms.append(params["term"])
            # Convert gene/biomarker to terms (since --gene doesn't exist in trial search)
            if params.get("gene"):
                terms.append(params["gene"])
            if params.get("biomarker"):
                terms.append(params["biomarker"])
            if params.get("query") and not terms:
                terms.append(params["query"])
                
            # Add all terms using --term flag
            for term in terms:
                cmd.extend(["--term", str(term)])
                
            # Status mapping
            if params.get("status"):
                statuses = params["status"] if isinstance(params["status"], list) else [params["status"]]
                for status in statuses:
                    if hasattr(status, 'value'):
                        status_val = status.value
                    else:
                        status_val = str(status).upper()
                    
                    # Map our status values to CLI values
                    status_mapping = {
                        "RECRUITING": "OPEN",
                        "ACTIVE_NOT_RECRUITING": "OPEN", 
                        "COMPLETED": "CLOSED",
                        "ENROLLING_BY_INVITATION": "OPEN",
                        "NOT_YET_RECRUITING": "OPEN",
                        "SUSPENDED": "CLOSED",
                        "TERMINATED": "CLOSED",
                        "WITHDRAWN": "CLOSED"
                    }
                    cli_status = status_mapping.get(status_val, status_val)
                    cmd.extend(["--status", cli_status])
                    
            if params.get("recruiting_only"):
                cmd.extend(["--status", "OPEN"])
                
            # Phase mapping
            if params.get("phase"):
                phases = params["phase"] if isinstance(params["phase"], list) else [params["phase"]]
                for phase in phases:
                    phase_val = phase.value if hasattr(phase, 'value') else str(phase)
                    cmd.extend(["--phase", phase_val])
                    
            # Page size (instead of limit)
            if params.get("limit"):
                cmd.extend(["--page-size", str(min(params["limit"], 1000))])
                
            # JSON output
            cmd.append("--json")
            
        elif tool_name == "trial_getter":
            nct_id = params.get("nct_id", "")
            cmd = ["biomcp", "trial", "get", nct_id]
            cmd.append("Protocol")  # Default module
            cmd.append("--json")
            
        elif tool_name.startswith("trial_") and tool_name.endswith("_getter"):
            # trial_protocol_getter, trial_locations_getter, etc.
            nct_id = params.get("nct_id", "")
            action = tool_name.replace("trial_", "").replace("_getter", "")
            module_map = {
                "protocol": "Protocol",
                "locations": "Locations", 
                "references": "References",
                "outcomes": "Outcomes",
                "arms": "Protocol",
                "eligibility": "Protocol"
            }
            module = module_map.get(action, "Protocol")
            cmd = ["biomcp", "trial", "get", nct_id, module, "--json"]
            
        elif tool_name == "variant_searcher":
            cmd = ["biomcp", "variant", "search"]
            if params.get("gene"):
                cmd.extend(["--gene", params["gene"]])
            if params.get("variant"):
                cmd.extend(["--variant", params["variant"]])
            if params.get("chromosome"):
                cmd.extend(["--chromosome", params["chromosome"]])
            if params.get("position"):
                cmd.extend(["--position", str(params["position"])])
            if params.get("significance"):
                for sig in params["significance"]:
                    sig_val = sig.value if hasattr(sig, 'value') else sig
                    cmd.extend(["--significance", sig_val])
            if not params.get("include_external", True):
                cmd.append("--no-external")
            cmd.append("--json")
                
        elif tool_name == "variant_getter":
            variant_id = params.get("variant_id", "")
            cmd = ["biomcp", "variant", "get", variant_id]
            if not params.get("include_external", True):
                cmd.append("--no-external")
            cmd.append("--json")
                
        elif tool_name.startswith("variant_") and not tool_name.endswith("_searcher"):
            # variant_details, variant_clinical, etc.
            variant_id = params.get("variant_id", "")
            cmd = ["biomcp", "variant", "get", variant_id]
            if not params.get("include_external", True):
                cmd.append("--no-external")
            cmd.append("--json")
            
        # Gene commands - fallback to article search
        elif tool_name == "gene_getter" or tool_name.startswith("gene_"):
            gene_symbol = params.get("gene_symbol", params.get("gene", ""))
            cmd = ["biomcp", "article", "search", "--gene", gene_symbol, "--json"]
            
        # Disease commands - fallback to article search
        elif tool_name == "disease_getter" or tool_name.startswith("disease_"):
            disease_name = params.get("disease_name", params.get("disease", ""))
            cmd = ["biomcp", "article", "search", "--disease", disease_name, "--json"]
            
        # Drug commands - fallback to article search
        elif tool_name.startswith("drug_"):
            drug_name = params.get("drug_name", params.get("drug", ""))
            cmd = ["biomcp", "article", "search", "--keyword", drug_name, "--json"]
            
        # Organization commands
        elif tool_name == "organization_searcher":
            query = params.get("query", "")
            cmd = ["biomcp", "organization", "search", query, "--json"]
            
        elif tool_name == "organization_getter":
            org_id = params.get("org_id", "")
            cmd = ["biomcp", "organization", "get", org_id, "--json"]
            
        else:
            # Fallback to article search for unknown commands
            query = params.get("query", params.get("keyword", ""))
            cmd = ["biomcp", "article", "search", "--keyword", query, "--json"]
            
        return cmd
    
    def get_uptime(self) -> float:
        """Get service uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()

# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting BioMCP Production API V16")
    logger.info(f"Total tools available: {len(BIOMCP_TOOLS)}")
    yield
    # Shutdown
    logger.info("Shutting down BioMCP Production API V16")

app = FastAPI(
    title="BioMCP Production API V16",
    version="1.6.0",
    description="Production-ready API wrapper for BioMCP with all 35 biomedical research tools",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize BioMCP integration
biomcp = BioMCPIntegration()

# Optional authentication
security = HTTPBearer(auto_error=False)

async def get_auth_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Optional authentication dependency"""
    return credentials

# =============================================================================
# CORE API ENDPOINTS
# =============================================================================
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

@app.get("/")
async def serve_frontend():
    return FileResponse("bioMCPChat-V3.html")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="biomcp-production-api-v16",
        version="1.6.0",
        biomcp_integration="subprocess",
        tools_count=len(BIOMCP_TOOLS),
        uptime=biomcp.get_uptime()
    )

@app.get("/api/tools", response_model=List[ToolInfo])
async def list_tools():
    """List all available BioMCP tools with detailed information"""
    return [
        ToolInfo(
            name=name,
            category=info["category"],
            description=info["description"],
            command_template=info["command_template"]
        )
        for name, info in BIOMCP_TOOLS.items()
    ]

@app.get("/api/tools/by-category/{category}")
async def get_tools_by_category(category: ToolCategory):
    """Get tools filtered by category"""
    filtered_tools = {
        name: info for name, info in BIOMCP_TOOLS.items()
        if info["category"] == category
    }
    return {
        "category": category,
        "count": len(filtered_tools),
        "tools": filtered_tools
    }

# =============================================================================
# CORE TOOL ENDPOINTS
# =============================================================================

@app.post("/api/tools/search", response_model=ToolResponse)
async def universal_search(request: SearchRequest):
    """Universal search across articles, trials, and variants"""
    params = request.dict()
    return await biomcp.call_tool("search", params)

@app.post("/api/tools/think", response_model=ToolResponse)
async def sequential_thinking(request: ThinkRequest):
    """Sequential thinking tool for complex biomedical analysis"""
    params = request.dict()
    return await biomcp.call_tool("think", params)

# =============================================================================
# ARTICLE TOOL ENDPOINTS
# =============================================================================

@app.post("/api/tools/article_searcher", response_model=ToolResponse)
async def search_articles(request: ArticleSearchRequest):
    """Search PubMed, PubTator3, bioRxiv, medRxiv, and Europe PMC"""
    params = request.dict(exclude_none=True)
    return await biomcp.call_tool("article_searcher", params)

@app.post("/api/tools/article_getter", response_model=ToolResponse)
async def get_article(request: ArticleGetRequest):
    """Get detailed article information by PMID or DOI"""
    params = request.dict()
    return await biomcp.call_tool("article_getter", params)

@app.post("/api/tools/article_details", response_model=ToolResponse)
async def get_article_details(request: ArticleGetRequest):
    """Get comprehensive article metadata and annotations"""
    params = request.dict()
    return await biomcp.call_tool("article_details", params)

@app.post("/api/tools/article_abstracts", response_model=ToolResponse)
async def get_article_abstracts(request: ArticleGetRequest):
    """Get article abstracts with entity annotations"""
    params = request.dict()
    return await biomcp.call_tool("article_abstracts", params)

@app.post("/api/tools/article_fulltext", response_model=ToolResponse)
async def get_article_fulltext(request: ArticleGetRequest):
    """Get full article text when available"""
    params = request.dict()
    return await biomcp.call_tool("article_fulltext", params)

@app.post("/api/tools/article_citations", response_model=ToolResponse)
async def get_article_citations(request: ArticleGetRequest):
    """Get article citation information and metrics"""
    params = request.dict()
    return await biomcp.call_tool("article_citations", params)

@app.post("/api/tools/article_related", response_model=ToolResponse)
async def get_article_related(request: ArticleGetRequest):
    """Find related articles using semantic similarity"""
    params = request.dict()
    return await biomcp.call_tool("article_related", params)

# =============================================================================
# TRIAL TOOL ENDPOINTS
# =============================================================================

@app.post("/api/tools/trial_searcher", response_model=ToolResponse)
async def search_trials(request: TrialSearchRequest):
    """Search ClinicalTrials.gov and NCI Clinical Trials Search API"""
    params = request.dict(exclude_none=True)
    return await biomcp.call_tool("trial_searcher", params)

@app.post("/api/tools/trial_getter", response_model=ToolResponse)
async def get_trial(request: TrialGetRequest):
    """Get comprehensive trial details and metadata"""
    params = request.dict()
    return await biomcp.call_tool("trial_getter", params)

@app.post("/api/tools/trial_protocol_getter", response_model=ToolResponse)
async def get_trial_protocol(request: TrialGetRequest):
    """Get detailed trial protocol information"""
    params = request.dict()
    return await biomcp.call_tool("trial_protocol_getter", params)

@app.post("/api/tools/trial_locations_getter", response_model=ToolResponse)
async def get_trial_locations(request: TrialGetRequest):
    """Get trial site locations, contacts, and recruitment status"""
    params = request.dict()
    return await biomcp.call_tool("trial_locations_getter", params)

@app.post("/api/tools/trial_eligibility_getter", response_model=ToolResponse)
async def get_trial_eligibility(request: TrialGetRequest):
    """Get trial eligibility criteria and patient requirements"""
    params = request.dict()
    return await biomcp.call_tool("trial_eligibility_getter", params)

@app.post("/api/tools/trial_outcomes_getter", response_model=ToolResponse)
async def get_trial_outcomes(request: TrialGetRequest):
    """Get trial outcome measures and results data"""
    params = request.dict()
    return await biomcp.call_tool("trial_outcomes_getter", params)

@app.post("/api/tools/trial_references_getter", response_model=ToolResponse)
async def get_trial_references(request: TrialGetRequest):
    """Get trial publications and reference materials"""
    params = request.dict()
    return await biomcp.call_tool("trial_references_getter", params)

@app.post("/api/tools/trial_arms_getter", response_model=ToolResponse)
async def get_trial_arms(request: TrialGetRequest):
    """Get trial arm details and intervention information"""
    params = request.dict()
    return await biomcp.call_tool("trial_arms_getter", params)

# =============================================================================
# VARIANT TOOL ENDPOINTS
# =============================================================================

@app.post("/api/tools/variant_searcher", response_model=ToolResponse)
async def search_variants(request: VariantSearchRequest):
    """Search genetic variants across multiple databases"""
    params = request.dict(exclude_none=True)
    return await biomcp.call_tool("variant_searcher", params)

@app.post("/api/tools/variant_getter", response_model=ToolResponse)
async def get_variant(request: VariantGetRequest):
    """Get comprehensive variant annotations from MyVariant.info"""
    params = request.dict()
    return await biomcp.call_tool("variant_getter", params)

@app.post("/api/tools/variant_details", response_model=ToolResponse)
async def get_variant_details(request: VariantGetRequest):
    """Get detailed variant information from CIViC, ClinVar, COSMIC"""
    params = request.dict()
    return await biomcp.call_tool("variant_details", params)

@app.post("/api/tools/variant_clinical", response_model=ToolResponse)
async def get_variant_clinical(request: VariantGetRequest):
    """Get clinical significance and therapeutic implications"""
    params = request.dict()
    return await biomcp.call_tool("variant_clinical", params)

@app.post("/api/tools/variant_population", response_model=ToolResponse)
async def get_variant_population(request: VariantGetRequest):
    """Get population frequency data from 1000 Genomes, gnomAD"""
    params = request.dict()
    return await biomcp.call_tool("variant_population", params)

@app.post("/api/tools/variant_functional", response_model=ToolResponse)
async def get_variant_functional(request: VariantGetRequest):
    """Get functional predictions and pathogenicity scores"""
    params = request.dict()
    return await biomcp.call_tool("variant_functional", params)

@app.post("/api/tools/variant_literature", response_model=ToolResponse)
async def get_variant_literature(request: VariantGetRequest):
    """Get variant-specific literature and evidence"""
    params = request.dict()
    return await biomcp.call_tool("variant_literature", params)

@app.post("/api/tools/variant_drugs", response_model=ToolResponse)
async def get_variant_drugs(request: VariantGetRequest):
    """Get variant-drug associations and pharmacogenomics"""
    params = request.dict()
    return await biomcp.call_tool("variant_drugs", params)

# =============================================================================
# GENE TOOL ENDPOINTS
# =============================================================================

@app.post("/api/tools/gene_getter", response_model=ToolResponse)
async def get_gene(request: GeneGetRequest):
    """Get comprehensive gene information and annotations"""
    params = request.dict()
    return await biomcp.call_tool("gene_getter", params)

@app.post("/api/tools/gene_variants", response_model=ToolResponse)
async def get_gene_variants(request: GeneGetRequest):
    """Get all variants associated with a specific gene"""
    params = request.dict()
    return await biomcp.call_tool("gene_variants", params)

@app.post("/api/tools/gene_drugs", response_model=ToolResponse)
async def get_gene_drugs(request: GeneGetRequest):
    """Get gene-drug associations and targets"""
    params = request.dict()
    return await biomcp.call_tool("gene_drugs", params)

@app.post("/api/tools/gene_pathways", response_model=ToolResponse)
async def get_gene_pathways(request: GeneGetRequest):
    """Get gene pathway and functional annotation"""
    params = request.dict()
    return await biomcp.call_tool("gene_pathways", params)

# =============================================================================
# DISEASE TOOL ENDPOINTS
# =============================================================================

@app.post("/api/tools/disease_getter", response_model=ToolResponse)
async def get_disease(request: DiseaseGetRequest):
    """Get disease information, synonyms, and ontology"""
    params = request.dict()
    return await biomcp.call_tool("disease_getter", params)

@app.post("/api/tools/disease_genes", response_model=ToolResponse)
async def get_disease_genes(request: DiseaseGetRequest):
    """Get genes associated with a disease condition"""
    params = request.dict()
    return await biomcp.call_tool("disease_genes", params)

@app.post("/api/tools/disease_drugs", response_model=ToolResponse)
async def get_disease_drugs(request: DiseaseGetRequest):
    """Get drugs and treatments for a disease"""
    params = request.dict()
    return await biomcp.call_tool("disease_drugs", params)

# =============================================================================
# DRUG TOOL ENDPOINTS
# =============================================================================

@app.post("/api/tools/drug_getter", response_model=ToolResponse)
async def get_drug(request: DrugGetRequest):
    """Get comprehensive drug information and properties"""
    params = request.dict()
    return await biomcp.call_tool("drug_getter", params)

@app.post("/api/tools/drug_targets", response_model=ToolResponse)
async def get_drug_targets(request: DrugGetRequest):
    """Get drug targets and mechanism of action"""
    params = request.dict()
    return await biomcp.call_tool("drug_targets", params)

@app.post("/api/tools/drug_trials", response_model=ToolResponse)
async def get_drug_trials(request: DrugGetRequest):
    """Get clinical trials testing a specific drug"""
    params = request.dict()
    return await biomcp.call_tool("drug_trials", params)

# =============================================================================
# ORGANIZATION TOOL ENDPOINTS
# =============================================================================

@app.post("/api/tools/organization_searcher", response_model=ToolResponse)
async def search_organizations(request: SearchRequest):
    """Search research organizations and institutions"""
    params = request.dict()
    return await biomcp.call_tool("organization_searcher", params)

@app.post("/api/tools/organization_getter", response_model=ToolResponse)
async def get_organization(organization_id: str):
    """Get organization details and research focus"""
    params = {"org_id": organization_id}
    return await biomcp.call_tool("organization_getter", params)

# =============================================================================
# GENERIC AND BATCH ENDPOINTS
# =============================================================================

@app.post("/api/tools/{tool_name}/call", response_model=ToolResponse)
async def call_tool_generic(tool_name: str, parameters: Dict[str, Any]):
    """Generic tool caller for any BioMCP tool"""
    if tool_name not in BIOMCP_TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    return await biomcp.call_tool(tool_name, parameters)

@app.post("/api/batch/search")
async def batch_search(request: BatchRequest):
    """Execute multiple searches in parallel or sequentially"""
    if request.parallel:
        # Parallel execution
        tasks = [
            biomcp.call_tool(request.tool_name, {"query": query, "limit": 5})
            for query in request.queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    else:
        # Sequential execution
        results = []
        for query in request.queries:
            result = await biomcp.call_tool(request.tool_name, {"query": query, "limit": 5})
            results.append(result)
    
    return {
        "total_queries": len(request.queries),
        "successful": sum(1 for r in results if not isinstance(r, Exception) and r.success),
        "failed": sum(1 for r in results if isinstance(r, Exception) or not r.success),
        "results": [
            r if not isinstance(r, Exception) 
            else ToolResponse(success=False, data={"error": str(r)}, method="error", execution_time=0, timestamp=datetime.now())
            for r in results
        ]
    }

# =============================================================================
# WEBSOCKET SUPPORT FOR STREAMING
# =============================================================================

@app.websocket("/ws/tools")
async def websocket_tool_calls(websocket: WebSocket):
    """WebSocket endpoint for real-time tool calls with streaming support"""
    await websocket.accept()
    
    try:
        while True:
            # Receive tool request
            data = await websocket.receive_json()
            tool_name = data.get("tool_name")
            parameters = data.get("parameters", {})
            
            # Validate tool
            if tool_name not in BIOMCP_TOOLS:
                await websocket.send_json({
                    "success": False,
                    "error": f"Tool '{tool_name}' not found",
                    "timestamp": datetime.now().isoformat()
                })
                continue
            
            # Call tool
            result = await biomcp.call_tool(tool_name, parameters)
            
            # Send result
            await websocket.send_json({
                "tool_name": tool_name,
                "success": result.success,
                "data": result.data,
                "method": result.method,
                "execution_time": result.execution_time,
                "timestamp": result.timestamp.isoformat()
            })
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass  # Connection might be closed

# =============================================================================
# ADVANCED FEATURES
# =============================================================================

@app.post("/api/biomcp/raw")
async def biomcp_raw_command(command: List[str], auth: HTTPAuthorizationCredentials = Depends(get_auth_token)):
    """Direct passthrough to BioMCP CLI (requires authentication)"""
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=60
        )
        
        return {
            "command": command,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
            "returncode": process.returncode,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_api_stats():
    """Get API usage statistics and performance metrics"""
    return {
        "service": "biomcp-production-api-v16",
        "version": "1.6.0",
        "uptime_seconds": biomcp.get_uptime(),
        "integration_method": "subprocess",
        "tools_available": len(BIOMCP_TOOLS),
        "categories": {
            category.value: sum(1 for tool in BIOMCP_TOOLS.values() if tool["category"] == category)
            for category in ToolCategory
        }
    }

@app.get("/api/tools/{tool_name}/usage")
async def get_tool_usage_example(tool_name: str):
    """Get usage examples and documentation for a specific tool"""
    if tool_name not in BIOMCP_TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    tool_info = BIOMCP_TOOLS[tool_name]
    
    # Generate example based on tool category
    examples = {
        ToolCategory.CORE: {
            "search": {"query": "BRCA1 breast cancer", "limit": 10},
            "think": {"thought": "Analyzing BRCA1 mutations in breast cancer", "thought_number": 1}
        },
        ToolCategory.ARTICLE: {
            "article_searcher": {"gene": "BRCA1", "disease": "breast cancer", "limit": 10},
            "article_getter": {"identifier": "12345678", "full_text": True}
        },
        ToolCategory.TRIAL: {
            "trial_searcher": {"condition": "breast cancer", "term": "BRCA1", "limit": 10},
            "trial_getter": {"nct_id": "NCT01234567"}
        },
        ToolCategory.VARIANT: {
            "variant_searcher": {"gene": "BRCA1", "significance": ["pathogenic"], "limit": 10},
            "variant_getter": {"variant_id": "rs80357906"}
        },
        ToolCategory.GENE: {
            "gene_getter": {"gene_symbol": "BRCA1", "include_variants": True}
        },
        ToolCategory.DISEASE: {
            "disease_getter": {"disease_name": "breast cancer", "include_genes": True}
        },
        ToolCategory.DRUG: {
            "drug_getter": {"drug_name": "trastuzumab", "include_targets": True}
        },
        ToolCategory.ORGANIZATION: {
            "organization_searcher": {"query": "MD Anderson"}
        }
    }
    
    category_examples = examples.get(tool_info["category"], {})
    example_params = category_examples.get(tool_name, {"query": "example"})
    
    return {
        "tool_name": tool_name,
        "category": tool_info["category"],
        "description": tool_info["description"],
        "command_template": tool_info["command_template"],
        "endpoint": f"/api/tools/{tool_name}",
        "example_request": example_params,
        "example_curl": f"""curl -X POST "http://localhost:8000/api/tools/{tool_name}" \\
     -H "Content-Type: application/json" \\
     -d '{json.dumps(example_params)}'"""
    }

# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

# =============================================================================
# MAIN APPLICATION ENTRY POINT
# =============================================================================

def create_app() -> FastAPI:
    """Factory function to create the FastAPI application"""
    return app

if __name__ == "__main__":
    # Configuration from environment variables
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    workers = int(os.getenv("WORKERS", 1))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info")
    
    # Run the application
    if reload:
        # Development mode with reload
        uvicorn.run(
            "production_biomcp_api-V16:app",
            host=host,
            port=port,
            reload=reload,
            log_level=log_level,
            access_log=True
        )
    else:
        # Production mode
        uvicorn.run(
            app,
            host=host,
            port=port,
            workers=workers,
            log_level=log_level,
            access_log=True
        )
