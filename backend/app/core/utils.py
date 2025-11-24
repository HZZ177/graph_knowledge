from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def success_response(message="成功", data=""):
    """通用的成功响应"""
    response_content = {
        "code": 200,
        "message": message,
        "data": data
    }
    return JSONResponse(content=jsonable_encoder(response_content))


def error_response(message="失败", data=""):
    """通用的错误响应"""
    response_content = {
        "code": 500,
        "message": message,
        "data": data
    }
    return JSONResponse(content=jsonable_encoder(response_content))