from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

import uuid
import enum
from app.core.database import Base


# ENUMS restricted values for certain fields
class EquipmentCategory(str, enum.Enum):
    SOURCE = "source"
    DC_SIDE = "dc_side"
    CONVERSION = "conversion"
    MONITORING = "monitoring"
    AC_SIDE = "ac_side"
    PROTECTION = "protection"
    METERING = "metering"
    GRID = "grid"
    STORAGE = "storage"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROGRESSING = "progressing"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


class MatchType(str, enum.Enum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    NOT_FOUND = "not_found"


# TABLE 1 : EQUIPMENT
class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    # Identify Fields
    label = Column(String(255), nullable=False)

    category = Column(
        SAEnum(EquipmentCategory, name="equipment_category_enum"),
        nullable=False
    )

    equipment_type = Column(String(100), nullable=False)
    equipment_sub_type = Column(String(100), nullable=False)
    manufacturer = Column(String(255), nullable=True)
    model = Column(String(255), nullable=True)
    priority = Column(Integer, default=100, nullable=False)

    # METADATA (JSONB)
    equipment_metadata = Column("metadata", JSONB, nullable=True, default=dict)

    # Original source URL (where the spec sheet was found)
    original_source_url = Column(Text, nullable=True)
    
    # Current source URL (may be S3 cached URL)
    source_url = Column(Text, nullable=True)
    confident_score = Column(Float, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Relationships
    extraction_jobs = relationship(
        "ExtractionJob",
        back_populates="equipment",
        lazy="select"
    )

    def __repr__(self):
        return f"<Equipment {self.manufacturer} {self.model} ({self.equipment_sub_type})>"


# TABLE 2 : EQUIPMENT TEMPLATE
class EquipmentTemplate(Base):
    __tablename__ = "equipment_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)

    equipment_sub_type = Column(String(100), unique=True, nullable=False)

    schema_template = Column(JSONB, nullable=False, default=dict)

    description = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self):
        return f"<EquipmentTemplate {self.equipment_sub_type}>"


# TABLE 3 : TRUSTED SOURCE
class TrustedSource(Base):
    __tablename__ = "trusted_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)

    domain = Column(String(255), unique=True, nullable=False)

    trust_score = Column(Integer, default=100, nullable=False)

    country = Column(String(10), default="US", nullable=False)

    source_type = Column(String(50), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self):
        return f"<TrustedSource {self.domain} score={self.trust_score}>"


# TABLE 4 : EXTRACTION JOB
class ExtractionJob(Base):
    __tablename__ = "equipment_extraction_jobs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    manufacturer = Column(String(255), nullable=True)
    model = Column(String(255), nullable=True)

    equipment_type = Column(String(100), nullable=True)
    equipment_sub_type = Column(String(100), nullable=True)

    # JOB STATUS
    status = Column(
        SAEnum(JobStatus, name="job_status_enum"),
        default=JobStatus.PENDING,
        nullable=False
    )

    error_message = Column(Text, nullable=True)

    matched_model = Column(String(255), nullable=True)

    match_type = Column(
        SAEnum(MatchType, name="match_type_enum"),
        nullable=True
    )

    selected_source_url = Column(Text, nullable=True)

    equipment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("equipment.id"),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    completed_at = Column(DateTime(timezone=True), nullable=True)

    # relationships
    equipment = relationship(
        "Equipment",
        back_populates="extraction_jobs"
    )

    sources = relationship(
        "EquipmentSource",
        back_populates="job",
        lazy="select"
    )

    match_logs = relationship(
        "MatchLog",
        back_populates="job",
        lazy="select"
    )

    extraction_log = relationship(
        "ExtractionLog",
        back_populates="job",
        uselist=False,
        lazy="select"
    )

    def __repr__(self):
        return f"<ExtractionJob {self.id} status={self.status}>"


# TABLE 5 : EQUIPMENT SOURCE
class EquipmentSource(Base):
    __tablename__ = "equipment_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("equipment_extraction_jobs.id"),
        nullable=False
    )

    url = Column(Text, nullable=False)

    domain = Column(String(255), nullable=True)

    trust_score = Column(Integer, nullable=True)

    is_selected = Column(Boolean, default=False, nullable=False)

    source_type = Column(String(20), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    job = relationship(
        "ExtractionJob",
        back_populates="sources"
    )

    def __repr__(self):
        return f"<EquipmentSource {self.domain} selected={self.is_selected}>"


# TABLE 6 : MATCH LOG
class MatchLog(Base):
    __tablename__ = "equipment_match_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("equipment_extraction_jobs.id"),
        nullable=False
    )

    input_model = Column(String(255), nullable=True)

    matched_model = Column(String(255), nullable=True)

    similarity_score = Column(Float, nullable=True)

    match_type = Column(
        SAEnum(MatchType, name="match_type_log_enum"),
        nullable=True
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    job = relationship(
        "ExtractionJob",
        back_populates="match_logs"
    )

    def __repr__(self):
        return (
            f"<MatchLog input={self.input_model} "
            f"matched={self.matched_model} "
            f"score={self.similarity_score}>"
        )


# TABLE 7 : EXTRACTION LOG
class ExtractionLog(Base):
    __tablename__ = "equipment_extraction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("equipment_extraction_jobs.id"),
        nullable=False,
        unique=True
    )

    raw_llm_response = Column(JSONB, nullable=True)

    validated_data = Column(JSONB, nullable=True)

    validation_status = Column(String(20), nullable=True)

    validation_errors = Column(JSONB, nullable=True, default=list)

    fields_extracted = Column(Integer, nullable=True)

    fields_expected = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    job = relationship(
        "ExtractionJob",
        back_populates="extraction_log"
    )

    def __repr__(self):
        return (
            f"<ExtractionLog job={self.job_id} "
            f"status={self.validation_status} "
            f"fields={self.fields_extracted}/{self.fields_expected}>"
        )