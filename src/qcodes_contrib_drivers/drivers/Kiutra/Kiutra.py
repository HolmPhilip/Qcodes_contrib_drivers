from time import sleep

from kiutra_api.controller_interfaces import (
    ADRControl,
    CryostatControl,
    HeaterControl,
    MagnetControl,
    SampleControl,
    TemperatureControl,
)
from kiutra_api.device_interfaces import Magnet
from qcodes.instrument import Instrument
from qcodes.validators import Numbers


class Kiutra(Instrument):
    def __init__(self, name: str,mag_field_limit:float, host_ip_address: str,**kwargs) -> None:
        super().__init__(name, **kwargs)
        self.host = host_ip_address

        self.CryostatControl = CryostatControl(
            device="cryostat",
            host=host_ip_address,
        )
        self.SampleControl = SampleControl(
            device="sample_loader",
            host=host_ip_address,
        )
        self.TemperatureControl = TemperatureControl(
            device="temperature_control",
            host=host_ip_address,
        )
        self.ADRControl = ADRControl(
            device="adr_control",
            host=host_ip_address,
        )
        self.HeaterControl = HeaterControl(
            device="sample_heater",
            host=host_ip_address,
        )
        self.MagnetControl = MagnetControl(
            device="sample_magnet",
            host=host_ip_address,
        )
        self.magnet_power_supply_1 = Magnet(
            device="mps_1",
            host=host_ip_address,
        )
        self.magnet_power_supply_2 = Magnet(
            device="mps_2",
            host=host_ip_address,
        )

        self.add_parameter(
            name="sample_stage_temperature",
            unit="K",
            label="sample_stage_temperature",
            get_cmd=lambda: self.TemperatureControl.kelvin,
        )
        self.add_parameter(
            name="sample_magnetic_field",
            unit="T",
            label="sample_magnetic_field",
            get_cmd=lambda: self.MagnetControl.field,
            set_cmd=lambda field: self.stabilize_at_magnetic_field(
                setpoint_magnetic_field=field
            ),
        )
        self.add_parameter(
            name="magnet_power_supply_1_field",
            unit="T",
            label="magnet_power_supply_1_field",
            get_cmd=lambda: self.magnet_power_supply_1.field,
        )
        self.add_parameter(
            name="magnet_power_supply_2_field",
            unit="T",
            label="magnet_power_supply_2_field",
            get_cmd=lambda: self.magnet_power_supply_2.field,
        )
        self.add_parameter(
            name="sample_heater_power",
            unit="W",
            label="sample_heater_power",
            get_cmd=lambda: self.HeaterControl.power,
        )

    def get_idn(self) -> dict[str, str | None]:
        return {"model": "Kiutra", "Host": self.host_ip_address}

    def start_magnetic_field_sweep(
        self,
        setpoint_magnetic_field: float,
        magnetic_field_ramp_rate: float | None = None,
    ) -> None:
        if magnetic_field_ramp_rate is None:
            magnetic_field_ramp_rate = self.get_magnetic_field_ramp_rate()

        self.MagnetControl.start(
            setpoint=setpoint_magnetic_field, ramp=magnetic_field_ramp_rate
        )
        print(
            f"Magnetic field ramping to {setpoint_magnetic_field} T at {magnetic_field_ramp_rate} T/min"
        )

    def get_magnetic_field_ramp_rate(self) -> float:
        """We choose a magnetic field ramp rate based on the reccommedantion from Kiutra Operator's Manuak p.30.
        Ramp rate is in Tesla/minute."""

        if self.sample_stage_temperature() < 1:
            return 0.1
        elif self.sample_stage_temperature() < 10:
            return 0.5
        else:
            raise ValueError(
                "Magnetic field ramp rate is not defined for temperatures above 10K."
            )

    def stabilize_at_magnetic_field(
        self,
        setpoint_magnetic_field: float,
        magnetic_field_ramp_rate: float | None = None,
    ) -> None:
        self.start_magnetic_field_sweep(
            setpoint_magnetic_field=setpoint_magnetic_field,
            magnetic_field_ramp_rate=magnetic_field_ramp_rate,
        )
        while not self.MagnetControl.stable:
            sleep(1)
