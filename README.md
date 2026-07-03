# Metro Apteka - README

Bu loyiha Metro Apteka uchun minimal demo ilovadir. UI va xabarlar O'zbek tilida.

Quick start (local):

1. Klonlab oling:
   git clone https://github.com/wwwkarvonsaroyuz0-droid/apteka-system.git
   cd apteka-system

2. Virtual environment o'rnating (python 3.8+):
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   venv\Scripts\activate    # Windows

3. O'rnating:
   pip install -r requirements.txt

4. Ishga tushuring (dev):
   export FLASK_APP=app.py
   flask run
   yoki
   python app.py

5. Demo credentiallar (seed):
   superadmin: admin / admin123
   korxona foydalanuvchilari: metro1 / pass123 , metro2 / pass123

6. Lokal test rejimi uchun foydalaning va credentiallarni o'zgartiring.

Eslatma: ishlab chiqarishdan oldin parollarni o'zgartiring va DATABASE_URL o'rnating.
