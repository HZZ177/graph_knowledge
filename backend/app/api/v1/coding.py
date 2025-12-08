"""Coding API - 对接 Coding 平台

获取需求文档、事项详情等信息。
"""

from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import Response

from backend.app.schemas.coding import IssueRequest
from backend.app.services.coding_service import coding_service
from backend.app.core.utils import success_response, error_response
from backend.app.core.logger import logger


router = APIRouter(prefix="/coding", tags=["coding"])


@router.post("/issue/detail")
async def get_issue_detail(request: IssueRequest):
    """获取事项详情
    
    返回需求名称、code、详情描述。
    """
    try:
        issue = await coding_service.get_issue_detail(
            project_name=request.project_name,
            issue_code=request.issue_code,
        )
        return success_response(data=issue.model_dump())
    except Exception as e:
        return error_response(message=f"获取事项详情失败: {str(e)}")


@router.post("/issue/file-urls")
async def get_issue_file_urls(request: IssueRequest):
    """获取事项文件下载地址
    
    返回事项中关联文件的下载地址列表。
    """
    try:
        file_urls = await coding_service.get_issue_file_urls(
            project_name=request.project_name,
            issue_code=request.issue_code,
        )
        return success_response(data={"file_urls": file_urls})
    except Exception as e:
        return error_response(message=f"获取文件地址失败: {str(e)}")


@router.post("/issue/export-pdf")
async def export_issue_pdf(request: IssueRequest):
    """导出需求文档为 PDF
    
    将需求详情（包含图片）导出为 PDF 文件，直接返回文件流供前端下载。
    """
    try:
        pdf_bytes, filename = await coding_service.export_issue_pdf(
            project_name=request.project_name,
            issue_code=request.issue_code,
        )
        
        # 返回文件流
        # filename: ASCII fallback（用需求编号）
        # filename*: UTF-8 编码的中文名（现代浏览器优先使用）
        encoded_filename = quote(filename)
        fallback_filename = f"{request.issue_code}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=\"{fallback_filename}\"; filename*=UTF-8''{encoded_filename}",
                "Content-Length": str(len(pdf_bytes)),
            }
        )
    except Exception as e:
        logger.error(f"[CodingAPI] 导出 PDF 失败: {e}")
        return error_response(message=f"导出 PDF 失败: {str(e)}")
