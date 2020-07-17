import logging
import yaml

from ssm_acquire.command import ensure_command
from ssm_acquire.jinja2_io import get_jinja2_plan


logger = logging.getLogger(__name__)


def _get_interrogate_plans(credentials, instance_id):
    """
    Loads the j2-formatted plans to interrogate the instance using OSQuery.
    """
    j2_file = "interrogate-plans/osquery.yml.j2"

    interrogate_plan = get_jinja2_plan(credentials, instance_id, j2_file)

    return yaml.safe_load(interrogate_plan)


def _get_interrogate_commands(credentials, instance_id):
    """
    TODO: Only supports amzn2 for now.  Add support for other distros.
    
    Gets commands to interrogate the instance using OSQuery.
    """
    return _get_interrogate_plans(
        credentials, 
        instance_id
    )['distros']['amzn2']['commands']


def _interrogate_instance_helper(ssm_client, instance_id, credentials):
    """
    Loads and runs the commands to interrogate the instance using OSQuery.
    """
    interrogate_commands = _get_interrogate_commands(credentials, instance_id)

    logger.info(
        'Attempting to interrogate the instance using the OSQuery binary for '
            'instance_id: {}'.format(instance_id)
    )

    ensure_command(ssm_client, interrogate_commands, instance_id)

    logger.info('Interrogate instance complete.')

    logger.info(
        'A .log has been added to the asset store for instance: {}'.format(
            instance_id
        )
    )


def interrogate_instance(ssm_client, instance_id, credentials):
    """
    Interrogates the specified EC2 instance using the OSQuery binary and 
    uploads the results to the asset bucket as a .log file.
    """
    print('Interrogate mode active.')

    _interrogate_instance_helper(ssm_client, instance_id, credentials)

    print('Interrogate completed successfully.')