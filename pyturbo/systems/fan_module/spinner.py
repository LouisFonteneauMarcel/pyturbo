import numpy as np
from cosapp.systems import System
from pyoccad.create import CreateAxis, CreateBezier, CreateRevolution, CreateTopology

from pyturbo.utils import rz_to_3d, slope_to_3d


class SpinnerGeom(System):
    """ """

    def setup(self):
        self.add_inward("fan_hub_kp", np.ones(2))
        self.add_inward("apex_kp", np.ones(2))
        self.add_inward("mean_angle", 40.0, unit="deg", desc="spinner mean angle")

    def _to_occt(self):
        edge = CreateTopology.make_edge(
            CreateBezier.g1_relative_tension(
                rz_to_3d(self.apex_kp),
                rz_to_3d(self.fan_hub_kp),
                (1.0, 0.0, 0.0),
                slope_to_3d(self.mean_angle),
                0.3,
                1.0,
            )
        )
        spinner = CreateRevolution.surface_from_curve(edge, CreateAxis.oz())
        return spinner
