"""
认证相关表单
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from models.user import User


class LoginForm(FlaskForm):
    """登录表单"""
    username = StringField('用户名',
                          validators=[DataRequired(message='请输入用户名'),
                                    Length(min=3, max=50, message='用户名长度应在3-50个字符之间')])
    password = PasswordField('密码',
                            validators=[DataRequired(message='请输入密码')])
    remember = BooleanField('记住我')
    submit = SubmitField('登录')


class UserCreateForm(FlaskForm):
    """创建用户表单（管理员使用）"""
    username = StringField('用户名',
                          validators=[DataRequired(message='请输入用户名'),
                                    Length(min=3, max=50, message='用户名长度应在3-50个字符之间')])
    email = StringField('邮箱',
                       validators=[DataRequired(message='请输入邮箱'),
                                 Email(message='请输入有效的邮箱地址')])
    password = PasswordField('密码',
                            validators=[DataRequired(message='请输入密码'),
                                      Length(min=6, message='密码长度至少为6个字符')])
    password_confirm = PasswordField('确认密码',
                                    validators=[DataRequired(message='请确认密码'),
                                              EqualTo('password', message='两次密码输入不一致')])
    role = SelectField('角色',
                      choices=[('user', '普通用户'), ('admin', '管理员')],
                      validators=[DataRequired(message='请选择角色')])
    submit = SubmitField('创建用户')

    def validate_username(self, field):
        """验证用户名是否已存在"""
        if User.find_by_username(field.data):
            raise ValidationError('该用户名已被使用')

    def validate_email(self, field):
        """验证邮箱是否已存在"""
        if User.find_by_email(field.data):
            raise ValidationError('该邮箱已被注册')


class UserEditForm(FlaskForm):
    """编辑用户表单（管理员使用）"""
    email = StringField('邮箱',
                       validators=[DataRequired(message='请输入邮箱'),
                                 Email(message='请输入有效的邮箱地址')])
    role = SelectField('角色',
                      choices=[('user', '普通用户'), ('admin', '管理员')],
                      validators=[DataRequired(message='请选择角色')])
    is_active = BooleanField('账户激活状态')
    submit = SubmitField('保存修改')


class ChangePasswordForm(FlaskForm):
    """修改密码表单（用户自己使用）"""
    current_password = PasswordField('当前密码',
                                    validators=[DataRequired(message='请输入当前密码')])
    new_password = PasswordField('新密码',
                                validators=[DataRequired(message='请输入新密码'),
                                          Length(min=6, message='密码长度至少为6个字符')])
    password_confirm = PasswordField('确认新密码',
                                    validators=[DataRequired(message='请确认新密码'),
                                              EqualTo('new_password', message='两次密码输入不一致')])
    submit = SubmitField('修改密码')
