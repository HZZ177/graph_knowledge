from typing import List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_models import AIModel
from backend.app.schemas.ai_models import (
    AIModelCreate,
    AIModelUpdate,
)
from backend.app.llm.config import LLMConfig


class AIModelService:
    """LLM 模型配置管理服务。"""

    @staticmethod
    def list_models(db: Session) -> List[AIModel]:
        return db.query(AIModel).order_by(AIModel.id).all()

    @staticmethod
    def create_model(db: Session, data: AIModelCreate) -> AIModel:
        # 名称唯一性校验
        existing = db.query(AIModel).filter(AIModel.name == data.name).first()
        if existing:
            raise ValueError("Model name already exists")

        obj = AIModel(
            name=data.name,
            provider=data.provider or "",
            model_name=data.model_name,
            api_key=data.api_key,
            base_url=data.base_url,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
        )
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def update_model(db: Session, model_id: int, data: AIModelUpdate) -> Optional[AIModel]:
        obj = db.query(AIModel).filter(AIModel.id == model_id).first()
        if not obj:
            return None

        update_data = data.dict(exclude_unset=True)

        # api_key 为空表示不更新
        api_key = update_data.pop("api_key", None)
        if api_key is not None:
            obj.api_key = api_key

        for field, value in update_data.items():
            if field == "provider":
                setattr(obj, field, value or "")
            else:
                setattr(obj, field, value)

        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def delete_model(db: Session, model_id: int) -> bool:
        """删除指定配置。

        如果是当前激活模型，则禁止删除并抛出 ValueError。
        返回 False 表示记录不存在。
        """

        obj = db.query(AIModel).filter(AIModel.id == model_id).first()
        if not obj:
            return False

        if obj.is_active:
            raise ValueError("Cannot delete active model")

        db.delete(obj)
        db.commit()
        return True

    @staticmethod
    def set_active_model(db: Session, model_id: int) -> Optional[AIModel]:
        """将指定模型设为激活状态，并取消其他模型的激活标记。"""

        obj = db.query(AIModel).filter(AIModel.id == model_id).first()
        if not obj:
            return None

        # 先取消所有当前激活模型
        db.query(AIModel).filter(AIModel.is_active.is_(True)).update(
            {AIModel.is_active: False}
        )

        obj.is_active = True
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def get_active_model(db: Session) -> Optional[AIModel]:
        """返回当前激活的 AIModel（若无则返回 None）。"""

        return db.query(AIModel).filter(AIModel.is_active.is_(True)).first()

    @staticmethod
    def get_active_llm_config(db: Session) -> LLMConfig:
        """从当前激活的 AIModel 构造 LLMConfig。"""

        obj = AIModelService.get_active_model(db)
        if not obj:
            raise RuntimeError("No active LLM model configured. Please configure one in ai_models.")

        return LLMConfig(
            provider=obj.provider,
            model_name=obj.model_name,
            base_url=obj.base_url,
            api_key=obj.api_key,
            temperature=obj.temperature,
            max_tokens=obj.max_tokens,
        )
