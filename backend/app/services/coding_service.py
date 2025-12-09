"""Coding 服务模块

对接 Coding 平台 Open API，用于获取需求文档等信息。
"""

import re
import io
import time
from typing import List, Tuple

import httpx
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

from backend.app.schemas.coding import (
    IssueDetail,
    ProjectInfo,
    ProjectListResponse,
    IterationInfo,
    IterationListResponse,
    IssueInfo,
    IssueListResponse,
)
from backend.app.core.logger import logger


class CodingService:
    """Coding 平台 API 服务"""
    

    
    def __init__(self):
        """初始化 Coding 服务，配置认证 token"""
        self.base_url = "https://e.coding.net/open-api"
        self._token = "10c0912e30e3a7ef9cd16c872cb8e75e2d39de10"
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
    
    async def get_issue_detail(self, project_name: str, issue_code: int) -> IssueDetail:
        """查询事项详情
        
        Args:
            project_name: 项目名称
            issue_code: 事项编号
            
        Returns:
            IssueDetail: 包含需求名称、code、详情
            
        Raises:
            httpx.HTTPStatusError: API 请求失败
            KeyError: 响应数据格式异常
        """
        url = f"{self.base_url}?Action=DescribeIssue"
        payload = {
            "ProjectName": project_name,
            "IssueCode": issue_code,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self._headers)
            response.raise_for_status()
            data = response.json()
        
        issue = data["Response"]["Issue"]
        return IssueDetail(
            name=issue["Name"],
            code=issue["Code"],
            description=issue.get("Description", ""),
        )
    
    async def get_issue_file_urls(self, project_name: str, issue_code: int) -> List[str]:
        """查询事项中文件的下载地址
        
        Args:
            project_name: 项目名称
            issue_code: 事项编号
            
        Returns:
            List[str]: 文件下载地址列表
            
        Raises:
            httpx.HTTPStatusError: API 请求失败
        """
        url = f"{self.base_url}?Action=DescribeIssueFileUrl"
        payload = {
            "ProjectName": project_name,
            "IssueCode": issue_code,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self._headers)
            response.raise_for_status()
            data = response.json()
        
        # DescriptionImageUrl 是一个列表，直接返回
        return data["Response"].get("DescriptionImageUrl", [])
    
    def _replace_images_with_urls(self, description: str, file_urls: List[str]) -> str:
        """将 description 中的 markdown 图片替换为真实下载地址
        
        图片格式: ![xxx](相对路径)
        按出现顺序与 file_urls 列表一一对应
        
        Args:
            description: 原始 markdown 描述
            file_urls: 图片真实下载地址列表
            
        Returns:
            替换后的 markdown 描述
        """
        # 匹配 markdown 图片语法: ![alt](url)
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        
        matches = list(re.finditer(pattern, description))
        logger.info(f"[CodingService] 发现 {len(matches)} 个图片，有 {len(file_urls)} 个下载地址")
        
        if not matches or not file_urls:
            return description
        
        # 从后往前替换，避免位置偏移
        result = description
        for i, match in enumerate(reversed(matches)):
            idx = len(matches) - 1 - i
            if idx < len(file_urls):
                alt_text = match.group(1)
                new_img = f'![{alt_text}]({file_urls[idx]})'
                result = result[:match.start()] + new_img + result[match.end():]
        
        return result
    
    def _download_image_sync(self, url: str) -> bytes | None:
        """同步下载图片
        
        Args:
            url: 图片 URL
            
        Returns:
            图片字节数据，失败返回 None
        """
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.warning(f"[CodingService] 下载图片失败: {url}, {e}")
            return None
    
    def _markdown_to_pdf(self, title: str, code: int, description: str) -> bytes:
        """将需求内容转换为 PDF（使用 reportlab）
        
        Args:
            title: 需求名称
            code: 需求编号
            description: markdown 格式的需求详情
            
        Returns:
            PDF 文件字节
        """
        # 注册中文字体
        font_path = "C:/Windows/Fonts/msyh.ttc"
        try:
            pdfmetrics.registerFont(TTFont('MSYH', font_path))
        except:
            # 如果 msyh.ttc 不行，尝试 simhei.ttf
            pdfmetrics.registerFont(TTFont('MSYH', "C:/Windows/Fonts/simhei.ttf"))
        
        # 创建 PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm,
        )
        
        # 定义样式
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'ChineseTitle',
            parent=styles['Title'],
            fontName='MSYH',
            fontSize=18,
            textColor=HexColor('#333333'),
            spaceAfter=6,
        )
        
        meta_style = ParagraphStyle(
            'Meta',
            parent=styles['Normal'],
            fontName='MSYH',
            fontSize=10,
            textColor=HexColor('#666666'),
            spaceAfter=12,
        )
        
        h2_style = ParagraphStyle(
            'H2',
            parent=styles['Heading2'],
            fontName='MSYH',
            fontSize=14,
            textColor=HexColor('#444444'),
            spaceBefore=12,
            spaceAfter=6,
        )
        
        h3_style = ParagraphStyle(
            'H3',
            parent=styles['Heading3'],
            fontName='MSYH',
            fontSize=12,
            textColor=HexColor('#444444'),
            spaceBefore=10,
            spaceAfter=4,
        )
        
        body_style = ParagraphStyle(
            'ChineseBody',
            parent=styles['Normal'],
            fontName='MSYH',
            fontSize=11,
            leading=16,
            spaceAfter=6,
        )
        
        list_style = ParagraphStyle(
            'ListItem',
            parent=body_style,
            leftIndent=20,
            bulletIndent=10,
        )
        
        # 构建内容
        story = []
        
        # 标题
        story.append(Paragraph(title, title_style))
        
        # 分割线
        story.append(HRFlowable(width="100%", thickness=2, color=HexColor('#007bff')))
        story.append(Spacer(1, 6))
        
        # 需求编号
        story.append(Paragraph(f"需求编号: {code}", meta_style))
        story.append(Spacer(1, 12))
        
        # 解析 markdown 内容
        lines = description.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6))
                continue
            
            # 处理图片
            if line.startswith('!['):
                # 提取图片 URL: ![alt](url)
                img_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line)
                if img_match:
                    img_url = img_match.group(2)
                    try:
                        # 下载图片
                        img_data = self._download_image_sync(img_url)
                        if img_data:
                            img_buffer = io.BytesIO(img_data)
                            # 获取图片原始尺寸
                            from PIL import Image as PILImage
                            pil_img = PILImage.open(io.BytesIO(img_data))
                            orig_width, orig_height = pil_img.size
                            
                            # 计算缩放后的尺寸（保持比例，最大宽度 170mm）
                            max_width = 170 * mm
                            max_height = 200 * mm
                            
                            # 按比例缩放
                            ratio = min(max_width / orig_width, max_height / orig_height, 1.0)
                            new_width = orig_width * ratio
                            new_height = orig_height * ratio
                            
                            img = Image(img_buffer, width=new_width, height=new_height)
                            story.append(img)
                            story.append(Spacer(1, 6))
                    except Exception as e:
                        logger.warning(f"[CodingService] 图片处理失败: {img_url}, {e}")
                continue
            
            # 转义 HTML 特殊字符
            line = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            # 处理标题
            if line.startswith('####'):
                story.append(Paragraph(line.lstrip('#').strip(), h3_style))
            elif line.startswith('###'):
                story.append(Paragraph(line.lstrip('#').strip(), h3_style))
            elif line.startswith('##'):
                story.append(Paragraph(line.lstrip('#').strip(), h2_style))
            elif line.startswith('#'):
                story.append(Paragraph(line.lstrip('#').strip(), h2_style))
            elif line.startswith('- ') or line.startswith('* '):
                # 列表项
                story.append(Paragraph(f"• {line[2:]}", list_style))
            else:
                # 普通段落，移除 markdown 标记
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', line)
                text = re.sub(r'\*(.+?)\*', r'\1', text)
                text = re.sub(r'~~(.+?)~~', r'\1', text)
                story.append(Paragraph(text, body_style))
        
        # 生成 PDF
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        logger.info(f"[CodingService] PDF 生成完成: {len(pdf_bytes)} 字节")
        return pdf_bytes
    
    async def export_issue_pdf(self, project_name: str, issue_code: int) -> Tuple[bytes, str]:
        """导出需求文档为 PDF
        
        Args:
            project_name: 项目名称
            issue_code: 事项编号
            
        Returns:
            (pdf_bytes, filename): PDF 文件字节和建议的文件名
            
        Raises:
            httpx.HTTPStatusError: API 请求失败
        """
        # 1. 获取需求详情
        issue = await self.get_issue_detail(project_name, issue_code)
        logger.info(f"[CodingService] 获取需求详情: {issue.name} (#{issue.code})")
        
        # 2. 获取图片下载地址
        file_urls = await self.get_issue_file_urls(project_name, issue_code)
        logger.info(f"[CodingService] 获取到 {len(file_urls)} 个文件下载地址")
        
        # 3. 替换图片地址
        description = self._replace_images_with_urls(issue.description, file_urls)
        
        # 4. 生成 PDF
        pdf_bytes = self._markdown_to_pdf(issue.name, issue.code, description)
        
        # 5. 生成文件名（需求名称.pdf）
        safe_name = re.sub(r'[\\/*?:"<>|]', '_', issue.name)[:80]
        filename = f"{safe_name}.pdf"
        
        return pdf_bytes, filename
    
    async def get_project_list(
        self,
        page_number: int = 1,
        page_size: int = 50,
        project_name: str = "",
    ) -> ProjectListResponse:
        """获取项目列表
        
        Args:
            page_number: 页码，从 1 开始
            page_size: 每页数量，最大 100
            project_name: 可选，按项目名称筛选
            
        Returns:
            ProjectListResponse: 项目列表响应
        """
        url = f"{self.base_url}?Action=DescribeCodingProjects"
        payload = {
            "PageNumber": page_number,
            "PageSize": page_size,
            "ProjectName": project_name or "",
        }
        
        logger.info(f"[CodingService] 请求项目列表: page={page_number}, size={page_size}, filter='{project_name}'")
        
        start_time = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self._headers)
            response.raise_for_status()
            data = response.json()
        elapsed = time.time() - start_time
        logger.debug(f"[CodingService] API 响应耗时: {elapsed:.2f}s")
        
        resp_data = data["Response"]["Data"]
        project_list = [
            ProjectInfo(
                id=p["Id"],
                name=p["Name"],
                display_name=p.get("DisplayName", p["Name"]),
                description=p.get("Description", ""),
                icon=p.get("Icon", ""),
                status=p.get("Status", 1),
                archived=p.get("Archived", False),
                created_at=p.get("CreatedAt", 0),
                updated_at=p.get("UpdatedAt", 0),
            )
            for p in resp_data.get("ProjectList", [])
        ]
        
        logger.info(f"[CodingService] 获取项目列表成功: 返回 {len(project_list)} 个项目, 总计 {resp_data.get('TotalCount', 0)} 个")
        
        return ProjectListResponse(
            page_number=resp_data.get("PageNumber", page_number),
            page_size=resp_data.get("PageSize", page_size),
            total_count=resp_data.get("TotalCount", 0),
            project_list=project_list,
        )
    
    async def get_iteration_list(
        self,
        project_name: str,
        limit: int = 20,
        offset: int = 0,
        keywords: str = "",
    ) -> IterationListResponse:
        """获取项目迭代列表
        
        Args:
            project_name: 项目名称（必填）
            limit: 每页数量
            offset: 偏移量
            keywords: 可选，关键词搜索
            
        Returns:
            IterationListResponse: 迭代列表响应
        """
        url = f"{self.base_url}?Action=DescribeIterationList"
        payload = {
            "ProjectName": project_name,
            "Limit": limit,
            "Offset": offset,
            "Keywords": keywords or "",
        }
        
        logger.info(f"[CodingService] 请求迭代列表: project='{project_name}', limit={limit}, offset={offset}")
        
        start_time = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self._headers)
            response.raise_for_status()
            data = response.json()
        elapsed = time.time() - start_time
        logger.debug(f"[CodingService] API 响应耗时: {elapsed:.2f}s")
        
        resp_data = data["Response"]["Data"]
        iterations = [
            IterationInfo(
                id=it["Id"],
                code=it["Code"],
                name=it["Name"],
                status=it.get("Status", ""),
                goal=it.get("Goal", ""),
                start_at=it.get("StartAt", 0),
                end_at=it.get("EndAt", 0),
                wait_process_count=it.get("WaitProcessCount", 0),
                processing_count=it.get("ProcessingCount", 0),
                completed_count=it.get("CompletedCount", 0),
                completed_percent=it.get("CompletedPercent", 0.0),
            )
            for it in resp_data.get("List", [])
        ]
        
        logger.info(f"[CodingService] 获取迭代列表成功: {project_name}, 返回 {len(iterations)} 个迭代, 总计 {resp_data.get('TotalRow', 0)} 个")
        
        return IterationListResponse(
            page=resp_data.get("Page", 1),
            page_size=resp_data.get("PageSize", limit),
            total_page=resp_data.get("TotalPage", 1),
            total_row=resp_data.get("TotalRow", 0),
            iterations=iterations,
        )
    
    async def get_issue_list(
        self,
        project_name: str,
        iteration_code: int,
        issue_type: str = "REQUIREMENT",
        limit: int = 50,
        offset: int = 0,
        keyword: str = "",
    ) -> IssueListResponse:
        """获取迭代下的事项列表
        
        Args:
            project_name: 项目名称
            iteration_code: 迭代 Code
            issue_type: 事项类型，REQUIREMENT/DEFECT/MISSION/SUB_TASK
            limit: 每页数量
            offset: 偏移量
            keyword: 关键词搜索
            
        Returns:
            IssueListResponse: 事项列表响应
        """
        url = f"{self.base_url}?Action=DescribeIssueList"
        
        # 构建查询条件
        conditions = [
            {
                "Key": "ITERATION",
                "Value": iteration_code,
            }
        ]
        # 如果有关键词，添加 KEYWORD 条件
        if keyword:
            conditions.append({
                "Key": "KEYWORD",
                "Value": keyword,
            })
        
        payload = {
            "ProjectName": project_name,
            "IssueType": issue_type,
            "Limit": limit,
            "Offset": offset,
            "SortKey": "CODE",
            "SortValue": "DESC",
            "Conditions": conditions,
        }
        
        logger.info(f"[CodingService] 请求事项列表: project='{project_name}', iteration={iteration_code}, type={issue_type}, keyword='{keyword}'")
        
        start_time = time.time()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=self._headers)
            response.raise_for_status()
            data = response.json()
        elapsed = time.time() - start_time
        logger.debug(f"[CodingService] API 响应耗时: {elapsed:.2f}s")
        
        issue_list = data["Response"].get("IssueList", [])
        issues = [
            IssueInfo(
                id=issue["Id"],
                code=issue["Code"],
                name=issue["Name"],
                type=issue.get("Type", issue_type),
                priority=issue.get("Priority", ""),
                status_name=issue.get("IssueStatusName", ""),
                status_type=issue.get("IssueStatusType", ""),
                iteration_id=issue.get("IterationId", 0),
                iteration_name=issue.get("Iteration", {}).get("Name", ""),
                assignee_names=[
                    a.get("Name", "") for a in issue.get("Assignees", [])
                ],
                created_at=issue.get("CreatedAt", 0),
                updated_at=issue.get("UpdatedAt", 0),
            )
            for issue in issue_list
        ]
        
        logger.info(
            f"[CodingService] 获取事项列表成功: {project_name}, 迭代 {iteration_code}, "
            f"返回 {len(issues)} 个 {issue_type}"
        )
        
        return IssueListResponse(
            total_count=len(issues),  # API 未返回 total，暂用当前数量
            issues=issues,
        )


# 全局单例
coding_service = CodingService()
