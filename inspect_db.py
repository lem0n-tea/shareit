"""Quick utility: dump every row in the files table so we can eyeball the data.
Run from the project root with the venv active:  python inspect_db.py
"""
from app import models
from app.database import SessionLocal

db = SessionLocal()
try:
    files = db.query(models.File).all()
    if not files:
        print("(no rows in files table)")
    for f in files:
        print(
            {
                "id": f.id,
                "name": f.name,
                "extension": f.extension,
                "content_type": f.content_type,
                "size": f.size,
                "uploaded_at": f.uploaded_at,
                "path": f.path,
            }
        )
finally:
    db.close()
