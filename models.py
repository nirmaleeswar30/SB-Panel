from datetime import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relations
    containers = db.relationship('Container', backref='user', lazy=True)
    websites = db.relationship('Website', backref='user', lazy=True)
    databases = db.relationship('Database', backref='user', lazy=True)
    cronjobs = db.relationship('CronJob', backref='user', lazy=True)
    
    # Resource limits
    cpu_limit = db.Column(db.Integer, default=1)  # Number of CPU cores
    memory_limit = db.Column(db.Integer, default=1024)  # Memory limit in MB
    disk_limit = db.Column(db.Integer, default=10240)  # Disk limit in MB
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Container(db.Model):
    __tablename__ = 'containers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    container_id = db.Column(db.String(64), unique=True, nullable=False)
    template = db.Column(db.String(64), nullable=False)  # nginx, apache, etc.
    status = db.Column(db.String(20), default='stopped')  # running, stopped, error
    ip_address = db.Column(db.String(15))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Resources allocated
    cpu_allocated = db.Column(db.Integer, default=1)
    memory_allocated = db.Column(db.Integer, default=1024)  # MB
    disk_allocated = db.Column(db.Integer, default=10240)  # MB
    
    # Relations
    services = db.relationship('Service', backref='container', lazy=True)
    
    def __repr__(self):
        return f'<Container {self.name}>'

class Website(db.Model):
    __tablename__ = 'websites'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    container_id = db.Column(db.Integer, db.ForeignKey('containers.id'), nullable=False)
    domain = db.Column(db.String(255), nullable=False)
    server_type = db.Column(db.String(20), nullable=False)  # nginx, apache
    php_version = db.Column(db.String(10))  # 5.6, 7.4, 8.0, etc.
    document_root = db.Column(db.String(255), default='/var/www/html')
    ssl_enabled = db.Column(db.Boolean, default=False)
    ssl_expires = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Website {self.domain}>'

class Database(db.Model):
    __tablename__ = 'databases'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    container_id = db.Column(db.Integer, db.ForeignKey('containers.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    db_type = db.Column(db.String(20), default='mysql')  # mysql, mariadb
    db_user = db.Column(db.String(64), nullable=False)
    db_password = db.Column(db.String(256), nullable=False)
    remote_access = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Database {self.name}>'

class Service(db.Model):
    __tablename__ = 'services'
    
    id = db.Column(db.Integer, primary_key=True)
    container_id = db.Column(db.Integer, db.ForeignKey('containers.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)  # nginx, apache, mysql, etc.
    service_type = db.Column(db.String(20), nullable=False)  # web, database, cache, etc.
    status = db.Column(db.String(20), default='stopped')  # running, stopped, error
    auto_start = db.Column(db.Boolean, default=True)
    port = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Service {self.name}>'

class CronJob(db.Model):
    __tablename__ = 'cronjobs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    container_id = db.Column(db.Integer, db.ForeignKey('containers.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    command = db.Column(db.Text, nullable=False)
    schedule = db.Column(db.String(100), nullable=False)  # cron expression
    active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    next_run = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<CronJob {self.name}>'

class SSHKey(db.Model):
    __tablename__ = 'ssh_keys'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    public_key = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SSHKey {self.name}>'

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ActivityLog {self.action}>'

class DNSRecord(db.Model):
    __tablename__ = 'dns_records'
    
    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id'), nullable=False)
    record_type = db.Column(db.String(10), nullable=False)  # A, CNAME, MX, TXT, etc.
    name = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text, nullable=False)
    ttl = db.Column(db.Integer, default=3600)
    priority = db.Column(db.Integer)  # For MX records
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    website = db.relationship('Website', backref='dns_records')
    
    def __repr__(self):
        return f'<DNSRecord {self.record_type} {self.name}>'

class Favorite(db.Model):
    __tablename__ = 'favorites'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    page_url = db.Column(db.String(255), nullable=False)
    page_name = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Favorite {self.page_name}>'

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.Text)
    
    def __repr__(self):
        return f'<SystemSetting {self.key}>'
