import logging
import yaml

#from ssm_acquire.command import ensure_command
from ssm_acquire.jinja2_io import get_jinja2_plan


logger = logging.getLogger(__name__)


def _get_build_plans(credentials, instance_id):
    """
    Loads the j2-formatted plans to build a rekall profile for the instance.
    """
    j2_file = "build-plans/linpmem.yml.j2"

    build_plan = get_jinja2_plan(credentials, instance_id, j2_file)

    return yaml.safe_load(build_plan)


def _get_build_commands(credentials, instance_id):
    """
    TODO: Only supports amzn2 for now.  Add support for other distros.
    
    Gets commands to build a rekall profile for the instance.
    """
    return _get_build_plans(
        credentials, 
        instance_id
    )['distros']['amzn2']['commands']


def _build_profile_helper(ssm_client, instance_id, credentials):
    """
    Loads and runs the commands to build a rekall profile for the instance.
    """
    build_commands = _get_build_commands(credentials, instance_id)

    logger.info('Attempting to build a rekall profile for instance: {}.'\
        .format(instance_id))
    
    ensure_command(ssm_client, build_commands, instance_id)

    logger.info('Rekall profile build complete.')

    logger.info(
        'A .zip has been added to the asset store for instance: {}'.format(
            instance_id
        )
    )


def build_profile(ssm_client, instance_id, credentials):
    """
    Builds a rekall profile for the specified EC2 instance and uploads it to 
    the asset bucket as a .zip file.
    """
    print('Build mode active.')

    _build_profile_helper(ssm_client, instance_id, credentials)

    print('Build completed successfully.')