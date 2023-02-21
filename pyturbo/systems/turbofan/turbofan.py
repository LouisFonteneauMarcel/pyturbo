from typing import Dict

import numpy as np
from cosapp.systems import System
from OCC.Core.TopoDS import TopoDS_Shape

from pyturbo.systems.atmosphere import Atmosphere
from pyturbo.systems.channel import Channel
from pyturbo.systems.duct import FanDuct
from pyturbo.systems.fan_module import FanModule
from pyturbo.systems.gas_generator import GasGenerator
from pyturbo.systems.inlet import Inlet
from pyturbo.systems.nacelle import Nacelle, Plug
from pyturbo.systems.nozzle import Nozzle
from pyturbo.systems.structures import CoreCowl
from pyturbo.systems.turbine import LPT
from pyturbo.systems.turbofan.turbofan_aero import TurbofanAero
from pyturbo.systems.turbofan.turbofan_geom import TurbofanGeom
from pyturbo.systems.turbofan.turbofan_weight import TurbofanWeight
from pyturbo.utils import JupyterViewable


class Turbofan(System, JupyterViewable):
    """Turbofan assembly system.

    Sub-systems
    -----------
    inlet: Inlet
        inlet before the fan
    fanmodule: FanModule
        fan module made of fan, booster, ogv, ic and shaft
    core: GasGenerator
        core is made of HPC, combustor and HPT
    tcf: Channel
        turbine center frame
    turbine: LPT
        low pressure turbine
    trf: Channel
        turbine rear frame
    primary_nozzle: Nozzle
        nozzle in the primary flow
    secondary_nozzle: Nozzle
        nozzle in the secondary flow
    nacelle: Nacelle
        nacelle

    aero: TurbofanAero
        turbofan aero performances computed from components
    weight: TurbofanWeight
        weight evaluation from geometry

    Inputs
    ------
    fl_in: FluidPort
        inlet flow
    pamb[Pa]: float
        ambiant static pressure
    fan_diameter[m]: float
        diameter of the fan
    fuel_W[kg/s]: float
        fuel mass flow

    Outputs
    -------
    pamb[Pa]: float
        ambiant pressure
    ipps_weight[kg]: float
        ipps weight
    thrust[N]: float
        total thrust generated by engine and nacelle
    bpr[-]: float
        by pass ratio = secondary flow / primary flow
    opr[-]: float
        overall pressure ration
    sfc[-]: float
        specific fuel consumption
    N1[rpm]: float
        Low pressure spool speed rotation
    N2[rpm]: float
        High pressure spool speed rotation
    pr_split[-]: float
        pressure split between fan module and core
    pr_nozzle[-] : float
        total pressure ratio between secondary nozzle and primary nozzle

    """

    def setup(self):
        # physics
        self.add_child(TurbofanGeom("geom"), pulling=["fan_diameter", "frd_mount", "aft_mount"])

        # component
        self.add_child(Inlet("inlet"), pulling=["fl_in", "pamb"])
        self.add_child(FanModule("fan_module"), pulling={"bpr": "bpr", "N": "N1"})
        self.add_child(FanDuct("fan_duct"))
        self.add_child(GasGenerator("core"), pulling={"fuel_W": "fuel_W", "N": "N2"})
        self.add_child(Channel("tcf"))
        self.add_child(LPT("turbine"))
        self.add_child(Channel("trf"))
        self.add_child(Nozzle("primary_nozzle"), pulling=["pamb"])
        self.add_child(Nozzle("secondary_nozzle"), pulling=["pamb"])
        self.add_child(Nacelle("nacelle"))
        self.add_child(Plug("plug"))
        self.add_child(CoreCowl("core_cowl"))

        # physics
        self.add_child(
            TurbofanAero("aero"),
            pulling=["fuel_W", "opr", "thrust", "pr_split", "sfc", "pr_nozzle"],
        )
        self.add_child(TurbofanWeight("weight"), pulling=["ipps_weight"])

        # shaft connectors
        self.connect(self.turbine.sh_out, self.fan_module.sh_in)

        # fluid connectors
        self.connect(self.inlet.fl_out, self.fan_module.fl_in)
        self.connect(self.fan_module.fl_bypass, self.fan_duct.fl_in)
        self.connect(self.fan_duct.fl_out, self.secondary_nozzle.fl_in)

        self.connect(self.fan_module.fl_core, self.core.fl_in)
        self.connect(self.core.fl_out, self.tcf.fl_in)
        self.connect(self.tcf.fl_out, self.turbine.fl_in)
        self.connect(self.turbine.fl_out, self.trf.fl_in)
        self.connect(self.trf.fl_out, self.primary_nozzle.fl_in)

        # geometry connectors
        self.connect(
            self.geom,
            self.inlet,
            ["fan_inlet_tip_kp"],
        )
        self.connect(
            self.geom,
            self.fan_module,
            {"fan_diameter": "fan_diameter", "fan_module_length": "length"},
        )
        self.connect(self.geom.core_kp, self.core.kp)
        self.connect(self.geom.tcf_kp, self.tcf.kp)
        self.connect(self.geom.turbine_kp, self.turbine.kp)
        self.connect(self.geom.trf_kp, self.trf.kp)
        self.connect(self.geom.primary_nozzle_kp, self.primary_nozzle.kp)
        self.connect(self.geom.secondary_nozzle_kp, self.secondary_nozzle.kp)
        self.connect(
            self.geom,
            self.nacelle,
            [
                "ogv_exit_tip_kp",
                # "turbine_exit_tip_kp",
                "sec_nozzle_exit_kp",
            ],
        )
        self.connect(
            self.inlet,
            self.nacelle,
            ["hilite_kp"],
        )
        self.connect(self, self.nacelle, ["fan_diameter"])
        self.connect(self.trf.kp, self.plug.inwards, {"exit_hub": "trf_exit_hub_kp"})
        self.connect(self.geom.secondary_nozzle_kp, self.fan_duct.kp)

        self.connect(self.geom, self.fan_duct, {"fan_duct_core_cowl_slope": "core_cowl_slope"})

        self.connect(
            self.geom,
            self.core_cowl,
            {"sec_nozzle_exit_hub_kp": "inlet_kp", "pri_nozzle_exit_kp": "exit_kp"},
        )

        # aerodynamic performance connectors
        self.connect(self.inlet.outwards, self.aero.inwards, {"drag": "inlet_drag"})
        self.connect(self.fan_module.outwards, self.aero.inwards, ["fan_pr", "booster_pr"])
        self.connect(self.core.outwards, self.aero.inwards, {"opr": "core_opr"})
        self.connect(
            self.primary_nozzle.outwards, self.aero.inwards, {"thrust": "primary_nozzle_thrust"}
        )
        self.connect(
            self.secondary_nozzle.outwards, self.aero.inwards, {"thrust": "secondary_nozzle_thrust"}
        )
        self.connect(self.fan_duct.fl_out, self.aero.fl_secondary_nozzle)
        self.connect(self.trf.fl_out, self.aero.fl_primary_nozzle)

        # weight connectors
        self.connect(self, self.weight, "fan_diameter")
        self.connect(self.geom, self.weight, {"engine_length": "length"})

        # solver
        self.add_unknown("fl_in.W")

        # default value : CFM56-7

        # geometrical data
        self.fan_diameter = 1.549

        # stage counts
        self.fan_module.booster.stage_count = 3
        self.core.compressor.stage_count = 9
        self.core.turbine.stage_count = 1
        self.turbine.stage_count = 4

        # fan module
        self.fan_module.fan.geom.blade_hub_to_tip_ratio = 0.3

        # core compressor
        self.geom.core_inlet_radius_ratio = 0.35
        self.core.compressor.geom.blade_hub_to_tip_ratio = 0.7

        # tcf
        self.geom.tcf_exit_radius_ratio = 1.4
        self.geom.tcf_length_ratio = 0.5

        # nozzles
        self.geom.pri_nozzle_area_ratio = 0.9
        self.geom.sec_nozzle_area_ratio = 0.6

        # init unknowns
        self.inlet.fl_in.W = 300.0
        self.fan_module.splitter_shaft.power_fractions = np.r_[0.8]
        self.fan_module.splitter_fluid.fluid_fractions = np.r_[0.8]

        self.core.turbine.aero.Ncqdes = 100.0
        self.core.turbine.sh_out.power = 30e6
        self.core.compressor.sh_in.power = 30e6
        self.core.turbine.sh_out.N = 15e3

        self.turbine.aero.Ncqdes = 100.0
        self.turbine.sh_out.power = 30e6
        self.fan_module.sh_in.power = 30e6
        self.turbine.sh_out.N = 5e3

        # design method
        design = self.add_design_method("scaling")
        design.add_unknown("fan_diameter")

        # inlet
        design.add_target("inlet.aero.mach")

        # fan
        design.add_unknown("fan_module.fan.aero.xnd", max_rel_step=0.5)
        design.add_unknown("fan_module.fan.aero.phiP", lower_bound=0.1, upper_bound=1.5)

        design.add_target("fan_module.fan.aero.pcnr")
        design.add_target("fan_module.fan.aero.utip")
        design.add_target("bpr")

        # booster
        design.add_unknown("fan_module.geom.booster_radius_ratio")
        design.add_unknown(
            "fan_module.booster.geom.blade_hub_to_tip_ratio", lower_bound=1e-5, upper_bound=1.0
        )
        design.add_unknown("fan_module.booster.aero.phiP")
        design.add_unknown("fan_module.booster.aero.xnd", max_rel_step=0.5)

        design.add_target("fan_module.booster.aero.phi")
        design.add_target("fan_module.booster.aero.psi")
        design.add_target("fan_module.booster.aero.spec_flow")
        design.add_target("fan_module.booster.aero.pcnr")

        # lpt
        design.add_unknown("geom.turbine_radius_ratio")
        design.add_unknown("turbine.geom.blade_height_ratio", lower_bound=0.0, upper_bound=1.0)
        design.add_unknown("turbine.aero.Ncdes")

        design.add_target("turbine.aero.psi")
        design.add_target("turbine.aero.Ncqdes")

        # hpc
        design.add_unknown("geom.core_inlet_radius_ratio", max_rel_step=0.8)
        design.add_unknown("core.compressor.aero.xnd", max_rel_step=0.5)
        design.add_unknown("core.compressor.aero.phiP")

        design.add_target("core.compressor.aero.pcnr")
        design.add_target("core.compressor.aero.phi")
        design.add_target("core.compressor.aero.utip")
        design.add_target("core.compressor.aero.pr")

        # combustor
        design.add_target("core.combustor.aero.Tcomb")

        # hpt
        design.add_unknown("geom.core_exit_radius_ratio", max_rel_step=0.8)
        design.add_unknown("core.turbine.geom.blade_height_ratio", lower_bound=0.0, upper_bound=1.0)
        design.add_unknown("core.turbine.aero.Ncdes")

        design.add_target("core.turbine.aero.psi")
        design.add_target("core.turbine.aero.Ncqdes")

        # nozzle
        design.add_unknown("geom.pri_nozzle_area_ratio", lower_bound=0.05)
        design.add_unknown("geom.sec_nozzle_area_ratio", upper_bound=1.0)

        design.add_target("pr_nozzle")

    def _to_occt(self) -> Dict[str, TopoDS_Shape]:
        return dict(
            inlet=self.inlet._to_occt(),
            fan_module=self.fan_module._to_occt(),
            fan_duct=self.fan_duct.geom._to_occt(),
            gas_generator=self.core._to_occt(),
            tcf=self.tcf.geom._to_occt(),
            turbine=self.turbine.geom._to_occt(),
            trf=self.trf.geom._to_occt(),
            # primary_nozzle=self.primary_nozzle.geom._to_occt(),
            # secondary_nozzle=self.secondary_nozzle.geom._to_occt(),
            nacelle=self.nacelle.geom._to_occt(),
            plug=self.plug.geom._to_occt(),
            core_cowl=self.core_cowl._to_occt(),
        )


class TurbofanWithAtm(System):
    """Turbofan assembly system used in atmosphere.

    Sub-systems
    -----------
    atm: Atmosphere
        simplified atmosphere from altitude, Mach and delta ambient temperature
    tf: Turbofan
        turbofan
    """

    def setup(self):
        self.add_child(Atmosphere("atm"))
        self.add_child(Turbofan("tf"))

        self.connect(self.atm.outwards, self.tf.fl_in, ["Pt", "Tt"])
        self.connect(self.atm.outwards, self.tf.inwards, ["pamb"])
