from fastapi import FastAPI, Depends, UploadFile, File, Form, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
import uvicorn
import shutil
import os
import uuid
import utils
import ai_helper
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize DB on startup
utils.init_db()

class CaseStatusUpdate(BaseModel):
    case_id: int 
    status: str
    project: str
    failed_case_text: Optional[str] = None
    bug_description: Optional[str] = None

class BugUpdate(BaseModel):
    case_id: int
    project: str
    new_text: str

class BugDelete(BaseModel):
    case_id: int
    project: str

# Batch Models
class BatchDelete(BaseModel):
    case_ids: List[int]

class BatchUpdateStatus(BaseModel):
    case_ids: List[int]
    status: str

class DeleteAll(BaseModel):
    project: str

class ModuleRetest(BaseModel):
    project: str
    module_name: str

@app.get("/")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/upload")
async def upload_file(project: str = Form(...), file: UploadFile = File(...)):
    temp_filename = f"temp_{uuid.uuid4()}_{file.filename}"
    try:
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        if file.filename.endswith(".docx"):
            text = utils.read_docx(temp_filename)
        elif file.filename.endswith(".doc"):
            text = utils.read_doc(temp_filename)
        else:
            text = utils.read_txt(temp_filename)
            
        module_name, cases = ai_helper.generate_test_cases(text)
        
        if not cases:
             return JSONResponse(status_code=400, content={"error": "No test cases found in document"})

        utils.add_cases(cases, module_name, project)
        return {"module": module_name, "count": len(cases)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@app.get("/api/modules")
async def get_modules(project: str = "togetherfun"):
    modules_stats = utils.get_module_stats(project)
    return {"modules": modules_stats}

@app.post("/api/start-module")
async def start_module(request: Request):
    data = await request.json()
    module_name = data.get("module_name")
    project = data.get("project", "togetherfun")
    
    if not module_name:
        return JSONResponse(status_code=400, content={"error": "Module name required"})
    
    case = utils.get_next_pending_case_by_module(module_name, project)
    if not case:
        return {"finished": True}
    return {"case": case}

@app.post("/api/submit-result")
async def submit_result(update: CaseStatusUpdate):
    try:
        if update.status == "Pass":
            utils.update_case_status(update.case_id, "Pass")
        else:
            bug_report = None
            if update.bug_description:
                 bug_report = ai_helper.generate_bug_report(update.failed_case_text, update.bug_description)
            utils.update_case_status(update.case_id, "FAILED", bug_report)
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/bugs")
async def get_bugs(project: str = "togetherfun"):
    try:
        bugs = utils.get_failed_cases_with_bugs(project)
        return {"bugs": bugs}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.put("/api/bugs")
async def update_bug(update: BugUpdate):
    try:
        utils.update_bug_report_text(update.case_id, update.new_text)
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.delete("/api/bugs")
async def delete_bug(req: BugDelete):
    try:
        utils.delete_bug_report(req.case_id)
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- New Endpoints ---

@app.get("/api/cases")
async def get_all_cases(project: str = "togetherfun", page: int = Query(1, ge=1), limit: int = Query(20, le=100), status: Optional[str] = None):
    try:
        cases, total, all_modules = utils.get_all_cases_paginated(project, page, limit, status)
        return {"cases": cases, "total": total, "page": page, "limit": limit, "all_modules": all_modules}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/cases/batch/delete")
async def batch_delete(req: BatchDelete):
    try:
        utils.delete_cases_bulk(req.case_ids)
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/cases/batch/status")
async def batch_status(req: BatchUpdateStatus):
    try:
        utils.update_cases_status_bulk(req.case_ids, req.status)
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/cases/all/delete")
async def delete_all(req: DeleteAll):
    try:
        utils.delete_all_cases_for_project(req.project)
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/modules/retest")
async def retest_module(req: ModuleRetest):
    try:
        success = utils.reset_module_cases(req.project, req.module_name)
        if not success:
            return JSONResponse(status_code=404, content={"error": "Module or project not found"})
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Project Management ---

@app.get("/api/projects")
async def get_projects():
    """Get all projects"""
    try:
        projects = utils.get_all_projects()
        return {"projects": projects}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

class ProjectCreate(BaseModel):
    name: str

@app.post("/api/projects")
async def create_project(req: ProjectCreate):
    """Create a new project"""
    try:
        if not req.name or len(req.name.strip()) < 2:
            return JSONResponse(status_code=400, content={"error": "Project name must be at least 2 characters"})
        
        success = utils.create_project(req.name.strip())
        if not success:
            return JSONResponse(status_code=400, content={"error": "Project already exists"})
        return {"success": True, "name": req.name.strip()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

class ProjectDelete(BaseModel):
    name: str

@app.delete("/api/projects")
async def delete_project(req: ProjectDelete):
    """Delete a project and all its data"""
    try:
        success = utils.delete_project(req.name)
        if not success:
            return JSONResponse(status_code=404, content={"error": "Project not found"})
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/stats")
async def get_stats(project: str = "Default"):
    """Get project statistics for dashboard"""
    try:
        stats = utils.get_project_stats(project)
        if not stats:
            return {"total_cases": 0, "passed": 0, "failed": 0, "pending": 0, "modules": 0}
        return stats
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Export ---
from fastapi.responses import StreamingResponse
import csv
import io

@app.get("/api/export/csv")
async def export_csv(project: str = "Default"):
    """Export all cases as CSV"""
    try:
        cases, total = utils.get_all_cases_paginated(project, page=1, limit=10000)
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Module", "Content", "Status", "Bug Report"])
        
        for case in cases:
            writer.writerow([
                case.get("id", ""),
                case.get("module", ""),
                case.get("content", ""),
                case.get("status", ""),
                case.get("bug_report", "") or ""
            ])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={project}_test_cases.csv"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- Search ---
@app.get("/api/search")
async def search_cases(project: str = "Default", q: str = ""):
    """Search cases by content"""
    try:
        if not q or len(q) < 2:
            return {"cases": [], "total": 0}
        
        cases, total = utils.get_all_cases_paginated(project, page=1, limit=1000)
        filtered = [c for c in cases if q.lower() in c.get("content", "").lower() or q.lower() in c.get("module", "").lower()]
        
        return {"cases": filtered[:50], "total": len(filtered)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    # Host on 0.0.0.0 to allow access from other devices on the network
    uvicorn.run(app, host="0.0.0.0", port=8000)
