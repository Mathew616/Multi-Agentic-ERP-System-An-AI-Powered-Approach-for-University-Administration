#!/usr/bin/env python
"""Check database users"""

import os
import sys

os.chdir(r'E:\Projects\MAJOR PROJECT\backend')
sys.path.insert(0, r'E:\Projects\MAJOR PROJECT\backend')

from flask import Flask
from flask_migrate import Migrate
from config import Config
from models import db, User

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    print("="*70)
    print("[USER DATABASE CHECK]")
    print("="*70)
    
    users = User.query.all()
    print(f"\nTotal users: {len(users)}\n")
    
    for user in users:
        print(f"Username: {user.username}")
        print(f"  Role: {user.role}")
        print(f"  Department: {user.department}")
        print(f"  Password hash: {user.password_hash[:20]}...")
        print(f"  Plain password: {user.plain_password}")
        print()
    
    # Check if IQC user exists
    iqc_user = User.query.filter_by(role='iqc').first()
    if iqc_user:
        print(f"✓ IQC user exists: {iqc_user.username}")
    else:
        print("✗ No IQC user found - creating one...")
        new_user = User(
            username='iqc_user',
            role='iqc',
            department='All'
        )
        new_user.set_password('iqc_password')
        db.session.add(new_user)
        db.session.commit()
        print(f"✓ Created IQC user: iqc_user / iqc_password")
