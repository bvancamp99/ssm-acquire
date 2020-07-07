import everett.ext.inifile
import everett.manager
import jinja2
import os.path
import yaml


dirname = os.path.dirname(__file__)


def _init_config():
    config_file = everett.ext.inifile.ConfigIniEnv([
        os.environ.get('THREATRESPONSE_INI'),
        '~/.threatresponse.ini',
        '/etc/threatresponse.ini'
    ])

    return everett.manager.ConfigManager([
        config_file, 
        everett.manager.ConfigOSEnv()
    ])


config = _init_config()

# will throw ConfigurationMissingError later in the chain if 
# .threatresponse.ini can't be found
s3_bucket = config('asset_bucket', namespace='ssm_acquire')


def _init_policy():
    path = os.path.join(dirname, "policies/instance-scoped-policy.yml")

    return yaml.safe_load(open(path))


policy = _init_policy()


def _init_acquire():
    path = os.path.join(dirname, "acquire-plans/linpmem.yml")

    return yaml.safe_load(open(path))


acquire_plans = _init_acquire()


def _get_jinja2_plan(credentials, instance_id, j2_file):
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
    j2_file = "transfer-plans/linpmem.yml.j2"

    transfer_plan = _get_jinja2_plan(credentials, instance_id, j2_file)

    return yaml.safe_load(transfer_plan)


def load_build(credentials, instance_id):
    j2_file = "build-plans/linpmem.yml.j2"

    build_plan = _get_jinja2_plan(credentials, instance_id, j2_file)

    return yaml.safe_load(build_plan)


def load_interrogate(credentials, instance_id):
    j2_file = "interrogate-plans/osquery.yml.j2"

    interrogate_plan = _get_jinja2_plan(credentials, instance_id, j2_file)

    return yaml.safe_load(interrogate_plan)