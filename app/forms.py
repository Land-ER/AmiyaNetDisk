from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FileField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional


class LoginForm(FlaskForm):
    email = StringField('邮箱', validators=[DataRequired(), Email(check_deliverability=False)])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6, max=128)])
    submit = SubmitField('登录')


class RegisterForm(FlaskForm):
    email = StringField('邮箱', validators=[DataRequired(), Email(check_deliverability=False)])
    password = PasswordField('密码', validators=[DataRequired(), Length(min=6, max=128)])
    code = StringField('验证码', validators=[DataRequired(), Length(min=6, max=6)])
    submit = SubmitField('注册')


class UploadForm(FlaskForm):
    file = FileField('选择文件', validators=[DataRequired()])
    title = StringField('文件标题', validators=[DataRequired(), Length(max=200)])
    search_tags = StringField('检索标签', validators=[Optional(), Length(max=500)])
    display_tags = StringField('展示标签', validators=[Optional(), Length(max=500)])
    submit = SubmitField('上传')


class FileEditForm(FlaskForm):
    title = StringField('文件标题', validators=[DataRequired(), Length(max=200)])
    search_tags = StringField('检索标签', validators=[Optional(), Length(max=500)])
    display_tags = StringField('展示标签', validators=[Optional(), Length(max=500)])
    submit = SubmitField('保存')
