import os
import sqlite3
import uuid
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify, session, make_response
from werkzeug.utils import secure_filename
from datetime import datetime

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ADMIN_PASSWORD = '1145141919810'  # 请改为自己的管理员密码

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'nI3uD0dI2nG8fA4cY6iI0eE0lU2iF8iC1yD2jA9bG8nM7mM7uB7rP6iD8bO8kQ0pO7jP8eS5yD8kI2aA1gB7bF2mO5yO5vK3nM4aC5fU0sZ9iL4dL1oI5aK3hQ8rY1mT'  # 请改为自己的随机字符串

# ------------------ 数据库初始化 ------------------
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_ip TEXT,
            device_id TEXT,
            username TEXT,
            PRIMARY KEY (user_ip, device_id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            uploader_ip TEXT,
            uploader_device TEXT,
            upload_time TEXT,
            likes INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER,
            user_ip TEXT,
            user_device TEXT,
            username TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER,
            user_ip TEXT,
            user_device TEXT,
            username TEXT,
            comment TEXT,
            comment_time TEXT,
            parent_id INTEGER,
            likes INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_username():
    user_ip = request.remote_addr
    device_id = request.cookies.get('device_id')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT username FROM users WHERE user_ip=? AND device_id=?', (user_ip, device_id))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

# ------------------ 用户名设置 ------------------
@app.route('/set_username', methods=['POST'])
def set_username():
    username = request.form['username']
    user_ip = request.remote_addr
    device_id = request.cookies.get('device_id')
    if not device_id:
        device_id = str(uuid.uuid4())
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('REPLACE INTO users (user_ip, device_id, username) VALUES (?, ?, ?)', (user_ip, device_id, username))
    conn.commit()
    conn.close()
    resp = redirect(request.referrer or url_for('index'))
    resp.set_cookie('device_id', device_id, max_age=10*365*24*60*60)
    return resp

# ------------------ 管理员登录/登出 ------------------
@app.route('/admin_login', methods=['POST'])
def admin_login():
    password = request.form['admin_password']
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
    return redirect(request.referrer or url_for('index'))

@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

# ------------------ 首页 ------------------
@app.route('/')
def index():
    if 'device_id' not in request.cookies:
        device_id = str(uuid.uuid4())
        resp = make_response(redirect(url_for('index')))
        resp.set_cookie('device_id', device_id, max_age=10*365*24*60*60)
        return resp
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT * FROM images ORDER BY upload_time DESC')
    images = c.fetchall()
    conn.close()
    username = get_username()
    return render_template('index.html', images=images, username=username, is_admin=session.get('is_admin', False))

# ------------------ 上传图片 ------------------
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = datetime.now().strftime('%Y%m%d%H%M%S_') + secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            user_ip = request.remote_addr
            device_id = request.cookies.get('device_id')
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('INSERT INTO images (filename, uploader_ip, uploader_device, upload_time) VALUES (?, ?, ?, ?)',
                      (filename, user_ip, device_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))
    username = get_username()
    return render_template('upload.html', username=username)

# ------------------ 图片详情 ------------------
@app.route('/image/<int:image_id>')
def image_detail(image_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT * FROM images WHERE id=?', (image_id,))
    image = c.fetchone()
    c.execute('SELECT * FROM comments WHERE image_id=? ORDER BY comment_time ASC', (image_id,))
    comments = c.fetchall()
    conn.close()
    username = get_username()
    is_admin = session.get('is_admin', False)
    return render_template('image.html', image=image, comments=comments, username=username, is_admin=is_admin)

# ------------------ 下载图片 ------------------
@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# ------------------ 删除图片 ------------------
@app.route('/delete/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT filename, uploader_ip, uploader_device FROM images WHERE id=?', (image_id,))
    img = c.fetchone()
    if not img:
        conn.close()
        return jsonify({'success': False, 'message': '图片不存在'})
    user_ip = request.remote_addr
    user_device = request.cookies.get('device_id')
    is_admin = session.get('is_admin', False)
    if (img[1] == user_ip and img[2] == user_device) or is_admin:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], img[0]))
        except Exception:
            pass
        c.execute('DELETE FROM images WHERE id=?', (image_id,))
        c.execute('DELETE FROM likes WHERE image_id=?', (image_id,))
        c.execute('DELETE FROM comments WHERE image_id=?', (image_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    else:
        conn.close()
        return jsonify({'success': False, 'message': '无权限删除'})

# ------------------ 点赞 ------------------
@app.route('/like/<int:image_id>', methods=['POST'])
def like(image_id):
    user_ip = request.remote_addr
    device_id = request.cookies.get('device_id')
    username = get_username()
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT * FROM likes WHERE image_id=? AND user_ip=? AND user_device=?', (image_id, user_ip, device_id))
    if c.fetchone() is None:
        c.execute('INSERT INTO likes (image_id, user_ip, user_device, username) VALUES (?, ?, ?, ?)', (image_id, user_ip, device_id, username))
        c.execute('UPDATE images SET likes = likes + 1 WHERE id=?', (image_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    conn.close()
    return jsonify({'success': False, 'message': '您已经点过赞了'})

# ------------------ 点赞用户名单 ------------------
@app.route('/like_users/<int:image_id>')
def like_users(image_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT username FROM likes WHERE image_id=?', (image_id,))
    users = [row[0] or '匿名' for row in c.fetchall()]
    conn.close()
    return jsonify(users)

# ------------------ 评论 ------------------
@app.route('/comment/<int:image_id>', methods=['POST'])
def comment(image_id):
    user_ip = request.remote_addr
    device_id = request.cookies.get('device_id')
    username = get_username()
    comment_text = request.form['comment']
    parent_id = request.form.get('parent_id')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('INSERT INTO comments (image_id, user_ip, user_device, username, comment, comment_time, parent_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (image_id, user_ip, device_id, username, comment_text, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), parent_id))
    conn.commit()
    conn.close()
    return redirect(url_for('image_detail', image_id=image_id))

# ------------------ 评论点赞 ------------------
@app.route('/comment_like/<int:comment_id>', methods=['POST'])
def comment_like(comment_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE comments SET likes = likes + 1 WHERE id=?', (comment_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ------------------ 启动 ------------------
if __name__ == '__main__':
    if not os.path.exists('database.db'):
        init_db()
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(host='0.0.0.0', port=8000, debug=True)