from fastapi import APIRouter

router = APIRouter(prefix="/processes", tags=["processes"])


@router.get("", summary="列出示例流程")
async def list_processes() -> list[dict]:
    """返回一个示例流程列表。

    工程化后这里会从数据库读取流程配置。
    """
    return [
        {"process_id": "c_open_card", "name": "C端开通月卡"},
    ]
