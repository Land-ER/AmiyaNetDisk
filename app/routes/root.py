import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from app.models import db, User, OperationLog
from app.decorators import root_required

root_bp = Blueprint('root', __name__, template_folder='../templates/root')


@root_bp.route('/admins', methods=['GET', 'POST'])
@root_required
def manage_admins():
    """管理员管理"""
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id', type=int)
        email = request.form.get('email', '').strip()

        if action == 'promote':
            # 通过邮箱升级用户为管理员
            user = User.query.filter_by(email=email).first()
            if not user:
                flash('未找到该邮箱对应的用户', 'danger')
            elif user.is_admin():
                flash(f'用户 {email} 已经是管理员', 'warning')
            else:
                user.role = 'admin'
                log = OperationLog(
                    admin_id=current_user.id,
                    action='promote_admin',
                    target_id=user.id,
                    detail=json.dumps({'email': user.email}),
                )
                db.session.add(log)
                db.session.commit()
                flash(f'已将 {email} 提升为管理员', 'success')

        elif action == 'demote':
            # 撤销管理员
            user = db.session.get(User, user_id)
            if not user:
                flash('用户不存在', 'danger')
            elif user.is_root():
                flash('不能撤销 root 用户的管理员身份', 'danger')
            elif user.role != 'admin':
                flash('该用户不是管理员', 'warning')
            else:
                user.role = 'user'
                log = OperationLog(
                    admin_id=current_user.id,
                    action='demote_admin',
                    target_id=user.id,
                    detail=json.dumps({'email': user.email}),
                )
                db.session.add(log)
                db.session.commit()
                flash(f'已撤销 {user.email} 的管理员身份', 'success')

        return redirect(url_for('root.manage_admins'))

    # 获取所有管理员和 root
    admins = User.query.filter(User.role.in_(['admin', 'root'])).order_by(User.created_at.desc()).all()
    return render_template('root/manage_admins.html', admins=admins)
