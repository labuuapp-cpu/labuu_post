from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON
from sqlalchemy.sql import func
from database import Base


class BrandConfig(Base):
    __tablename__ = "brand_config"
    id = Column(Integer, primary_key=True)
    audience = Column(String, default="ambos")
    tone = Column(String, default="informal natural")
    themes = Column(JSON, default=list)
    weekly_frequency = Column(Integer, default=7)
    update_hour_1 = Column(Integer, default=8)
    update_hour_2 = Column(Integer, default=15)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DailyContent(Base):
    __tablename__ = "daily_content"
    id = Column(Integer, primary_key=True)
    date = Column(String, nullable=False)
    slot = Column(String, nullable=False)  # "morning" | "afternoon"
    video_idea = Column(Text)
    hook = Column(Text)
    script = Column(Text)
    image_prompt = Column(Text)
    image_recommendation = Column(Text)
    video_prompt = Column(Text)
    organic_tasks = Column(JSON)
    engagement_posts = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    caption = Column(Text)
    hashtags = Column(Text)
    file_path = Column(String)
    file_type = Column(String)  # "video" | "image"
    platforms = Column(JSON)  # ["instagram", "facebook", "tiktok"]
    scheduled_at = Column(DateTime)
    status = Column(String, default="pending")  # pending | posted | failed
    post_ids = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())


class PostMetrics(Base):
    __tablename__ = "post_metrics"
    id = Column(Integer, primary_key=True)
    scheduled_post_id = Column(Integer)
    platform = Column(String)
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    reach = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    collected_at = Column(DateTime, server_default=func.now())


class LearnedPattern(Base):
    __tablename__ = "learned_patterns"
    id = Column(Integer, primary_key=True)
    pattern_type = Column(String)  # hook_style | format | duration | theme | posting_hour
    pattern_value = Column(String)
    avg_engagement = Column(Float, default=0.0)
    sample_count = Column(Integer, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BrandImage(Base):
    __tablename__ = "brand_images"
    id = Column(Integer, primary_key=True)
    filename = Column(String)
    file_path = Column(String)
    description = Column(Text)
    tags = Column(JSON, default=list)
    uploaded_at = Column(DateTime, server_default=func.now())
