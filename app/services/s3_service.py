# ==============================================================================
# services/s3_service.py
# ==============================================================================
# PURPOSE:
#   Handles S3 upload operations for PDF files and other documents.
#   Integrates with Vultr Object Storage (S3-compatible).
#
# FEATURES:
#   - Upload PDF files to S3 bucket
#   - Generate S3 URLs for uploaded files
#   - Support per-item storage (each equipment gets its own S3 object)
#
# ==============================================================================

import logging
import io
import requests
from typing import Optional
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from app.core.config import Settings

logger = logging.getLogger(__name__)

settings = Settings()


class S3Service:
    """
    Service for managing S3 uploads to Vultr Object Storage.
    Handles PDF uploads per equipment item with auto-generated keys.
    """

    def __init__(self):
        """Initialize S3 client with Vultr credentials."""
        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=settings.AWS_S3_ENDPOINT,
                region_name=settings.AWS_S3_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            self.bucket_name = settings.AWS_S3_BUCKET
            logger.info(
                "✅ S3 Service initialized: %s (endpoint: %s)",
                self.bucket_name,
                settings.AWS_S3_ENDPOINT
            )
        except Exception as e:
            logger.error("❌ Failed to initialize S3 Service: %s", str(e))
            raise

    def upload_pdf_from_url(
        self,
        pdf_url: str,
        manufacturer: str,
        model: str,
        equipment_type: str
    ) -> Optional[str]:
        """
        Download PDF from URL and upload to S3.

        Args:
            pdf_url: URL of the PDF to download
            manufacturer: Equipment manufacturer name
            model: Equipment model name
            equipment_type: Equipment type (inverter, module, etc.)

        Returns:
            S3 URL of the uploaded PDF, or None if upload failed
        """
        try:
            logger.info(
                "⬇️ Downloading PDF from: %s",
                pdf_url
            )

            # Download PDF from source URL
            response = requests.get(pdf_url, timeout=30)
            response.raise_for_status()

            pdf_content = response.content
            logger.info("✅ PDF downloaded: %d bytes", len(pdf_content))

            # Generate unique S3 key (filename in bucket)
            s3_key = self._generate_s3_key(manufacturer, model, equipment_type)

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=pdf_content,
                ContentType="application/pdf"
            )

            # Generate and return S3 URL
            s3_url = self._generate_s3_url(s3_key)
            logger.info("✅ PDF uploaded to S3: %s", s3_url)

            return s3_url

        except requests.RequestException as e:
            logger.error("❌ Failed to download PDF from %s: %s", pdf_url, str(e))
            return None

        except ClientError as e:
            logger.error("❌ S3 upload failed: %s", str(e))
            return None

        except Exception as e:
            logger.error("❌ Unexpected error during PDF upload: %s", str(e))
            return None

    def upload_pdf_from_bytes(
        self,
        pdf_bytes: bytes,
        manufacturer: str,
        model: str,
        equipment_type: str
    ) -> Optional[str]:
        """
        Upload PDF directly from bytes to S3.

        Args:
            pdf_bytes: PDF file content as bytes
            manufacturer: Equipment manufacturer name
            model: Equipment model name
            equipment_type: Equipment type

        Returns:
            S3 URL of the uploaded PDF, or None if upload failed
        """
        try:
            logger.info(
                "📤 Uploading PDF to S3: %s %s (%s)",
                manufacturer,
                model,
                equipment_type
            )

            # Generate unique S3 key
            s3_key = self._generate_s3_key(manufacturer, model, equipment_type)

            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=pdf_bytes,
                ContentType="application/pdf"
            )

            # Generate and return S3 URL
            s3_url = self._generate_s3_url(s3_key)
            logger.info("✅ PDF uploaded to S3: %s", s3_url)

            return s3_url

        except ClientError as e:
            logger.error("❌ S3 upload failed: %s", str(e))
            return None

        except Exception as e:
            logger.error("❌ Unexpected error during PDF upload: %s", str(e))
            return None

    def _generate_s3_key(
        self,
        manufacturer: str,
        model: str,
        equipment_type: str
    ) -> str:
        """
        Generate a unique S3 object key (filename).

        Format: equipment/{equipment_type}/{manufacturer}/{model}/{timestamp}.pdf

        This ensures per-item organization and uniqueness.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Clean up names for safe S3 keys
        manufacturer_clean = manufacturer.replace(" ", "_").lower()
        model_clean = model.replace(" ", "_").lower()
        equipment_type_clean = equipment_type.replace(" ", "_").lower()

        s3_key = (
            f"equipment/{equipment_type_clean}/{manufacturer_clean}/"
            f"{model_clean}/{timestamp}.pdf"
        )

        return s3_key

    def _generate_s3_url(self, s3_key: str) -> str:
        """
        Generate the public S3 URL for the uploaded object.

        Format: https://<endpoint>/<bucket>/<key>
        """
        # Remove https:// from endpoint and trailing slashes
        endpoint = settings.AWS_S3_ENDPOINT.replace("https://", "").rstrip("/")
        
        s3_url = f"https://{endpoint}/{self.bucket_name}/{s3_key}"
        return s3_url

    def delete_pdf(self, s3_key: str) -> bool:
        """
        Delete a PDF from S3.

        Args:
            s3_key: S3 object key to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info("✅ Deleted S3 object: %s", s3_key)
            return True

        except ClientError as e:
            logger.error("❌ Failed to delete S3 object: %s", str(e))
            return False

    def object_exists(self, s3_key: str) -> bool:
        """
        Check if an object exists in S3.

        Args:
            s3_key: S3 object key to check

        Returns:
            True if object exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            logger.error("❌ Error checking S3 object: %s", str(e))
            return False
