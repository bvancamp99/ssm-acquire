import jinja2
import os.path
import yaml

from ssm_acquire.config import asset_bucket


def _get_jinja2_plan(credentials, instance_id, j2_file):
    dirname = os.path.dirname(__file__)

    path = os.path.join(dirname, j2_file)

    template = None
    with open(path) as f:
        template = jinja2.Template(f.read())

    jinja2_plan = template.render(
        ssm_acquire_access_key=credentials['Credentials']['AccessKeyId'],
        ssm_acquire_secret_key=credentials['Credentials']['SecretAccessKey'],
        ssm_acquire_session_token=credentials['Credentials']['SessionToken'],
        ssm_acquire_s3_bucket=asset_bucket,
        ssm_acquire_instance_id=instance_id
    )

    return jinja2_plan


def get_transfer_plans(credentials, instance_id):
    j2_file = "transfer-plans/linpmem.yml.j2"

    transfer_plan = _get_jinja2_plan(credentials, instance_id, j2_file)

    return yaml.safe_load(transfer_plan)


def get_build_plans(credentials, instance_id):
    j2_file = "build-plans/linpmem.yml.j2"

    build_plan = _get_jinja2_plan(credentials, instance_id, j2_file)

    return yaml.safe_load(build_plan)


def get_interrogate_plans(credentials, instance_id):
    j2_file = "interrogate-plans/osquery.yml.j2"

    interrogate_plan = _get_jinja2_plan(credentials, instance_id, j2_file)

    return yaml.safe_load(interrogate_plan)