import dqmsquare_cfg
from server import create_app

cfg = dqmsquare_cfg.load_cfg()
flask_app = create_app(cfg)
