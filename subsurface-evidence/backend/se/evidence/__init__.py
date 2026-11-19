"""Registry of evidence layers, in the order they are combined. Add one here to add a data type."""
from .logs import Logs
from .seismic import Seismic
from .spatial import Spatial
from .strat import Strat

REGISTRY = {"strat": Strat, "spatial": Spatial, "logs": Logs, "seismic": Seismic}
