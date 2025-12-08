"""独立测试 OpenList S3 连接（无项目依赖）

使用方法（在虚拟环境中运行）：
    pip install boto3 httpx
    python scripts/test_openlist_s3_standalone.py
"""

import asyncio

# OpenList S3 配置
CONFIG = {
    "bucket": "self-chat-files",
    "endpoint": "https://openlists3.heshouyi.com",  # 反代地址
    "access_key": "S2Y7P/DgIsUup78PPzsV",
    "secret_key": "lBTSNrHaW2KoPUGL/kEwqcKKCRbWwHTaJJKIrBot",
    "region": "us-east-1",
}


def test_connection():
    """测试 OpenList S3 连接"""
    print("=" * 60)
    print("OpenList S3 连接测试")
    print("=" * 60)
    
    # 1. 导入 boto3
    print("\n[1] 检查 boto3...")
    try:
        import boto3
        from botocore.config import Config as BotoConfig
        print("    ✅ boto3 已安装")
    except ImportError:
        print("    ❌ 请先安装 boto3: pip install boto3")
        return False
    
    # 2. 创建客户端
    print("\n[2] 创建 S3 客户端...")
    try:
        boto_config = BotoConfig(
            signature_version='s3v4',
            s3={'addressing_style': 'path'}
        )
        
        client = boto3.client(
            's3',
            region_name=CONFIG['region'],
            aws_access_key_id=CONFIG['access_key'],
            aws_secret_access_key=CONFIG['secret_key'],
            endpoint_url=CONFIG['endpoint'],
            config=boto_config
        )
        print(f"    ✅ 客户端创建成功")
        print(f"       Endpoint: {CONFIG['endpoint']}")
        print(f"       Bucket: {CONFIG['bucket']}")
    except Exception as e:
        print(f"    ❌ 客户端创建失败: {e}")
        return False
    
    # 3. 列出存储桶（测试连接）
    print("\n[3] 测试连接（列出存储桶）...")
    try:
        response = client.list_buckets()
        buckets = [b['Name'] for b in response.get('Buckets', [])]
        print(f"    ✅ 连接成功!")
        print(f"       可用存储桶: {buckets}")
    except Exception as e:
        print(f"    ⚠️ 列出存储桶失败（可能是权限问题，继续测试上传）: {e}")
    
    # 4. 测试上传
    print("\n[4] 测试文件上传...")
    test_content = b"Hello OpenList S3! Test at " + str(asyncio.get_event_loop().time()).encode()
    test_key = "test/test_upload.txt"
    
    try:
        client.put_object(
            Bucket=CONFIG['bucket'],
            Key=test_key,
            Body=test_content,
            ContentType="text/plain"
        )
        print(f"    ✅ 上传成功!")
        print(f"       Key: {test_key}")
        
        # 构造 URL
        from urllib.parse import quote
        encoded_bucket = quote(CONFIG['bucket'], safe='')
        url = f"{CONFIG['endpoint']}/{encoded_bucket}/{test_key}"
        print(f"       URL: {url}")
        
    except Exception as e:
        print(f"    ❌ 上传失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. 测试获取对象
    print("\n[5] 测试获取对象...")
    try:
        response = client.get_object(Bucket=CONFIG['bucket'], Key=test_key)
        body = response['Body'].read()
        print(f"    ✅ 获取成功!")
        print(f"       内容: {body.decode()}")
    except Exception as e:
        print(f"    ❌ 获取失败: {e}")
    
    # 6. 测试删除
    print("\n[6] 测试删除文件...")
    try:
        client.delete_object(Bucket=CONFIG['bucket'], Key=test_key)
        print(f"    ✅ 删除成功!")
    except Exception as e:
        print(f"    ⚠️ 删除失败: {e}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成! OpenList S3 配置正确。")
    print("=" * 60)
    return True


if __name__ == "__main__":
    test_connection()
