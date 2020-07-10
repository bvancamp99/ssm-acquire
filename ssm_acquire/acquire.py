import os.path
import yaml


def _get_acquire_plans():
    dirname = os.path.dirname(__file__)

    path = os.path.join(dirname, "acquire-plans/linpmem.yml")

    return yaml.safe_load(open(path))


acquire_plans = _get_acquire_plans()