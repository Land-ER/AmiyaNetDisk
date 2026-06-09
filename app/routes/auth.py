from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import db, User
from app.forms import LoginForm, RegisterForm
from app.passwords import check_user_password, generate_user_password_hash, is_sha256_hex
from app.utils import send_verification_code, verify_code, is_safe_redirect_url
from app.campus import (
    campus_verification_enabled,
    issue_campus_challenge,
    verify_campus_proofs,
    campus_session_verified,
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        password = form.password.data
        code = form.code.data.strip()

        if not is_sha256_hex(password):
            flash('密码安全处理失败，请刷新页面后重试', 'danger')
            return render_template('register.html', form=form)

        # 验证邮箱唯一性
        if User.query.filter_by(email=email).first():
            flash('该邮箱已注册', 'danger')
            return render_template('register.html', form=form)

        if campus_verification_enabled() and not campus_session_verified():
            flash('请先完成校园网验证', 'danger')
            return render_template('register.html', form=form)

        # 验证验证码
        if not verify_code(email, code):
            flash('验证码错误或已过期', 'danger')
            return render_template('register.html', form=form)

        # 创建用户
        user = User(
            email=email,
            password_hash=generate_user_password_hash(password),
            role='user',
            is_active=True,
            campus_verified_at=datetime.utcnow() if campus_verification_enabled() else None,
            campus_verify_method='campus_image' if campus_verification_enabled() else None,
        )
        db.session.add(user)
        db.session.commit()

        # 自动登录
        login_user(user)
        flash('注册成功，欢迎使用 AmiyaNetDisk！', 'success')
        return redirect(url_for('main.index'))

    return render_template('register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip()
        password = form.password.data

        if not is_sha256_hex(password):
            flash('密码安全处理失败，请刷新页面后重试', 'danger')
            return render_template('login.html', form=form)

        user = User.query.filter_by(email=email).first()
        if not user:
            flash('邮箱未注册', 'danger')
            return render_template('login.html', form=form)

        if not user.is_active:
            flash('账号已被禁用，请联系管理员', 'danger')
            return render_template('login.html', form=form)

        if check_user_password(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            flash('登录成功', 'success')
            if next_page and is_safe_redirect_url(next_page):
                return redirect(next_page)
            return redirect(url_for('main.index'))
        else:
            flash('密码错误', 'danger')

    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """用户登出"""
    logout_user()
    flash('已退出登录', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/send_code', methods=['POST'])
def send_code():
    """发送验证码（AJAX接口）"""
    data = request.get_json()
    if not data or 'email' not in data:
        return jsonify({'success': False, 'message': '请提供邮箱地址'}), 400

    email = data['email'].strip()
    purpose = data.get('purpose', 'register')
    if (purpose == 'register' and campus_verification_enabled() and
            not campus_session_verified()):
        return jsonify({'success': False, 'message': '请先完成校园网验证'}), 403

    success, message = send_verification_code(email)
    return jsonify({'success': success, 'message': message})


@auth_bp.route('/campus_verify/config')
def campus_verify_config():
    """获取校园网验证挑战"""
    if not campus_verification_enabled():
        return jsonify({'enabled': False, 'images': [], 'nonce': None})
    challenge = issue_campus_challenge()
    return jsonify({'enabled': True, **challenge})


@auth_bp.route('/campus_verify/check', methods=['POST'])
def campus_verify_check():
    """校验浏览器提交的校园网图片加载证明"""
    if not campus_verification_enabled():
        return jsonify({'success': True, 'message': '校园网验证未启用'})
    data = request.get_json() or {}
    success, message = verify_campus_proofs(data.get('proofs', []))
    status = 200 if success else 400
    return jsonify({'success': success, 'message': message}), status


@auth_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    """找回密码：通过邮箱验证码重置密码"""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        code = request.form.get('code', '').strip()
        password = request.form.get('password', '')

        if not email or not code or not password:
            flash('请填写所有字段', 'danger')
            return render_template('reset_password.html', email=email)

        if not is_sha256_hex(password):
            flash('密码安全处理失败，请刷新页面后重试', 'danger')
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
        user.password_hash = generate_user_password_hash(password)
        db.session.commit()

        flash('密码重置成功，请使用新密码登录', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')
