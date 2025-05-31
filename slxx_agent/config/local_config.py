import os
import yaml


class LocalConfig:
    def __init__(self, app_dir):
        self.app_dir = app_dir

        config_path = os.path.join(app_dir, 'agent_config.yaml')

        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            self.base_endpoint = config['slxx']['base_endpoint']



