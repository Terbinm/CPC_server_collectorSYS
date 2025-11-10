"""
配置管理相关表单
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional


class ConfigForm(FlaskForm):
    """分析配置表单"""
    analysis_method_id = StringField('分析方法 ID',
                                     validators=[DataRequired(message='请输入分析方法 ID'),
                                               Length(max=100)])
    config_name = StringField('配置名称',
                             validators=[DataRequired(message='请输入配置名称'),
                                       Length(max=200)])
    description = TextAreaField('描述',
                               validators=[Optional(),
                                         Length(max=500)])
    parameters = TextAreaField('参数 (JSON 格式)',
                              validators=[Optional()],
                              render_kw={'rows': 10, 'placeholder': '请输入 JSON 格式的参数配置'})
    enabled = BooleanField('启用', default=True)
    submit = SubmitField('保存')


class ModelUploadForm(FlaskForm):
    """模型文件上传表单"""
    file = FileField('模型文件',
                    validators=[
                        DataRequired(message='请选择文件'),
                        FileAllowed(['pkl', 'pth', 'h5', 'onnx', 'pb'],
                                  message='只支持 .pkl, .pth, .h5, .onnx, .pb 格式的文件')
                    ])
    config_id = HiddenField('配置 ID')
    submit = SubmitField('上传')


class RoutingRuleForm(FlaskForm):
    """路由规则表单"""
    rule_name = StringField('规则名称',
                           validators=[DataRequired(message='请输入规则名称'),
                                     Length(max=200)])
    description = TextAreaField('描述',
                               validators=[Optional(),
                                         Length(max=500)])
    priority = StringField('优先级',
                          validators=[DataRequired(message='请输入优先级')],
                          render_kw={'type': 'number', 'min': '0', 'value': '0'})
    conditions = TextAreaField('匹配条件 (JSON 格式)',
                              validators=[DataRequired(message='请输入匹配条件')],
                              render_kw={'rows': 8, 'placeholder': '请输入 JSON 格式的匹配条件'})
    actions = TextAreaField('操作 (JSON 格式)',
                           validators=[DataRequired(message='请输入操作配置')],
                           render_kw={'rows': 8, 'placeholder': '请输入 JSON 格式的操作配置'})
    enabled = BooleanField('启用', default=True)
    submit = SubmitField('保存')


class MongoDBInstanceForm(FlaskForm):
    """MongoDB 实例表单"""
    instance_name = StringField('实例名称',
                               validators=[DataRequired(message='请输入实例名称'),
                                         Length(max=200)])
    description = TextAreaField('描述',
                               validators=[Optional(),
                                         Length(max=500)])
    host = StringField('主机地址',
                      validators=[DataRequired(message='请输入主机地址'),
                                Length(max=100)])
    port = StringField('端口',
                      validators=[DataRequired(message='请输入端口')],
                      render_kw={'type': 'number', 'min': '1', 'max': '65535', 'value': '27017'})
    username = StringField('用户名',
                          validators=[DataRequired(message='请输入用户名'),
                                    Length(max=100)])
    password = StringField('密码',
                          validators=[DataRequired(message='请输入密码'),
                                    Length(max=200)],
                          render_kw={'type': 'password'})
    database = StringField('数据库名',
                          validators=[DataRequired(message='请输入数据库名'),
                                    Length(max=100)])
    collection = StringField('集合名',
                            validators=[Optional(),
                                      Length(max=100)],
                            render_kw={'value': 'recordings'})
    auth_source = StringField('认证数据库',
                             validators=[Optional(),
                                       Length(max=100)],
                             render_kw={'value': 'admin'})
    enabled = BooleanField('启用', default=True)
    submit = SubmitField('保存')
