import sys

sys.path.insert(0, '/home/moghadda/git/bcbio-nextgen/bcbio/pipeline')

from config_utils import *


config = load_config('/home/moghadda/git/bcbio-nextgen/config/examples/NA12878-ensemble.yaml')
print config
# config_utils.load_config('/home/moghadda/git/bcbio-nextgen/config/examples/NA12878-ensemble.yaml')
# print cfg.load_config('/home/moghadda/git/bcbio-nextgen/config/examples/NA12878-ensemble.yaml')
