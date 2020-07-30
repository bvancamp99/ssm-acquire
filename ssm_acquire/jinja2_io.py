import jinja2
import os.path
import yaml

from ssm_acquire.config import asset_bucket

from ssm_acquire.command import SSMClient


def _get_path(j2_file):
    """
    Gets the path of the j2 file.
    """
    dirname = os.path.dirname(__file__)

    path = os.path.join(dirname, j2_file)

    return path


def _get_j2_template(path):
    """
    With the jinja2 module, load a template from the j2 file given its path.
    """
    template = None
    with open(path) as f:
        template = jinja2.Template(f.read())
    
    return template


def _create_jinja2_plan_with_template(template, ssm_client: SSMClient):
    """
    Creates a jinja2 plan using the provided template, filling in the 
    appropriate credentials and EC2 instance id.
    """
    creds = ssm_client.credentials

    return template.render(
        ssm_acquire_access_key=creds['Credentials']['AccessKeyId'],
        ssm_acquire_secret_key=creds['Credentials']['SecretAccessKey'],
        ssm_acquire_session_token=creds['Credentials']['SessionToken'],
        ssm_acquire_s3_bucket=asset_bucket,
        ssm_acquire_instance_id=ssm_client.instance_id
    )


def _get_jinja2_plan_from_path(path, ssm_client: SSMClient):
    """
    Given a path to a j2-formatted file, loads a jinja2 template from the 
    file.
    
    Then, creates a plan using the template, filling in the appropriate 
    credentials and EC2 instance id.
    """
    template = _get_j2_template(path)

    return _create_jinja2_plan_with_template(template, ssm_client)


def get_jinja2_plan(ssm_client: SSMClient, j2_file):
    """
    Loads the j2-formatted plans to perform actions on the EC2 instance.
    """
    path = _get_path(j2_file)

    jinja2_plan = _get_jinja2_plan_from_path(path, ssm_client)

    return jinja2_plan