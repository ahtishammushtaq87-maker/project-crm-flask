"""Universal Saved Filter model for Query Builder"""
from datetime import datetime
from app import db


class SavedFilter(db.Model):
    """Generic saved filter that works across any module"""
    __tablename__ = 'saved_filters'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50), nullable=False, index=True)
    rules = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'module': self.module,
            'rules': self.rules,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<SavedFilter {self.name} ({self.module})>'

