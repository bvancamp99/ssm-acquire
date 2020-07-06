import everett.ext.inifile
import everett.manager
import jinja2
import os.path
import yaml
"""
from everett.ext.inifile import ConfigIniEnv
from everett.manager import ConfigManager
from everett.manager import ConfigOSEnv
"""
#from jinja2 import Template


dirname = os.path.dirname(__file__)

config = get_config()

s3_bucket = config('asset_bucket', namespace='ssm_acquire')


def get_config():
    ini_config = everett.ext.inifile.ConfigIniEnv([
        os.environ.get('THREATRESPONSE_INI'),
        '~/.threatresponse.ini',
        '/etc/threatresponse.ini'
    ])

    return everett.manager.ConfigManager([
        ini_config, 
        everett.manager.ConfigOSEnv()
    ])


def load_acquire():
    this_path = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(this_path, "acquire-plans/linpmem.yml")

    return yaml.safe_load(open(path))


# TODO: use in below methods
def get_jinja2_plan(credentials, instance_id, j2_file):
    path = os.path.join(dirname, j2_file)

    template = None
    with open(path) as f:
        template = jinja2.Template(f.read())

    jinja2_plan = template.render(
        ssm_acquire_access_key=credentials['Credentials']['AccessKeyId'],
        ssm_acquire_secret_key=credentials['Credentials']['SecretAccessKey'],
        ssm_acquire_session_token=credentials['Credentials']['SessionToken'],
        ssm_acquire_s3_bucket=s3_bucket,
        ssm_acquire_instance_id=instance_id
    )

    return jinja2_plan


def load_transfer(credentials, instance_id):
    this_path = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(this_path, "transfer-plans/linpmem.yml.j2")
    config = get_config()

    fh = open(path)
    template_contents = fh.read()
    fh.close()
    s3_bucket = config('asset_bucket', namespace='ssm_acquire')
    jinja_template = jinja2.Template(template_contents)
    transfer_plan = jinja_template.render(
        ssm_acquire_access_key=credentials['Credentials']['AccessKeyId'],
        ssm_acquire_secret_key=credentials['Credentials']['SecretAccessKey'],
        ssm_acquire_session_token=credentials['Credentials']['SessionToken'],
        ssm_acquire_s3_bucket=s3_bucket,
        ssm_acquire_instance_id=instance_id

    )
    return yaml.safe_load(transfer_plan)


def load_build(credentials, instance_id):
    this_path = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(this_path, "build-plans/linpmem.yml.j2")
    config = get_config()

    fh = open(path)
    template_contents = fh.read()
    fh.close()
    s3_bucket = config('asset_bucket', namespace='ssm_acquire')
    jinja_template = jinja2.Template(template_contents)
    build_plan = jinja_template.render(
        ssm_acquire_access_key=credentials['Credentials']['AccessKeyId'],
        ssm_acquire_secret_key=credentials['Credentials']['SecretAccessKey'],
        ssm_acquire_session_token=credentials['Credentials']['SessionToken'],
        ssm_acquire_s3_bucket=s3_bucket,
        ssm_acquire_instance_id=instance_id

    )
    return yaml.safe_load(build_plan)


def load_interrogate(credentials, instance_id):
    this_path = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(this_path, "interrogate-plans/osquery.yml.j2")
    config = get_config()

    fh = open(path)
    template_contents = fh.read()
    fh.close()
    s3_bucket = config('asset_bucket', namespace='ssm_acquire')
    jinja_template = jinja2.Template(template_contents)
    interrogate_plan = jinja_template.render(
        ssm_acquire_access_key=credentials['Credentials']['AccessKeyId'],
        ssm_acquire_secret_key=credentials['Credentials']['SecretAccessKey'],
        ssm_acquire_session_token=credentials['Credentials']['SessionToken'],
        ssm_acquire_s3_bucket=s3_bucket,
        ssm_acquire_instance_id=instance_id

    )
    return yaml.safe_load(interrogate_plan)


def load_policy():
    this_path = os.path.abspath(os.path.dirname(__file__))
    path = os.path.join(this_path, "policies/instance-scoped-policy.yml")
    return yaml.safe_load(open(path))