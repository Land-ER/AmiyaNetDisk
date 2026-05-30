from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db, User
from app.forms import LoginForm, RegisterForm
from app.utils import send_verification_code, verify_code

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    if current_user.is_authenticated:
        return redirect(url_for('main.search'))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        password = form.password.data  # 前端已做 SHA-256
        code = form.code.data.strip()

        # 验证邮箱唯一性
        if User.query.filter_by(email=email).first():
            flash('该邮箱已注册', 'danger')
            return render_template('register.html', form=form)

        # 验证验证码
        if not verify_code(email, code):
            flash('验证码错误或已过期', 'danger')
            return render_template('register.html', form=form)

        # 创建用户
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            role='user',
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        # 自动登录
        login_user(user)
        flash('注册成功，欢迎使用 AmiyaNetDisk！', 'success')
        return redirect(url_for('main.search'))

    return render_template('register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if current_user.is_authenticated:
        return redirect(url_for('main.search'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        password = form.password.data  # 前端已做 SHA-256

        user = User.query.filter_by(email=email).first()
        if not user:
            flash('邮箱未注册', 'danger')
            return render_template('login.html', form=form)

        if not user.is_active:
            flash('账号已被禁用，请联系管理员', 'danger')
            return render_template('login.html', form=form)

        if check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            flash('登录成功', 'success')
            return redirect(next_page or url_for('main.search'))
        else:
            flash('密码错误', 'danger')

    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """用户登出"""
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('main.search'))


@auth_bp.route('/send_code', methods=['POST'])
def send_code():
    """发送验证码（AJAX接口）"""
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'success': False, 'message': '请提供邮箱地址'}), 400

    email = data['email'].strip()
    success, message = send_verification_code(email)
    return jsonify({'success': success, 'message': message})


@auth_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    """找回密码：通过邮箱验证码重置密码"""
    if current_user.is_authenticated:
        return redirect(url_for('main.search'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        code = request.form.get('code', '').strip()
        password = request.form.get('password', '')  # 前端已做 SHA-256

        if not email or not code or not password:
            flash('请填写所有字段', 'danger')
            return render_template('reset_password.html', email=email)

        # 验证邮箱存在
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('该邮箱未注册', 'danger')
            return render_template('reset_password.html', email=email)

        # 验证验证码
        if not verify_code(email, code):
            flash('验证码错误或已过期', 'danger')
            return render_template('reset_password.html', email=email)

        # 更新密码
        user.password_hash = generate_password_hash(password)
        db.session.commit()

        flash('密码重置成功，请使用新密码登录', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')
