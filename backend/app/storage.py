from io import BytesIO
from pathlib import Path
import zipfile
from cryptography.fernet import Fernet
from PIL import Image
from fastapi import HTTPException
from .config import settings


def cipher():
    return Fernet(settings().encryption_key.encode())


def s3():
    import boto3

    s = settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint or None,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
    )


def path_for(key):
    root = settings().storage_dir.resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Invalid storage key")
    return path


def save(key, data):
    encrypted = cipher().encrypt(data)
    if settings().storage_backend == "s3":
        s3().put_object(Bucket=settings().s3_bucket, Key=key, Body=encrypted)
    else:
        path = path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encrypted)
        path.chmod(0o600)


def read(key):
    if settings().storage_backend == "s3":
        data = s3().get_object(Bucket=settings().s3_bucket, Key=key)["Body"].read()
    else:
        data = path_for(key).read_bytes()
    return cipher().decrypt(data)


def delete(key):
    if settings().storage_backend == "s3":
        s3().delete_object(Bucket=settings().s3_bucket, Key=key)
    else:
        path_for(key).unlink(missing_ok=True)


def validate(data, name):
    if not data or len(data) > settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(
            413,
            f"Размер файла должен быть от 1 байта до {settings().max_upload_mb} МБ.",
        )
    ext = Path(name).suffix.lower()
    try:
        if ext == ".pdf" and data.startswith(b"%PDF-"):
            return "application/pdf"
        if ext in (".txt", ".md"):
            text = data.decode("utf-8-sig")
            if "\0" in text:
                raise ValueError()
            return "text/plain"
        if ext == ".docx":
            with zipfile.ZipFile(BytesIO(data)) as z:
                if (
                    len(z.infolist()) > 2000
                    or sum(x.file_size for x in z.infolist()) > 50_000_000
                    or "word/document.xml" not in z.namelist()
                ):
                    raise ValueError()
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if ext in (".jpg", ".jpeg", ".png", ".heic", ".heif"):
            from pillow_heif import register_heif_opener

            register_heif_opener()
            with Image.open(BytesIO(data)) as im:
                if im.width * im.height > 25_000_000 or im.format not in (
                    "JPEG",
                    "PNG",
                    "HEIF",
                ):
                    raise ValueError()
                im.verify()
            return (
                "image/heic"
                if ext in (".heic", ".heif")
                else ("image/png" if ext == ".png" else "image/jpeg")
            )
    except Exception:
        pass
    raise HTTPException(
        422,
        "Файл повреждён или формат не поддерживается. Выберите фото, PDF, DOCX или TXT.",
    )
