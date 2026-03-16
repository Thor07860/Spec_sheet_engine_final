"""
==============================================================================
scripts/backfill_equipment_urls.py
==============================================================================
PURPOSE:
  Update existing equipment records with source URLs (original_source_url and 
  source_url from S3 cache). This fixes equipment that was in the database 
  before URL-capturing was added.

FLOW:
  For each equipment:
    1. Search for its PDF datasheet (Serper API)
    2. Download PDF to Vultr S3 bucket
    3. Update database with both URLs
    4. Log results

HOW TO RUN:
  python scripts/backfill_equipment_urls.py
==============================================================================
"""

import os
import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, engine, Base
from app.models.equipment_model import Equipment
from app.services.serper_service import SerperService
from app.services.s3_service import S3Service

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def backfill_urls():
    """Backfill source URLs for all equipment without them."""
    
    db = SessionLocal()
    serper = SerperService(db=db)
    s3 = S3Service()
    
    try:
        # Find all equipment without original_source_url set
        equipment_list = db.query(Equipment).filter(
            Equipment.original_source_url == None
        ).all()
        
        logger.info(f"Found {len(equipment_list)} equipment records without source URLs")
        
        for idx, equipment in enumerate(equipment_list, 1):
            logger.info(f"\n[{idx}/{len(equipment_list)}] Processing: {equipment.manufacturer} {equipment.model}")
            
            try:
                # Step 1: Search for PDF
                logger.info(f"  → Searching for PDF datasheet...")
                search_results = serper.search_spec_sheet(
                    manufacturer=equipment.manufacturer,
                    model=equipment.model,
                    equipment_type=equipment.equipment_type
                )
                
                if not search_results:
                    logger.warning(f"  ✗ No PDF found for {equipment.manufacturer} {equipment.model}")
                    continue
                
                # Get first PDF result
                pdf_url = search_results[0].get("url")
                if not pdf_url:
                    logger.warning(f"  ✗ No URL in search results for {equipment.manufacturer} {equipment.model}")
                    continue
                
                logger.info(f"  ✓ Found PDF: {pdf_url}")
                
                # Step 2: Download and cache to S3
                logger.info(f"  → Downloading to S3 bucket...")
                s3_url = s3.download_and_cache_pdf(
                    url=pdf_url,
                    equipment_type=equipment.equipment_type,
                    manufacturer=equipment.manufacturer,
                    model=equipment.model
                )
                
                if not s3_url:
                    logger.warning(f"  ✗ Failed to cache PDF to S3")
                    continue
                
                logger.info(f"  ✓ Cached to S3: {s3_url}")
                
                # Step 3: Update database
                logger.info(f"  → Updating database...")
                equipment.original_source_url = pdf_url
                equipment.source_url = s3_url
                db.commit()
                db.refresh(equipment)
                
                logger.info(f"  ✓ Updated database successfully")
                
            except Exception as e:
                logger.error(f"  ✗ Error processing {equipment.manufacturer} {equipment.model}: {str(e)}")
                db.rollback()
                continue
        
        logger.info(f"\n✓ Backfill completed!")
        
    except Exception as e:
        logger.error(f"Fatal error during backfill: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    backfill_urls()
