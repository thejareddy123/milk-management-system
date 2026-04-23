from flask import Flask
from config import Config
from extensions import mysql, mail, bcrypt

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    #extensions
    mysql.init_app(app)
    mail.init_app(app)
    bcrypt.init_app(app)
    
    #Register the blueprints
    from routes.auth_routes import auth_bp
    from routes.admin_routes import admin_bp
    from routes.supplier_routes import supplier_bp
    from routes.provider_routes import provider_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(supplier_bp)
    app.register_blueprint(provider_bp)
    
    # Create admin on first run
    with app.app_context():
        try:
            create_default_admin(app)
        except Exception as e:
            print(f"Note: Could not create admin (DB may not be ready): {e}")
    
    return app

def create_default_admin(app):
    from extensions import mysql as db, bcrypt as bc
    cur = db.connection.cursor()
    
    cur.execute("SELECT id FROM admins WHERE email=%s", (app.config['ADMIN_EMAIL'],))
    existing = cur.fetchone()
    
    if existing:
        print("Admin already exists ")
        cur.close()
        return   

    print("Creating admin... ")

    hashed = bc.generate_password_hash(app.config['ADMIN_PASSWORD']).decode('utf-8')

    cur.execute(
        "INSERT INTO admins (name, email, password) VALUES (%s,%s,%s)",
        ('Admin', app.config['ADMIN_EMAIL'], hashed)
    )
    db.connection.commit()
    
    print(f"Default admin created: {app.config['ADMIN_EMAIL']} ")
    cur.close()

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)