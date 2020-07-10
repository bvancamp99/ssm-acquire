import logging

from ssm_acquire.credential import StsManager
from ssm_acquire.policy import get_json_policy


logger = logging.getLogger(__name__)


def get_credentials(region, instance_id):
    """Obtains the credentials required to run commands on the EC2 
    instance."""

    json_policy = get_json_policy(region, instance_id)

    logger.info(
        'Limited scope role generated for assumeRole: {}'.format(
            json_policy
        )
    )

    logger.debug('Generating limited scoped policy for instance-id to be '
        'used in all operations: {}'.format(json_policy))
    
    sts_manager = StsManager(
        region_name=region, 
        limited_scope_policy=json_policy
    )

    credentials = sts_manager.auth()

    return credentials