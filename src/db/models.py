"""
SQLAlchemy models and JSON helpers for Job Intelligence Agent.
"""

import json
import logging

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

log = logging.getLogger(__name__)

DB_PATH = "data/jobs.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def json_serialize(data) -> str:
    """Serializa un objeto Python a JSON string para almacenar en TEXT."""
    if data is None:
        return json.dumps(None)
    return json.dumps(data, ensure_ascii=False)


def json_deserialize(text: str):
    """Deserializa un JSON string desde TEXT a objeto Python."""
    if text is None or text == "":
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log.error("Error deserializando JSON: %s | texto: %.100s", e, text)
        return None


class CandidateProfile(Base):
    __tablename__ = "candidate_profile"

    id = Column(Integer, primary_key=True)
    version = Column(String, default="1.0")
    created_at = Column(DateTime, default=func.datetime("now"))
    is_active = Column(Integer, default=1)
    full_name = Column(String)
    location_current = Column(String)
    skills_technical = Column(Text)
    education = Column(Text)
    experience = Column(Text)
    languages = Column(Text)
    projects = Column(Text)
    employment_gap_years = Column(Float)
    salary_min_viable = Column(Float)
    salary_notes = Column(Text)
    location_preference = Column(String)
    relocation_conditions = Column(String)
    work_mode_preference = Column(String)
    personal_concerns = Column(Text)
    environment_avoid_keywords = Column(Text)
    environment_prefer_keywords = Column(Text)
    min_score_to_recommend = Column(Integer, default=45)
    cv_version_id = Column(Integer)

    @property
    def skills_technical_parsed(self):
        return json_deserialize(self.skills_technical)

    @skills_technical_parsed.setter
    def skills_technical_parsed(self, value):
        self.skills_technical = json_serialize(value)

    @property
    def education_parsed(self):
        return json_deserialize(self.education)

    @education_parsed.setter
    def education_parsed(self, value):
        self.education = json_serialize(value)

    @property
    def experience_parsed(self):
        return json_deserialize(self.experience)

    @experience_parsed.setter
    def experience_parsed(self, value):
        self.experience = json_serialize(value)

    @property
    def languages_parsed(self):
        return json_deserialize(self.languages)

    @languages_parsed.setter
    def languages_parsed(self, value):
        self.languages = json_serialize(value)

    @property
    def projects_parsed(self):
        return json_deserialize(self.projects)

    @projects_parsed.setter
    def projects_parsed(self, value):
        self.projects = json_serialize(value)

    @property
    def environment_avoid_keywords_parsed(self):
        return json_deserialize(self.environment_avoid_keywords)

    @environment_avoid_keywords_parsed.setter
    def environment_avoid_keywords_parsed(self, value):
        self.environment_avoid_keywords = json_serialize(value)

    @property
    def environment_prefer_keywords_parsed(self):
        return json_deserialize(self.environment_prefer_keywords)

    @environment_prefer_keywords_parsed.setter
    def environment_prefer_keywords_parsed(self, value):
        self.environment_prefer_keywords = json_serialize(value)


def save_candidate_profile(profile: dict, version: str = "1.0") -> CandidateProfile:
    """
    Guarda (upsert) el perfil en candidate_profile.
    Desactiva perfiles anteriores antes de insertar el nuevo.
    """
    with SessionLocal() as session:
        session.query(CandidateProfile).filter(CandidateProfile.is_active == 1).update(
            {"is_active": 0}
        )
        session.commit()

        skills = normalize_skills_for_db(profile.get("skills_technical", []))

        record = CandidateProfile(
            version=version,
            full_name=profile.get("full_name"),
            location_current=profile.get("location_current"),
            skills_technical=json_serialize(skills),
            education=json_serialize(profile.get("education", [])),
            experience=json_serialize(profile.get("experience", [])),
            languages=json_serialize(profile.get("languages", [])),
            projects=json_serialize(profile.get("projects", [])),
            employment_gap_years=profile.get("employment_gap_years"),
            salary_min_viable=profile.get("salary_min_viable"),
            salary_notes=profile.get("salary_notes"),
            location_preference=profile.get("location_preference"),
            relocation_conditions=profile.get("relocation_conditions"),
            work_mode_preference=profile.get("work_mode_preference"),
            personal_concerns=profile.get("personal_concerns"),
            environment_avoid_keywords=json_serialize(
                profile.get("environment_avoid_keywords", [])
            ),
            environment_prefer_keywords=json_serialize(
                profile.get("environment_prefer_keywords", [])
            ),
            min_score_to_recommend=profile.get("min_score_to_recommend", 45),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        log.info("Perfil guardado en DB (id=%d, version=%s)", record.id, version)
        return record


def normalize_skills_for_db(skills: list) -> list:
    """Convierte skills a lista plana de strings para JSON."""
    result: list = []
    for item in skills:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            for skill_name, level in item.items():
                result.append(f"{skill_name}: {level}" if level else skill_name)
    return result


def get_active_candidate_profile() -> CandidateProfile | None:
    """Recupera el perfil activo desde la base de datos."""
    with SessionLocal() as session:
        stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.is_active == 1)
            .order_by(CandidateProfile.created_at.desc())
            .limit(1)
        )
        return session.scalar(stmt)
