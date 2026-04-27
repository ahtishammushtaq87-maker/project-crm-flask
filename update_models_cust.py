import os

path = 'app/models.py'
with open(path, 'r') as f:
    content = f.read()

# 1. Define CustomerGroup model
customer_group_model = """
class CustomerGroup(db.Model):
    \"\"\"Customer Group model\"\"\"
    __tablename__ = 'customer_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customers = db.relationship('Customer', backref='group', lazy=True)
    
    def __repr__(self):
        return f'<CustomerGroup {self.name}>'
"""

# Insert CustomerGroup before Customer
if 'class CustomerGroup' not in content:
    content = content.replace('class Customer(db.Model):', customer_group_model + '\nclass Customer(db.Model):')

# 2. Update Customer model fields
# I'll add them after pan_number or contact_person
if 'company_name =' not in content:
    content = content.replace('contact_person = db.Column(db.String(100))', 
                               'contact_person = db.Column(db.String(100))\n    company_name = db.Column(db.String(150), index=True)\n    group_id = db.Column(db.Integer, db.ForeignKey(\'customer_groups.id\'), nullable=True, index=True)')

with open(path, 'w') as f:
    f.write(content)

print("Successfully updated app/models.py")
