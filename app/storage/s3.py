import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings


class Storage:
    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )

    def garantir_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def upload(self, key: str, conteudo: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=conteudo, ContentType=content_type
        )

    def baixar(self, key: str) -> bytes:
        resposta = self.client.get_object(Bucket=self.bucket, Key=key)
        return resposta["Body"].read()

    def apagar(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def url_temporaria(self, key: str, filename: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=settings.presigned_url_minutes * 60,
        )


storage = Storage()
